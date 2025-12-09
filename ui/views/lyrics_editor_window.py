import sys
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton,
    QTableWidget, QTableWidgetItem, QApplication
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QBrush 

import sounddevice as sd
import soundfile as sf
import threading
import time
import os 

# Tenta l'importazione di numpy per la gestione dei dati audio di fallback
try:
    import numpy as np
except ImportError:
    np = None


class LyricsEditorWindow(QDialog):
    """
    Finestra di dialogo per la sincronizzazione dei lyrics con un file audio locale.
    """
    def __init__(self, audio_file: str, text_lines: list[str], timestamps: list[float], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lyrics Editor")
        self.setMinimumSize(900, 600)

        self.audio_file = audio_file
        self.text_lines = text_lines.copy()
        self.timestamps = timestamps.copy()
        
        # Assicura che le liste siano allineate
        while len(self.timestamps) < len(self.text_lines):
            self.timestamps.append(0.0)

        # --- STATO AUDIO INTERNO ---
        self.audio_data = None
        self.samplerate = None
        self.audio_pos = 0
        self.playing = False
        self.start_time = 0.0
        self.pause_time = 0.0
        self.active_row = -1

        self.load_audio(audio_file)
        self.init_ui()

        # Timer per aggiornare l'interfaccia e la colorazione del testo (20ms = 50 FPS)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_playback)
        self.timer.start(20) 

    # -------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------
    def init_ui(self):
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # TABELLA (Timestamp + Testo)
        self.table = QTableWidget()
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Timestamp (s)", "Testo"])
        self.table.verticalHeader().setVisible(False)
        self.table.setColumnWidth(0, 120) 
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setRowCount(len(self.text_lines))

        for i, (ts, line) in enumerate(zip(self.timestamps, self.text_lines)):
            # Cella Timestamp (cliccabile per salvare il tempo)
            ts_item = QTableWidgetItem(f"{ts:.2f}") 
            ts_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable) 
            ts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(i, 0, ts_item)

            # Cella Testo (modificabile)
            line_item = QTableWidgetItem(line)
            line_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, line_item)

        self.table.cellClicked.connect(self.handle_cell_clicked)
        self.table.itemChanged.connect(self.handle_item_changed)

        main_layout.addWidget(self.table, 3)

        # CONTROLLI AUDIO
        controls_layout = QVBoxLayout()
        self.btn_play = QPushButton("Play ▶️")
        self.btn_pause = QPushButton("Pausa ⏸️")
        self.btn_stop = QPushButton("Stop ⏹️")
        self.btn_save = QPushButton("Salva e Chiudi ✅")

        self.btn_play.clicked.connect(self.play_audio)
        self.btn_pause.clicked.connect(self.pause_audio)
        self.btn_stop.clicked.connect(self.stop_audio)
        self.btn_save.clicked.connect(self.save_and_close)

        controls_layout.addWidget(self.btn_play)
        controls_layout.addWidget(self.btn_pause)
        controls_layout.addWidget(self.btn_stop)
        controls_layout.addStretch()
        controls_layout.addWidget(self.btn_save)
        main_layout.addLayout(controls_layout)

    # -------------------------------------------------------------
    # AUDIO PLAYBACK (Interno, per Editing)
    # -------------------------------------------------------------
    def load_audio(self, path):
        """Carica i dati audio del file per la riproduzione locale."""
        try:
            data, sr = sf.read(path, always_2d=True)
            self.audio_data = data
            self.samplerate = sr
            self.audio_pos = 0
        except Exception:
            # Fallback a dati silenziosi se il file non è trovato o è corrotto
            self.audio_data = np.zeros((44100*10, 1)) if np else None
            self.samplerate = 44100
            
    def audio_callback(self, outdata, frames, time_info, status):
        """Funzione di callback per sounddevice."""
        if self.audio_data is None: return

        if self.audio_pos + frames > len(self.audio_data):
            remaining = len(self.audio_data) - self.audio_pos
            if remaining > 0:
                outdata[:remaining] = self.audio_data[self.audio_pos:]
            outdata[remaining:] = 0
            self.audio_pos = len(self.audio_data)
            self.playing = False
        else:
            outdata[:] = self.audio_data[self.audio_pos:self.audio_pos + frames]
            self.audio_pos += frames

    def _play_thread(self):
        """Thread separato per la riproduzione sounddevice."""
        try:
            with sd.OutputStream(
                samplerate=self.samplerate,
                channels=self.audio_data.shape[1],
                callback=self.audio_callback
            ):
                while self.playing:
                    sd.sleep(30)
        except Exception as e:
            print(f"Errore nel thread audio: {e}")
        
        self.playing = False
        self.pause_time = 0.0
        self.active_row = -1
        self.update_playback()


    def get_current_time(self) -> float:
        """Restituisce il tempo di riproduzione corrente in secondi."""
        if self.playing:
            return time.time() - self.start_time
        elif self.pause_time > 0.0:
            return self.pause_time
        return 0.0

    def play_audio(self):
        """Avvia o riprende l'audio, con priorità al timestamp della riga selezionata."""
        if self.playing: return
        if self.audio_data is None or self.audio_data.size == 0:
            print("Nessun dato audio caricato.")
            return

        current_row = self.table.currentRow()
        start_ts = 0.0
        
        # 1. Priorità 1: Salta alla riga selezionata (se ha un timestamp valido > 0)
        if current_row >= 0 and current_row < len(self.timestamps):
            ts = self.timestamps[current_row]
            if ts > 0.0:
                start_ts = ts
                # print(f"Riproduzione dalla riga selezionata a {ts:.2f}s.")
        
        # 2. Priorità 2: Riprendi da Pausa
        elif self.pause_time > 0.0:
            start_ts = self.pause_time
            # print(f"Riproduzione ripresa da Pausa a {start_ts:.2f}s.")
        
        self.playing = True
        
        # Calcola la posizione audio in frames
        self.audio_pos = int(start_ts * self.samplerate)
        
        # Aggiorna il tempo di inizio per il tracking
        self.start_time = time.time() - start_ts
        self.pause_time = 0.0
        
        threading.Thread(target=self._play_thread, daemon=True).start()

    def pause_audio(self):
        """Mette in pausa l'audio e registra il tempo."""
        if self.playing:
            self.playing = False
            self.pause_time = time.time() - self.start_time
            # print(f"Pausa a {self.pause_time:.2f}s.")

    def stop_audio(self):
        """Ferma l'audio e resetta la posizione."""
        self.playing = False
        self.pause_time = 0.0
        self.audio_pos = 0
        self.active_row = -1 
        self.update_playback() 

    # -------------------------------------------------------------
    # LOGICA LYRICS E TIMESTAMP
    # -------------------------------------------------------------
    
    def handle_cell_clicked(self, row, column):
        """Salva il timestamp corrente nella cella della tabella al click."""
        if column == 0:
            current_time = self.get_current_time()
            
            if not self.playing and current_time < 0.01:
                print("Premi Play prima di registrare un timestamp.")
                return
            
            new_ts = round(current_time, 2) 
            
            if row < len(self.timestamps):
                self.timestamps[row] = new_ts
            else:
                return

            ts_item = self.table.item(row, 0)
            
            # Crea l'oggetto QTableWidgetItem se non esiste (necessario per robustezza)
            if ts_item is None:
                ts_item = QTableWidgetItem()
                ts_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
                ts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, 0, ts_item)
            
            # Scrittura del timestamp nella casella
            ts_item.setText(f"{new_ts:.2f}") 
            
            self.active_row = self.find_active_row(current_time)
            self.update_row_color(row)
            
            self.table.viewport().update() 


    def handle_item_changed(self, item: QTableWidgetItem):
        """Gestisce la modifica del testo e l'aggiunta di nuove righe con Invio."""
        if item.column() != 1: return
        row = item.row()
        text = item.text()

        if row < len(self.text_lines):
            self.text_lines[row] = text
        else:
            self.text_lines.append(text)
            self.timestamps.append(0.0)

        # Gestione Multi-linea (Invio)
        if "\n" in text:
            lines = text.split("\n")
            self.table.blockSignals(True)
            
            current_item = self.table.item(row, 1)
            if current_item:
                current_item.setText(lines[0])
            self.text_lines[row] = lines[0]

            for l in lines[1:]:
                new_row = self.table.rowCount()
                self.table.insertRow(new_row)
                
                ts_item = QTableWidgetItem("0.00") 
                ts_item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable) 
                ts_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(new_row, 0, ts_item)

                line_item = QTableWidgetItem(l)
                line_item.setFlags(Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(new_row, 1, line_item)

                self.text_lines.append(l)
                self.timestamps.append(0.0)
            self.table.blockSignals(False)
        
    # -------------------------------------------------------------
    # COLORAZIONE E AGGIORNAMENTO
    # -------------------------------------------------------------

    def find_active_row(self, current_time: float) -> int:
        """Trova l'indice della riga attiva in base al tempo corrente."""
        if not self.playing or current_time < 0.04: return -1
        
        valid_timestamps = sorted([(ts, i) for i, ts in enumerate(self.timestamps) if ts > 0.0], key=lambda x: x[0])
        
        active_index = -1
        for ts, index in valid_timestamps:
            if ts <= current_time:
                active_index = index
            else:
                break 
                
        return active_index

    def update_row_color(self, row):
        """Aggiorna il colore della riga (verde se attiva, bianco altrimenti)."""
        line_item = self.table.item(row, 1)
        ts_item = self.table.item(row, 0)
        
        if line_item and ts_item:
            is_active = (row == self.active_row and self.timestamps[row] > 0.0)
            
            bg_color = QColor(220, 255, 220) if is_active else QColor("white")
            txt_color = QColor("green") if is_active else QColor("black")
            
            line_item.setBackground(QBrush(bg_color))
            line_item.setForeground(QBrush(txt_color))
            
            ts_item.setBackground(QBrush(bg_color))
            ts_item.setForeground(QBrush(QColor("black")))

    def update_playback(self):
        """Aggiorna la riga attiva e la colorazione tramite timer."""
        if not self.playing and self.active_row == -1: return
            
        current_time = self.get_current_time()
        new_active_row = self.find_active_row(current_time)
        
        if new_active_row != self.active_row:
            if self.active_row != -1: self.update_row_color(self.active_row)
                
            self.active_row = new_active_row
            
            if self.active_row != -1:
                self.update_row_color(self.active_row)
                # Scorri la tabella sulla riga attiva
                self.table.scrollToItem(self.table.item(self.active_row, 1), 
                                        QTableWidget.ScrollHint.EnsureVisible)

    def save_and_close(self):
        """Formattazione e chiusura del dialogo."""
        lyrics_result = []
        for row in range(self.table.rowCount()):
            ts = self.timestamps[row] 
            line = self.table.item(row, 1).text()
            lyrics_result.append({"line": line, "time": ts})

        self.final_result = lyrics_result
        self.accept()