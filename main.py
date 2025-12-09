# main_unified.py (Entry point del software unificato)

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar, QMessageBox, QLabel, QWidget, QVBoxLayout
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt, QSize

# --- 1. Import dei Componenti Core ---
from core.data_manager import DataManager 
from engines.audio_engine import AudioEngine
from engines.midi_engine import MidiEngine
from engines.video_engine import VideoEngine # Engine Video
from ui.components.settings_manager import SettingsManager

# --- 2. Import dei Componenti UI Refactorizzati (Widget) ---
from ui.views.dmx_control_widget import DMXControlWidget 
from ui.views.scenografia_daw_widget import ScenografiaDAWWidget 
from ui.views.stage_view import StageViewWidget # Importato il widget rifattorizzato
from ui.views.lyrics_player_window import LyricsPlayerWidget # Importato il widget lyrics rifattorizzato
from ui.views.midi_monitor_tab_widget import MidiMonitorTabWidget 
from ui.views.video_player_widget import VideoPlayerWidget # Player Video effettivo

# --- New Placeholder Widgets for new tabs ---
# Rimosso VideoPlaceholderWidget
# --- End Placeholder Widgets ---


class UnifiedMainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified Lighting & Media Controller")
        self.setGeometry(100, 100, 1600, 900) 
        
        # --- 3. Inizializzazione Core Engines/Managers ---
        self.audio_engine = AudioEngine()
        self.midi_engine = MidiEngine() 
        self.video_engine = VideoEngine() # NUOVO: Engine Video
        self.scenografia_data_manager = DataManager() 
        self.settings_manager = SettingsManager()

        # --- Stage View and Lyrics Widgets (Instantiated by MainWindow for embedding) ---
        self.stage_view_widget = StageViewWidget() 
        
        # INJECTION POINT: Instanziazione del Lyrics Player come QWidget
        self.lyrics_player_widget = LyricsPlayerWidget(
            audio_engine=self.audio_engine, 
            midi_engine=self.midi_engine,
            settings_manager=self.settings_manager,
            parent=self
        )
        
        # INJECTION POINT: Instanziazione del Video Player effettivo
        self.video_player_widget = VideoPlayerWidget(
            video_engine=self.video_engine,
            audio_engine=self.audio_engine,
            settings_manager=self.settings_manager
        )
        
        # --- 4. Setup Main UI (Tabs) ---
        tab_widget = QTabWidget()
        self.setCentralWidget(tab_widget)
        self.tab_widget = tab_widget
        
        # Inizializza la Status Bar
        self.setStatusBar(QStatusBar())

        # --- 5. Media Tab (FIRST) ---
        self.scenografia_widget = ScenografiaDAWWidget(
            audio_engine=self.audio_engine, 
            midi_engine=self.midi_engine,
            video_engine=self.video_engine, # INJECTED
            data_manager=self.scenografia_data_manager, 
            settings_manager=self.settings_manager,
            lyrics_player_widget=self.lyrics_player_widget, # INJECTED
            video_player_widget=self.video_player_widget, # INJECTED
            parent=self
        )
        tab_widget.addTab(self.scenografia_widget, "Media")
        
        # --- 6. Video Tab (SECOND) ---
        tab_widget.addTab(self.video_player_widget, "Video") # USA IL WIDGET EFFETTIVO
        
        # --- 7. Lyrics Tab (THIRD) ---
        tab_widget.addTab(self.lyrics_player_widget, "Lyrics") 

        # --- 8. Fixtures Tab (FOURTH) ---
        self.dmx_widget = DMXControlWidget(
            audio_engine=self.audio_engine,
            midi_engine=self.midi_engine,
            settings_manager=self.settings_manager,
            stage_view=self.stage_view_widget, # INJECTED
            parent=self
        )
        tab_widget.addTab(self.dmx_widget, "Fixtures")
        
        # --- 9. Stage Tab (FIFTH) ---
        tab_widget.addTab(self.stage_view_widget, "Stage") 

        # --- 10. MIDI Monitor Tab (SIXTH / ULTIMO) ---
        self.midi_monitor_tab_widget = MidiMonitorTabWidget( 
            midi_controller=self.dmx_widget.midi_controller, 
            midi_engine=self.midi_engine, 
            parent=self
        )
        tab_widget.addTab(self.midi_monitor_tab_widget, "MIDI Monitor") 

        # --- 11. Setup Menu Bar (CENTRALE) ---
        self._setup_menu_bar()
        
        # --- 12. Applica Stile Comune ---
        self._apply_style()

    def _setup_menu_bar(self):
        """Crea il QMenuBar e implementa i menu File/Strumenti/Impostazioni/Info."""
        
        menu_bar = self.menuBar()
        
        # ====================================================
        # AZIONI CONDIVISE
        # ====================================================
        
        save_action = QAction(QIcon.fromTheme("document-save"), "Salva Progetto DMX...", self)
        save_action.triggered.connect(self.dmx_widget.salva_progetto_a_file)
        
        load_action = QAction(QIcon.fromTheme("document-open"), "Carica Progetto DMX...", self)
        load_action.triggered.connect(self.dmx_widget.carica_progetto_da_file)
        
        reconnect_action = QAction(QIcon.fromTheme("network-transmit-receive"), "Riconnetti DMX", self)
        reconnect_action.triggered.connect(self.dmx_widget._handle_dmx_connection)


        # ====================================================
        # MENU FILE
        # ====================================================
        file_menu = menu_bar.addMenu("File")
        
        file_menu.addAction(save_action)
        file_menu.addAction(load_action)
        file_menu.addSeparator()

        exit_action = QAction(QIcon.fromTheme("application-exit"), "Esci", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # ====================================================
        # MENU STRUMENTI
        # ====================================================
        tools_menu = menu_bar.addMenu("Strumenti")
        
        # Stage View
        stage_action = QAction(QIcon.fromTheme("view-stage"), "Stage View (Posizioni Luci)", self)
        stage_action.triggered.connect(self.dmx_widget._open_stage_view)
        tools_menu.addAction(stage_action)

        # Editor Modelli
        editor_action = QAction(QIcon.fromTheme("document-edit"), "Editor Modelli Fixture", self)
        editor_action.triggered.connect(self.dmx_widget._open_fixture_editor)
        tools_menu.addAction(editor_action)

        # Mappature MIDI
        midi_map_action = QAction(QIcon.fromTheme("preferences-desktop-keyboard-shortcuts"), "Mappature MIDI Input", self)
        midi_map_action.triggered.connect(self.dmx_widget._open_midi_mapping_dialog)
        tools_menu.addAction(midi_map_action)
        
        # ====================================================
        # MENU IMPOSTAZIONI
        # ====================================================
        settings_menu = menu_bar.addMenu("Impostazioni")
        
        # Settings Dialog (Generali)
        settings_action = QAction(QIcon.fromTheme("preferences-system"), "Audio / MIDI / Display...", self)
        settings_action.triggered.connect(self.dmx_widget._open_settings_dialog)
        settings_menu.addAction(settings_action)
        
        settings_menu.addSeparator()

        # Riconnetti DMX
        settings_menu.addAction(reconnect_action)
        
        # ====================================================
        # MENU INFO
        # ====================================================
        info_menu = menu_bar.addMenu("Info")
        
        info_action = QAction(QIcon.fromTheme("help-about"), "Informazioni Software", self)
        info_action.triggered.connect(self.dmx_widget._show_info_dialog)
        info_menu.addAction(info_action)
        
        # --- TOOLBAR PRINCIPALE (CONTROLLI RAPIDI) ---
        # Rimosso: toolbar creation and adding actions


    def _apply_style(self):
        # Applica lo stile scuro/moderno a tutta l'app
        app = QApplication.instance()
        app.setStyleSheet("""
            QMainWindow {
                background-color: #333;
            }
            QTabWidget::pane {
                border-top: 1px solid #555;
                background-color: #444;
            }
            QTabWidget::tab-bar {
                left: 5px; 
            }
            QTabBar::tab {
                background: #555;
                border: 1px solid #555;
                border-bottom-color: #444; 
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                min-width: 150px;
                padding: 5px 10px;
                color: white;
            }
            QTabBar::tab:selected, QTabBar::tab:hover {
                background: #666;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                background-color: #444;
                color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
                color: white;
            }
            QLabel {
                color: #ddd;
            }
            QComboBox {
                background-color: #555;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #555;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px;
            }
            QLineEdit {
                background-color: #555;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px;
            }
            QListWidget, QTableWidget {
                background-color: #555;
                color: white;
                border: 1px solid #555;
                gridline-color: #333;
            }
            QHeaderView::section {
                background-color: #666;
                color: white;
                padding: 4px;
                border: 1px solid #555;
            }
            QPushButton {
                background-color: #0078D4; 
                color: white;
                border-radius: 4px;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #005A9E;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 8px;
                background: #555;
                margin: 2px 0;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #ddd;
                border: 1px solid #555;
                width: 18px;
                margin: -5px 0; 
                border-radius: 9px;
            }
        """)
        
    def closeEvent(self, event):
        """Gestione della chiusura unificata: pulizia DMX e stop media."""
        self.dmx_widget.cleanup()
        self.scenografia_widget.cleanup()
        self.midi_monitor_tab_widget.cleanup()
        super().closeEvent(event)

if __name__ == '__main__':
    # Assicura che la libreria Python corretta sia usata e che le dipendenze siano installate
    app = QApplication(sys.argv)
    window = UnifiedMainWindow()
    window.show()
    sys.exit(app.exec())