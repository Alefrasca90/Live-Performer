from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QApplication,
    QColorDialog, QSpinBox, QDoubleSpinBox, QCheckBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QScreen, QColor 

import sounddevice as sd
import numpy as np
import mido


class SettingsDialog(QDialog):
    """
    Finestra di dialogo per configurare le impostazioni persistenti di Audio, MIDI e Display.
    """
    def __init__(self, audio_engine, midi_engine, settings_manager):
        super().__init__()
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.settings = settings_manager
        
        self.available_screens = QApplication.screens()

        self.setWindowTitle("Impostazioni Audio / MIDI / Display")
        self.setMinimumWidth(600)

        layout = QVBoxLayout()
        self.setLayout(layout)

        # ----------------------------
        # AUDIO & MIDI DRIVER
        # ----------------------------
        layout.addWidget(QLabel("--- IMPOSTAZIONI AUDIO / MIDI ---"))
        self._setup_audio_midi_controls(layout)


        # ----------------------------
        # DISPLAY / VIDEO SETTINGS
        # ----------------------------
        layout.addSpacing(20)
        layout.addWidget(QLabel("--- IMPOSTAZIONI DISPLAY (Schermi) ---"))
        self._setup_display_controls(layout)
        
        # ----------------------------
        # LYRICS PROMPTER SETTINGS
        # ----------------------------
        layout.addSpacing(20)
        layout.addWidget(QLabel("--- IMPOSTAZIONI LYRICS PROMPTER ---"))
        self._setup_lyrics_controls(layout)


        # ----------------------------
        # Pulsanti
        # ----------------------------
        layout.addSpacing(10)
        btns = QHBoxLayout()
        btn_ok = QPushButton("Salva")
        btn_ok.clicked.connect(self.apply)
        btn_cancel = QPushButton("Annulla")
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_ok)
        btns.addWidget(btn_cancel)

        layout.addLayout(btns)

        # Carica impostazioni salvate
        self.load_saved_settings()
        
    def _setup_audio_midi_controls(self, layout):
        # Audio Driver
        layout.addWidget(QLabel("Driver Audio (Host API):"))
        self.combo_audio_driver = QComboBox()
        self.combo_audio_driver.addItem("Default")
        self.hostapis = sd.query_hostapis()
        for i, h in enumerate(self.hostapis):
            self.combo_audio_driver.addItem(f"{i} - {h['name']}")
        layout.addWidget(self.combo_audio_driver)

        # Test Audio
        btn_test_audio = QPushButton("Test Audio Output")
        btn_test_audio.clicked.connect(self.test_audio)
        layout.addWidget(btn_test_audio)

        # MIDI Port (Tracks/Default)
        layout.addWidget(QLabel("Porte MIDI (Tracce/Default):"))
        self.combo_midi = QComboBox()
        for p in self.midi_engine.outputs:
            self.combo_midi.addItem(p)
        layout.addWidget(self.combo_midi)

        # Test MIDI
        btn_test_midi = QPushButton("Test MIDI (Nota 60)")
        btn_test_midi.clicked.connect(self.test_midi)
        layout.addWidget(btn_test_midi)
        
        # --- MIDI CLOCK (NUOVO - SENZA BPM GLOBALE) ---
        layout.addSpacing(15)
        layout.addWidget(QLabel("--- CONTROLLI MIDI CLOCK (SYNC) ---"))
        
        # 1. Abilita Clock
        self.chk_midi_clock_enabled = QCheckBox("Abilita invio MIDI Clock (Sync)")
        layout.addWidget(self.chk_midi_clock_enabled)
        
        # 2. Porta Clock
        clock_port_layout = QHBoxLayout()
        clock_port_layout.addWidget(QLabel("Porta MIDI Clock (Sync):"))
        self.combo_midi_clock = QComboBox()
        # Aggiungi tutte le porte disponibili
        for p in self.midi_engine.outputs: 
            self.combo_midi_clock.addItem(p)
        clock_port_layout.addWidget(self.combo_midi_clock)
        layout.addLayout(clock_port_layout)


    def _setup_display_controls(self, layout):
        
        def create_screen_combo(setting_label):
            """Crea una QComboBox popolata con gli schermi disponibili."""
            combo = QComboBox()
            if not self.available_screens:
                combo.addItem("Nessun schermo rilevato")
                combo.setEnabled(False)
                return combo

            for i, screen in enumerate(self.available_screens):
                name = f"Schermo {i+1} ({screen.availableGeometry().width()}x{screen.availableGeometry().height()})"
                # Memorizza il nome del QScreen come item data
                combo.addItem(name, screen.name()) 
            return combo

        # 1. Main Window Screen
        layout.addWidget(QLabel("Schermo per la Finestra Principale:"))
        self.combo_main_screen = create_screen_combo("main_window_screen")
        layout.addWidget(self.combo_main_screen)

        # 2. Video Playback Screen
        layout.addWidget(QLabel("Schermo per Riproduzione Video:"))
        self.combo_video_screen = create_screen_combo("video_playback_screen")
        layout.addWidget(self.combo_video_screen)
        
        # 3. Lyrics Prompter Screen
        layout.addWidget(QLabel("Schermo per il Teleprompter Lyrics:"))
        self.combo_lyrics_screen = create_screen_combo("lyrics_prompter_screen")
        layout.addWidget(self.combo_lyrics_screen)
        
    def _setup_lyrics_controls(self, layout):
        # 1. Background Color
        bg_layout = QHBoxLayout()
        self.btn_bg_color = QPushButton("Seleziona Colore Sfondo")
        self.label_bg_color = QLabel("#000000")
        self.label_bg_color.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_bg_color.setStyleSheet(f"background-color: #000000; color: #FFFFFF; padding: 5px; border: 1px solid gray;")
        self.btn_bg_color.clicked.connect(lambda: self._choose_color("lyrics_bg_color", self.label_bg_color, is_bg=True))
        bg_layout.addWidget(self.btn_bg_color)
        bg_layout.addWidget(self.label_bg_color)
        bg_layout.addStretch()
        layout.addLayout(bg_layout)

        # 2. Font Color (Previous/Next Lines)
        font_layout = QHBoxLayout()
        self.btn_font_color = QPushButton("Seleziona Colore Testo (Non Attivo)")
        self.label_font_color = QLabel("#FFFFFF")
        self.label_font_color.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_font_color.setStyleSheet(f"color: #FFFFFF; padding: 5px; border: 1px solid gray;")
        self.btn_font_color.clicked.connect(lambda: self._choose_color("lyrics_font_color", self.label_font_color, is_text_color=True))
        font_layout.addWidget(self.btn_font_color)
        font_layout.addWidget(self.label_font_color)
        font_layout.addStretch()
        layout.addLayout(font_layout)
        
        # 3. Highlight Color (Active Line)
        highlight_layout = QHBoxLayout()
        self.btn_highlight_color = QPushButton("Seleziona Colore Evidenziato (Attivo)")
        self.label_highlight_color = QLabel("#00FF00")
        self.label_highlight_color.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_highlight_color.setStyleSheet(f"color: #00FF00; padding: 5px; border: 1px solid gray;")
        self.btn_highlight_color.clicked.connect(lambda: self._choose_color("lyrics_highlight_color", self.label_highlight_color, is_text_color=True))
        highlight_layout.addWidget(self.btn_highlight_color)
        highlight_layout.addWidget(self.label_highlight_color)
        highlight_layout.addStretch()
        layout.addLayout(highlight_layout)

        
        # 6. Read Ahead Time (Tempo di Anticipo)
        ahead_layout = QHBoxLayout()
        ahead_layout.addWidget(QLabel("Anticipo Visualizzazione Lyrics:"))
        self.spin_read_ahead = QDoubleSpinBox()
        self.spin_read_ahead.setRange(0.0, 5.0) # 0.0 a 5.0 secondi
        self.spin_read_ahead.setSingleStep(0.1)
        self.spin_read_ahead.setDecimals(2)
        ahead_layout.addWidget(self.spin_read_ahead)
        ahead_layout.addWidget(QLabel("s"))
        ahead_layout.addStretch()
        layout.addLayout(ahead_layout)
        
        # --- NUOVE IMPOSTAZIONI ---
        layout.addSpacing(10)

        # 7. Scrolling Mode (Nuova CheckBox)
        scroll_layout = QHBoxLayout()
        self.chk_scrolling_mode = QCheckBox("Modalità Scorrimento Karaoke (Testo Continuo)")
        scroll_layout.addWidget(self.chk_scrolling_mode)
        scroll_layout.addStretch()
        layout.addLayout(scroll_layout)
        
    def _choose_color(self, key, label, is_bg=False, is_text_color=False):
        """Abre il dialogo per la scelta del colore e aggiorna l'etichetta."""
        initial_color = QColor(self.settings.data.get(key, "#000000"))
        color = QColorDialog.getColor(initial_color, self, "Scegli Colore")
        
        if color.isValid():
            hex_color = color.name().upper()
            
            # Aggiorna l'anteprima
            label.setText(hex_color)
            if is_bg:
                # Per lo sfondo, aggiorna anche il colore del testo per leggibilità
                text_color = "#000000" if QColor(hex_color).lightness() > 128 else "#FFFFFF"
                label.setStyleSheet(f"background-color: {hex_color}; color: {text_color}; padding: 5px; border: 1px solid gray;")
            elif is_text_color:
                label.setStyleSheet(f"color: {hex_color}; padding: 5px; border: 1px solid gray;")
            else:
                 label.setStyleSheet(f"background-color: transparent; color: {hex_color}; padding: 5px; border: 1px solid gray;")
            
            # Salva temporaneamente l'impostazione (sarà salvata in modo permanente in apply)
            self.settings.data[key] = hex_color


    # -------------------------------------------------------------
    # LOAD SAVED SETTINGS
    # -------------------------------------------------------------
    def load_saved_settings(self):
        """Carica le impostazioni audio, MIDI, schermo e lyrics salvate."""
        # --- AUDIO ---
        driver = self.settings.data.get("audio_driver", None)
        if driver is None:
            self.combo_audio_driver.setCurrentIndex(0)
        else:
            for i in range(self.combo_audio_driver.count()):
                if self.combo_audio_driver.itemText(i).startswith(f"{driver} - "):
                    self.combo_audio_driver.setCurrentIndex(i)
                    break

        # --- MIDI (Tracks/Default) ---
        saved_port = self.settings.data.get("midi_port", None)
        if saved_port:
            idx = self.combo_midi.findText(saved_port)
            if idx >= 0:
                self.combo_midi.setCurrentIndex(idx)

        # --- MIDI CLOCK (NUOVO - SENZA BPM GLOBALE) ---
        clock_enabled = self.settings.data.get("midi_clock_enabled", False)
        self.chk_midi_clock_enabled.setChecked(clock_enabled)
        
        clock_port = self.settings.data.get("midi_clock_port", None)
        if clock_port:
            idx_clock = self.combo_midi_clock.findText(clock_port)
            if idx_clock >= 0:
                self.combo_midi_clock.setCurrentIndex(idx_clock)

        # --- SCREENS ---
        self._load_screen_setting(self.combo_main_screen, "main_window_screen")
        self._load_screen_setting(self.combo_video_screen, "video_playback_screen")
        self._load_screen_setting(self.combo_lyrics_screen, "lyrics_prompter_screen")

        # --- LYRICS PROMPTER ---
        # 1. Background Color
        bg_color = self.settings.data.get("lyrics_bg_color", "#000000")
        text_color_for_bg = "#000000" if QColor(bg_color).lightness() > 128 else "#FFFFFF"
        self.label_bg_color.setText(bg_color)
        self.label_bg_color.setStyleSheet(f"background-color: {bg_color}; color: {text_color_for_bg}; padding: 5px; border: 1px solid gray;")
        
        # 2. Font Color
        font_color = self.settings.data.get("lyrics_font_color", "#FFFFFF")
        self.label_font_color.setText(font_color)
        self.label_font_color.setStyleSheet(f"color: {font_color}; padding: 5px; border: 1px solid gray;")
        
        # 3. Highlight Color
        highlight_color = self.settings.data.get("lyrics_highlight_color", "#00FF00")
        self.label_highlight_color.setText(highlight_color)
        self.label_highlight_color.setStyleSheet(f"color: {highlight_color}; padding: 5px; border: 1px solid gray;")
        
        
        # 6. Read Ahead Time
        read_ahead = self.settings.data.get("lyrics_read_ahead_time", 1.0)
        self.spin_read_ahead.setValue(read_ahead)
        
        # 7. Scrolling Mode (NUOVO)
        scrolling_mode = self.settings.data.get("lyrics_scrolling_mode", True)
        self.chk_scrolling_mode.setChecked(scrolling_mode)


    def _load_screen_setting(self, combo: QComboBox, key: str):
        """Helper per caricare un'impostazione di schermo salvata (tramite QScreen name)."""
        if not self.available_screens:
            return
        
        saved_screen_name = self.settings.data.get(key, None)
        if saved_screen_name:
            # Trova l'indice nel combo box che corrisponde al nome salvato
            for i in range(combo.count()):
                item_data_name = combo.itemData(i)
                if item_data_name == saved_screen_name:
                    combo.setCurrentIndex(i)
                    return
            
            # Se lo schermo salvato non è disponibile, usa il default (indice 0)


    # -------------------------------------------------------------
    # TEST E APPLY
    # -------------------------------------------------------------
    def test_audio(self):
        """Tenta di riprodurre un tono per testare l'output audio."""
        try:
            fs = 44100
            duration = 0.3
            t = np.linspace(0, duration, int(fs * duration), False)
            tone = 0.2 * np.sin(440 * 2 * np.pi * t)

            sd.play(tone, fs)
            sd.wait()

            QMessageBox.information(self, "Test Audio", "Audio OK!")
        except Exception as e:
            QMessageBox.critical(self, "Errore Audio", str(e))

    def test_midi(self):
        """Tenta di inviare un messaggio MIDI per testare la porta."""
        try:
            port_name = self.combo_midi.currentText()
            with mido.open_output(port_name) as p:
                p.send(mido.Message("note_on", note=60, velocity=100, channel=0))
                p.send(mido.Message("note_off", note=60, velocity=100, channel=0))

            QMessageBox.information(self, "Test MIDI", "MIDI OK!")
        except Exception as e:
            QMessageBox.critical(self, "Errore MIDI", str(e))

    def apply(self):
        """Salva tutte le impostazioni e le applica ai motori."""
        # 1. AUDIO DRIVER
        selected_audio = self.combo_audio_driver.currentText()
        if selected_audio == "Default":
            self.audio_engine.set_driver(None)
            self.settings.set_audio_driver(None)
        else:
            driver_index = int(selected_audio.split(" - ")[0])
            self.audio_engine.set_driver(driver_index)
            self.settings.set_audio_driver(driver_index)


        # 2. MIDI PORT (Tracks/Default)
        if self.combo_midi.count() > 0:
            port = self.combo_midi.currentText()
            self.midi_engine.default_port = port
            self.settings.set_midi_port(port)
            
        # 3. MIDI CLOCK (NUOVO - SENZA BPM GLOBALE)
        midi_clock_enabled = self.chk_midi_clock_enabled.isChecked()
        
        self.settings.set_midi_clock_enabled(midi_clock_enabled)
        
        # Salva la porta solo se il clock è abilitato
        if midi_clock_enabled and self.combo_midi_clock.count() > 0:
            clock_port = self.combo_midi_clock.currentText()
            self.settings.set_midi_clock_port(clock_port)
            self.midi_engine.midi_clock_port = clock_port # Aggiorna l'engine porta
        else:
            self.settings.set_midi_clock_port(None)
            self.midi_engine.midi_clock_port = None


        # 4. DISPLAY / SCREENS
        self._save_screen_setting(self.combo_main_screen, "main_window_screen")
        self._save_screen_setting(self.combo_video_screen, "video_playback_screen")
        self._save_screen_setting(self.combo_lyrics_screen, "lyrics_prompter_screen")
        
        # 5. LYRICS PROMPTER SETTINGS
        self.settings.set_lyrics_bg_color(self.settings.data["lyrics_bg_color"])
        self.settings.set_lyrics_font_color(self.settings.data["lyrics_font_color"])
        self.settings.set_lyrics_highlight_color(self.settings.data["lyrics_highlight_color"])
        
        self.settings.set_lyrics_read_ahead_time(self.spin_read_ahead.value())

        # NUOVE IMPOSTAZIONI
        self.settings.set_lyrics_scrolling_mode(self.chk_scrolling_mode.isChecked())

        self.accept()
        
    def _save_screen_setting(self, combo: QComboBox, key: str):
        """Helper per salvare l'impostazione dello schermo (nome del QScreen)."""
        if combo.count() > 0 and combo.isEnabled():
            screen_name = combo.itemData(combo.currentIndex()) 
            self.settings.set_screen_setting(key, screen_name)
        else:
            self.settings.set_screen_setting(key, None)