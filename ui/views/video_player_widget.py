# ui/views/video_player_widget.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QUrl, QTimer, QPoint
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtMultimedia import QMediaPlayer 
# Import dependencies
from engines.video_engine import VideoEngine 
from engines.audio_engine import AudioEngine 
from core.data_manager import DataManager 
from ui.components.settings_manager import SettingsManager 

class VideoPlayerWidget(QWidget):
    """
    Widget che visualizza la riproduzione video sincronizzata.
    Contiene un QVideoWidget e gestisce la traccia video tramite VideoEngine.
    """
    def __init__(self, video_engine: VideoEngine, audio_engine: AudioEngine, settings_manager: SettingsManager, parent=None):
        super().__init__(parent)
        self.video_engine = video_engine
        self.audio_engine = audio_engine
        self.settings_manager = settings_manager
        
        self.current_video_path = None
        self.current_song_name = None
        
        self.init_ui()
        
        # Timer per la sincronizzazione continua
        self.sync_timer = QTimer(self)
        self.sync_timer.timeout.connect(self.sync_playback_state)
        self.sync_timer.start(50) # Sync a 20 FPS

        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 1. Video Widget (Area di visualizzazione)
        self.video_widget = QVideoWidget()
        self.video_widget.setStyleSheet("background-color: black;")
        
        self.status_label = QLabel("Nessun video caricato.")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("color: white; font-size: 18px;")
        
        # 2. Layer per mostrare l'etichetta di stato sopra il video
        overlay_container = QWidget(self.video_widget)
        overlay_container.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents) 
        overlay_layout = QVBoxLayout(overlay_container)
        overlay_layout.addStretch()
        overlay_layout.addWidget(self.status_label)
        overlay_layout.addStretch()
        
        # Sposta l'overlay in cima al QVideoWidget
        overlay_container.setParent(self.video_widget) 
        overlay_container.setGeometry(self.video_widget.geometry())
        
        main_layout.addWidget(self.video_widget)
        
        # Assicuriamo che l'area video sia espandibile
        self.video_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding, 
            QSizePolicy.Policy.Expanding
        )

    def _handle_player_error(self, error: QMediaPlayer.Error, error_string: str):
        """Gestisce gli errori fatali del player."""
        if error != QMediaPlayer.Error.NoError:
             error_message = f"ERRORE PLAYER [{error.name}]: {error_string}."
             if self.current_video_path:
                 error_message += f" Problema con {self.current_video_path.split('/')[-1]} (Verifica Codec)."
             
             self.status_label.setText(error_message)
             self.status_label.show()
             print(f"⚠️ VIDEO PLAYER ERRORE FATALE: {error_message}") # Aggiunta linea di debug

    def load_video_track(self, song_name: str | None, video_path: str | None):
        """
        Carica un nuovo video path nel VideoEngine.
        Se il path è None, pulisce le tracce.
        """
        is_new_path = video_path != self.current_video_path or not self.video_engine.videos
        
        print(f"--- Video Load Start for Song: {song_name} ---") # Debug: Start Load
        
        self.current_song_name = song_name
        self.current_video_path = video_path

        if is_new_path:
            print("DEBUG: New path or no existing track. Clearing old tracks.") # Debug: Clearing
            self.video_engine.clear_videos()

        if video_path:
            print(f"DEBUG: Attempting to load video file: {video_path}") # Debug: Path attempt
            try:
                if is_new_path:
                    track = self.video_engine.add_video(video_path)
                    track.set_widget(self.video_widget)
                    track.set_volume(0.0) 
                    track.player.errorOccurred.connect(self._handle_player_error)
                    
                    print(f"DEBUG: Track added. Video Source: {track.player.source()}") # Debug: Source URI
                    
                self.status_label.setText(f"Video caricato: {video_path.split('/')[-1]}")
                self.status_label.show() 

                if self.video_engine.videos:
                     # FIX RENDERING: Forziamo il Play/Pause per stabilizzare l'output video.
                     self.video_engine.play() 
                     self.video_engine.pause() 
                     self.video_engine.seek(0)
                     self.video_widget.repaint() # Forziamo un redraw del widget
                     
                     print("DEBUG: Initial Play/Pause/Seek(0) sequence executed.") # Debug: Play/Pause sequence
                     
            except Exception as e:
                self.status_label.setText(f"Errore caricamento video: {e}")
                self.status_label.show()
                print(f"⚠️ VIDEO LOAD EXCEPTION: {e}") # Debug: Load Exception
        else:
            self.status_label.setText("Nessun video caricato.")
            self.status_label.show()
            print("DEBUG: Video path is None. Player is idle.") # Debug: Path None
            
        print(f"--- Video Load End ---") # Debug: End Load

    def sync_playback_state(self):
        """Sincronizza lo stato di riproduzione (Play/Stop/Seek) con AudioEngine."""
        
        has_video_track = bool(self.video_engine.videos)
        
        # Condizioni iniziali
        if not self.audio_engine.playing_song or not has_video_track:
            if has_video_track and self.video_engine.videos[0].player.playbackState() != self.video_engine.videos[0].player.PlaybackState.StoppedState:
                 self.video_engine.stop()
                 self.video_engine.seek(0)
                 self.status_label.setText(f"Video in Stop: {self.current_video_path.split('/')[-1]}")
                 self.status_label.show()
                 print("DEBUG SYNC: Audio stopped or song ended. Stopping video player.") # Debug: Stop
            elif not has_video_track and self.audio_engine.playing_song and self.current_video_path is None:
                 self.status_label.setText("Nessun video associato al brano.")
                 self.status_label.show()
            return
            
        current_time_ms = int(self.audio_engine.get_current_time() * 1000)
        is_playing = self.audio_engine.playing_song is not None and not self.audio_engine.is_stopped()
        
        if is_playing:
            self.video_engine.sync_to_position(current_time_ms)
            self.video_engine.play()
            self.status_label.hide()
        else:
            # Pausa/Seek quando il brano è in pausa o fermo (ma ha una posizione)
            self.video_engine.pause()
            self.video_engine.sync_to_position(current_time_ms)
            self.status_label.setText(f"Video in Pausa: {self.current_video_path.split('/')[-1]}")
            self.status_label.show()