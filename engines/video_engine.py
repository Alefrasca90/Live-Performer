# engines/video_engine.py

from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget
from PyQt6.QtCore import Qt, QObject, QUrl


class VideoTrack:
    """Rappresenta un singolo video player e la sua configurazione."""
    def __init__(self, video_path: str):
        self.path = video_path

        self.player = QMediaPlayer(None, QMediaPlayer.Flags.StreamPlayback)
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        # QVideoWidget associato (deve essere assegnato dall'esterno)
        self.video_widget: QVideoWidget | None = None

        # Carica il file
        self.player.setSource(QUrl.fromLocalFile(video_path))
        self.audio_output.setVolume(1.0) # Volume di default

    def set_widget(self, widget: QVideoWidget):
        """Associa il video a un QVideoWidget esterno."""
        self.video_widget = widget
        self.player.setVideoOutput(widget)

    def _ensure_widget_output(self):
        """Metodo aggiunto per forzare la riconnessione del widget prima di riproduzione/seek."""
        if self.video_widget and self.player.videoOutput() is None:
             self.player.setVideoOutput(self.video_widget)

    def set_volume(self, volume: float):
        self.audio_output.setVolume(volume)


class VideoEngine(QObject):
    """Gestisce una lista di video per il playback sincronizzato."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.videos: list[VideoTrack] = []

    # ---------------------------------------------------
    # CARICAMENTO VIDEO
    # ---------------------------------------------------

    def add_video(self, video_path: str) -> VideoTrack:
        """Crea e ritorna un VideoTrack."""
        track = VideoTrack(video_path)
        self.videos.append(track)
        return track

    def clear_videos(self):
        """Rimuove tutti i VideoTrack dalla lista."""
        # Prima di cancellare, resettiamo l'output per evitare crash.
        for v in self.videos:
             v.player.setVideoOutput(None)
        self.videos.clear()

    # ---------------------------------------------------
    # CONTROLLO PLAYBACK
    # ---------------------------------------------------

    def play(self):
        """Play sincronizzato di tutti i video."""
        for v in self.videos:
            v._ensure_widget_output() # Assicuriamo che l'output sia settato
            v.player.play()

    def pause(self):
        """Pausa tutti i video."""
        for v in self.videos:
            v._ensure_widget_output()
            v.player.pause()

    def stop(self):
        """Stop completo e resetta la posizione."""
        for v in self.videos:
            v.player.stop()

    def seek(self, ms: int):
        """Imposta la posizione in millisecondi per tutti i video."""
        for v in self.videos:
            v._ensure_widget_output()
            v.player.setPosition(ms)

    # ---------------------------------------------------
    # SINCRONIZZAZIONE ESTERNA
    # ---------------------------------------------------

    def sync_to_position(self, ms: int):
        """Forza i video ad andare al tempo specificato (seek forzato)."""
        for v in self.videos:
            v._ensure_widget_output() # Assicuriamo che l'output sia settato
            # Tolleranza 40 ms
            delta = abs(v.player.position() - ms)
            if delta > 40:
                v.player.setPosition(ms)

    # ---------------------------------------------------
    # UTILITY PER MULTI-SCHERMO
    # ---------------------------------------------------

    def fullscreen_on_screen(self, track_index: int, screen):
        """Manda il video track[n] a schermo intero su uno specifico monitor."""
        if 0 <= track_index < len(self.videos):
            track = self.videos[track_index]

            if track.video_widget is None:
                print("⚠️ No video widget assegnato a questo video.")
                return

            # Esegui la stessa logica di re-associazione prima di forzare il fullscreen
            track._ensure_widget_output() 
            
            window = track.video_widget.window()
            window.windowHandle().setScreen(screen)
            window.showFullScreen()