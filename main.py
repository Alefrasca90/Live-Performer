# main_unified.py (Entry point del software unificato)

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar
from PyQt6.QtCore import Qt

# --- 1. Import dei Componenti Core ---
# DMX Core (Project Data Manager)
from core.data_manager import DataManager as DMXDataManager 

# Scenografia Core (Media Engines e Data Manager)
from engines.audio_engine import AudioEngine
from engines.midi_engine import MidiEngine
from data_manager import DataManager as ScenografiaDataManager # Alias per Media DataManager
from ui.components.settings_manager import SettingsManager

# --- 2. Import dei Componenti UI Refactorizzati (Widget) ---
from ui.views.dmx_control_widget import DMXControlWidget 
from ui.views.scenografia_daw_widget import ScenografiaDAWWidget 

class UnifiedMainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unified Lighting & Media Controller")
        # Aumentiamo la dimensione per accomodare le due tabs
        self.setGeometry(100, 100, 1600, 900) 
        
        # --- 3. Inizializzazione Core Engines/Managers ---
        self.audio_engine = AudioEngine()
        self.midi_engine = MidiEngine() # Engine Output MIDI/Clock (Scenografia)
        self.scenografia_data_manager = ScenografiaDataManager()
        self.settings_manager = SettingsManager()
        
        # --- 4. Setup Main UI (Tabs) ---
        tab_widget = QTabWidget()
        self.setCentralWidget(tab_widget)
        
        # Inizializza la Status Bar
        self.setStatusBar(QStatusBar())

        # --- 5. DMX Tab ---
        # DMXControlWidget inizializza le sue dipendenze (DMXController, MIDIController Input)
        self.dmx_widget = DMXControlWidget(parent=self)
        tab_widget.addTab(self.dmx_widget, "DMX Controllo Luci")
        
        # --- 6. Scenografia Tab ---
        self.scenografia_widget = ScenografiaDAWWidget(
            audio_engine=self.audio_engine, 
            midi_engine=self.midi_engine, 
            data_manager=self.scenografia_data_manager, 
            settings_manager=self.settings_manager,
            parent=self
        )
        tab_widget.addTab(self.scenografia_widget, "Scenografia Media & Lyrics")
        
        # --- 7. Applica Stile Comune ---
        self._apply_style()

    def _apply_style(self):
        # Applica lo stile scuro/moderno (da midi-fixtures/main.py) a tutta l'app
        app = QApplication.instance()
        # Nota: lo stile è stato condensato in un'unica stringa CSS.
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
        # Chiama la funzione di pulizia dei widget (disconnessioni, salvataggi finali)
        self.dmx_widget.cleanup()
        self.scenografia_widget.cleanup()
        super().closeEvent(event)

if __name__ == '__main__':
    # Assicura che la libreria Python corretta sia usata e che le dipendenze siano installate
    app = QApplication(sys.argv)
    window = UnifiedMainWindow()
    window.show()
    sys.exit(app.exec())