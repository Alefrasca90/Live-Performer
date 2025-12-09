import sys
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QApplication, QPushButton, QSizePolicy
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QPoint, QEasingCurve 
from PyQt6.QtGui import QFont, QScreen, QRegion, QFontMetrics
from math import floor
import time

class LyricsPlayerWidget(QWidget): # Rinominated and inheritance changed
    """
    Widget che visualizza i lyrics sincronizzati (incorporabile in un tab).
    """
    # Nuove costanti per il ridimensionamento automatico
    TARGET_CHARS = 60 # Numero di caratteri orizzontali di riferimento
    FIXED_SPACING = 0 # Spaziatura verticale fissa tra le linee (in pixel)
    MIN_VISIBLE_LINES = 3 # Numero minimo di linee visualizzabili
    BASE_HEIGHT_FACTOR = 2.0 # FATTORE CHIAVE: 2.0 per garantire che la linea centrale sia sempre visibile
    
    def __init__(self, audio_engine, midi_engine, settings_manager, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Lyrics Prompter") # Keep title for consistency
        
        self.resize(200, 200) 
        self.setMinimumSize(200, 200) 
        
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.settings = settings_manager 
        self.lyrics_data = [] 
        
        self.active_line_index = -1
        self.is_fullscreen = False # Still managed, but toggle is done via main app
        
        # Carica le impostazioni dinamiche
        settings_data = self.settings.data
        self.read_ahead_time = settings_data.get("lyrics_read_ahead_time", 1.0)
        self.scrolling_mode = settings_data.get("lyrics_scrolling_mode", True)
        
        # Inizializzazione per il calcolo dinamico
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


        self.init_ui()
        self.setup_timer()
        
        # --- Rimosso setWindowFlags e setModal: ora è un QWidget incorporato ---

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
        """Prepara l'UI per il caricamento di nuovi dati (rimuove/ricrea i label se necessario)."""
        
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
        
        self.reload_ui_for_new_data(len(self.lyrics_data)) 
        
        if not self.lyrics_data and self.lyric_labels:
             if len(self.lyric_labels) > self.center_line_index:
                 self.lyric_labels[self.center_line_index].setText(f"Nessun lyric sincronizzato: {song_name}")
        
        self.apply_settings()
        self.resize_and_reposition_wrapper(force=True)
        
        self.update_lyrics_display()

    def keyPressEvent(self, event):
        """Intercetta il tasto F11 per il toggle fullscreen e Esc per chiudere."""
        if event.key() == Qt.Key.Key_F11:
            self.toggle_fullscreen()
        elif event.key() == Qt.Key.Key_Escape:
            self.close()
        super().keyPressEvent(event)


    # -------------------------------------------------------------
    # UI SETUP E SCHERMO MULTIPLO
    # -------------------------------------------------------------

    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)
        
        # AREA DI CONTROLLO
        controls_layout = QHBoxLayout()
        self.btn_fullscreen = QPushButton("F11")
        self.btn_fullscreen.setVisible(False)
        controls_layout.addWidget(self.btn_fullscreen)
        controls_layout.addStretch()
        
        main_layout.addLayout(controls_layout) 

        # 1. Viewport 
        self.lyrics_viewport = QWidget()
        self.lyrics_viewport.setContentsMargins(0, 0, 0, 0)
        
        main_layout.addWidget(self.lyrics_viewport, 1) 
        
        # 2. Wrapper
        self.lyrics_wrapper = QWidget(self.lyrics_viewport)
        self.lyrics_wrapper.setObjectName("LyricsWrapper")

        # 3. Layout dentro il wrapper 
        self.lyrics_layout = QVBoxLayout(self.lyrics_wrapper)
        self.lyrics_layout.setContentsMargins(0, 0, 0, 0)

        # Creiamo un set minimo di QLabel
        for i in range(self.MIN_VISIBLE_LINES): 
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setWordWrap(True)
            self.lyrics_layout.addWidget(label)
            self.lyric_labels.append(label)
            
        if self.lyric_labels:
             self.current_line_label = self.lyric_labels[(self.MIN_VISIBLE_LINES - 1) // 2]
             self.current_line_label.setText("Nessun brano in riproduzione.")

        # Configura l'animazione
        self.animation = QPropertyAnimation(self.lyrics_wrapper, b'pos')
        self.animation.setDuration(400) 
        self.animation.setEasingCurve(QEasingCurve.Type.InOutQuad) 

    def apply_settings(self):
        """Applica le impostazioni di styling e schermo dal SettingsManager."""
        
        settings = self.settings.data
        bg_color = settings.get("lyrics_bg_color", "#000000")
        font_color = settings.get("lyrics_font_color", "#FFFFFF")
        highlight_color = settings.get("lyrics_highlight_color", "#00FF00")
        self.read_ahead_time = settings.get("lyrics_read_ahead_time", 1.0)
        self.scrolling_mode = settings.get("lyrics_scrolling_mode", True)
        
        self.lyrics_layout.setSpacing(self.FIXED_SPACING) 
        
        # 1. STYLING GENERALE
        self.setStyleSheet(f"background-color: {bg_color};")
        
        reference_font = QFont("Arial", 12, QFont.Weight.Bold)
        if self.lyric_labels:
            self.lyric_labels[0].setFont(reference_font) 

        # 2. POSIZIONAMENTO SCHERMO (Non necessario per QWidget, ma la logica del font dipende dalle dimensioni)
        screen_name = settings.get("lyrics_prompter_screen", None)
        self.available_screens = QApplication.screens()
        
        target_screen = QApplication.primaryScreen()
        if screen_name:
            for screen in self.available_screens:
                if screen.name() == screen_name:
                    target_screen = screen
                    break
        
        # L'unica cosa che facciamo per il posizionamento è informarci sulla geometria per i calcoli del resize.
        
        self.resize_and_reposition_wrapper(force=True)


    def resizeEvent(self, event):
        """Ricalcola le dimensioni del viewport e del wrapper al ridimensionamento."""
        super().resizeEvent(event)
        if self.lyrics_viewport:
            self.lyrics_viewport.setMask(QRegion(self.lyrics_viewport.rect())) 
        self.resize_and_reposition_wrapper()
        
    def resize_and_reposition_wrapper(self, force=False):
        """
        Calcola dinamicamente la dimensione del font e il numero di linee visibili
        in base alle dimensioni della finestra.
        """
        if not self.lyrics_viewport or not self.lyric_labels:
            return

        # --- 1. Calcolo dinamico della dimensione del font (in base alla larghezza) ---
        window_width = self.lyrics_viewport.width()
        
        CHAR_ASPECT_RATIO = 0.6 
        
        if window_width > 0:
            calculated_font_size_width = int(window_width / (self.TARGET_CHARS * CHAR_ASPECT_RATIO))
            self.font_base_size = max(10, calculated_font_size_width) 
        else:
             self.font_base_size = 48 
             
        # --- 2. Aggiornamento del font e delle metriche ---
        reference_font = QFont("Arial", self.font_base_size, QFont.Weight.Bold)
        
        reference_label = self.lyric_labels[0]
        reference_label.setFont(reference_font) 
        font_metrics = QFontMetrics(reference_font)

        label_base_height = font_metrics.height()
        label_min_height = int(label_base_height * self.BASE_HEIGHT_FACTOR)
        
        if label_min_height <= 0: return

        spacing = self.FIXED_SPACING
        self.pixel_per_line = label_min_height + spacing
        
        # --- 3. Calcolo dinamico delle linee visibili (in base all'altezza) ---
        
        viewport_height = self.lyrics_viewport.height()
        
        if viewport_height > 0 and self.pixel_per_line > 0:
            calculated_visible_lines = floor((viewport_height + spacing) / self.pixel_per_line)
            
            if calculated_visible_lines % 2 == 0:
                calculated_visible_lines -= 1
                
            new_visible_lines = max(self.MIN_VISIBLE_LINES, calculated_visible_lines)
        else:
            new_visible_lines = self.MIN_VISIBLE_LINES

        # --- 4. Ricarica la UI e aggiorna gli stati ---
        
        if new_visible_lines != self.visible_lines:
             self.visible_lines = new_visible_lines
             self.center_line_index = (self.visible_lines - 1) // 2
             
             if not self.scrolling_mode:
                 self.update_fixed_labels_count(new_visible_lines)
        
        # --- 5. Final Layout e Riposizionamento ---

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

    def move_to_screen(self, screen: QScreen):
        """Sposta la finestra sullo schermo specificato, mantenendo la dimensione attuale se non in fullscreen."""
        screen_geometry = screen.geometry()
        self.move(screen_geometry.topLeft() + QPoint(20, 20))
        
        if self.is_fullscreen:
             # This part might need external help if we want to toggle fullscreen from a widget
             pass

    def toggle_fullscreen(self):
        """Alterna lo stato fullscreen (da implementare esternamente per un QWidget)."""
        # Se si tenta il fullscreen da un QWidget embedded, si applica alla MainWindow.
        # Per ora, lasciamo la logica qui, ma l'attivazione dovrà essere delegata alla MainWindow.
        pass

    def setup_timer(self):
        """Configura il timer per l'aggiornamento dei testi."""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_lyrics_display)
        self.timer.start(50)

    def update_lyrics_display(self):
        """Aggiorna le lyrics in base al tempo di riproduzione (Master Clock: AudioEngine)."""
        
        current_time_s = self.audio_engine.get_current_time() 
        duration = self.audio_engine.get_duration()
        
        if not self.lyrics_data:
             return
        
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
        
    def closeEvent(self, event):
        """Intercetta la chiusura per fermare il timer (essendo un QWidget, la chiusura è gestita dal tab)."""
        if self.timer.isActive():
            self.timer.stop()
        
        super().closeEvent(event)