# ui/midi_mapping_dialog.py (COMPLETO E AGGIORNATO)

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, 
    QTableWidgetItem, QHeaderView, QPushButton, QComboBox, 
    QSpinBox, QAbstractItemView, QWidget, QLineEdit, QMessageBox, QGroupBox, QCheckBox 
)
from PyQt6.QtCore import pyqtSignal, Qt

from core.project_models import MidiMapping
from core.dmx_models import Scena, Chaser

class MidiMappingDialog(QDialog):
    """Dialogo per configurare le mappature MIDI da/verso Scene/Chaser/Stop."""
    
    # Segnale emesso quando le mappature sono salvate (inclusi canale e porta)
    mappings_saved = pyqtSignal(list, int, str) 

    def __init__(self, parent=None, scene_list: list[Scena] = None, chaser_list: list[Chaser] = None, 
                 current_mappings: list[MidiMapping] = None, 
                 current_channel_filter: int = 0, 
                 available_ports: list[str] = None, 
                 current_port_name: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Gestione Mappature MIDI")
        self.setModal(True)
        
        self.scene_list = scene_list if scene_list is not None else []
        self.chaser_list = chaser_list if chaser_list is not None else []
        self.current_mappings = current_mappings if current_mappings is not None else []
        self.channel_filter = current_channel_filter
        self.available_ports = available_ports if available_ports is not None else []
        self.port_name = current_port_name
        
        self._setup_ui()
        self._load_mappings()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        self.resize(1000, 500) # Dimensione aumentata per la nuova colonna

        # --- Sezione Impostazioni MIDI ---
        settings_group = QGroupBox("Impostazioni Controller")
        settings_layout = QHBoxLayout(settings_group)
        
        # Filtro Canale
        channel_layout = QVBoxLayout()
        channel_layout.addWidget(QLabel("Canale Filtro:"))
        self.midi_channel_spinbox = QSpinBox()
        self.midi_channel_spinbox.setRange(0, 16)
        self.midi_channel_spinbox.setToolTip("0 = Tutti i canali, 1-16 = Canale specifico.")
        self.midi_channel_spinbox.setValue(self.channel_filter)
        channel_layout.addWidget(self.midi_channel_spinbox)
        settings_layout.addLayout(channel_layout)
        
        # Selezione Porta
        port_layout = QVBoxLayout()
        port_layout.addWidget(QLabel("Porta MIDI In:"))
        self.midi_port_combo = QComboBox()
        self.midi_port_combo.addItems(self.available_ports)
        if self.port_name in self.available_ports:
             self.midi_port_combo.setCurrentText(self.port_name)
        port_layout.addWidget(self.midi_port_combo)
        settings_layout.addLayout(port_layout)
        
        settings_layout.addStretch(1)
        main_layout.addWidget(settings_group)
        
        # 1. Tabella di Mappatura
        self.table = QTableWidget()
        self.table.setColumnCount(6) # MODIFICATO: da 5 a 6 colonne
        self.table.setHorizontalHeaderLabels([
            "Tipo MIDI", 
            "Numero (Nota/CC/PC#)", 
            "Valore Min/Soglia", 
            "Azione", 
            "Target (Scena/Chaser)",
            "Solo DMX Interno" # NUOVO NOME COLONNA
        ])
        
        # Imposta le colonne per le dimensioni
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents) # NUOVA COLONNA
        
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        main_layout.addWidget(self.table)

        # 2. Controlli Tabella
        control_layout = QHBoxLayout()
        self.btn_add = QPushButton("Aggiungi Mappatura")
        self.btn_remove = QPushButton("Rimuovi Selezionata")
        
        self.btn_add.clicked.connect(lambda: self._add_row())
        self.btn_remove.clicked.connect(self._remove_row)
        
        control_layout.addWidget(self.btn_add)
        control_layout.addWidget(self.btn_remove)
        control_layout.addStretch(1)
        main_layout.addLayout(control_layout)

        # 3. Pulsanti Azione
        action_buttons = QHBoxLayout()
        self.save_btn = QPushButton("Salva Mappature")
        self.cancel_btn = QPushButton("Annulla")
        
        self.save_btn.clicked.connect(self._validate_and_save)
        self.cancel_btn.clicked.connect(self.reject)
        
        action_buttons.addStretch(1)
        action_buttons.addWidget(self.save_btn)
        action_buttons.addWidget(self.cancel_btn)
        main_layout.addLayout(action_buttons)

    def _add_row(self, mapping: MidiMapping = None):
        """Aggiunge una riga alla tabella, con widget per l'input."""
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # Colonna 0: Tipo MIDI (ComboBox)
        combo_type = QComboBox()
        combo_type.addItems(['note', 'cc', 'pc'])
        self.table.setCellWidget(row, 0, combo_type)
        
        # Colonna 1: Numero (SpinBox 0-127/128)
        spin_number = QSpinBox()
        spin_number.setRange(0, 127)
        self.table.setCellWidget(row, 1, spin_number)
        
        # Colonna 2: Valore/Soglia (SpinBox 0-127)
        spin_value = QSpinBox()
        spin_value.setRange(0, 127)
        spin_value.setToolTip("Per CC: Valore di Soglia (Es: 64).\nPer Note: 1 (On), 0 (Off/ignora).")
        self.table.setCellWidget(row, 2, spin_value)

        # Colonna 3: Azione (ComboBox)
        combo_action = QComboBox()
        combo_action.addItems(['stop', 'scene', 'chaser'])
        self.table.setCellWidget(row, 3, combo_action)
        
        # Colonna 4: Target (ComboBox)
        combo_target = QComboBox()
        combo_target.addItem("-")
        
        target_options = []
        if self.scene_list:
            target_options.extend([f"Scena: {s.nome}" for s in self.scene_list])
        if self.chaser_list:
            target_options.extend([f"Chaser: {c.nome}" for c in self.chaser_list])
        
        combo_target.addItems(target_options)
        self.table.setCellWidget(row, 4, combo_target)
        
        # Colonna 5: Solo DMX Interno (Checkbox)
        chk_internal = QCheckBox()
        # Verifichiamo l'esistenza dell'attributo per compatibilità con dati vecchi
        if mapping and hasattr(mapping, 'internal_only'): 
             chk_internal.setChecked(mapping.internal_only)
        self.table.setCellWidget(row, 5, chk_internal)
        
        if mapping:
            combo_type.setCurrentText(mapping.midi_type)
            spin_number.setValue(mapping.midi_number)
            spin_value.setValue(mapping.value)
            combo_action.setCurrentText(mapping.action_type)
            
            # Cerca il target corretto
            if mapping.action_type == 'stop':
                 combo_target.setCurrentIndex(0) # Deve essere "-"
            elif mapping.action_type == 'scene':
                 try:
                    target_name = self.scene_list[mapping.action_index].nome
                    combo_target.setCurrentText(f"Scena: {target_name}")
                 except IndexError:
                      pass
            elif mapping.action_type == 'chaser':
                 try:
                    target_name = self.chaser_list[mapping.action_index].nome
                    combo_target.setCurrentText(f"Chaser: {target_name}")
                 except IndexError:
                      pass

    def _remove_row(self):
        """Rimuove la riga selezionata dalla tabella."""
        selected_rows = self.table.selectedIndexes()
        if selected_rows:
            row_index = selected_rows[0].row()
            self.table.removeRow(row_index)

    def _load_mappings(self):
        """Carica le mappature esistenti nella tabella."""
        self.table.setRowCount(0)
        for mapping in self.current_mappings:
            self._add_row(mapping)

    def _validate_and_save(self):
        """Estrae i dati dalla tabella, crea gli oggetti MidiMapping e li emette."""
        new_mappings = []
        scene_names = [s.nome for s in self.scene_list]
        chaser_names = [c.nome for c in self.chaser_list]
        
        # 1. Ottieni il filtro canale e porta
        new_channel_filter = self.midi_channel_spinbox.value()
        new_port_name = self.midi_port_combo.currentText()

        # 2. Estrazione Mappature
        for row in range(self.table.rowCount()):
            try:
                # Estrarre i widget
                combo_type = self.table.cellWidget(row, 0)
                spin_number = self.table.cellWidget(row, 1)
                spin_value = self.table.cellWidget(row, 2)
                combo_action = self.table.cellWidget(row, 3)
                combo_target = self.table.cellWidget(row, 4)
                chk_internal = self.table.cellWidget(row, 5) # NUOVO WIDGET

                # Estrazione dei valori
                midi_type = combo_type.currentText()
                midi_number = spin_number.value()
                value = spin_value.value()
                action_type = combo_action.currentText()
                target_text = combo_target.currentText()
                
                internal_only = chk_internal.isChecked() if chk_internal else False # NUOVO VALORE

                action_index = -1 

                # Validazione Target (Scena/Chaser)
                if action_type == 'scene' or action_type == 'chaser':
                    if target_text == "-":
                        QMessageBox.warning(self, "Errore Mappatura", f"Il Passo {row+1} con Azione '{action_type}' deve avere un Target valido.")
                        return

                    target_name = target_text.split(": ")[1]
                    if action_type == 'scene':
                        if target_name not in scene_names:
                             QMessageBox.warning(self, "Errore Mappatura", f"Scena '{target_name}' non trovata per il Passo {row+1}.")
                             return
                        action_index = scene_names.index(target_name)
                    elif action_type == 'chaser':
                        if target_name not in chaser_names:
                             QMessageBox.warning(self, "Errore Mappatura", f"Chaser '{target_name}' non trovato per il Passo {row+1}.")
                             return
                        action_index = chaser_names.index(target_name)
                
                # Validazione Stop
                elif action_type == 'stop':
                    if midi_type == 'note' and value == 0:
                        QMessageBox.warning(self, "Errore Mappatura", f"Lo Stop con Note On deve avere un Valore Soglia > 0.")
                        return
                    action_index = -1 

                new_mappings.append(MidiMapping(
                    midi_type=midi_type, 
                    midi_number=midi_number, 
                    value=value, 
                    action_type=action_type, 
                    action_index=action_index,
                    internal_only=internal_only # AGGIUNTO
                ))

            except Exception as e:
                QMessageBox.critical(self, "Errore Interno", f"Errore estrazione riga {row+1}: {e}")
                return
            
        # 3. Emette tutti i dati
        self.mappings_saved.emit(new_mappings, new_channel_filter, new_port_name) 
        self.accept()