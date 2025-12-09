# data_manager.py
# Gestore di persistenza per Canzoni (.scn), Playlist e Lyrics (dal progetto Scenografia).

import os
import json

class DataManager:
    """
    Gestisce la persistenza dei dati: canzoni (.scn), playlist e impostazioni in-memory.
    """
    def __init__(self):
        # Manteniamo la logica originale per i percorsi (anche se la root è cambiata, 
        # i percorsi relativi interni rimangono coerenti se la struttura data/ è mantenuta)
        self.base_dir = os.path.join(os.getcwd(), "data")
        self.songs_dir = os.path.join(self.base_dir, "songs")
        self.playlists_dir = os.path.join(self.base_dir, "playlists")
        self.song_extension = ".scn"

        os.makedirs(self.songs_dir, exist_ok=True)
        os.makedirs(self.playlists_dir, exist_ok=True)

        # Cache in-memory
        self.audio_tracks = {}
        self.midi_tracks = {}
        self.lyrics = {}

    # -------------------------------------------------------------
    # GESTIONE CANZONI (.SCN)
    # -------------------------------------------------------------
    
    def get_songs(self):
        """Restituisce la lista dei nomi delle canzoni salvate."""
        return [
            f.rsplit(".", 1)[0]
            for f in os.listdir(self.songs_dir)
            if f.endswith(self.song_extension)
        ]

    def create_song(self, name):
        """Crea un nuovo file .scn con la struttura base."""
        path = os.path.join(self.songs_dir, f"{name}{self.song_extension}")
        if os.path.exists(path):
            return False
        data = {"name": name, "audio_tracks": [], "midi_tracks": [], "lyrics": [], "lyrics_txt": None}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        self.audio_tracks[name] = []
        self.midi_tracks[name] = []
        self.lyrics[name] = []
        return True

    def load_song(self, name):
        """Carica i dati della canzone dal file .scn e li mette in cache."""
        path = os.path.join(self.songs_dir, f"{name}{self.song_extension}")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"Errore lettura file JSON {name}: {e}")
            return None
            
        self.audio_tracks[name] = data.get("audio_tracks", [])
        self.midi_tracks[name] = data.get("midi_tracks", [])
        self.lyrics[name] = data.get("lyrics", [])
        return data

    def save_song(self, name, data=None):
        """Salva lo stato corrente della canzone sul file .scn."""
        if data is None:
            # Recupera i dati correnti dalla cache
            data = {
                "name": name,
                "audio_tracks": self.audio_tracks.get(name, []),
                "midi_tracks": self.midi_tracks.get(name, []),
                "lyrics": self.lyrics.get(name, []),
                "lyrics_txt": self.get_lyrics_txt_file(name)
            }
        path = os.path.join(self.songs_dir, f"{name}{self.song_extension}")
        
        # Aggiorna la cache con i dati che vengono salvati
        if "audio_tracks" in data:
            self.audio_tracks[name] = data["audio_tracks"]
        if "midi_tracks" in data:
            self.midi_tracks[name] = data["midi_tracks"]
        if "lyrics" in data:
            self.lyrics[name] = data["lyrics"]

        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
             print(f"Errore durante il salvataggio del file {name}: {e}")

    def delete_song(self, name):
        """Elimina il file .scn e i dati dalla cache."""
        path = os.path.join(self.songs_dir, f"{name}{self.song_extension}")
        if os.path.exists(path):
            os.remove(path)
        self.audio_tracks.pop(name, None)
        self.midi_tracks.pop(name, None)
        self.lyrics.pop(name, None)

    # -------------------------------------------------------------
    # GESTIONE TRACCE AUDIO
    # -------------------------------------------------------------
    
    def add_audio_track(self, song_name, file_path, output_index=0, channels=2, channels_used=2, output_start_channel=1, bpm=None):
        """Aggiunge una traccia audio con i dettagli dei canali usati e il BPM."""
        self.audio_tracks.setdefault(song_name, []).append({
            "file": file_path,
            "output": output_index,
            "channels": channels,         # Canali originali del file
            "channels_used": channels_used, # Canali effettivamente mappati
            "output_start_channel": output_start_channel, # Canale di partenza sull'output device
            "bpm": bpm # NUOVO: BPM specifico del brano (solo per traccia 0 se necessario)
        })
        self.save_song(song_name)

    def remove_audio_track(self, song_name, index):
        """Rimuove una traccia audio dall'array in cache."""
        if song_name in self.audio_tracks and 0 <= index < len(self.audio_tracks[song_name]):
            self.audio_tracks[song_name].pop(index)
            self.save_song(song_name)

    def update_audio_track_output(self, song_name, index, output_index, channels_used, output_start_channel=1, bpm=None):
        """Aggiorna l'output, i canali utilizzati e il BPM per una traccia audio specifica."""
        if song_name in self.audio_tracks and 0 <= index < len(self.audio_tracks[song_name]):
            track = self.audio_tracks[song_name][index]
            track["output"] = output_index
            track["channels_used"] = channels_used
            track["output_start_channel"] = output_start_channel
            if bpm is not None:
                 track["bpm"] = bpm # Aggiorna BPM se specificato
            self.save_song(song_name)

    # -------------------------------------------------------------
    # GESTIONE TRACCE MIDI
    # -------------------------------------------------------------
    
    # MODIFICATO: Aggiunto l'argomento 'file_path'
    def add_midi_track(self, song_name, channel, port=None, file_path=None):
        """Aggiunge una traccia MIDI con percorso del file."""
        # Aggiungi "file" al dizionario della traccia MIDI
        self.midi_tracks.setdefault(song_name, []).append({"file": file_path, "channel": channel, "port": port})
        self.save_song(song_name)

    def remove_midi_track(self, song_name, index):
        """Rimuove una traccia MIDI dall'array in cache."""
        if song_name in self.midi_tracks and 0 <= index < len(self.midi_tracks[song_name]):
            self.midi_tracks[song_name].pop(index)
            self.save_song(song_name)

    def update_midi_track_output(self, song_name, index, port_name, channel):
        """Aggiorna la porta e il canale per una traccia MIDI specifica."""
        if song_name in self.midi_tracks and 0 <= index < len(self.midi_tracks[song_name]):
            self.midi_tracks[song_name][index]["port"] = port_name
            self.midi_tracks[song_name][index]["channel"] = channel
            self.save_song(song_name)

    # -------------------------------------------------------------
    # GESTIONE LYRICS
    # -------------------------------------------------------------
    
    def save_lyrics(self, song_name: str, lyrics_list: list[dict]):
        """Salva le lyrics aggiornate (formato con timestamp) sul file .scn."""
        song_data = self.load_song(song_name)
        if song_data is None:
            return

        song_data["lyrics"] = lyrics_list
        self.lyrics[song_name] = lyrics_list
        self.save_song(song_name, song_data)

    def set_lyrics_txt_file(self, song_name: str, filename: str):
        """Salva il nome del file TXT originale associato ai lyrics."""
        song_data = self.load_song(song_name)
        if song_data is None:
            return

        song_data["lyrics_txt"] = filename
        self.save_song(song_name, song_data)

    def get_lyrics_txt_file(self, song_name: str):
        """Restituisce il nome del file txt associato."""
        song_data = self.load_song(song_name)
        if not song_data:
            return None

        return song_data.get("lyrics_txt", None)

    def get_lyrics_with_txt(self, song_name: str):
        """Restituisce i lyrics e il nome del file txt in una tupla."""
        song_data = self.load_song(song_name)
        if not song_data:
            return [], None

        lyrics = song_data.get("lyrics", [])
        txt = song_data.get("lyrics_txt", None)

        # Conversione da eventuale formato vecchio
        if lyrics and isinstance(lyrics[0], str):
            lyrics = [{"line": l, "time": 0.0} for l in lyrics]

        return lyrics, txt

    # -------------------------------------------------------------
    # GESTIONE PLAYLISTS
    # -------------------------------------------------------------

    def get_playlists(self):
        """Restituisce la lista dei nomi delle playlist."""
        return [
            f.rsplit(".", 1)[0]
            for f in os.listdir(self.playlists_dir)
            if f.endswith(".json")
        ]

    def create_playlist(self, name):
        """Crea un nuovo file .json per la playlist."""
        path = os.path.join(self.playlists_dir, f"{name}.json")
        if os.path.exists(path):
            return False
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"name": name, "songs": []}, f, indent=2)
        return True

    def load_playlist(self, name):
        """Carica i dati della playlist."""
        path = os.path.join(self.playlists_dir, f"{name}.json")
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_playlist(self, name, data):
        """Salva lo stato corrente della playlist."""
        path = os.path.join(self.playlists_dir, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def delete_playlist(self, name):
        """Elimina il file .json della playlist."""
        path = os.path.join(self.playlists_dir, f"{name}.json")
        if os.path.exists(path):
            os.remove(path)

    # --- METODI PER EDITING PLAYLIST ---

    def add_song_to_playlist(self, playlist_name, song_name):
        """Aggiunge un brano alla lista di canzoni della playlist."""
        playlist_data = self.load_playlist(playlist_name)
        if playlist_data and song_name not in playlist_data["songs"]:
            playlist_data["songs"].append(song_name)
            self.save_playlist(playlist_name, playlist_data)

    def remove_song_from_playlist(self, playlist_name, index):
        """Rimuove un brano dalla playlist tramite indice."""
        playlist_data = self.load_playlist(playlist_name)
        if playlist_data and 0 <= index < len(playlist_data["songs"]):
            playlist_data["songs"].pop(index)
            self.save_playlist(playlist_name, playlist_data)
            
    def update_playlist_songs(self, playlist_name, new_songs: list):
        """Sostituisce l'intera lista di brani della playlist (usato per il riordino)."""
        playlist_data = self.load_playlist(playlist_name)
        if playlist_data:
            playlist_data["songs"] = new_songs
            self.save_playlist(playlist_name, playlist_data)