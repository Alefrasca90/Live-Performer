# ui/views/scenografia_daw_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QLabel,
    QPushButton, QSplitter, QInputDialog, QMessageBox
)
from PyQt6.QtGui import QAction, QDrag, QCursor, QMouseEvent 
from PyQt6.QtCore import Qt, QMimeData 

# Import dei componenti (Media/App)
from engines.audio_engine import AudioEngine
from engines.midi_engine import MidiEngine
from engines.video_engine import VideoEngine # IMPORT AGGIUNTO
from core.data_manager import DataManager as ScenografiaDataManager
from ui.components.settings_manager import SettingsManager
from ui.views.lyrics_player_window import LyricsPlayerWidget 
from ui.views.video_player_widget import VideoPlayerWidget # IMPORT AGGIUNTO

# Import delle Views/Components
from ui.views.song_editor_widget import SongEditorWidget
from ui.components.settings_dialog import SettingsDialog
from ui.views.playlist_editor_widget import PlaylistEditorWidget 


class SongListWidget(QListWidget):
    """QListWidget customizzato per permettere il drag di nomi di canzoni."""
    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton:
            item = self.currentItem()
            if item:
                drag = QDrag(self)
                mime = QMimeData()
                mime.setText(item.text()) 
                drag.setMimeData(mime)
                drag.exec(Qt.DropAction.CopyAction)
        super().mouseMoveEvent(event)


