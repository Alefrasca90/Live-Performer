# ui/views/song_editor_widget.py

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QPushButton, QFileDialog, QComboBox, QInputDialog, QMessageBox, QDoubleSpinBox, QLineEdit 
)
from PyQt6.QtCore import Qt, QTimer
import soundfile as sf
import os
# Import adattati
from ui.views.lyrics_editor_window import LyricsEditorWindow
from ui.views.lyrics_player_window import LyricsPlayerWidget # RIFATTORIZZATO A WIDGET
from ui.components.midi_monitor_widget import MidiMonitorWidget 
# Import Engine e Player Video
from engines.video_engine import VideoEngine 
from ui.views.video_player_widget import VideoPlayerWidget 
from core.data_manager import DataManager


class SongEditorWidget(QWidget):
    """
    Widget per la configurazione e l'editing di una singola canzone.
    """
    def __init__(self, song_name, audio_engine, midi_engine, data_manager, settings_manager=None, lyrics_player_widget: LyricsPlayerWidget | None = None, video_engine: VideoEngine | None = None, video_player_widget: VideoPlayerWidget | None = None):
        super().__init__()
        self.song_name = song_name
        self.audio_engine = audio_engine
        self.midi_engine = midi_engine
        self.data_manager = data_manager
        self.settings_manager = settings_manager
        self.loaded_txt_file = None
        self.current_bpm = 120.0 
        self.video_file = None 
        
        # Dipendenze media iniettate
        self.lyrics_player: LyricsPlayerWidget | None = lyrics_player_widget 
        self.video_engine = video_engine
        self.video_player = video_player_widget

        self.init_ui()
        self.load_song()

    def open_lyrics_prompter_on_init(self):
         """Avvia la finestra LyricsPlayerWindow all'inizializzazione con i dati del brano."""
         self.open_lyrics_prompter(force_show=True)

    # -------------------------------------------------------------
    # UI SETUP
    # -------------------------------------------------------------
    def init_ui(self):
        main_layout = QVBoxLayout()
        self.setLayout(main_layout)

        # --- BPM Control ---
        bpm_layout = QHBoxLayout()
        bpm_layout.addWidget(QLabel("BPM Master (per Sync MIDI):"))
        self.spin_bpm = QDoubleSpinBox()
        self.spin_bpm.setRange(20.0, 300.0)
        self.spin_bpm.setSingleStep(0.1)
        self.spin_bpm.setDecimals(2)
        self.spin_bpm.setValue(self.current_bpm) 
        self.spin_bpm.valueChanged.connect(self.update_song_bpm)
        bpm_layout.addWidget(self.spin_bpm)
        bpm_layout.addStretch()
        main_layout.addLayout(bpm_layout)
        main_layout.addSpacing(10)
        
        # --- AUDIO TRACKS ---
        self.audio_label = QLabel("Tracce Audio")
        main_layout.addWidget(self.audio_label)
        self.audio_list = QListWidget()
        self.audio_list.setContextMenuPolicy(Qt.ContextMenuPolicy.ActionsContextMenu)
        main_layout.addWidget(self.audio_list)
        
        btn_audio_layout = QHBoxLayout()
        btn_audio_layout.addWidget(QPushButton("Aggiungi traccia audio", clicked=self.add_audio))
        btn_audio_layout.addWidget(QPushButton("Rimuovi traccia audio", clicked=self.remove_audio))
        
        self.btn_edit_audio_output = QPushButton("Modifica Output/Canali")
        self.btn_edit_audio_output.clicked.connect(self.select_audio_output)
        btn_audio_layout.addWidget(self.btn_edit_audio_output)
        main_layout.addLayout(btn_audio_layout)

        # --- MIDI TRACKS ---
        self.midi_label = QLabel("Tracce MIDI")
        main_layout.addWidget(self.midi_label)
        self.midi_list = QListWidget()
        main_layout.addWidget(self.midi_list)

        btn_midi_layout = QHBoxLayout()
        btn_midi_layout.addWidget(QPushButton("Aggiungi traccia MIDI", clicked=self.add_midi))
        btn_midi_layout.addWidget(QPushButton("Rimuovi traccia MIDI", clicked=self.remove_midi))
        
        self.btn_edit_midi_output = QPushButton("Modifica Porta/Canale")
        self.btn_edit_midi_output.clicked.connect(self.select_midi_output)
        btn_midi_layout.addWidget(self.btn_edit_midi_output)
        main_layout.addLayout(btn_midi_layout)

        # --- NUOVO: VIDEO TRACK ---
        main_layout.addSpacing(10)
        self.video_label = QLabel("Traccia Video")
        main_layout.addWidget(self.video_label)
        
        video_layout = QHBoxLayout()
        self.video_path_input = QLineEdit()
        self.video_path_input.setReadOnly(True)
        self.video_path_input.setPlaceholderText("Nessun file video selezionato.")
        
        self.btn_load_video = QPushButton("Carica Video...")
        self.btn_clear_video = QPushButton("Rimuovi")
        
        self.btn_load_video.clicked.connect(self.load_video)
        self.btn_clear_video.clicked.connect(lambda: self.set_video_path(None))
        
        video_layout.addWidget(self.video_path_input)
        video_layout.addWidget(self.btn_load_video)
        video_layout.addWidget(self.btn_clear_video)
        main_layout.addLayout(video_layout)
        
        # --- LYRICS CONTROLS ---
        self.lyrics_label = QLabel("Lyrics")
        main_layout.addWidget(self.lyrics_label)

        lyrics_layout = QHBoxLayout()
        lyrics_buttons_layout = QVBoxLayout()
        
        self.btn_load_txt = QPushButton("Carica TXT", clicked=self.load_txt)
        self.btn_edit_lyrics = QPushButton("Modifica Lyrics", clicked=self.edit_lyrics)
        
        lyrics_buttons_layout.addWidget(self.btn_load_txt)
        lyrics_buttons_layout.addWidget(self.btn_edit_lyrics)
        lyrics_buttons_layout.addStretch()

        lyrics_layout.addLayout(lyrics_buttons_layout)
        main_layout.addLayout(lyrics_layout)

        # --- PLAYBACK CONTROLS ---
        main_layout.addSpacing(15)
        main_layout.addWidget(QLabel("Controlli Riproduzione"))

        playback_layout = QHBoxLayout()
        self.btn_play_song = QPushButton("PLAY ▶️", clicked=self.start_playback)
        self.btn_stop_song = QPushButton("STOP ⏹️", clicked=self.stop_playback)
        self.btn_prompt_lyrics = QPushButton("Visualizza Lyrics 🎤", clicked=self.open_lyrics_prompter)
        
        playback_layout.addWidget(self.btn_play_song)
        playback_layout.addWidget(self.btn_stop_song)
        playback_layout.addWidget(self.btn_prompt_lyrics)
        main_layout.addLayout(playback_layout)

        # --- MIDI Monitor ---
        main_layout.addSpacing(10)
        
        # --- SAVE ---
        main_layout.addWidget(QPushButton("SALVA CANZONE", clicked=self.save_song))
        
        self.update_playback_buttons()

    def update_song_bpm(self, new_bpm):
        """Aggiorna il BPM nella cache del DataManager per la traccia audio 0."""
        self.current_bpm = new_bpm
        audio_tracks = self.data_manager.audio_tracks.get(self.song_name, [])
        if audio_tracks:
            self.data_manager.update_audio_track_output(
                self.song_name, 
                0, 
                audio_tracks[0].get("output"), 
                audio_tracks[0].get("channels_used"),
                audio_tracks[0].get("output_start_channel"),
                bpm=new_bpm
            )

    # -------------------------------------------------------------
    # GESTIONE DATI E CARICAMENTO
    # -------------------------------------------------------------
    def load_song(self):
        """Carica i dati della canzone dal DataManager e aggiorna la UI."""
        song_data = self.data_manager.load_song(self.song_name) 
        if not song_data:
            song_data = {
                "audio_tracks": [],
                "midi_tracks": [],
                "lyrics": [],
                "lyrics_txt": None,
                "video_file": None 
            }

        # --- AUDIO LIST ---
        self.audio_list.clear()
        self.data_manager.audio_tracks[self.song_name] = song_data.get("audio_tracks", [])
        
        self.audio_engine.tracks.pop(self.song_name, None)
        
        self.current_bpm = 120.0
        audio_tracks = self.data_manager.audio_tracks.get(self.song_name, [])

        if audio_tracks:
             self.current_bpm = audio_tracks[0].get("bpm", 120.0)

        if hasattr(self, 'spin_bpm'):
             self.spin_bpm.setValue(self.current_bpm)
        
        for i, t in enumerate(audio_tracks):
            output_name = "Sconosciuto"
            output_channels_count = 0
            
            for dev in self.audio_engine.outputs:
                if dev["index"] == t.get("output"):
                    output_name = dev['name']
                    output_channels_count = dev['channels']
                    break
            
            track_channels_used = t.get("channels_used", 1)
            output_start_channel = t.get("output_start_channel", 1) 
            bpm_info = f" | BPM: {t.get('bpm', 'N/D')}" if i == 0 else ""

            self.audio_engine.add_track(
                self.song_name, 
                t['file'], 
                t.get("output"), 
                channels_used=track_channels_used, 
                output_start_channel=output_start_channel
            )

            channel_range = f"{output_start_channel}"
            if track_channels_used > 1:
                 channel_range += f"-{output_start_channel + track_channels_used - 1}"
            elif output_start_channel != 1:
                 channel_range = f"{output_start_channel}"


            # Utilizza os.sep per uno split più robusto sui percorsi locali
            file_name = t['file'].split(os.sep)[-1]

            self.audio_list.addItem(
                f"{file_name} -> Output: {output_name} ({output_channels_count} ch) | Canali Sorgente Usati: {track_channels_used} -> Output Ch: {channel_range}{bpm_info}"
            )

        # --- MIDI LIST ---
        self.midi_list.clear()
        self.data_manager.midi_tracks[self.song_name] = song_data.get("midi_tracks", [])
        
        self.midi_engine.tracks.pop(self.song_name, None)
        
        for t in self.data_manager.midi_tracks.get(self.song_name, []):
             
             self.midi_engine.add_track(
                 self.song_name, 
                 t.get('channel'), 
                 t.get('port'),
                 file_path=t.get('file') 
             )
            
             midi_file_info = ""
             if t.get('file'):
                  # Utilizza os.sep per uno split più robusto sui percorsi locali
                  file_name = t['file'].split(os.sep)[-1]
                  midi_file_info = f"File: {file_name} | "
                 
             self.midi_list.addItem(f"{midi_file_info}Porta: {t['port']} | Canale MIDI: {t['channel']}")
        
        # --- VIDEO TRACK ---
        self.video_file = song_data.get("video_file", None)
        if hasattr(self, 'video_path_input'): 
            self.set_video_path(self.video_file, update_data_manager=False)


        # --- LYRICS LABEL ---
        lyrics_txt = song_data.get("lyrics_txt")
        if lyrics_txt:
            self.loaded_txt_file = lyrics_txt
            self.lyrics_label.setText(f"Lyrics (file caricato: {lyrics_txt})")
        else:
            self.lyrics_label.setText("Lyrics (nessun file caricato)")

        self.update_playback_buttons()


    def save_song(self):
        """Salva tutti i dati della canzone, inclusi i lyrics aggiornati."""
        lyrics_data, txt_file = self.data_manager.get_lyrics_with_txt(self.song_name)
        video_file = self.data_manager.get_video_file(self.song_name) 

        song_data = {
            "name": self.song_name,
            "audio_tracks": self.data_manager.audio_tracks.get(self.song_name, []),
            "midi_tracks": self.data_manager.midi_tracks.get(self.song_name, []),
            "video_file": video_file, 
            "lyrics": lyrics_data,
            "lyrics_txt": txt_file
        }

        self.data_manager.save_song(self.song_name, song_data)


    # -------------------------------------------------------------
    # GESTIONE TRACCE VIDEO
    # -------------------------------------------------------------
    def load_video(self):
        """Apre il dialogo per selezionare e impostare un file video."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona file Video",
            filter="Video Files (*.mp4 *.avi *.mov *.mkv *.webm)" 
        )
        if file_path:
            self.set_video_path(file_path)
            # AGGIUNTO: Ricarica la canzone per aggiornare il percorso video con quello stabile (copiato)
            self.load_song()

    def set_video_path(self, file_path: str | None, update_data_manager: bool = True):
        """Aggiorna la UI e lo stato del file video."""
        self.video_file = file_path
        
        if file_path:
            # Usiamo os.sep per il path splitting che è più robusto di '/'
            display_text = file_path.split(os.sep)[-1]
            self.video_path_input.setText(display_text)
            self.video_path_input.setToolTip(file_path)
            self.video_label.setStyleSheet("font-weight: bold; color: white;") 
        else:
            self.video_path_input.clear()
            self.video_path_input.setPlaceholderText("Nessun file video selezionato.")
            self.video_path_input.setToolTip("")
            self.video_label.setStyleSheet("font-weight: bold; color: white;") 

        if update_data_manager:
            # Chiama il set_video_file su DataManager, che ora si occupa della copia
            self.data_manager.set_video_file(self.song_name, file_path)


    # -------------------------------------------------------------
    # GESTIONE TRACCE AUDIO
    # -------------------------------------------------------------
    def add_audio(self):
        """Apre il dialogo per selezionare e aggiungere una nuova traccia audio."""
        files, _ = QFileDialog.getOpenFileNames(self, "Seleziona file audio")
        if not files:
            return

        for f in files:
            try:
                info = sf.info(f)
                required_channels = info.channels
            except Exception as e:
                print(f"Errore lettura file audio: {e}")
                continue

            default_output_index = -1
            default_channels_used = required_channels
            default_output_start_channel = 1 
            
            for dev in self.audio_engine.outputs:
                if dev['channels'] >= required_channels:
                    default_output_index = dev['index']
                    default_channels_used = required_channels
                    default_output_start_channel = 1
                    break
            
            if default_output_index == -1 and self.audio_engine.outputs:
                default_output_index = self.audio_engine.outputs[0]['index']
                default_channels_used = min(required_channels, self.audio_engine.outputs[0]['channels'])
                default_output_start_channel = 1
                print("Attenzione: Nessun output audio perfettamente compatibile trovato. Usando il primo disponibile.")
                
            if default_output_index != -1:
                current_audio_tracks_count = len(self.data_manager.audio_tracks.get(self.song_name, []))
                bpm_to_save = self.current_bpm if current_audio_tracks_count == 0 else None
                
                # add_audio_track ora si occupa di COPIARE il file e salvare il nuovo percorso
                self.data_manager.add_audio_track(
                    self.song_name, 
                    f, 
                    default_output_index, 
                    channels=required_channels,
                    channels_used=default_channels_used,
                    output_start_channel=default_output_start_channel,
                    bpm=bpm_to_save
                )
            
        self.load_song()

    def remove_audio(self):
        """Rimuove la traccia audio selezionata."""
        current = self.audio_list.currentRow()
        if current >= 0:
            self.data_manager.remove_audio_track(self.song_name, current)
            self.audio_engine.remove_track(self.song_name, current)
            self.load_song()

    def select_audio_output(self):
        """Abre un dialogo per selezionare l'output device, i canali sorgente usati e il canale di partenza sull'output per la traccia selezionata."""
        current = self.audio_list.currentRow()
        if current < 0:
            return

        audio_tracks = self.data_manager.audio_tracks.get(self.song_name, [])
        if not audio_tracks or current >= len(audio_tracks): return
        
        track = audio_tracks[current]
        required_channels = track["channels"]
        current_output_index = track.get("output")
        current_channels_used = track.get("channels_used", 1)
        current_output_start_channel = track.get("output_start_channel", 1)

        # 1. Selezione Output Device
        output_options = []
        for dev in self.audio_engine.outputs:
            is_compatible = dev['channels'] >= required_channels
            name = f"{dev['index']} - {dev['name']} ({dev['channels']} ch)"
            if not is_compatible:
                 name += f" [Attenzione: Canali file {required_channels}]"
            output_options.append(name)
        
        if not output_options:
            QInputDialog.getText(self, "Errore", "Nessun dispositivo audio trovato.")
            return

        default_output_index = -1
        for i, opt in enumerate(output_options):
            if opt.startswith(f"{current_output_index} - "):
                default_output_index = i
                break

        output_selected, ok = QInputDialog.getItem(
            self,
            "Seleziona Output Audio",
            f"Seleziona dispositivo per '{track['file'].split(os.sep)[-1]}':",
            output_options,
            editable=False,
            current=default_output_index if default_output_index >= 0 else 0
        )
        
        if not ok or not output_selected:
            return

        output_index = int(output_selected.split(" - ")[0])
        selected_dev = next(d for d in self.audio_engine.outputs if d['index'] == output_index)
        max_available_channels = selected_dev['channels']
        
        mappable_channels = min(required_channels, max_available_channels)
        
        # 2. Selezione Canali da Utilizzare
        channels_options = [str(i) for i in range(1, mappable_channels + 1)]
        if not channels_options: channels_options = ['1']
        
        default_channels_used_index = max(0, current_channels_used - 1)
        
        channels_used_str, ok_channels = QInputDialog.getItem(
            self,
            "Seleziona Canali Sorgente Usati",
            f"Quanti canali sorgente utilizzare (Max: {mappable_channels})?",
            channels_options,
            editable=False,
            current=default_channels_used_index
        )
        
        if not ok_channels or not channels_used_str:
            return
            
        channels_used = int(channels_used_str)
        
        # 3. Selezione Canale di Partenza sull'Output Device
        max_start_channel = max_available_channels - channels_used + 1
        start_channel_options = [str(i) for i in range(1, max_start_channel + 1)]
        if not start_channel_options: start_channel_options = ['1']
        
        default_start_channel_index = max(0, current_output_start_channel - 1)
        if default_start_channel_index >= len(start_channel_options):
             default_start_channel_index = 0

        start_channel_str, ok_start_channel = QInputDialog.getItem(
            self,
            "Seleziona Canale di Partenza",
            f"Canale di partenza sull'output device (usa {channels_used} canali):",
            start_channel_options,
            editable=False,
            current=default_start_channel_index
        )

        if ok_start_channel and start_channel_str:
            output_start_channel = int(start_channel_str)
            
            # 4. Aggiorna DataManager e AudioEngine
            bpm_to_save = self.current_bpm if current == 0 else None
            
            self.data_manager.update_audio_track_output(
                self.song_name, 
                current, 
                output_index, 
                channels_used,
                output_start_channel,
                bpm=bpm_to_save
            )
            self.audio_engine.update_track_output(
                self.song_name, 
                current, 
                output_index,
                channels_used,
                output_start_channel
            )
            self.load_song()


    # -------------------------------------------------------------
    # GESTIONE TRACCE MIDI
    # -------------------------------------------------------------
    def add_midi(self):
        """Apre il dialogo per selezionare il file, la porta e aggiunge una traccia MIDI."""
        
        # 1. SELEZIONE FILE MIDI
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleziona file MIDI",
            filter="MIDI Files (*.mid *.midi)" 
        )
        if not file_path:
            return
            
        file_name = file_path.split(os.sep)[-1]

        # 2. SELEZIONE PORTA E CANALE
        next_channel = (self.midi_list.count() % 16) + 1
        
        port_options = self.midi_engine.outputs
        if not port_options:
            QMessageBox.warning(self, "Attenzione", "Nessuna porta MIDI trovata. Impossibile aggiungere la traccia.")
            return

        port_name, ok = QInputDialog.getItem(
            self,
            "Seleziona Porta MIDI",
            f"Seleziona porta per il file '{file_name}' (Canale suggerito: {next_channel}):",
            port_options,
            editable=False
        )
        
        if ok and port_name:
            # 3. Aggiorna DataManager (add_midi_track ora si occupa della copia del file)
            self.data_manager.add_midi_track(self.song_name, next_channel, port_name, file_path=file_path)
            self.load_song()
            
            QMessageBox.information(self, "Importazione MIDI", 
                "Il percorso del file MIDI è stato salvato. La riproduzione sincronizzata è in modalità sperimentale e il monitor MIDI ti aiuterà a capire cosa viene inviato.")


    def remove_midi(self):
        """Rimuove la traccia MIDI selezionata."""
        current = self.midi_list.currentRow()
        if current >= 0:
            self.data_manager.remove_midi_track(self.song_name, current)
            self.midi_engine.remove_track(self.song_name, current)
            self.load_song()

    def select_midi_output(self):
        """Apre un dialogo per selezionare la porta e il canale per la traccia MIDI selezionata."""
        current = self.midi_list.currentRow()
        if current < 0:
            return

        midi_tracks = self.data_manager.midi_tracks.get(self.song_name, [])
        if not midi_tracks or current >= len(midi_tracks): return

        # 1. Selezione Porta
        port_options = self.midi_engine.outputs
        if not port_options:
            QInputDialog.getText(self, "Errore", "Nessuna porta MIDI trovata.")
            return
            
        new_port, ok_port = QInputDialog.getItem(
            self,
            "Modifica Porta MIDI",
            f"Seleziona nuova porta per la traccia:",
            port_options,
            editable=False
        )
        
        # 2. Selezione Canale
        channel_options = [str(i) for i in range(1, 17)]
        new_channel_str, ok_channel = QInputDialog.getItem(
            self,
            "Modifica Canale MIDI",
            f"Seleziona nuovo canale MIDI (1-16):",
            channel_options,
            editable=False
        )

        if ok_port and new_port and ok_channel and new_channel_str:
            new_channel = int(new_channel_str)
            
            # 3. Aggiorna DataManager e MidiEngine
            self.data_manager.update_midi_track_output(
                self.song_name, 
                current, 
                new_port, 
                new_channel
            )
            self.midi_engine.update_track_output(
                self.song_name, 
                current, 
                new_port, 
                new_channel
            )
            self.load_song()

    # -------------------------------------------------------------
    # GESTIONE LYRICS
    # -------------------------------------------------------------
    def load_txt(self):
        """Carica un file TXT e inizializza la struttura lyrics con timestamp 0.0."""
        file_path, _ = QFileDialog.getOpenFileNames(
            self,
            "Seleziona file TXT",
            filter="Text Files (*.txt)"
        )
        if not file_path:
            return

        file_name = file_path[0].split(os.sep)[-1]

        with open(file_path[0], "r", encoding="utf-8") as f:
            lyrics_data = [
                {"line": line.strip(), "time": 0.0}
                for line in f.readlines()
                if line.strip()
            ]

        self.data_manager.save_lyrics(self.song_name, lyrics_data)
        self.data_manager.set_lyrics_txt_file(self.song_name, file_name)

        # Aggiorna il file .scn con tutti i dati
        song_data = {
            "name": self.song_name,
            "audio_tracks": self.data_manager.audio_tracks.get(self.song_name, []),
            "midi_tracks": self.data_manager.midi_tracks.get(self.song_name, []),
            "video_file": self.data_manager.get_video_file(self.song_name), 
            "lyrics": lyrics_data,
            "lyrics_txt": file_name
        }
        self.data_manager.save_song(self.song_name, song_data)

        self.loaded_txt_file = file_name
        self.lyrics_label.setText(f"Lyrics (file caricato: {file_name})")
        
        self.update_playback_buttons()


    def edit_lyrics(self):
        """Avvia la finestra di editing lyrics (LyricsEditorWindow)."""
        lyrics_data, txt_file = self.data_manager.get_lyrics_with_txt(self.song_name)

        if not lyrics_data:
            QMessageBox.warning(self, "Attenzione", "Carica prima un file TXT con il testo.")
            return 

        lines = [l["line"] for l in lyrics_data]
        timestamps = [l["time"] for l in lyrics_data]

        audio_tracks = self.data_manager.audio_tracks.get(self.song_name, [])
        if not audio_tracks:
            QMessageBox.warning(self, "Attenzione", "Aggiungi una traccia audio (Master) per l'ascolto durante l'editing.")
            return

        audio_file = audio_tracks[0]["file"]

        editor = LyricsEditorWindow(
            audio_file=audio_file,
            text_lines=lines,
            timestamps=timestamps,
            parent=self
        )

        if editor.exec():
            new_lines = editor.text_lines
            new_times = editor.timestamps

            updated = [{"line": l, "time": t} for l, t in zip(new_lines, new_times)]
            self.data_manager.save_lyrics(self.song_name, updated)
            
            self.update_playback_buttons()


    # -------------------------------------------------------------
    # PLAYBACK
    # -------------------------------------------------------------
    
    def update_playback_buttons(self):
        """Abilita/Disabilita i pulsanti in base alla presenza di tracce e lyrics sincronizzati."""
        has_audio = len(self.data_manager.audio_tracks.get(self.song_name, [])) > 0
        has_midi = len(self.data_manager.midi_tracks.get(self.song_name, [])) > 0
        has_tracks = has_audio or has_midi
        
        lyrics_data, _ = self.data_manager.get_lyrics_with_txt(self.song_name)
        has_synced_lyrics = has_tracks and bool(lyrics_data)
        
        if hasattr(self, 'btn_play_song'):
             self.btn_play_song.setEnabled(has_tracks)
             self.btn_stop_song.setEnabled(has_tracks)
             self.btn_prompt_lyrics.setEnabled(has_synced_lyrics)


    def start_playback(self):
        """Avvia la riproduzione combinata (Audio/MIDI)."""
        audio_tracks = self.data_manager.audio_tracks.get(self.song_name, [])
        bpm_master = audio_tracks[0].get('bpm', 120.0) if audio_tracks else 120.0

        self.audio_engine.start_playback(self.song_name)
        self.midi_engine.start_playback(self.song_name, bpm=bpm_master)
        
        # --- GESTIONE VIDEO ---
        # Carica il video nel player per la sincronizzazione (lo stato è gestito dal player stesso tramite timer)
        if self.video_player:
             self.video_player.load_video_track(self.song_name, self.video_file)
        
        lyrics_data, _ = self.data_manager.get_lyrics_with_txt(self.song_name)
        has_lyrics = bool(lyrics_data)
        
        # Non creiamo il player, lo usiamo se iniettato
        if self.lyrics_player: 
             self.lyrics_player.set_lyrics_data(lyrics_data, self.song_name)
        
        self.update_playback_buttons()


    def stop_playback(self):
        """Ferma la riproduzione combinata (Audio/MIDI)."""
        
        self.audio_engine.stop_playback(self.song_name)
        self.midi_engine.stop_playback(self.song_name)
        
        # --- GESTIONE VIDEO ---
        # Lo stop deve essere chiamato sul player per pulire lo stato
        if self.video_player:
             # Richiamare load_video_track(None) non è necessario qui,
             # perché il sync_playback_state del VideoPlayerWidget gestisce l'arresto e il reset del frame.
             self.video_engine.stop()

        if self.lyrics_player: # Se il player è stato iniettato
            self.lyrics_player.set_lyrics_data([], "Riproduzione Ferma")
            
    def open_lyrics_prompter(self, force_show=False):
        """Avvia la finestra LyricsPlayerWindow per la visualizzazione sincronizzata."""
        song_name_to_prompt = self.song_name
        
        lyrics_data, _ = self.data_manager.get_lyrics_with_txt(song_name_to_prompt)
        has_lyrics = bool(lyrics_data)

        if not has_lyrics:
             QMessageBox.warning(self, "Attenzione", f"Il brano '{song_name_to_prompt}' non ha lyrics sincronizzati.")
             return

        # L'istanza è gestita esternamente (MainWindow), noi la aggiorniamo e attiviamo il tab
        if self.lyrics_player:
            self.lyrics_player.set_lyrics_data(lyrics_data, self.song_name)
            
            if self.parent() and hasattr(self.parent(), 'tab_widget'):
                # Attiva il tab che contiene l'istanza del player lyrics
                tab_index = self.parent().tab_widget.indexOf(self.lyrics_player)
                if tab_index != -1:
                     self.parent().tab_widget.setCurrentIndex(tab_index)
        
        self.update_playback_buttons()
        
    def closeEvent(self, event):
         self.stop_playback()
         super().closeEvent(event)