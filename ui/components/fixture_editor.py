# ui/fixture_editor.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox, 
    QSpinBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal

# Importiamo i modelli di dati
from core.dmx_models import FixtureModello, CanaleDMX

class FixtureEditorDialog(QDialog):
    """
    Dialogo per creare o modificare un FixtureModello personalizzato.
    Emette un segnale quando un nuovo modello è stato salvato.
    """
    
    # Segnale personalizzato per notificare la MainWindow del modello salvato
    model_saved = pyqtSignal(FixtureModello) 

    def __init__(self, parent=None, modello_esistente: FixtureModello = None):
        super().__init__(parent)
        self.setWindowTitle("Editor Modello Fixture DMX")
        self.modello_originale = modello_esistente
        self.setGeometry(200, 200, 600, 500)
        
        self._setup_ui()
        
        # Se stiamo modificando un modello esistente, lo carichiamo
        if self.modello_originale:
            self._load_modello(self.modello_originale)
        else:
            # Altrimenti, iniziamo con 5 canali vuoti
            self._add_row(5) 

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Nome della Fixture
        name_group = QHBoxLayout()
        name_group.addWidget(QLabel("Nome Fixture:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Es: PAR LED RGBW (5ch)")
        name_group.addWidget(self.name_input)
        main_layout.addLayout(name_group)
        
        # 2. Tabella dei Canali
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Indice DMX", "Funzione (Nome)", "Valore Default (0-255)"])
        
        # Rende l'intestazione della Funzione espandibile
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        
        main_layout.addWidget(self.table)
        
        # 3. Controlli Tabella
        table_controls = QHBoxLayout()
        self.add_btn = QPushButton("Aggiungi Canale (+)")
        self.remove_btn = QPushButton("Rimuovi Ultimo (-)")
        
        self.add_btn.clicked.connect(lambda: self._add_row(1))
        self.remove_btn.clicked.connect(self._remove_row)
        
        table_controls.addWidget(self.add_btn)
        table_controls.addWidget(self.remove_btn)
        table_controls.addStretch(1)
        main_layout.addLayout(table_controls)
        
        # 4. Pulsanti Azione
        action_buttons = QHBoxLayout()
        self.save_btn = QPushButton("Salva Modello")
        self.cancel_btn = QPushButton("Annulla")
        
        self.save_btn.clicked.connect(self._validate_and_save)
        self.cancel_btn.clicked.connect(self.reject)
        
        action_buttons.addStretch(1)
        action_buttons.addWidget(self.save_btn)
        action_buttons.addWidget(self.cancel_btn)
        main_layout.addLayout(action_buttons)

    def _add_row(self, count=1):
        """Aggiunge una o più righe vuote alla tabella."""
        current_row_count = self.table.rowCount()
        for i in range(count):
            row = current_row_count + i
            self.table.insertRow(row)
            
            # Colonna 0: Indice DMX (Visualizzazione, non modificabile)
            item_index = QTableWidgetItem(str(row + 1))
            item_index.setFlags(item_index.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, item_index)
            
            # Colonna 1: Funzione (LineEdit)
            item_name = QLineEdit()
            item_name.setPlaceholderText("Es: Rosso / Dimmer")
            self.table.setCellWidget(row, 1, item_name)
            
            # Colonna 2: Valore Default (SpinBox 0-255)
            spin_box = QSpinBox()
            spin_box.setRange(0, 255)
            spin_box.setValue(0)
            self.table.setCellWidget(row, 2, spin_box)
            
    def _remove_row(self):
        """Rimuove l'ultima riga dalla tabella, se ce ne sono più di 1."""
        current_row_count = self.table.rowCount()
        if current_row_count > 1:
            self.table.removeRow(current_row_count - 1)

    def _load_modello(self, modello: FixtureModello):
        """Carica i dati di un modello esistente nella UI."""
        self.name_input.setText(modello.nome)
        
        # Pulisce la tabella e carica i canali
        self.table.setRowCount(0) 
        for i, canale in enumerate(modello.descrizione_canali):
            self._add_row(1) # Aggiunge una riga
            
            # Carica il nome/funzione
            name_widget = self.table.cellWidget(i, 1)
            if isinstance(name_widget, QLineEdit):
                name_widget.setText(canale.nome)
                
            # Carica il valore di default
            spin_widget = self.table.cellWidget(i, 2)
            if isinstance(spin_widget, QSpinBox):
                spin_widget.setValue(canale.valore_default)

    def _validate_and_save(self):
        """Estrae i dati dalla tabella, crea il modello e lo salva."""
        nome_fixture = self.name_input.text().strip()
        
        if not nome_fixture:
            QMessageBox.warning(self, "Errore", "Il nome della Fixture non può essere vuoto.")
            return

        canali_definiti: list[CanaleDMX] = []
        try:
            for row in range(self.table.rowCount()):
                # Colonna 1: Nome/Funzione (QLineEdit)
                name_widget = self.table.cellWidget(row, 1)
                canale_nome = name_widget.text().strip() if name_widget else ""

                if not canale_nome:
                    QMessageBox.warning(self, "Errore Canale", f"Il canale {row+1} deve avere un nome (Funzione).")
                    return

                # Colonna 2: Valore Default (QSpinBox)
                spin_widget = self.table.cellWidget(row, 2)
                canale_default = spin_widget.value() if spin_widget else 0
                
                # Per semplicità, la funzione DMX la poniamo come lo stesso nome per ora
                canali_definiti.append(CanaleDMX(
                    nome=canale_nome, 
                    funzione=canale_nome, # TODO: Migliorare con una ComboBox per funzioni predefinite
                    valore_default=canale_default
                ))

        except Exception as e:
            QMessageBox.critical(self, "Errore Interno", f"Si è verificato un errore durante l'estrazione dei dati: {e}")
            return
            
        # Creazione del nuovo Modello
        nuovo_modello = FixtureModello(nome=nome_fixture, descrizione_canali=canali_definiti)
        
        # Emette il segnale con il nuovo modello
        self.model_saved.emit(nuovo_modello) 
        
        self.accept() # Chiude la finestra di dialogo