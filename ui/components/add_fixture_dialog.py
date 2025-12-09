# ui/add_fixture_dialog.py

from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QSpinBox, QPushButton, QMessageBox, QLineEdit 
from PyQt6.QtCore import pyqtSignal

# Import Models for type hinting
from core.dmx_models import FixtureModello

class AddFixtureDialog(QDialog):
    """Dialogo per selezionare il modello e l'indirizzo DMX per una nuova fixture."""
    
    # Segnale per inviare il nome del modello selezionato, l'indirizzo DMX e il nome utente
    fixture_selected = pyqtSignal(str, int, str) 

    def __init__(self, parent=None, fixture_modelli: list[FixtureModello] = None):
        super().__init__(parent)
        self.setWindowTitle("Aggiungi Fixture all'Universo")
        # Il dialogo deve essere modale
        self.setModal(True) 
        self.fixture_modelli = fixture_modelli if fixture_modelli is not None else []
        
        self._setup_ui()
        self._populate_models()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Modello
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Modello Fixture:"))
        self.combo_modelli = QComboBox()
        model_layout.addWidget(self.combo_modelli)
        main_layout.addLayout(model_layout)

        # 2. Indirizzo DMX
        addr_layout = QHBoxLayout()
        addr_layout.addWidget(QLabel("Indirizzo DMX:"))
        self.addr_spinbox = QSpinBox()
        self.addr_spinbox.setRange(1, 512)
        self.addr_spinbox.setValue(1)
        addr_layout.addWidget(self.addr_spinbox)
        main_layout.addLayout(addr_layout)
        
        # 3. Nome Personalizzato
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome Personalizzato (Opz.):"))
        self.name_input = QLineEdit() 
        self.name_input.setPlaceholderText("Es: Luce Frontale Sinistra")
        name_layout.addWidget(self.name_input)
        main_layout.addLayout(name_layout)
        
        # 4. Pulsanti Azione
        action_buttons = QHBoxLayout()
        self.add_btn = QPushButton("Aggiungi Fixture")
        self.cancel_btn = QPushButton("Annulla")
        
        self.add_btn.clicked.connect(self._validate_and_emit)
        self.cancel_btn.clicked.connect(self.reject)
        
        action_buttons.addStretch(1)
        action_buttons.addWidget(self.add_btn)
        action_buttons.addWidget(self.cancel_btn)
        main_layout.addLayout(action_buttons)

    def _populate_models(self):
        """Popola la QComboBox con i modelli disponibili."""
        self.combo_modelli.clear()
        if self.fixture_modelli:
            for modello in self.fixture_modelli:
                # Esclude i modelli virtuali
                if "Virtuale" not in modello.nome:
                    self.combo_modelli.addItem(f"{modello.nome} ({modello.numero_canali}ch)")

    def _validate_and_emit(self):
        """Estrae i dati e emette il segnale prima di chiudere."""
        selected_text = self.combo_modelli.currentText()
        start_addr = self.addr_spinbox.value()
        user_name = self.name_input.text().strip() 
        
        if not selected_text:
            QMessageBox.warning(self, "Errore", "Nessun modello selezionato o disponibile.")
            return

        # Estraiamo solo il nome del modello (prima della parentesi)
        model_name_full = selected_text.split(" (")[0]
        
        self.fixture_selected.emit(model_name_full, start_addr, user_name) 
        self.accept() # Chiude la finestra di dialogo