class ScenografiaDAWWidget(QWidget):
    def __init__(self, audio_engine: AudioEngine, midi_engine: MidiEngine, video_engine: VideoEngine, data_manager: ScenografiaDataManager, settings_manager: SettingsManager, lyrics_player_widget: LyricsPlayerWidget, video_player_widget: VideoPlayerWidget, parent=None):
        super().__init__(parent)
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.video_engine = video_engine # AGGIUNTO
        self.data_manager = data_manager
        self.settings_manager = settings_manager
        self.lyrics_player_widget = lyrics_player_widget 
        self.video_player_widget = video_player_widget # AGGIUNTO
        self.current_editor = None 

        self.init_ui()
        self.setWindowTitle("Scenografia Media & Lyrics")

    def init_ui(self):
        # Layout Principale del Widget
        layout = QVBoxLayout(self)

        # Splitter (Pannello sinistro per liste, pannello destro per editor)
        self.splitter = QSplitter()
        self.left_panel = QWidget()
        self.right_panel = QWidget()
        self.splitter.addWidget(self.left_panel)
        self.splitter.addWidget(self.right_panel)
        layout.addWidget(self.splitter)

        # --- Pannello Sinistro (Liste) ---
        left = QVBoxLayout(self.left_panel)

        # Brani
        left.addWidget(QLabel("Brani"))
        self.song_list = SongListWidget()
        self.song_list.setMinimumHeight(200)
        left.addWidget(self.song_list)

        hl_songs = QHBoxLayout()
        self.btn_add_song = QPushButton("+")
        self.btn_remove_song = QPushButton("x")
        hl_songs.addWidget(self.btn_add_song)
        hl_songs.addWidget(self.btn_remove_song)
        left.addLayout(hl_songs)

        # Playlist
        left.addWidget(QLabel("Playlist"))
        self.playlist_list = QListWidget()
        self.playlist_list.setMinimumHeight(200)
        left.addWidget(self.playlist_list)

        hl_playlists = QHBoxLayout()
        self.btn_add_playlist = QPushButton("+")
        self.btn_remove_playlist = QPushButton("x")
        hl_playlists.addWidget(self.btn_add_playlist)
        hl_playlists.addWidget(self.btn_remove_playlist)
        left.addLayout(hl_playlists)
        
        # Pulsante Impostazioni globali
        settings_button = QPushButton("Audio / MIDI / Display Settings")
        settings_button.clicked.connect(self.open_settings)
        left.addWidget(settings_button)
        
        left.addStretch(1)


        # --- Connessioni ---
        self.song_list.itemDoubleClicked.connect(self.on_song_selected)
        self.btn_add_song.clicked.connect(self.add_song)
        self.btn_remove_song.clicked.connect(self.remove_selected_song)
        self.btn_add_playlist.clicked.connect(self.add_playlist)
        self.btn_remove_playlist.clicked.connect(self.remove_selected_playlist)
        
        self.playlist_list.itemDoubleClicked.connect(self.on_playlist_selected)

        self.load_lists()

    # --- Metodi di gestione (Adattati per QWidget) ---
    def open_settings(self):
        """Apre la finestra di dialogo delle impostazioni audio/MIDI/Display."""
        dlg = SettingsDialog(self.audio_engine, self.midi_engine, self.settings_manager)
        dlg.exec()

    def load_lists(self):
        """Carica i brani e le playlist dai dati persistenti."""
        self.song_list.clear()
        self.playlist_list.clear() 
        for s in self.data_manager.get_songs():
            self.song_list.addItem(s)
        for p in self.data_manager.get_playlists():
            self.playlist_list.addItem(p)

    def on_song_selected(self, item):
        """Crea e mostra l'editor della canzone selezionata."""
        name = item.text()
        editor = SongEditorWidget(
            name,
            self.audio_engine,
            self.midi_engine,
            self.data_manager,
            self.settings_manager,
            lyrics_player_widget=self.lyrics_player_widget, # INJECTED
            video_engine=self.video_engine, # INJECTED
            video_player_widget=self.video_player_widget # INJECTED
        )
        self.show_editor(editor)

    def on_playlist_selected(self, item):
        """Crea e mostra l'editor della playlist selezionata."""
        name = item.text()
        editor = PlaylistEditorWidget( 
            name,
            self.audio_engine,
            self.midi_engine,
            self.data_manager,
            self.settings_manager,
            lyrics_player_widget=self.lyrics_player_widget, # INJECTED
            video_engine=self.video_engine, # INJECTED
            video_player_widget=self.video_player_widget # INJECTED
        )
        self.show_editor(editor)

    def add_song(self):
        """Apre il dialogo per creare un nuovo brano."""
        name, ok = QInputDialog.getText(self, "Nuovo Brano", "Nome:")
        if ok and name:
            if self.data_manager.create_song(name):
                self.load_lists()
            else:
                QMessageBox.warning(self, "Errore", "Brano già esistente.")

    def remove_selected_song(self):
        """Rimuove il brano selezionato."""
        item = self.song_list.currentItem()
        if item:
            self.data_manager.delete_song(item.text())
            self.load_lists()

    def add_playlist(self):
        """Abre il dialogo per creare una nuova playlist."""
        name, ok = QInputDialog.getText(self, "Nuova Playlist", "Nome:")
        if ok and name:
            if self.data_manager.create_playlist(name):
                self.load_lists()
            else:
                QMessageBox.warning(self, "Errore", "Playlist già esistente.")

    def remove_selected_playlist(self):
        """Rimuove la playlist selezionata."""
        item = self.playlist_list.currentItem()
        if item:
            self.data_manager.delete_playlist(item.text())
            self.load_lists()

    def show_editor(self, editor: QWidget):
        """Sostituisce l'editor corrente nel pannello destro con un nuovo editor."""
        if self.current_editor:
            # Chiama l'eventuale metodo di pulizia (ad esempio per i timer interni dei player)
            if hasattr(self.current_editor, 'closeEvent'):
                 # Simula un evento di chiusura per permettere al widget di fare il suo cleanup
                 self.current_editor.closeEvent(QAction()) 
            self.current_editor.deleteLater() 

        layout = self.right_panel.layout()
        if not layout:
            layout = QVBoxLayout()
            self.right_panel.setLayout(layout)

        layout.addWidget(editor)
        self.current_editor = editor
        
    def cleanup(self):
        """Assicura che eventuali riproduzioni attive vengano interrotte."""
        if self.current_editor and hasattr(self.current_editor, 'stop_playback'):
             self.current_editor.stop_playback()