# ui/main_window.py (COMPLETO E AGGIORNATO)

import sys
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QGroupBox, QPushButton, QComboBox, QSpinBox, QMessageBox, 
    QSpacerItem, QSizePolicy, QLineEdit, QListWidget, QCheckBox, QScrollArea, QSlider, QSplitter,
    QInputDialog, QToolBar 
)
from PyQt6.QtCore import Qt, QTimer, QCoreApplication, QSize
from PyQt6.QtGui import QIcon, QAction, QMouseEvent

# Import dei componenti Core del Progetto
from core.dmx_models import FixtureModello, IstanzaFixture, Scena, PassoChaser, Chaser 
from core.dmx_universe import UniversoDMX
from core.data_manager import DataManager
from core.dmx_comm import DMXController 
from core.project_models import Progetto, UniversoStato
from ui.components.fixture_editor import FixtureEditorDialog 
from ui.views.stage_view import StageViewDialog, DraggableLightWidget 
from ui.components.add_fixture_dialog import AddFixtureDialog 
from ui.components.chaser_editor_dialog import ChaserEditorDialog 
from ui.components.midi_mapping_dialog import MidiMappingDialog
from core.midi_comm import MIDIController 

# Import del widget riutilizzabile
from ui.components.widgets import FixtureGroupBox 

# Import dei Mixin per la logica pulita
from ui.mixins.project_and_view_mixin import ProjectAndViewMixin 
from ui.mixins.dmx_comm_mixin import DMXCommunicationMixin 
from ui.mixins.fixture_control_mixin import FixtureControlMixin 
from ui.mixins.scene_chaser_mixin import SceneChaserMixin 
from ui.mixins.midi_control_mixin import MIDIControlMixin 

# Import DMX Dialogs
from ui.components.fixture_editor import FixtureEditorDialog 
from ui.views.stage_view import StageViewDialog, DraggableLightWidget 
from ui.components.add_fixture_dialog import AddFixtureDialog 
from ui.components.chaser_editor_dialog import ChaserEditorDialog 
from ui.components.midi_mapping_dialog import MidiMappingDialog

# Import UI Scenografia (CORREZIONE ERRORE PYLANCE) <--- AGGIUNGI QUI
from ui.views.song_editor_widget import SongEditorWidget 
from ui.views.playlist_editor_widget import PlaylistEditorWidget 

# Import Engine e Mixin 
from core.midi_comm import MIDIController

