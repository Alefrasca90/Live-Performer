# ui/chaser_editor_dialog.py

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QListWidget, QPushButton, QDoubleSpinBox, QTableWidget, 
    QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox
)
from PyQt6.QtCore import pyqtSignal, Qt

from core.dmx_models import Scena, PassoChaser, Chaser 

class ChaserEditorDialog(QDialog):
    """Dialogo per creare o modificare un Chaser DMX."""
    
    # Segnale per notificare la MainWindow del Chaser salvato
    chaser_saved = pyqtSignal(Chaser) 
    
    def __init__(self, parent=None, scene_list: list[Scena] = None, chaser_to_edit: Chaser = None):
        super().__init__(parent)
        self.setWindowTitle("Editor Sequenza DMX (Chaser)")
        self.setModal(True)
        self.scene_list = scene_list if scene_list is not None else []
        self.scene_map = {s.nome: s for s in self.scene_list}
        self.chaser_to_edit = chaser_to_edit
        
        self._setup_ui()
        self._populate_scenes_table()
        
        if self.chaser_to_edit:
            self._load_chaser(self.chaser_to_edit)
            
    def _setup_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Nome Chaser
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Nome Sequenza:"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Es: RGB Flash")
        name_layout.addWidget(self.name_input)
        main_layout.addLayout(name_layout)
        
        # 2. Struttura Editor (Scene disponibili vs Passi)
        editor_layout = QHBoxLayout()
        
        # 2a. Scene Disponibili (Source)
        source_group = QVBoxLayout()
        source_group.addWidget(QLabel("Scene Disponibili (Doppio Click per Aggiungere):"))
        self.available_scenes_list = QListWidget()
        self.available_scenes_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.available_scenes_list.doubleClicked.connect(self._add_step_from_selected_scene)
        source_group.addWidget(self.available_scenes_list)
        editor_layout.addLayout(source_group, 1)

        # 2b. Passi Chaser (Destination)
        dest_group = QVBoxLayout()
        dest_group.addWidget(QLabel("Passi Sequenza (Scena / Tempi in Sec):"))
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(5) # N. Passo, Scena, Durata, Fade In, Fade Out
        self.steps_table.setHorizontalHeaderLabels(["#", "Scena", "Hold (s)", "Fade In (s)", "Fade Out (s)"])
        
        # Imposta le colonne per le dimensioni
        self.steps_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents) # #
        self.steps_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch) # Scena
        self.steps_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents) # Hold
        self.steps_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents) # Fade In
        self.steps_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents) # Fade Out
        
        self.steps_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        dest_group.addWidget(self.steps_table)

        # Controlli Passi
        step_controls = QHBoxLayout()
        self.btn_remove_step = QPushButton("Rimuovi Passo Selezionato")
        self.btn_remove_step.clicked.connect(self._remove_step)
        step_controls.addStretch(1)
        step_controls.addWidget(self.btn_remove_step)
        dest_group.addLayout(step_controls)
        
        editor_layout.addLayout(dest_group, 3)
        main_layout.addLayout(editor_layout)

        # 3. Pulsanti Azione
        action_buttons = QHBoxLayout()
        self.save_btn = QPushButton("Salva Sequenza")
        self.cancel_btn = QPushButton("Annulla")
        
        self.save_btn.clicked.connect(self._validate_and_save)
        self.cancel_btn.clicked.connect(self.reject)
        
        action_buttons.addStretch(1)
        action_buttons.addWidget(self.save_btn)
        action_buttons.addWidget(self.cancel_btn)
        main_layout.addLayout(action_buttons)
        
    def _populate_scenes_table(self):
        """Popola la lista delle scene disponibili."""
        self.available_scenes_list.clear()
        for s in self.scene_list:
            self.available_scenes_list.addItem(s.nome)
            
    def _load_chaser(self, chaser: Chaser):
        """Carica i dati di un chaser esistente nella UI."""
        self.name_input.setText(chaser.nome)
        self.steps_table.setRowCount(0)
        for passo in chaser.passi:
            self._add_step(
                passo.scena.nome, 
                passo.tempo_permanenza, 
                passo.tempo_fade_in, 
                passo.tempo_fade_out
            )

    def _add_step_from_selected_scene(self):
        """Aggiunge un passo dalla scena selezionata nella lista delle scene."""
        selected_item = self.available_scenes_list.currentItem()
        if selected_item:
            scene_name = selected_item.text()
            self._add_step(scene_name)

    def _create_time_spinbox(self, initial_value: float, suffix: str = " s") -> QDoubleSpinBox:
        """Crea e configura una QDoubleSpinBox per i tempi."""
        spinbox = QDoubleSpinBox()
        spinbox.setRange(0.0, 60.0)
        spinbox.setSingleStep(0.1)
        spinbox.setDecimals(1)
        spinbox.setSuffix(suffix)
        spinbox.setValue(initial_value)
        return spinbox

    def _add_step(self, scene_name: str, hold_time: float = 1.0, fade_in: float = 0.0, fade_out: float = 0.0):
        """Aggiunge una riga (passo) alla tabella dei passi."""
        row = self.steps_table.rowCount()
        self.steps_table.insertRow(row)
        
        # Colonna 0: Numero Passo
        item_index = QTableWidgetItem(str(row + 1))
        item_index.setFlags(item_index.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.steps_table.setItem(row, 0, item_index)
        
        # Colonna 1: Nome Scena
        item_scene_name = QTableWidgetItem(scene_name)
        item_scene_name.setFlags(item_scene_name.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.steps_table.setItem(row, 1, item_scene_name)
        
        # Colonna 2: Tempo di Permanenza (Hold)
        hold_spinbox = self._create_time_spinbox(hold_time)
        self.steps_table.setCellWidget(row, 2, hold_spinbox)
        
        # Colonna 3: Tempo di Fade In
        fade_in_spinbox = self._create_time_spinbox(fade_in)
        self.steps_table.setCellWidget(row, 3, fade_in_spinbox)

        # Colonna 4: Tempo di Fade Out
        fade_out_spinbox = self._create_time_spinbox(fade_out)
        self.steps_table.setCellWidget(row, 4, fade_out_spinbox)
        
    def _remove_step(self):
        """Rimuove il passo selezionato dalla tabella."""
        selected_rows = self.steps_table.selectedIndexes()
        if selected_rows:
            # Rimuove la riga (indice riga della prima cella selezionata)
            row_index = selected_rows[0].row()
            self.steps_table.removeRow(row_index)
            # Riassegna i numeri di passo
            for row in range(self.steps_table.rowCount()):
                 self.steps_table.item(row, 0).setText(str(row + 1))

    def _validate_and_save(self):
        """Estrae i dati, crea l'oggetto Chaser e lo emette."""
        nome_chaser = self.name_input.text().strip()
        
        if not nome_chaser:
            QMessageBox.warning(self, "Errore", "Il nome della Sequenza non può essere vuoto.")
            return

        row_count = self.steps_table.rowCount()
        if row_count < 1:
            QMessageBox.warning(self, "Errore", "La Sequenza deve contenere almeno un Passo.")
            return
            
        passi_definiti: list[PassoChaser] = []
        try:
            for row in range(row_count):
                scene_name = self.steps_table.item(row, 1).text()
                
                # Recupera Hold Time (Colonna 2)
                hold_widget = self.steps_table.cellWidget(row, 2)
                hold_time = hold_widget.value() if hold_widget else 1.0

                # Recupera Fade In Time (Colonna 3)
                fade_in_widget = self.steps_table.cellWidget(row, 3)
                fade_in_time = fade_in_widget.value() if fade_in_widget else 0.0

                # Recupera Fade Out Time (Colonna 4)
                fade_out_widget = self.steps_table.cellWidget(row, 4)
                fade_out_time = fade_out_widget.value() if fade_out_widget else 0.0

                if hold_time <= 0.0 and fade_in_time <= 0.0 and fade_out_time <= 0.0:
                    QMessageBox.warning(self, "Errore Passo", f"Il Passo {row+1} deve avere almeno un tempo (Hold, Fade In o Fade Out) > 0.0s.")
                    return
                
                scena = self.scene_map.get(scene_name)
                if not scena:
                    raise Exception(f"Scena '{scene_name}' non trovata. Ricarica la finestra.")
                
                passo = PassoChaser(
                    scena=scena, 
                    tempo_permanenza=hold_time,
                    tempo_fade_in=fade_in_time,
                    tempo_fade_out=fade_out_time
                )
                passi_definiti.append(passo)

        except Exception as e:
            QMessageBox.critical(self, "Errore Interno", f"Si è verificato un errore durante l'estrazione dei dati: {e}")
            return
            
        nuovo_chaser = Chaser(nome=nome_chaser, passi=passi_definiti)
        
        self.chaser_saved.emit(nuovo_chaser) 
        
        self.accept()