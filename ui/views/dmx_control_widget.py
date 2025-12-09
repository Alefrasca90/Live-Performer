# ui/views/dmx_control_widget.py

import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QSpinBox, QMessageBox, 
    QSpacerItem, QSizePolicy, QLineEdit, QListWidget, QCheckBox, QScrollArea, QSlider
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction 

# Import dei componenti Core del Progetto (DMX)
from core.dmx_models import FixtureModello, IstanzaFixture, Scena, PassoChaser, Chaser 
from core.dmx_universe import UniversoDMX
from core.data_manager import DataManager 
from core.dmx_comm import DMXController 
from core.project_models import Progetto, UniversoStato, MidiMapping
from core.midi_comm import MIDIController 
from ui.components.settings_manager import SettingsManager 
from ui.components.settings_dialog import SettingsDialog 

# Import dei componenti UI (DMX) dalla cartella components/
from ui.components.fixture_editor import FixtureEditorDialog 
from ui.views.stage_view import StageViewWidget # Importato il widget rifattorizzato
from ui.views.stage_view import DraggableLightWidget # Importato DraggableLightWidget
from ui.components.add_fixture_dialog import AddFixtureDialog 
from ui.components.chaser_editor_dialog import ChaserEditorDialog 
from ui.components.midi_mapping_dialog import MidiMappingDialog
from ui.components.widgets import FixtureGroupBox 

# Import dei Mixin per la logica pulita
from ui.mixins.project_and_view_mixin import ProjectAndViewMixin 
from ui.mixins.dmx_comm_mixin import DMXCommunicationMixin 
from ui.mixins.fixture_control_mixin import FixtureControlMixin 
from ui.mixins.scene_chaser_mixin import SceneChaserMixin 
from ui.mixins.midi_control_mixin import MIDIControlMixin 

