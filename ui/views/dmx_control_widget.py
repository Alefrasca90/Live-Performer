# ui/views/dmx_control_widget.py

import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QSpinBox, QMessageBox, 
    QSpacerItem, QSizePolicy, QLineEdit, QListWidget, QCheckBox, QScrollArea, QSlider
)
from PyQt6.QtCore import Qt, QTimer

# Import dei componenti Core del Progetto (DMX)
from core.dmx_models import FixtureModello, IstanzaFixture, Scena, PassoChaser, Chaser 
from core.dmx_universe import UniversoDMX
from core.data_manager import DataManager # DataManager per DMX (Project, Models)
from core.dmx_comm import DMXController 
from core.project_models import Progetto, UniversoStato, MidiMapping
from core.midi_comm import MIDIController # Controller MIDI Input (per mappature)

# Import dei componenti UI (DMX) dalla cartella components/
from ui.components.fixture_editor import FixtureEditorDialog 
from ui.views.stage_view import StageViewDialog # StageView è una view a sé
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

# La classe DMXControlWidget ora eredita da QWidget e tutti i Mixins
class DMXControlWidget(QWidget, 
                     ProjectAndViewMixin, 
                     DMXCommunicationMixin, 
                     FixtureControlMixin, 
                     SceneChaserMixin,
                     MIDIControlMixin):
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
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
        # CARICA LA PORTA DMX DALLO STATO DEL PROGETTO
        current_u_state = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])
        dmx_port = getattr(current_u_state, 'dmx_port_name', 'COM5') # Prende il nuovo campo o il default
        
        self.dmx_comm = DMXController(port_name=dmx_port) 
        self.dmx_comm.connect() 
        
        # 4. Stage View
        self.stage_view: StageViewDialog | None = None
        
        # 5. Timer e Scene
        self.chaser_attivo: Chaser | None = None
        self.chaser_timer = QTimer(self)
        self.chaser_timer.timeout.connect(self._esegui_passo_chaser)
        self.fade_timer = QTimer(self) 
        self.fade_timer.setInterval(10)
        self.fade_timer.timeout.connect(self._fade_tick) 
        
        # 6. Setup MIDI Control (Input)
        self.midi_controller = MIDIController(parent=self)
        # Il router invia il messaggio sia al log che alla logica di mappatura
        self.midi_controller.midi_message.connect(self._midi_message_router) 
        self._load_midi_settings() 
        
        # 7. Setup UI: Inizializza il logger MIDI
        self.midi_log_list = QListWidget() 
        self.midi_log_list.setMaximumHeight(150)
        
        # 8. Setup Layout del Widget
        self._setup_ui_layout()
        
        # 9. Final Setup
        self._ricostruisci_scene_chasers(
            next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])
        ) 
        self.popola_controlli_fader()
        self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)

    # Questo metodo sostituisce la vecchia _setup_ui, ora è solo il layout principale del Widget
    def _setup_ui_layout(self):
        main_layout = QHBoxLayout(self)

        # --- Pannello di Controllo (Sinistra) ---
        control_panel = self._crea_pannello_controllo()
        main_layout.addWidget(control_panel, 1)  

        # --- Fader (Destra) ---
        self.fader_scroll = QScrollArea()
        self.fader_scroll.setWidgetResizable(True)
        self.fader_container = QWidget()
        self.fader_layout = QVBoxLayout(self.fader_container)
        self.fader_scroll.setWidget(self.fader_container)
        main_layout.addWidget(self.fader_scroll, 3) 

        # Aggiungiamo un Pulsante di Salvataggio rapido per la tab
        save_btn = QPushButton("Salva Configurazione DMX (Fader, Scene, Posizioni)")
        save_btn.clicked.connect(self._salva_stato_progetto)
        main_layout.addWidget(save_btn)
        main_layout.setStretchFactor(save_btn, 0)
        
    def cleanup(self):
        """Esegue il salvataggio e la disconnessione quando il widget viene chiuso."""
        if hasattr(self, 'midi_controller'):
             self.midi_controller.disconnect() 
        self._salva_stato_progetto()
        self.dmx_comm.disconnect()
        if self.stage_view:
            self.stage_view.close()
            
    # La logica del menu bar (ora toolbar) è stata spostata nel metodo _crea_pannello_controllo
    # come Pulsanti che aprono i dialog
    def _setup_toolbar(self):
        # Questo metodo viene chiamato dal vecchio codice ma non è più necessario
        # dato che i pulsanti sono nel pannello di controllo. Lasciamo vuoto per compatibilità
        pass

    # Metodi ausiliari per la UI (ripristinati come nell'originale, ma ora in un mixin o nella classe)
    # L'implementazione completa di _crea_pannello_controllo è qui sotto.

    def _midi_message_router(self, msg):
        """Reindirizza il messaggio MIDI al logger e al gestore di mappatura (dal Mixin)."""
        self._log_midi_message(msg)
        self._handle_midi_message(msg) 
        
    # Implementazioni dei dialoghi ausiliari dal vecchio main_window (necessari per i mixins)
    def _open_stage_view(self):
        self._open_stage_view_impl()

    def _open_fixture_editor(self):
        self._open_fixture_editor_impl()

    def _open_midi_mapping_dialog(self):
        self._open_midi_mapping_dialog_impl()

    def _open_add_fixture_dialog(self):
        from ui.components.add_fixture_dialog import AddFixtureDialog 
        dialog = AddFixtureDialog(self, fixture_modelli=self.fixture_modelli)
        dialog.fixture_selected.connect(self._handle_fixture_add_request)
        dialog.exec()
        
    def _open_chaser_editor_dialog(self):
        from ui.components.chaser_editor_dialog import ChaserEditorDialog 
        selected_chaser = None
        if hasattr(self, 'chaser_list_widget'):
            selected_items = self.chaser_list_widget.selectedItems()
            if selected_items:
                if hasattr(self, 'chaser_list'):
                    index = self.chaser_list_widget.row(selected_items[0])
                    if 0 <= index < len(self.chaser_list):
                        selected_chaser = self.chaser_list[index]
             
        dialog = ChaserEditorDialog(
            parent=self, 
            scene_list=self.scene_list if hasattr(self, 'scene_list') else [], 
            chaser_to_edit=selected_chaser
        )
        
        dialog.chaser_saved.connect(self._handle_chaser_saved)
        dialog.exec()

    # --- UI DMX ---
    def _crea_pannello_controllo(self):
        """Metodo che crea l'intero pannello di controllo DMX a sinistra/sotto."""
        group_box = QGroupBox("Gestione Controller DMX")
        layout = QVBoxLayout(group_box)
        
        # 1. MIDI MONITOR (Ingresso)
        midi_group = QGroupBox("MIDI Monitor (Segnali in Ingresso)")
        midi_layout = QVBoxLayout(midi_group)
        
        # Usa la QListWidget creata in __init__
        midi_layout.addWidget(self.midi_log_list) 
        midi_layout.addItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Minimum)) 
        
        layout.addWidget(midi_group)
        
        # 2. Lista Fixture Assegnate e Rimozione
        list_group = QGroupBox(f"Fixture Assegnate: {self.universo_attivo.nome}")
        list_layout = QVBoxLayout(list_group)

        self.assigned_list_widget = QListWidget() 
        self.assigned_list_widget.setMaximumHeight(100)
        
        # Layout Pulsanti (Aggiungi/Rimuovi)
        add_remove_layout = QHBoxLayout() 
        
        # Pulsante che apre il Dialog per l'aggiunta
        self.btn_open_add_fixture = QPushButton("Aggiungi Fixture")
        self.btn_open_add_fixture.clicked.connect(self._open_add_fixture_dialog) 
        
        self.btn_remove_instance = QPushButton("Rimuovi Selezionato")
        self.btn_remove_instance.clicked.connect(self._rimuovi_istanza_da_universo) 
        
        self._update_assigned_list_ui() 

        list_layout.addWidget(self.assigned_list_widget)

        add_remove_layout.addWidget(self.btn_open_add_fixture) 
        add_remove_layout.addWidget(self.btn_remove_instance)
        list_layout.addLayout(add_remove_layout) 
        
        layout.addWidget(list_group)
        
        # 3. Stato Connessione DMX (Toggle)
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
        layout.addWidget(comm_group)
        self._update_dmx_status_ui() 
        
        # 4. Gestione Scene (SEPARATO)
        scene_group = QGroupBox("Gestione Scene")
        scene_layout = QVBoxLayout(scene_group)
        
        # Cattura Scena
        capture_layout = QHBoxLayout()
        self.scene_name_input = QLineEdit()
        self.scene_name_input.setPlaceholderText("Nome Scena")
        self.btn_capture_scene = QPushButton("Salva")
        self.btn_capture_scene.clicked.connect(self._cattura_scena_corrente) 
        capture_layout.addWidget(self.scene_name_input)
        capture_layout.addWidget(self.btn_capture_scene)
        scene_layout.addWidget(QLabel("Cattura Scena Corrente:"))
        scene_layout.addLayout(capture_layout)
        
        # Lista Scene
        scene_layout.addWidget(QLabel("\nScene Salvate (Doppio Click per Applicare):"))
        self.scene_list_widget = QListWidget() 
        self.scene_list_widget.setMaximumHeight(100)
        self.scene_list_widget.doubleClicked.connect(self._applica_scena_selezionata) 
        scene_layout.addWidget(self.scene_list_widget)
        
        scene_list_ctrl = QHBoxLayout()
        self.btn_delete_scene = QPushButton("Cancella")
        self.btn_delete_scene.clicked.connect(self._cancella_scena_selezionata) 
        scene_list_ctrl.addStretch(1) 
        scene_list_ctrl.addWidget(self.btn_delete_scene)
        scene_layout.addLayout(scene_list_ctrl)
        
        layout.addWidget(scene_group) 
        
        # 5. Gestione Sequenze (Chaser) (NUOVO GRUPPO)
        chaser_group = QGroupBox("Gestione Sequenze (Chaser)")
        chaser_layout = QVBoxLayout(chaser_group)
        
        # Editor Chaser
        editor_layout = QHBoxLayout()
        self.btn_open_chaser_editor = QPushButton("Crea / Modifica Sequenza") 
        self.btn_open_chaser_editor.clicked.connect(self._open_chaser_editor_dialog)
        self.btn_delete_chaser = QPushButton("Cancella Sequenza") 
        self.btn_delete_chaser.clicked.connect(self._cancella_chaser_selezionato)
        editor_layout.addWidget(self.btn_open_chaser_editor)
        editor_layout.addWidget(self.btn_delete_chaser)
        chaser_layout.addLayout(editor_layout)
        
        # Lista Chaser
        chaser_layout.addWidget(QLabel("\nSequenze Salvate (Seleziona per Avviare):"))
        self.chaser_list_widget = QListWidget() 
        self.chaser_list_widget.setMaximumHeight(100)
        self.chaser_list_widget.doubleClicked.connect(self._open_chaser_editor_dialog) 
        chaser_layout.addWidget(self.chaser_list_widget)
        
        # Controlli Chaser
        chaser_ctrl_layout = QHBoxLayout()
        self.btn_start_chaser = QPushButton("Avvia Sequenza Selezionata") 
        self.btn_start_chaser.clicked.connect(self._avvia_chaser) 
        self.btn_stop_chaser = QPushButton("Stop Sequenza") 
        self.btn_stop_chaser.clicked.connect(self._ferma_chaser) 
        chaser_ctrl_layout.addWidget(self.btn_start_chaser)
        chaser_ctrl_layout.addWidget(self.btn_stop_chaser)
        chaser_layout.addLayout(chaser_ctrl_layout)
        
        layout.addWidget(chaser_group) 
        
        # Spaziatore per spingere gli elementi in alto
        layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)) 
        return group_box