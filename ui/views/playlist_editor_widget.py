# ui/views/playlist_editor_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QListWidgetItem, QSlider, QSizePolicy, QMessageBox
)
from PyQt6.QtCore import Qt, QMimeData, QTimer, QPoint 
from PyQt6.QtGui import QMouseEvent
# Import adattato
from ui.views.lyrics_player_window import LyricsPlayerWindow 

class PlaylistListWidget(QListWidget):
    """QListWidget customizzato per accettare il drag and drop di nomi di canzoni e riordinare."""
    def __init__(self, data_manager, playlist_name, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.data_manager = data_manager
        self.playlist_name = playlist_name
        self.model().rowsMoved.connect(self.on_rows_moved)

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.setDropAction(Qt.DropAction.CopyAction)
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            song_name = event.mimeData().text()
            
            if event.source() != self:
                self.data_manager.add_song_to_playlist(self.playlist_name, song_name)
                self.parent().load_playlist_songs()
                event.acceptProposedAction()
            else:
                 super().dropEvent(event)
        else:
            super().dropEvent(event)

    def on_rows_moved(self, parent, start, end, destination, row):
        new_songs = []
        for i in range(self.count()):
             new_songs.append(self.item(i).text())
        self.data_manager.update_playlist_songs(self.playlist_name, new_songs)


class PlaylistEditorWidget(QWidget):
    
    PLAYLIST_SYNC_INTERVAL_MS = 200
    
    def __init__(self, playlist_name, audio_engine, midi_engine, data_manager, settings_manager, parent=None):
        super().__init__(parent)
        self.playlist_name = playlist_name
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.data_manager = data_manager
        self.settings_manager = settings_manager
        
        self.is_playing_playlist = False
        self.autoplay_enabled = False 
        self.current_song_index = -1
        self.playlist_songs = []
        self.is_slider_pressed = False
        
        self.song_name: str | None = None
        
        self.lyrics_player: LyricsPlayerWindow | None = None
        
        self.init_ui()
        self.load_playlist_songs()
        
        QTimer.singleShot(100, self.open_lyrics_prompter_on_init) 
        
        self.playback_timer = QTimer(self)
        self.playback_timer.timeout.connect(self.update_playback_state)
        self.playback_timer.start(self.PLAYLIST_SYNC_INTERVAL_MS)

    def open_lyrics_prompter_on_init(self):
         """Avvia la finestra LyricsPlayerWindow all'inizializzazione con i dati del primo brano."""
         song_name_to_prompt = None
        
         if self.playlist_songs:
              song_name_to_prompt = self.playlist_songs[0]
              self.playlist_list.setCurrentRow(0)
              self.current_song_index = 0
             
         self.open_lyrics_prompter(force_show=True, force_song_name=song_name_to_prompt)

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel(f"<h2>Editor Playlist: {self.playlist_name}</h2>"))
        
        layout.addWidget(QLabel("Brani in Playlist (Drag & Drop qui da lista Brani):"))
        self.playlist_list = PlaylistListWidget(self.data_manager, self.playlist_name, parent=self)
        self.playlist_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.playlist_list.itemClicked.connect(self.on_song_clicked)
        layout.addWidget(self.playlist_list)
        
        self.btn_remove_song = QPushButton("Rimuovi Brano Selezionato")
        self.btn_remove_song.clicked.connect(self.remove_selected_song)
        layout.addWidget(self.btn_remove_song)
        
        layout.addWidget(QLabel("--- CONTROLLI PLAYBACK ---"))

        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.sliderMoved.connect(self.on_slider_moved)
        self.progress_slider.sliderPressed.connect(self.on_slider_press)
        self.progress_slider.sliderReleased.connect(self.on_slider_release)
        self.progress_slider.setEnabled(False) 
        layout.addWidget(self.progress_slider)
        
        self.time_label = QLabel("00:00 / 00:00")
        layout.addWidget(self.time_label)

        # Pulsanti Playback Aggiornati
        btn_layout = QHBoxLayout()
        self.btn_prev = QPushButton("⏮️ Indietro")
        self.btn_play_pause = QPushButton("▶️ Play") 
        self.btn_stop = QPushButton("⏹️ STOP")
        self.btn_next = QPushButton("⏭️ Avanti")
        self.btn_lyrics = QPushButton("🎤 Visualizza Lyrics")
        
        # Nuovo Pulsante Autoplay
        self.btn_autoplay_toggle = QPushButton("Autoplay: Off")
        self.btn_autoplay_toggle.setCheckable(True)
        self.btn_autoplay_toggle.clicked.connect(self.toggle_autoplay)
        
        self.btn_prev.clicked.connect(self.previous_song)
        self.btn_play_pause.clicked.connect(self.toggle_play_pause) 
        self.btn_stop.clicked.connect(self.stop_playback)
        self.btn_next.clicked.connect(self.next_song)
        self.btn_lyrics.clicked.connect(self.open_lyrics_prompter)
        
        # Layout UI
        playback_controls_layout = QHBoxLayout()
        playback_controls_layout.addWidget(self.btn_prev)
        playback_controls_layout.addWidget(self.btn_play_pause)
        playback_controls_layout.addWidget(self.btn_stop)
        playback_controls_layout.addWidget(self.btn_next)
        playback_controls_layout.addWidget(self.btn_lyrics)
        
        # Aggiungo il toggle Autoplay
        autoplay_layout = QHBoxLayout()
        autoplay_layout.addStretch()
        autoplay_layout.addWidget(self.btn_autoplay_toggle)
        autoplay_layout.addStretch()
        
        layout.addLayout(playback_controls_layout) 
        layout.addLayout(autoplay_layout)
        
        layout.addStretch() 

    def load_playlist_songs(self):
        """Carica i nomi delle canzoni dalla playlist e aggiorna la UI."""
        playlist_data = self.data_manager.load_playlist(self.playlist_name)
        self.playlist_songs = playlist_data.get("songs", [])
        
        current_row = self.playlist_list.currentRow()
        
        self.playlist_list.clear()
        for song_name in self.playlist_songs:
            self.playlist_list.addItem(song_name)
        
        if self.current_song_index >= 0 and self.current_song_index < self.playlist_list.count():
             self.playlist_list.setCurrentRow(self.current_song_index)
        elif current_row >= 0 and current_row < self.playlist_list.count():
             self.playlist_list.setCurrentRow(current_row)
        
        self.update_playback_buttons()

    def remove_selected_song(self):
        """Rimuove la canzone selezionata dalla playlist e aggiorna DataManager."""
        current_row = self.playlist_list.currentRow()
        if current_row >= 0:
            self.data_manager.remove_song_from_playlist(self.playlist_name, current_row)
            self.load_playlist_songs()
            self.stop_playback()

    # --- LOGICA PLAYBACK ---
    
    def toggle_play_pause(self):
        """Gestisce lo stato Play/Pausa/Riprendi."""
        current_song_name = self.audio_engine.playing_song
        is_playing = current_song_name and not self.audio_engine.is_stopped()
        is_currently_paused = self.audio_engine.pause_time > 0.0 and self.audio_engine.is_stopped()

        if is_playing:
            self.pause_playback()
        elif is_currently_paused:
            self.play_song(current_song_name) 
        else:
            self.play_selected_song(is_playlist_mode=self.autoplay_enabled)


    def toggle_autoplay(self):
        """Abilita/Disabilita l'avanzamento automatico al brano successivo."""
        self.autoplay_enabled = self.btn_autoplay_toggle.isChecked()
        
        if self.autoplay_enabled:
            self.btn_autoplay_toggle.setText("Autoplay: On")
            if self.audio_engine.playing_song:
                 self.is_playing_playlist = True
                 
        else:
            self.btn_autoplay_toggle.setText("Autoplay: Off")
            if self.is_playing_playlist:
                 self.is_playing_playlist = False
                 self.current_song_index = self.playlist_list.currentRow() if self.playlist_list.currentRow() >= 0 else -1
                 
        self.update_playback_buttons()

    
    def play_song(self, song_name, start_time_s=0.0):
        """Carica e avvia un singolo brano nell'AudioEngine e MidiEngine."""
        
        self.song_name = song_name
        
        is_resuming = (self.audio_engine.playing_song == song_name and self.audio_engine.pause_time > 0.0 and start_time_s == 0.0)

        if not is_resuming:
            # Importa i motori per il type hint, non per l'istanza.
            
            self.stop_playback(reset_state=False) 

            song_data = self.data_manager.load_song(song_name) 
            if not song_data or not song_data.get("audio_tracks"):
                self.stop_playback(reset_state=True)
                QMessageBox.warning(self, "Errore", f"Brano '{song_name}' non ha tracce audio valide.")
                self.song_name = None
                
                if self.lyrics_player and self.lyrics_player.isVisible():
                     self.lyrics_player.set_lyrics_data([], f"Errore: {song_name}")
                
                return False
                
            audio_tracks = self.data_manager.audio_tracks.get(song_name, [])
            midi_tracks = self.data_manager.midi_tracks.get(song_name, [])
            
            self.audio_engine.tracks[song_name] = []
            self.midi_engine.tracks[song_name] = []
            
            for t in audio_tracks:
                self.audio_engine.add_track(song_name, t['file'], t['output'], t.get('channels_used'), t.get('output_start_channel'))
            for t in midi_tracks:
                self.midi_engine.add_track(song_name, t['channel'], t['port'], file_path=t.get('file'))
            
            lyrics_data, _ = self.data_manager.get_lyrics_with_txt(song_name)
            
            if self.lyrics_player is None:
                self.open_lyrics_prompter(force_show=True) 
            
            self.lyrics_player.set_lyrics_data(lyrics_data, song_name)
            
        bpm = audio_tracks[0].get('bpm', 120.0) if audio_tracks else 120.0

        self.audio_engine.start_playback(song_name, start_time_s)
        self.midi_engine.start_playback(song_name, bpm=bpm)
        
        self.update_playback_buttons()
        return True
        
    def pause_playback(self):
        """Mette in pausa la riproduzione e memorizza la posizione."""
        current_song_name = self.audio_engine.playing_song
        if current_song_name and not self.audio_engine.is_stopped():
            self.audio_engine.pause_playback(current_song_name)
            self.midi_engine.pause_playback(current_song_name)
            self.update_playback_buttons()

    def next_song(self):
        """Passa al brano successivo nella playlist."""
        if not self.playlist_songs: return

        start_index = self.current_song_index
        if start_index < 0:
            start_index = self.playlist_list.currentRow()
            if start_index < 0: return

        next_index = start_index + 1
        
        if next_index < len(self.playlist_songs):
            song_name = self.playlist_songs[next_index]
            self.current_song_index = next_index
            self.is_playing_playlist = self.autoplay_enabled 
            self.play_song(song_name)
            self.playlist_list.setCurrentRow(self.current_song_index)
        else:
            self.stop_playback()

    def previous_song(self):
        """Torna al brano precedente nella playlist, o riparte dall'inizio del corrente."""
        if not self.playlist_songs: return

        start_index = self.current_song_index
        if start_index < 0:
            start_index = self.playlist_list.currentRow()
            if start_index < 0: return
            
        current_playback_time = self.audio_engine.get_current_time()
        
        if current_playback_time > 3.0 and self.audio_engine.playing_song:
            song_name = self.playlist_songs[start_index]
            self.play_song(song_name, start_time_s=0.0)
            return

        prev_index = start_index - 1
        
        if prev_index >= 0:
            song_name = self.playlist_songs[prev_index]
            self.current_song_index = prev_index
            self.is_playing_playlist = self.autoplay_enabled 

            self.play_song(song_name) 
            self.playlist_list.setCurrentRow(self.current_song_index)
        else:
            if start_index == 0 and self.audio_engine.playing_song:
                 self.play_song(self.playlist_songs[0], start_time_s=0.0)
            else:
                 self.stop_playback(reset_state=True)


    def play_selected_song(self, is_playlist_mode=False):
        """Avvia la riproduzione del brano selezionato (singolo o in modalità playlist)."""
        current_row = self.playlist_list.currentRow()
        if current_row < 0: return

        song_name = self.playlist_songs[current_row]
        self.current_song_index = current_row
        self.is_playing_playlist = is_playlist_mode 
        
        if self.play_song(song_name):
             self.playlist_list.setCurrentRow(current_row) 

    def stop_playback(self, reset_state=True):
        """Ferma la riproduzione e resetta lo stato dei motori e della playlist."""
        
        current_song_name = self.audio_engine.playing_song
        if current_song_name:
            self.audio_engine.stop_playback(current_song_name)
            self.midi_engine.stop_playback(current_song_name)
            
        if reset_state:
            self.is_playing_playlist = False
            self.current_song_index = -1
            self.song_name = None
        
        if self.lyrics_player and self.lyrics_player.isVisible():
            self.lyrics_player.set_lyrics_data([], "Riproduzione Ferma")
        
        if hasattr(self, 'progress_slider'):
             self.update_playback_buttons()
             self.progress_slider.setValue(0)
             self.time_label.setText("00:00 / 00:00")
             self.progress_slider.setEnabled(False)

    def update_playback_buttons(self):
        """Aggiorna lo stato di attivazione e il testo dei pulsanti."""
        current_row = self.playlist_list.currentRow()
        playlist_size = self.playlist_list.count()
        can_play = current_row >= 0 and playlist_size > 0
        
        is_playing = self.audio_engine.playing_song is not None and not self.audio_engine.is_stopped()
        is_currently_paused = self.audio_engine.pause_time > 0.0 and self.audio_engine.is_stopped()
        
        song_name_to_check = self.audio_engine.playing_song
        has_lyrics = False
        if song_name_to_check:
             lyrics_data, _ = self.data_manager.get_lyrics_with_txt(song_name_to_check)
             has_lyrics = bool(lyrics_data)

        # Stato Play/Pause Toggle
        if is_playing:
            self.btn_play_pause.setText("⏸️ Pausa")
        elif is_currently_paused:
            self.btn_play_pause.setText("▶️ Riprendi")
        else:
            self.btn_play_pause.setText("▶️ Play")
            
        self.btn_play_pause.setEnabled(can_play or is_currently_paused)

        # Stato Navigazione
        is_active_song_in_list = self.current_song_index != -1
        current_index_for_nav = self.current_song_index if is_active_song_in_list else current_row
        
        can_next = current_index_for_nav < playlist_size - 1
        can_prev = current_index_for_nav > 0
        
        self.btn_stop.setEnabled(is_playing or is_currently_paused)
        
        nav_enabled = (is_playing or is_currently_paused) and playlist_size > 1
        self.btn_next.setEnabled(can_next and nav_enabled)
        self.btn_prev.setEnabled((can_prev or (current_index_for_nav == 0 and is_playing)) and nav_enabled)
        
        self.progress_slider.setEnabled(is_playing or is_currently_paused)
        self.btn_lyrics.setEnabled((is_playing or is_currently_paused) and has_lyrics)


    def update_playback_state(self):
        """Aggiorna la barra di avanzamento e gestisce la transizione tra brani (Autoplay)."""
        
        current_song_name = self.audio_engine.playing_song
        is_playing = current_song_name is not None and not self.audio_engine.is_stopped()

        if is_playing or self.audio_engine.pause_time > 0.0:
            current_time = self.audio_engine.get_current_time()
            duration = self.audio_engine.get_duration()

            if duration > 0:
                progress = int((current_time / duration) * 1000)
                if not self.is_slider_pressed:
                     self.progress_slider.setValue(progress)

            time_str = self.format_time(current_time)
            duration_str = self.format_time(duration)
            self.time_label.setText(f"{time_str} / {duration_str}")

            # Gestione Fine Brano e Transizione Playlist (FIX Autoplay)
            if self.autoplay_enabled and self.is_playing_playlist and is_playing and current_time >= duration and duration > 0:
                self.current_song_index += 1
                if self.current_song_index < len(self.playlist_songs):
                    next_song_name = self.playlist_songs[self.current_song_index]
                    self.play_song(next_song_name)
                    self.playlist_list.setCurrentRow(self.current_song_index)
                else:
                    self.stop_playback()

        elif self.audio_engine.playing_song is not None and self.audio_engine.is_stopped():
             self.update_playback_buttons()


    def format_time(self, seconds):
        """Formatta i secondi in stringa MM:SS."""
        if seconds is None or seconds < 0: return "00:00"
        m, s = divmod(int(seconds), 60)
        return f"{m:02d}:{s:02d}"

    # --- FUNZIONE LYRICS PROMPTER ---
    def open_lyrics_prompter(self, force_show=False, force_song_name=None):
        from ui.views.lyrics_player_window import LyricsPlayerWindow
        
        song_name_to_prompt = self.audio_engine.playing_song
        
        if not song_name_to_prompt:
             current_row = self.playlist_list.currentRow()
             if current_row >= 0:
                  song_name_to_prompt = self.playlist_songs[current_row]
        
        if not song_name_to_prompt and force_song_name:
             song_name_to_prompt = force_song_name

        if not song_name_to_prompt:
             song_name_to_prompt = "Nessun brano selezionato"
             lyrics_data = []
             has_lyrics = False
        else:
             lyrics_data, _ = self.data_manager.get_lyrics_with_txt(song_name_to_prompt)
             has_lyrics = bool(lyrics_data)
        
        if not has_lyrics and song_name_to_prompt != "Nessun brano selezionato":
             if not force_show: 
                 QMessageBox.warning(self, "Attenzione", f"Il brano '{song_name_to_prompt}' non ha lyrics sincronizzati.")
                 return
             lyrics_data = [] 

        if self.lyrics_player is None:
            self.lyrics_player = LyricsPlayerWindow(
                audio_engine=self.audio_engine, 
                midi_engine=self.midi_engine,
                settings_manager=self.settings_manager,
                parent=self
            )
            
        self.lyrics_player.set_lyrics_data(lyrics_data, song_name_to_prompt)
        
        if not self.lyrics_player.isVisible() or force_show:
             self.lyrics_player.show()
        
        self.update_playback_buttons()


    # --- GESTIONE SLIDER (SEEK) ---

    def on_slider_press(self):
         self.is_slider_pressed = True

    def on_slider_release(self):
        """Esegue il seek al rilascio del cursore."""
        self.is_slider_pressed = False
        current_song_name = self.audio_engine.playing_song
        if not current_song_name: return

        duration = self.audio_engine.get_duration()
        if duration > 0:
            progress = self.progress_slider.value()
            target_time_s = (progress / 1000) * duration
            
            self.play_song(current_song_name, start_time_s=target_time_s)


    def on_slider_moved(self, value):
        current_song_name = self.audio_engine.playing_song
        if not current_song_name: return

        duration = self.audio_engine.get_duration()
        if duration > 0:
            target_time = (value / 1000) * duration
            time_str = self.format_time(target_time)
            duration_str = self.format_time(duration)
            self.time_label.setText(f"{time_str} / {duration_str}")

    def on_song_clicked(self, item):
         self.update_playback_buttons()
         
    def closeEvent(self, event):
         self.stop_playback()
         if self.lyrics_player:
              self.lyrics_player.close() 
         event.accept()