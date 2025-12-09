import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QPushButton, QSizePolicy, QSlider, QComboBox, QDialog
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve 
from PyQt6.QtGui import QFont, QScreen, QRegion, QFontMetrics
from math import floor
import time

class LyricsPlayerWidget(QWidget): 
    """
    Widget che visualizza i lyrics sincronizzati (incorporabile in un tab).
    Include la barra di trasporto e i controlli per la proiezione esterna.
    """
    # Nuove costanti per il ridimensionamento automatico
    TARGET_CHARS = 60
    FIXED_SPACING = 0
    MIN_VISIBLE_LINES = 3
    BASE_HEIGHT_FACTOR = 2.0
    
    def __init__(self, audio_engine, midi_engine, settings_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lyrics Prompter") 
        
        self.resize(200, 200) 
        self.setMinimumSize(200, 200) 
        
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.settings = settings_manager 
        self.lyrics_data = [] 
        
        self.active_line_index = -1
        self.is_fullscreen = False 
        self.is_slider_pressed = False
        
        settings_data = self.settings.data
        self.read_ahead_time = settings_data.get("lyrics_read_ahead_time", 1.0)
        self.scrolling_mode = settings_data.get("lyrics_scrolling_mode", True)
        
        self.visible_lines = self.MIN_VISIBLE_LINES 
        self.center_line_index = (self.visible_lines - 1) // 2
        self.font_base_size = 48 
        
        self.lyric_labels: list[QLabel] = []
        self.font_scale = 0.5 
        self.current_line_label = None 
        
        self.lyrics_viewport: QWidget | None = None
        self.lyrics_wrapper: QWidget | None = None
        self.lyrics_layout: QVBoxLayout | None = None
        self.pixel_per_line: float = 0.0
        self.target_offset_y: int = 0
        self.animation: QPropertyAnimation | None = None
        
        # Controlli esterni per la proiezione
        self.external_window: QDialog | None = None 
        self.external_content_widget: QWidget | None = None
        self.available_screens = QApplication.screens()

        self.init_ui()
        self.setup_timer()
        
        self._update_screen_combo()
        self.update_playback_buttons()
        
    def _format_time(self, seconds):
        """Formatta i secondi in stringa MM:SS."""
        if seconds is None or seconds < 0: return "00:00"
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    # --- UI SETUP ---

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        
        # 1. Title Label
        self.title_label = QLabel("Nessun Brano in Riproduzione")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet("font-size: 16px; font-weight: bold; color: #00FF00;")
        main_layout.addWidget(self.title_label)
        main_layout.addSpacing(10)

        # 2. Controls Toolbar (Horizontal, inherits app theme)
        self._setup_controls(main_layout)
        
        # 3. Lyrics Display Container (Receives dynamic color)
        self.display_container = QWidget()
        display_layout = QVBoxLayout(self.display_container)
        display_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.display_container, 1) 
        
        # 4. Lyrics Area (Viewport + Wrapper inside display_container)
        self._setup_lyrics_display_area(display_layout)
        # Re-assign self.lyrics_viewport to the viewport widget itself
        # (Needed to correctly calculate dimensions in resizeEvent)
        self.lyrics_viewport = self.display_container.findChild(QWidget, "LyricsViewport")
        
    def _setup_controls(self, main_layout):
        """Setup della barra di trasporto e dei controlli display (pulsanti, slider, schermo)."""
        
        # Main horizontal layout for transport/screen selection
        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(5, 0, 5, 5)

        # 1. Buttons (Left)
        self.btn_play = QPushButton("▶️ Play")
        self.btn_stop = QPushButton("⏹️ Stop")
        self.btn_play.clicked.connect(self._toggle_play_pause)
        self.btn_stop.clicked.connect(self._stop_playback)
        
        button_group = QHBoxLayout()
        button_group.addWidget(self.btn_play)
        button_group.addWidget(self.btn_stop)
        
        toolbar_layout.addLayout(button_group) 
        
        # 2. Time Label (Fixed width)
        self.time_label = QLabel("00:00 / 00:00")
        self.time_label.setFixedWidth(80) 
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toolbar_layout.addWidget(self.time_label)

        # 3. Slider (Half Screen Width - Stretch Factor 2)
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderMoved.connect(self._on_slider_moved)
        self.progress_slider.sliderPressed.connect(lambda: setattr(self, 'is_slider_pressed', True))
        self.progress_slider.sliderReleased.connect(self._on_slider_release)
        self.progress_slider.setEnabled(False) 
        
        toolbar_layout.addWidget(self.progress_slider, 2) # Stretch factor 2 (approx half width)
        
        # 4. Screen Selection (Right - Stretch Factor 1)
        screen_label = QLabel("Proietta su:")
        screen_label.setFixedWidth(70) 
        toolbar_layout.addWidget(screen_label)
        
        self.combo_screen = QComboBox()
        self.combo_screen.currentIndexChanged.connect(self._handle_screen_change)
        toolbar_layout.addWidget(self.combo_screen, 1) # Stretch factor 1
        
        main_layout.addLayout(toolbar_layout)

    def _setup_lyrics_display_area(self, display_layout: QVBoxLayout):
        """Setup dell'area di visualizzazione dei lyrics (Viewport + Wrapper) all'interno di un layout fornito."""
        
        # 1. Viewport (Area visibile che esegue il clipping del contenuto)
        lyrics_viewport = QWidget() 
        lyrics_viewport.setObjectName("LyricsViewport")
        lyrics_viewport.setContentsMargins(0, 0, 0, 0)
        
        display_layout.addWidget(lyrics_viewport, 1) 
        
        # 2. Wrapper (Il contenuto che scorre) - Parented al viewport
        self.lyrics_wrapper = QWidget(lyrics_viewport) 
        self.lyrics_wrapper.setObjectName("LyricsWrapper")

        # 3. Layout dentro il wrapper
        self.lyrics_layout = QVBoxLayout(self.lyrics_wrapper) 
        self.lyrics_layout.setContentsMargins(0, 0, 0, 0)

        for i in range(self.MIN_VISIBLE_LINES): 
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            self.lyrics_layout.addWidget(label)
            self.lyric_labels.append(label)
            
        if self.lyric_labels:
             self.current_line_label = self.lyric_labels[(self.MIN_VISIBLE_LINES - 1) // 2]
             self.current_line_label.setText("Premi Play sulla tab Media per avviare la riproduzione.")

        # Configura l'animazione
        self.animation = QPropertyAnimation(self.lyrics_wrapper, b'pos')
        self.animation.setDuration(400) 
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad) 

    # --- EXTERNAL PROJECTION LOGIC ---

    def _update_screen_combo(self):
        """Popola la QComboBox con gli schermi disponibili."""
        self.combo_screen.clear()
        self.available_screens = QApplication.screens()
        
        # Option 0: No projection
        self.combo_screen.addItem("Non proiettare (Solo Tab)")
        
        for i, screen in enumerate(self.available_screens):
            name = f"Schermo {i+1} ({screen.availableGeometry().width()}x{screen.availableGeometry().height()})"
            # Store the screen name as item data
            self.combo_screen.addItem(name, screen.name()) 

        # Tentativo di caricare l'ultima impostazione salvata
        saved_screen_name = self.settings.data.get("lyrics_prompter_screen", None)
        if saved_screen_name:
            idx = self.combo_screen.findData(saved_screen_name)
            if idx > 0: 
                 self.combo_screen.setCurrentIndex(idx)


    def _handle_screen_change(self, index):
        """Gestisce il cambio di selezione nello schermo e attiva/disattiva la proiezione."""
        screen_name = self.combo_screen.itemData(index)
        
        # 1. Salva l'impostazione
        if index == 0:
            self.settings.set_lyrics_prompter_screen(None)
        else:
            self.settings.set_lyrics_prompter_screen(screen_name)

        # 2. Attiva/disattiva la proiezione
        self._toggle_external_window(screen_name)

    def _toggle_external_window(self, target_screen_name: str | None):
        """Crea, sposta o chiude la finestra di proiezione esterna."""
        
        # Chiudi la finestra se il target è None (Non proiettare)
        if not target_screen_name:
            if self.external_window:
                self.external_window.close()
                self.external_window = None
            return

        # Trova lo schermo di destinazione
        target_screen = next((s for s in self.available_screens if s.name() == target_screen_name), None)
        if not target_screen: return

        # Crea/Aggiorna la finestra esterna
        if not self.external_window:
            self.external_window = QDialog()
            self.external_window.setWindowTitle(self.windowTitle() + " (Proiezione)")
            self.external_window.setWindowFlags(Qt.WindowType.Window | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            
            # Utilizza una replica semplice del layout interno
            external_layout = QVBoxLayout(self.external_window)
            external_layout.setContentsMargins(0, 0, 0, 0)
            
            # Il contenuto effettivo (label, wrapper) viene replicato tramite lo styling dinamico
            # L'area lyrics_viewport gestisce il disegno. Per la finestra esterna, replichiamo lo styling.
            
        # Sposta e imposta la modalità fullscreen
        screen_geometry = target_screen.geometry()
        self.external_window.move(screen_geometry.topLeft())
        self.external_window.resize(screen_geometry.size())
        self.external_window.showFullScreen()
        
        # Applica lo styling dinamico per il background (il font sarà gestito da reapply_side_font)
        bg_color = self.settings.data.get("lyrics_bg_color", "#000000")
        self.external_window.setStyleSheet(f"background-color: {bg_color};")


    # --- PLAYBACK & UI UPDATE LOGIC ---
    
    def _toggle_play_pause(self):
        """Gestisce lo stato Play/Pausa/Riprendi sull'AudioEngine condiviso."""
        current_song_name = self.audio_engine.playing_song
        is_playing = current_song_name and not self.audio_engine.is_stopped()
        is_currently_paused = self.audio_engine.pause_time > 0.0 and self.audio_engine.is_stopped()

        if is_playing:
            self.audio_engine.pause_playback(current_song_name)
            self.midi_engine.pause_playback(current_song_name)
        elif is_currently_paused:
            self.audio_engine.start_playback(current_song_name) 
            self.midi_engine.start_playback(current_song_name)
        
        self.update_playback_buttons()
        
    def _stop_playback(self):
        """Ferma la riproduzione sull'AudioEngine condiviso."""
        current_song_name = self.audio_engine.playing_song
        if current_song_name:
            self.audio_engine.stop_playback(current_song_name)
            self.midi_engine.stop_playback(current_song_name)
        
        self.update_playback_buttons()

    def _on_slider_release(self):
        """Esegue il seek al rilascio del cursore."""
        self.is_slider_pressed = False
        current_song_name = self.audio_engine.playing_song
        if not current_song_name: return

        duration = self.audio_engine.get_duration()
        if duration > 0:
            progress = self.progress_slider.value()
            target_time_s = (progress / 1000) * duration
            
            # Riavvia la riproduzione dal tempo di destinazione
            self.audio_engine.stop_playback(current_song_name)
            self.audio_engine.start_playback(current_song_name, start_time_s=target_time_s)
            self.midi_engine.start_playback(current_song_name) # Riavvia MIDI sync
            
            self.update_playback_buttons()

    def _on_slider_moved(self, value):
        """Aggiorna solo l'etichetta del tempo mentre si trascina lo slider."""
        current_song_name = self.audio_engine.playing_song
        if not current_song_name: return

        duration = self.audio_engine.get_duration()
        if duration > 0:
            target_time = (value / 1000) * duration
            time_str = self._format_time(target_time)
            duration_str = self._format_time(duration)
            self.time_label.setText(f"{time_str} / {duration_str}")

    def update_playback_buttons(self):
        """Aggiorna lo stato di attivazione e il testo dei pulsanti di controllo."""
        is_playing = self.audio_engine.playing_song is not None and not self.audio_engine.is_stopped()
        is_currently_paused = self.audio_engine.pause_time > 0.0 and self.audio_engine.is_stopped()
        has_song = self.audio_engine.playing_song is not None
        
        # Stato Play/Pause Toggle
        if is_playing:
            self.btn_play.setText("⏸️ Pausa")
        elif is_currently_paused:
            self.btn_play.setText("▶️ Riprendi")
        else:
            self.btn_play.setText("▶️ Play")
        
        self.btn_play.setEnabled(has_song or is_currently_paused)
        self.btn_stop.setEnabled(is_playing or is_currently_paused)
        self.progress_slider.setEnabled(has_song or is_currently_paused)


    def setup_timer(self):
        """Configura il timer per l'aggiornamento dei testi e della barra di trasporto."""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_lyrics_display)
        self.timer.timeout.connect(self._update_transport_state)
        self.timer.start(50)

    def _update_transport_state(self):
        """Aggiorna lo slider e l'etichetta del tempo in base ad AudioEngine."""
        current_song_name = self.audio_engine.playing_song
        is_playing_or_paused = current_song_name is not None and (not self.audio_engine.is_stopped() or self.audio_engine.pause_time > 0.0)

        if is_playing_or_paused:
            current_time = self.audio_engine.get_current_time()
            duration = self.audio_engine.get_duration()
            
            # Aggiorna il titolo
            self.title_label.setText(f"Lyrics: {current_song_name}")

            if duration > 0:
                progress = int((current_time / duration) * 1000)
                if not self.is_slider_pressed:
                     self.progress_slider.setValue(progress)

            time_str = self._format_time(current_time)
            duration_str = self._format_time(duration)
            self.time_label.setText(f"{time_str} / {duration_str}")
        else:
            self.title_label.setText("Nessun Brano in Riproduzione")
            
        self.update_playback_buttons()
        

    def update_lyrics_display(self):
        """Aggiorna le lyrics in base al tempo di riproduzione (Master Clock: AudioEngine)."""
        
        current_time_s = self.audio_engine.get_current_time() 
        duration = self.audio_engine.get_duration()
        
        if not self.lyrics_data:
             return
        
        # Logica di stop fine brano
        if current_time_s >= duration and duration > 0 and self.audio_engine.is_stopped():
             self.active_line_index = -1
             if self.lyrics_wrapper:
                 self.lyrics_wrapper.move(0, self.target_offset_y)
             if self.current_line_label:
                 self.current_line_label.setText("Riproduzione Terminata...")
             return
             
        if self.audio_engine.is_stopped() and current_time_s < 0.1:
             self.active_line_index = -1
             if self.lyrics_wrapper:
                 self.lyrics_wrapper.move(0, self.target_offset_y)
             if self.current_line_label:
                 self.current_line_label.setText("Riproduzione Ferma...")
             return
             
        sync_time_s = current_time_s + self.read_ahead_time 
             
        new_active_index = -1
        for i, entry in enumerate(self.lyrics_data):
            if entry['time'] <= sync_time_s + 0.05: 
                new_active_index = i
            else:
                break
        
        if new_active_index != self.active_line_index:
            self.active_line_index = new_active_index
            
            if self.scrolling_mode:
                 self.update_lyric_labels_continuous() 
                 self._start_scroll_animation(new_active_index) 
            else:
                 self.update_lyric_labels_fixed(new_active_index)

        # Sincronizza l'aspetto della finestra esterna
        if self.external_window and self.external_window.isVisible():
            # Forza l'aggiornamento visivo (redraw) della finestra esterna
            self.external_window.update() 
    
    def update_fixed_labels_count(self, target_count):
        """Aggiunge o rimuove i QLabel per adattarsi al numero di linee visibili (solo in Fixed Mode)."""
        current_count = len(self.lyric_labels)
        
        if target_count < current_count:
            for _ in range(current_count - target_count):
                label = self.lyric_labels.pop()
                self.lyrics_layout.removeWidget(label)
                label.deleteLater()
        
        elif target_count > current_count:
            for _ in range(target_count - current_count):
                label = QLabel()
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                label.setWordWrap(True)
                self.lyrics_layout.addWidget(label)
                self.lyric_labels.append(label)

        if self.lyric_labels:
             self.center_line_index = (target_count - 1) // 2
             self.current_line_label = self.lyric_labels[self.center_line_index]
        else:
             self.center_line_index = 0
             self.current_line_label = QLabel(self.lyrics_wrapper)

    def reload_ui_for_new_data(self, lyrics_count):
        """Prepara l'UI per il caricamento di nuovi dati."""
        
        if self.scrolling_mode:
            current_count = len(self.lyric_labels)
            
            if lyrics_count < current_count:
                for _ in range(current_count - lyrics_count):
                    label = self.lyric_labels.pop()
                    self.lyrics_layout.removeWidget(label)
                    label.deleteLater()
            
            elif lyrics_count > current_count:
                for _ in range(lyrics_count - current_count):
                    label = QLabel()
                    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    label.setWordWrap(True)
                    self.lyrics_layout.addWidget(label)
                    self.lyric_labels.append(label)

            if self.lyric_labels:
                 self.current_line_label = self.lyric_labels[0]
            else:
                 self.current_line_label = QLabel(self.lyrics_wrapper)

        elif not self.lyric_labels:
             self.update_fixed_labels_count(self.MIN_VISIBLE_LINES)
             

    def set_lyrics_data(self, lyrics_data: list[dict], song_name: str):
        """Aggiorna i dati dei lyrics e la UI, ricaricando i QLabel se necessario."""
        self.lyrics_data = sorted(lyrics_data, key=lambda x: x['time'])
        self.active_line_index = -1
        self.setWindowTitle(f"Lyrics Prompter - {song_name}")
        self.title_label.setText(f"Lyrics: {song_name}")
        
        self.reload_ui_for_new_data(len(self.lyrics_data)) 
        
        if not self.lyrics_data and self.lyric_labels:
             if len(self.lyric_labels) > self.center_line_index:
                 self.lyric_labels[self.center_line_index].setText(f"Nessun lyric sincronizzato: {song_name}")
        
        self.apply_settings()
        self.resize_and_reposition_wrapper(force=True)
        
        self.update_lyrics_display()

    def resizeEvent(self, event):
        """Ricalcola le dimensioni del viewport e del wrapper al ridimensionamento."""
        super().resizeEvent(event)
        if self.lyrics_viewport:
            self.lyrics_viewport.setMask(QRegion(self.lyrics_viewport.rect())) 
        self.resize_and_reposition_wrapper()
        
    def apply_settings(self):
        """Applica le impostazioni di styling e schermo dal SettingsManager."""
        
        settings = self.settings.data
        bg_color = settings.get("lyrics_bg_color", "#000000")
        font_color = settings.get("lyrics_font_color", "#FFFFFF")
        highlight_color = settings.get("lyrics_highlight_color", "#00FF00")
        self.read_ahead_time = settings.get("lyrics_read_ahead_time", 1.0)
        self.scrolling_mode = settings.get("lyrics_scrolling_mode", True)
        
        self.lyrics_layout.setSpacing(self.FIXED_SPACING) 
        
        # 1. APPLY STYLING ONLY TO THE DISPLAY CONTAINER
        if hasattr(self, 'display_container'):
             self.display_container.setStyleSheet(f"background-color: {bg_color};")
        
        reference_font = QFont("Arial", 12, QFont.Weight.Bold)
        if self.lyric_labels:
            self.lyric_labels[0].setFont(reference_font) 

        self._update_screen_combo()
        
        self.resize_and_reposition_wrapper(force=True)
        
        saved_screen_name = self.settings.data.get("lyrics_prompter_screen", None)
        self._toggle_external_window(saved_screen_name)
        
    def resize_and_reposition_wrapper(self, force=False):
        """
        Calcola dinamicamente la dimensione del font e il numero di linee visibili
        in base alle dimensioni della finestra.
        """
        if not self.lyrics_viewport or not self.lyric_labels:
            return

        window_width = self.lyrics_viewport.width()
        CHAR_ASPECT_RATIO = 0.6 
        
        if window_width > 0:
            calculated_font_size_width = int(window_width / (self.TARGET_CHARS * CHAR_ASPECT_RATIO))
            self.font_base_size = max(10, calculated_font_size_width) 
        else:
             self.font_base_size = 48 
             
        reference_font = QFont("Arial", self.font_base_size, QFont.Weight.Bold)
        
        reference_label = self.lyric_labels[0]
        reference_label.setFont(reference_font) 
        font_metrics = QFontMetrics(reference_font)

        label_base_height = font_metrics.height()
        label_min_height = int(label_base_height * self.BASE_HEIGHT_FACTOR)
        
        if label_min_height <= 0: return

        spacing = self.FIXED_SPACING
        self.pixel_per_line = label_min_height + spacing
        
        viewport_height = self.lyrics_viewport.height()
        
        if viewport_height > 0 and self.pixel_per_line > 0:
            calculated_visible_lines = floor((viewport_height + spacing) / self.pixel_per_line)
            
            if calculated_visible_lines % 2 == 0:
                calculated_visible_lines -= 1
                
            new_visible_lines = max(self.MIN_VISIBLE_LINES, calculated_visible_lines)
        else:
            new_visible_lines = self.MIN_VISIBLE_LINES

        if new_visible_lines != self.visible_lines:
             self.visible_lines = new_visible_lines
             self.center_line_index = (self.visible_lines - 1) // 2
             
             if not self.scrolling_mode:
                 self.update_fixed_labels_count(new_visible_lines)
        
        viewport_required_height = viewport_height

        self.lyrics_viewport.setMinimumHeight(viewport_required_height)
        self.lyrics_viewport.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
        if not self.scrolling_mode:
            total_height = int(self.visible_lines * self.pixel_per_line - spacing)
        else:
             total_height = int(len(self.lyric_labels) * self.pixel_per_line - spacing)
             
        self.lyrics_wrapper.resize(self.lyrics_viewport.width(), total_height)
        
        for i, label in enumerate(self.lyric_labels):
            label.setMinimumHeight(self.pixel_per_line - spacing)
            
            distance_from_center = abs(i - self.center_line_index)
            self.reapply_side_font(label, distance_from_center) 
        
        current_viewport_height = self.lyrics_viewport.height()
        
        self.target_offset_y = int(current_viewport_height / 2 - self.pixel_per_line / 2)
        
        if self.scrolling_mode:
            if self.active_line_index >= 0:
                target_y_scrolling = int(self.target_offset_y - (self.active_line_index * self.pixel_per_line))
                self.lyrics_wrapper.move(0, target_y_scrolling)
                self._start_scroll_animation(self.active_line_index, force=force)
            elif self.active_line_index < 0 or force:
                 self.lyrics_wrapper.move(0, self.target_offset_y)
        else:
            target_y_fixed = int((current_viewport_height / 2) - 
                                 (self.center_line_index * self.pixel_per_line + self.pixel_per_line / 2))
            self.lyrics_wrapper.move(0, target_y_fixed)


        self.lyrics_viewport.setMask(QRegion(self.lyrics_viewport.rect()))
        
    def _start_scroll_animation(self, target_line_index: int, force=False):
        """Avvia l'animazione di scorrimento verticale."""
        if not self.scrolling_mode or self.pixel_per_line == 0 or not self.animation:
            return

        target_y = int(self.target_offset_y - (target_line_index * self.pixel_per_line))

        current_y = self.lyrics_wrapper.pos().y()
        if abs(current_y - target_y) < 2 and not force:
             return

        self.animation.stop()
        self.animation.setStartValue(QPoint(0, current_y))
        self.animation.setEndValue(QPoint(0, target_y))
        
        distance = abs(current_y - target_y)
        duration = 400 * distance / self.pixel_per_line
        self.animation.setDuration(max(100, int(duration))) 
        
        self.animation.start()

    def update_lyric_labels_continuous(self):
        """Aggiorna i testi dei label e gli stili in modalità scorrimento continuo."""
        
        lyrics_count = len(self.lyrics_data)
        
        for i, label in enumerate(self.lyric_labels):
            if i < lyrics_count:
                text = self.lyrics_data[i]["line"]
            else:
                text = ""

            label.setText(text)
            
            self.reapply_side_font(label, abs(i - self.active_line_index))

    def update_lyric_labels_fixed(self, active_index: int):
        """Aggiorna solo la riga centrale e le sue adiacenti (modalità fissa)."""
        
        lyrics_count = len(self.lyrics_data)
        
        start_data_index = active_index - self.center_line_index
        
        for i, label in enumerate(self.lyric_labels):
            data_index = start_data_index + i
            
            if 0 <= data_index < lyrics_count:
                 text = self.lyrics_data[data_index]["line"]
            else:
                 text = ""
                 
            label.setText(text)
            
            self.reapply_side_font(label, abs(i - self.center_line_index))

    def reapply_side_font(self, label: QLabel, distance_from_center: int):
         """
         Re-applica il font scalato per le righe laterali e lo stile.
         """
         
         settings = self.settings.data
         font_color = settings.get("lyrics_font_color", "#FFFFFF")
         highlight_color = settings.get("lyrics_highlight_color", "#00FF00")
         
         if distance_from_center == 0:
             side_font_size = self.font_base_size
             label.setStyleSheet(f"color: {highlight_color};")
         else:
             side_line_count = (self.visible_lines - 1) // 2 
             
             scale_factor = 1.0 - (distance_from_center / (side_line_count + 1)) * (1.0 - self.font_scale)
             
             side_font_size = int(self.font_base_size * scale_factor)
             
             if self.scrolling_mode and distance_from_center >= side_line_count:
                 side_font_size = int(self.font_base_size * 0.4)
             
             label.setStyleSheet(f"color: {font_color};")
             
         side_font = QFont("Arial", side_font_size, QFont.Weight.Bold if distance_from_center == 0 else QFont.Weight.Normal)
         label.setFont(side_font)

    def closeEvent(self, event):
        """Gestione della chiusura. Chiude la finestra esterna se è aperta."""
        if self.timer.isActive():
            self.timer.stop()
        
        if self.external_window:
             self.external_window.close()

        super().closeEvent(event)