class DMXControlWidget(QWidget, 
                     ProjectAndViewMixin, 
                     DMXCommunicationMixin, 
                     FixtureControlMixin, 
                     SceneChaserMixin,
                     MIDIControlMixin):
    
    # MODIFIED CONSTRUCTOR: Accepts the injected stage_view
    def __init__(self, audio_engine, midi_engine, settings_manager, stage_view: StageViewWidget, parent=None):
        super().__init__(parent)
        
        # Assegna i motori condivisi
        self.audio_engine = audio_engine 
        self.midi_engine = midi_engine 
        self.settings_manager = settings_manager 
        
        # 1. Carica Modelli Fixture e Progetto (Logica locale per Mixins)
        self.fixture_modelli: list[FixtureModello] = DataManager.carica_modelli()
        if not self.fixture_modelli:
            self.fixture_modelli = self._crea_modello_esempio()
            DataManager.salva_modelli(self.fixture_modelli)
            
        self._aggiungi_modelli_virtuali()
        self.progetto: Progetto = DataManager.carica_progetto()
            
        # 2. Inizializza gli Universi Attivi
        self.universi: dict[int, UniversoDMX] = {}
        self._ricostruisci_universi()
        
        if self.universi:
            self.universo_attivo: UniversoDMX = next(iter(self.universi.values()))
        else:
             self.universo_attivo = self._crea_nuovo_universo(1, "Universo Principale")
             self._ricostruisci_universi() 
             self.universo_attivo = next(iter(self.universi.values()))

        # 3. DMX Controller
        current_u_state = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])
        dmx_port = getattr(current_u_state, 'dmx_port_name', 'COM5') 
        
        self.dmx_comm = DMXController(port_name=dmx_port) 
        self.dmx_comm.connect() 
        
        # 4. Stage View: Assign the injected widget
        self.stage_view: StageViewWidget = stage_view
        
        # 5. Timer e Scene
        self.chaser_attivo: Chaser | None = None
        self.chaser_timer = QTimer(self)
        self.chaser_timer.timeout.connect(self._esegui_passo_chaser)
        self.fade_timer = QTimer(self) 
        self.fade_timer.setInterval(10)
        self.fade_timer.timeout.connect(self._fade_tick) 
        
        # 6. Setup MIDI Control (Input)
        self.midi_controller = MIDIController(parent=self)
        
        # Connette il segnale del controller hardware MIDI (Input) al router DMX
        self.midi_controller.midi_message.connect(self._midi_message_router) 
        
        # [MODIFICATO] Connette il segnale del file MIDI (Output/Engine) al router DMX
        if hasattr(self.midi_engine, 'midi_file_message'):
             self.midi_engine.midi_file_message.connect(self._midi_message_router) 
             
        self._load_midi_settings() 
        
        # 7. Setup UI: Rimosso il setup locale del MIDI log.
        
        # 8. Setup Layout del Widget
        self._setup_ui_layout()
        
        # 9. Final Setup
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])
        
        # Initialize Stage View content
        self.stage_view.clear_and_repopulate(u_stato.istanze_stato) 
        
        # Connect signals from the injected Stage View after populating
        for light_widget in self.stage_view.light_widgets.values():
             light_widget.moved.connect(self._update_fixture_position)


        self._ricostruisci_scene_chasers(u_stato) 
        self.popola_controlli_fader()
        self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)


    def _setup_ui_layout(self):
        main_layout = QHBoxLayout(self)

        # --- Colonna 1: Left Controls (Fixtures/DMX Status) ---
        # Creiamo il contenitore per la colonna sinistra (peso 1)
        left_controls_widget = self._build_left_control_column()
        main_layout.addWidget(left_controls_widget, 1) 

        # --- Fader Area (Center) ---
        self.fader_scroll = QScrollArea()
        self.fader_scroll.setWidgetResizable(True)
        self.fader_container = QWidget()
        self.fader_layout = QVBoxLayout(self.fader_container)
        self.fader_scroll.setWidget(self.fader_container)
        main_layout.addWidget(self.fader_scroll, 3) # Colonna centrale ottiene 3x spazio

        # --- Colonna 2: Right Controls (Scenes/Chasers) ---
        # Creiamo il contenitore per la colonna destra (peso 1)
        right_controls_widget = self._build_right_control_column()
        main_layout.addWidget(right_controls_widget, 1) 
        
    def cleanup(self):
        """Esegue il salvataggio e la disconnessione quando il widget viene chiuso."""
        if hasattr(self, 'midi_controller'):
             self.midi_controller.disconnect() 
        self._salva_stato_progetto()
        self.dmx_comm.disconnect()
        if self.stage_view:
            self.stage_view.close()
            
    # Redundant method called by Menu Bar. We implement logic to activate the tab.
    def _open_stage_view(self):
        """Metodo chiamato dal menu bar per attivare il tab 'Stage'."""
        if self.parent() and hasattr(self.parent(), 'tab_widget'):
            # Trova l'indice del tab che contiene l'istanza di StageViewWidget
            tab_index = self.parent().tab_widget.indexOf(self.stage_view)
            if tab_index != -1:
                 self.parent().tab_widget.setCurrentIndex(tab_index)
        # We must keep the method signature because the Menu Bar calls it.
        pass

    # --- UI DMX: Helper per costruire le colonne ---

    def _build_left_control_column(self):
        """Costruisce i widget per la colonna sinistra (Fixture & DMX Status)."""
        widget = QWidget()
        col_layout = QVBoxLayout(widget)

        # 1a. Lista Fixture Assegnate e Rimozione
        list_group = QGroupBox(f"Fixture Assegnate: {self.universo_attivo.nome}")
        list_layout = QVBoxLayout(list_group)

        self.assigned_list_widget = QListWidget() 
        list_layout.addWidget(self.assigned_list_widget, 1) # Stretch 1 for QListWidget

        add_remove_layout = QHBoxLayout() 
        
        self.btn_open_add_fixture = QPushButton("Aggiungi Fixture")
        self.btn_open_add_fixture.clicked.connect(self._open_add_fixture_dialog) 
        
        self.btn_remove_instance = QPushButton("Rimuovi Selezionato")
        self.btn_remove_instance.clicked.connect(self._rimuovi_istanza_da_universo) 
        
        self._update_assigned_list_ui() 

        add_remove_layout.addWidget(self.btn_open_add_fixture) 
        add_remove_layout.addWidget(self.btn_remove_instance)
        list_layout.addLayout(add_remove_layout) 
        
        col_layout.addWidget(list_group, 2) # Groupbox ha stretch factor 2 per spazio verticale

        # 1b. Stato Connessione DMX (Toggle)
        comm_group = QGroupBox("Stato Uscita DMX")
        comm_layout = QVBoxLayout(comm_group)

        self.dmx_enable_checkbox = QCheckBox("Abilita Uscita DMX")
        self.dmx_enable_checkbox.setChecked(self.dmx_comm.is_enabled)
        self.dmx_enable_checkbox.stateChanged.connect(self._toggle_dmx_output) 
        comm_layout.addWidget(self.dmx_enable_checkbox)
        
        self.status_label = QLabel("Non Connesso")
        self.refresh_ports_btn = QPushButton("Riconnetti / Aggiorna Porte")
        self.refresh_ports_btn.clicked.connect(self._handle_dmx_connection) 
        
        comm_layout.addWidget(self.status_label)
        comm_layout.addWidget(self.refresh_ports_btn)
        
        col_layout.addWidget(comm_group) # Groupbox a dimensione fissa
        self._update_dmx_status_ui() 
        
        col_layout.addStretch(1) # Spazio espandibile in fondo alla Colonna 1

        return widget

    def _build_right_control_column(self):
        """Costruisce i widget per la colonna destra (Scenes & Chasers)."""
        widget = QWidget()
        col_layout = QVBoxLayout(widget)

        # 2a. Gestione Scene 
        scene_group = QGroupBox("Gestione Scene")
        scene_layout = QVBoxLayout(scene_group)
        
        capture_layout = QHBoxLayout()
        self.scene_name_input = QLineEdit()
        self.scene_name_input.setPlaceholderText("Nome Scena")
        self.btn_capture_scene = QPushButton("Salva")
        self.btn_capture_scene.clicked.connect(self._cattura_scena_corrente) 
        capture_layout.addWidget(self.scene_name_input)
        capture_layout.addWidget(self.btn_capture_scene)
        scene_layout.addWidget(QLabel("Cattura Scena Corrente:"))
        scene_layout.addLayout(capture_layout)
        
        scene_layout.addWidget(QLabel("\nScene Salvate (Doppio Click per Applicare):"))
        self.scene_list_widget = QListWidget() 
        self.scene_list_widget.doubleClicked.connect(self._applica_scena_selezionata) 
        scene_layout.addWidget(self.scene_list_widget, 1) # Stretch 1 for QListWidget
        
        scene_list_ctrl = QHBoxLayout()
        self.btn_delete_scene = QPushButton("Cancella")
        self.btn_delete_scene.clicked.connect(self._cancella_scena_selezionata) 
        scene_list_ctrl.addStretch(1) 
        scene_list_ctrl.addWidget(self.btn_delete_scene)
        scene_layout.addLayout(scene_list_ctrl)
        
        col_layout.addWidget(scene_group, 2) # Groupbox ha stretch factor 2

        # 2b. Gestione Sequenze (Chaser) 
        chaser_group = QGroupBox("Gestione Sequenze (Chaser)")
        chaser_layout = QVBoxLayout(chaser_group)
        
        editor_layout = QHBoxLayout()
        self.btn_open_chaser_editor = QPushButton("Crea / Modifica Sequenza") 
        self.btn_open_chaser_editor.clicked.connect(self._open_chaser_editor_dialog)
        self.btn_delete_chaser = QPushButton("Cancella Sequenza") 
        self.btn_delete_chaser.clicked.connect(self._cancella_chaser_selezionato)
        editor_layout.addWidget(self.btn_open_chaser_editor)
        editor_layout.addWidget(self.btn_delete_chaser)
        chaser_layout.addLayout(editor_layout)
        
        chaser_layout.addWidget(QLabel("\nSequenze Salvate (Seleziona per Avviare):"))
        self.chaser_list_widget = QListWidget() 
        self.chaser_list_widget.doubleClicked.connect(self._open_chaser_editor_dialog) 
        chaser_layout.addWidget(self.chaser_list_widget, 1) # Stretch 1 for QListWidget
        
        chaser_ctrl_layout = QHBoxLayout()
        self.btn_start_chaser = QPushButton("Avvia Sequenza Selezionata") 
        self.btn_start_chaser.clicked.connect(self._avvia_chaser) 
        self.btn_stop_chaser = QPushButton("Stop Sequenza") 
        self.btn_stop_chaser.clicked.connect(self._ferma_chaser) 
        chaser_ctrl_layout.addWidget(self.btn_start_chaser)
        chaser_ctrl_layout.addWidget(self.btn_stop_chaser)
        chaser_layout.addLayout(chaser_ctrl_layout)
        
        col_layout.addWidget(chaser_group, 2) # Groupbox ha stretch factor 2

        col_layout.addStretch(1) # Spazio espandibile in fondo alla Colonna 2

        return widget


    # Metodi esposti a main.py dalla barra dei menu (delegati al Mixin):
    def salva_progetto_a_file(self):
        self._salva_stato_progetto()
        super().salva_progetto_a_file()
        
    def carica_progetto_da_file(self):
        super().carica_progetto_da_file()

    def _open_settings_dialog(self):
        super()._open_settings_dialog()

    def _show_info_dialog(self):
        super()._show_info_dialog()
        
    def _open_stage_view(self):
        super()._open_stage_view()
        
    def _open_fixture_editor(self):
        super()._open_fixture_editor()

    def _open_midi_mapping_dialog(self):
        # Assicuriamo che le liste siano aggiornate, prendendole dai mixin
        scene_list = getattr(self, 'scene_list', [])
        chaser_list = getattr(self, 'chaser_list', [])
        
        # Assicuriamo che lo stato sia aggiornato
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])

        dialog = MidiMappingDialog(
            parent=self,
            scene_list=scene_list,
            chaser_list=chaser_list,
            current_mappings=u_stato.midi_mappings,
            current_channel_filter=u_stato.midi_channel,
            available_ports=self.midi_controller.list_input_ports(),
            current_port_name=self.midi_controller.input_port_name 
        )
        # [NUOVO] Connette il segnale per salvare i risultati al nuovo handler del mixin
        dialog.mappings_saved.connect(self._handle_midi_mappings_saved)
        dialog.exec()
    
    def _handle_dmx_connection(self):
         super()._handle_dmx_connection()
         
    def _midi_message_router(self, msg):
        # La logica di log MIDI IN è stata spostata nel tab 'MIDI Monitor'.
        # self._log_midi_message(msg)
        self._handle_midi_message(msg) 
        
    def _open_add_fixture_dialog(self):
        super()._open_add_fixture_dialog()
        
    def _open_chaser_editor_dialog(self):
        super()._open_chaser_editor_dialog()