# La classe MainWindow ora eredita da QMainWindow e tutti i Mixins
class MainWindow(QMainWindow, 
                 ProjectAndViewMixin, 
                 DMXCommunicationMixin, 
                 FixtureControlMixin, 
                 SceneChaserMixin,
                 MIDIControlMixin):
    
    # __init__ ora accetta i motori Audio/MIDI/DataManager esterni
    def __init__(self, audio_engine, midi_engine, data_manager, settings_manager):
        super().__init__()
        self.setWindowTitle("DMX Controller - Universo 1")
        self.setGeometry(100, 100, 1200, 700)
        
        # Assegna i motori condivisi
        self.audio_engine = audio_engine 
        self.midi_engine_for_sync = midi_engine # Motore MIDI per sync Audio/Lyrics
        self.settings_manager = settings_manager 
        self.data_manager_scenografia = data_manager # DataManager per Canzoni/Playlist
        
        # 1. Carica Modelli Fixture e Progetto (Logica da Mixins)
        self.fixture_modelli: list[FixtureModello] = DataManager.carica_modelli()
        if not self.fixture_modelli:
            self.fixture_modelli = self._crea_modello_esempio()
            DataManager.salva_modelli(self.fixture_modelli)
            
        self._aggiungi_modelli_virtuali()
        self.progetto: Progetto = DataManager.carica_progetto()
            
        # 2. Inizializza gli Universi Attivi (Logica da Mixins)
        self.universi: dict[int, UniversoDMX] = {}
        self._ricostruisci_universi()
        
        if self.universi:
            self.universo_attivo: UniversoDMX = next(iter(self.universi.values()))
        else:
             self.universo_attivo = self._crea_nuovo_universo(1, "Universo Principale")
             self._ricostruisci_universi() 
             self.universo_attivo = next(iter(self.universi.values()))

        # 3. DMX Controller
        self.dmx_comm = DMXController(port_name="COM5") 
        self.dmx_comm.connect() 
        
        # 4. Stage View
        self.stage_view: StageViewDialog | None = None
        
        # 5. Timer e Scene
        self.chaser_attivo: Chaser | None = None
        
        # Timer principale per il tempo di permanenza (Hold Time)
        self.chaser_timer = QTimer(self)
        self.chaser_timer.timeout.connect(self._esegui_passo_chaser)
        
        # Timer ad alta frequenza per il fading (10ms)
        self.fade_timer = QTimer(self) 
        self.fade_timer.setInterval(10)
        self.fade_timer.timeout.connect(self._fade_tick) 
        
        # 6. Setup MIDI Control (Ingresso/Mappature)
        self.midi_controller = MIDIController(parent=self)
        # Reindirizza il segnale al router che gestisce sia il log che la mappatura
        self.midi_controller.midi_message.connect(self._midi_message_router) 
        self._load_midi_settings() 
        
        # 7. Setup UI - NUOVA INIZIALIZZAZIONE WIDGET MIDI LOG (Ingresso)
        self.midi_log_list = QListWidget() 
        self.midi_log_list.setMaximumHeight(150)
        
        # 8. Setup UI Principale (Menu, Splitter, Barra di Riproduzione, Liste Canzoni/Playlist)
        self._setup_ui() 
        
        # 8.1. Configura la Barra degli Strumenti DMX
        self._setup_toolbar()
        
        # 9. Carica scene e chaser (Logica da SceneChaserMixin)
        self._ricostruisci_scene_chasers(
            next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), Progetto.crea_vuoto().universi_stato[0])
        ) 
        
        # 10. Popola l'UI DMX con i dati (Fader e Liste)
        self.popola_controlli_fader()
        self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)

    def closeEvent(self, event):
        """Salva il progetto e chiude le connessioni, inclusa quella MIDI."""
        if hasattr(self, 'midi_controller'):
             self.midi_controller.disconnect() 
             
        self._salva_stato_progetto()
        self.dmx_comm.disconnect()
        if self.stage_view:
            self.stage_view.close()
        event.accept()
        
    def _setup_toolbar(self):
        """Crea la barra degli strumenti in alto e aggiunge le azioni principali."""
        toolbar = QToolBar("Barra Principale")
        self.addToolBar(toolbar)
        
        # Azione 1: Salva Progetto
        save_action = QAction(QIcon.fromTheme("document-save"), "Salva Progetto", self)
        save_action.triggered.connect(self._salva_stato_progetto)
        save_action.setStatusTip("Salva la configurazione corrente del progetto (Fixture, Scene, Posizioni).")
        toolbar.addAction(save_action)

        # Azione 2: Apri Stage View
        stage_action = QAction(QIcon.fromTheme("view-stage"), "Stage View", self)
        stage_action.triggered.connect(self._open_stage_view)
        stage_action.setStatusTip("Apri/Sposta in primo piano la finestra di visualizzazione scenica.")
        toolbar.addAction(stage_action)

        # Azione 3: Editor Modelli
        editor_action = QAction(QIcon.fromTheme("document-edit"), "Editor Modelli", self)
        editor_action.triggered.connect(self._open_fixture_editor)
        editor_action.setStatusTip("Apri l'editor per creare o modificare i modelli di fixture DMX.")
        toolbar.addAction(editor_action)
        
        # Separatore
        toolbar.addSeparator()

        # Azione 4: Gestione Mappature MIDI
        midi_map_action = QAction(QIcon.fromTheme("preferences-desktop-keyboard-shortcuts"), "Mappature MIDI", self)
        midi_map_action.triggered.connect(self._open_midi_mapping_dialog)
        midi_map_action.setStatusTip("Apri il dialogo per mappare Note, CC e PC a Scene/Chaser.")
        toolbar.addAction(midi_map_action)
        
        # Separatore
        toolbar.addSeparator()

        # Azione 5: Riconnetti DMX (Azione del Mixin DMX)
        reconnect_action = QAction(QIcon.fromTheme("network-transmit-receive"), "Riconnetti DMX", self)
        reconnect_action.triggered.connect(self._handle_dmx_connection)
        reconnect_action.setStatusTip("Riconnetti o aggiorna le porte seriali DMX.")
        toolbar.addAction(reconnect_action)
        
    # --- Gestione Dialog Mappature MIDI (definito nei Mixin) ---
    def _open_midi_mapping_dialog(self):
        """Apre il dialogo per gestire le mappature MIDI."""
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        
        if not u_stato:
            QMessageBox.critical(self, "Errore", "Universo non caricato.")
            return

        dialog = MidiMappingDialog(
            parent=self, 
            scene_list=self.scene_list if hasattr(self, 'scene_list') else [],
            chaser_list=self.chaser_list if hasattr(self, 'chaser_list') else [],
            current_mappings=u_stato.midi_mappings,
            current_channel_filter=u_stato.midi_channel, # <-- Passa il filtro canale corrente
            available_ports=self.midi_controller.list_input_ports(),
            current_port_name=self.midi_controller.input_port_name if self.midi_controller.input_port_name else ""
        )
        
        dialog.mappings_saved.connect(self._handle_midi_mappings_saved)
        dialog.exec()
        
    def _handle_midi_mappings_saved(self, new_mappings, new_channel_filter, new_port_name):
        """Gestisce il salvataggio delle mappature MIDI dal dialogo."""
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        if u_stato:
             u_stato.midi_mappings = new_mappings
             u_stato.midi_channel = new_channel_filter 
             
             self._salva_stato_progetto()
             
             # Ricarica le impostazioni e tenta la riconnessione MIDI
             self._load_midi_settings(new_port_name) 
             QMessageBox.information(self, "Successo", "Mappature MIDI salvate e aggiornate.")

    # --- Gestione Dialog Aggiungi Fixture (definito nei Mixin) ---
    
    def _open_add_fixture_dialog(self):
        """Apre il dialogo per aggiungere una nuova fixture."""
        dialog = AddFixtureDialog(self, fixture_modelli=self.fixture_modelli)
        dialog.fixture_selected.connect(self._handle_fixture_add_request)
        dialog.exec()

    def _handle_fixture_add_request(self, selected_model_name_full: str, start_addr: int, nome_utente: str):
        """Esegue l'aggiunta effettiva della fixture dopo aver ricevuto i dati dal dialogo."""
        selected_model = next((m for m in self.fixture_modelli if m.nome == selected_model_name_full), None)
        
        if not selected_model:
            QMessageBox.critical(self, "Errore", "Modello selezionato non trovato.")
            return
            
        self._aggiungi_istanza_core(selected_model, start_addr, nome_utente)

    # --- Gestione Dialog Editor Chaser (definito nei Mixin) ---
    
    def _open_chaser_editor_dialog(self):
        """Apre il dialogo per creare o modificare un Chaser."""
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

    # --- Router per i Messaggi MIDI (Ingresso) ---
    def _midi_message_router(self, msg):
        """Reindirizza il messaggio MIDI al logger e al gestore di mappatura."""
        self._log_midi_message(msg)
        self._handle_midi_message(msg) # Chiama la logica di mappatura del mixin

    def _log_midi_message(self, msg):
        """Formatta e aggiunge il messaggio MIDI alla lista del monitor."""
        if not hasattr(self, 'midi_log_list'):
            return

        log_text = ""
        # Mido usa type 'note_on'/'note_off', 'control_change', 'program_change'

        if msg.type == 'note_on' and msg.velocity > 0:
            log_text = f"🎹 ON | CH {msg.channel + 1:02} | Note {msg.note:03} | Vel {msg.velocity:03}"
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            log_text = f"🎹 OFF | CH {msg.channel + 1:02} | Note {msg.note:03}"
        elif msg.type == 'control_change':
            log_text = f"🎚 CC | CH {msg.channel + 1:02} | Num {msg.control:03} | Val {msg.value:03}"
        elif msg.type == 'program_change':
            log_text = f"💽 PC | CH {msg.channel + 1:02} | Num {msg.program + 1:03}"
        else:
             # Altri messaggi come timing_clock, sysex, ecc.
             log_text = f"🎶 {msg.type.upper()} | {str(msg)}" 

        if log_text:
            # Inserisce in cima alla lista
            self.midi_log_list.insertItem(0, log_text)
            # Limita la dimensione della lista (es. 50 messaggi)
            if self.midi_log_list.count() > 50:
                self.midi_log_list.takeItem(50)
    # --- FINE NUOVI METODI MIDI ---
    
    # --- UI SCENOGRAFIA ---
    def _setup_ui(self):
        # Il layout principale della MainWindow divide le liste Scenografia (Sinistra) dal Controller DMX (Destra)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Splitter verticale per dividere lo spazio di lavoro (Liste/Editor Scenografia vs Controller DMX)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(main_splitter)

        # 1. Pannello Sinistro (Liste Scenografia)
        self.left_panel_scenografia = QWidget()
        self.left_panel_scenografia_layout = QVBoxLayout(self.left_panel_scenografia)
        main_splitter.addWidget(self.left_panel_scenografia)

        # Aggiungi le liste Brani e Playlist (con funzioni Drag & Drop)
        self._add_scenografia_lists()
        
        # 2. Pannello Destro (Editor Scenografia/Controller DMX)
        self.right_panel_editor_dmx = QWidget()
        self.right_panel_editor_dmx_layout = QVBoxLayout(self.right_panel_editor_dmx)
        main_splitter.addWidget(self.right_panel_editor_dmx)

        # Splitter interno per l'Editor DMX (Controller DMX vs Editor Canzoni/Playlist)
        dmx_editor_splitter = QSplitter(Qt.Orientation.Vertical)
        self.right_panel_editor_dmx_layout.addWidget(dmx_editor_splitter)
        
        # 2a. Pannello Editor Dinamico (Editor Canzone o Playlist)
        self.editor_container = QWidget()
        self.editor_layout = QVBoxLayout(self.editor_container)
        self.current_editor = None
        dmx_editor_splitter.addWidget(self.editor_container)

        # 2b. Pannello Fader/Controlli DMX (Aggiunto in basso per lasciare spazio all'editor)
        self.dmx_controls_scroll = QScrollArea()
        self.dmx_controls_scroll.setWidgetResizable(True)
        self.dmx_controls_container = QWidget()
        self.dmx_controls_layout = QVBoxLayout(self.dmx_controls_container)
        self.dmx_controls_scroll.setWidget(self.dmx_controls_container)
        dmx_editor_splitter.addWidget(self.dmx_controls_scroll)
        
        # Inizializza il pannello di controllo DMX (Scene, Chaser, DMX Comm, MIDI Monitor)
        control_panel_dmx = self._crea_pannello_controllo()
        self.dmx_controls_layout.addWidget(control_panel_dmx) 
        
        # 3. Imposta le dimensioni iniziali dello splitter per privilegiare l'editor
        main_splitter.setSizes([300, 900])
        dmx_editor_splitter.setSizes([500, 200]) # Editor sopra, Controlli DMX sotto
        
        # Popola le liste Scenografia
        self.load_scenografia_lists()


    def _add_scenografia_lists(self):
        """Aggiunge i widget per le liste di Brani e Playlist."""
        
        # --- Brani ---
        self.left_panel_scenografia_layout.addWidget(QLabel("Brani"))
        self.song_list = SongListWidget()
        self.left_panel_scenografia_layout.addWidget(self.song_list)

        hl_songs = QHBoxLayout()
        self.btn_add_song = QPushButton("+")
        self.btn_remove_song = QPushButton("x")
        hl_songs.addWidget(self.btn_add_song)
        hl_songs.addWidget(self.btn_remove_song)
        self.left_panel_scenografia_layout.addLayout(hl_songs)

        # --- Playlist ---
        self.left_panel_scenografia_layout.addWidget(QLabel("Playlist"))
        self.playlist_list = QListWidget()
        self.left_panel_scenografia_layout.addWidget(self.playlist_list)

        hl_playlists = QHBoxLayout()
        self.btn_add_playlist = QPushButton("+")
        self.btn_remove_playlist = QPushButton("x")
        hl_playlists.addWidget(self.btn_add_playlist)
        hl_playlists.addWidget(self.btn_remove_playlist)
        self.left_panel_scenografia_layout.addLayout(hl_playlists)
        
        self.left_panel_scenografia_layout.addStretch(1)

        # --- Connessioni ---
        self.song_list.itemDoubleClicked.connect(self.on_song_selected)
        self.btn_add_song.clicked.connect(self.add_song)
        self.btn_remove_song.clicked.connect(self.remove_selected_song)
        self.btn_add_playlist.clicked.connect(self.add_playlist)
        self.btn_remove_playlist.clicked.connect(self.remove_selected_playlist)
        
        self.playlist_list.itemDoubleClicked.connect(self.on_playlist_selected)


    def load_scenografia_lists(self):
        """Carica i brani e le playlist dai dati persistenti (DataManager di Scenografia)."""
        self.song_list.clear()
        self.playlist_list.clear() 
        for s in self.data_manager_scenografia.get_songs():
            self.song_list.addItem(s)
        for p in self.data_manager_scenografia.get_playlists():
            self.playlist_list.addItem(p)

    def on_song_selected(self, item):
        """Crea e mostra l'editor della canzone selezionata (SongEditorWidget)."""
        name = item.text()
        editor = SongEditorWidget(
            name,
            self.audio_engine,
            self.midi_engine_for_sync,
            self.data_manager_scenografia,
            self.settings_manager
        )
        self.show_editor(editor)

    def on_playlist_selected(self, item):
        """Crea e mostra l'editor della playlist selezionata (PlaylistEditorWidget)."""
        name = item.text()
        editor = PlaylistEditorWidget( 
            name,
            self.audio_engine,
            self.midi_engine_for_sync,
            self.data_manager_scenografia,
            self.settings_manager 
        )
        self.show_editor(editor)

    def add_song(self):
        """Apre il dialogo per creare un nuovo brano."""
        name, ok = QInputDialog.getText(self, "Nuovo Brano", "Nome:")
        if ok and name:
            if self.data_manager_scenografia.create_song(name):
                self.load_scenografia_lists()
            else:
                self.statusBar().showMessage("Brano già esistente", 3000)

    def remove_selected_song(self):
        """Rimuove il brano selezionato."""
        item = self.song_list.currentItem()
        if item:
            self.data_manager_scenografia.delete_song(item.text())
            self.load_scenografia_lists()

    def add_playlist(self):
        """Apre il dialogo per creare una nuova playlist."""
        name, ok = QInputDialog.getText(self, "Nuova Playlist", "Nome:")
        if ok and name:
            if self.data_manager_scenografia.create_playlist(name):
                self.load_scenografia_lists()
            else:
                self.statusBar().showMessage("Playlist già esistente", 3000)

    def remove_selected_playlist(self):
        """Rimuove la playlist selezionata."""
        item = self.playlist_list.currentItem()
        if item:
            self.data_manager_scenografia.delete_playlist(item.text())
            self.load_scenografia_lists()

    def show_editor(self, editor: QWidget):
        """Sostituisce l'editor corrente nel pannello destro con un nuovo editor."""
        if self.current_editor:
            self.current_editor.deleteLater() 

        layout = self.editor_layout
        if not layout:
            layout = QVBoxLayout()
            self.editor_container.setLayout(layout)

        layout.addWidget(editor)
        self.current_editor = editor
        
    # --- UI DMX ---
    def _crea_pannello_controllo(self):
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

# --- CLASSE HELPER PER DRAG & DROP ---

class SongListWidget(QListWidget):
    """QListWidget customizzato per permettere il drag di nomi di canzoni."""
    def mouseMoveEvent(self, event: QMouseEvent):
        from PyQt6.QtGui import QDrag, QMimeData, QMouseEvent 
        if event.buttons() == Qt.MouseButton.LeftButton:
            item = self.currentItem()
            if item:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(item.text()) 
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(event)