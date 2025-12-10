# core/data_manager.py
# Gestore Unificato per la persistenza di:
# 1. Modelli Fixture e Stato del Progetto DMX (Metodi statici/classe).
# 2. Canzoni, Playlist e Cache Media (Metodi di istanza).

import json
import os
from pathlib import Path
import shutil 
from core.dmx_models import FixtureModello, CanaleDMX, Scena, Chaser, PassoChaser
from core.project_models import Progetto, UniversoStato, IstanzaFixtureStato, MidiMapping

# --- DMX / Project Constants ---
DATA_PATH = Path(__file__).parent.parent / "data"
PROFILE_FILE = DATA_PATH / "fixture_profiles.json"
PROJECT_FILE = DATA_PATH / "project.json"

# [NUOVO] Costante per la porta interna (deve essere lo stesso di song_editor_widget.py)
INTERNAL_DMX_PORT = "INTERNAL_DMX_PORT_TRIGGER" 

class DataManager:
    """
    Gestore Unificato per la persistenza di:
    1. Modelli Fixture e Stato del Progetto DMX (Metodi statici/classe).
    2. Canzoni, Playlist e Cache Media (Metodi di istanza).
    """

    def __init__(self):
        # --- SCENOGRAFIA / MEDIA ATTRIBUTES ---
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
        
    # =============================================================
    # --- DMX / PROJECT / FIXTURE MODELS MANAGEMENT (STATIC) ---
    # =============================================================
    
    @staticmethod
    def _modello_to_dict(modello: FixtureModello) -> dict:
        canali = [
            {'nome': c.nome, 'funzione': c.funzione, 'default': c.valore_default}
            for c in modello.descrizione_canali
        ]
        return {
            'nome': modello.nome,
            'canali': canali
        }

    @staticmethod
    def _dict_to_modello(data: dict) -> FixtureModello:
        canali = [
            CanaleDMX(c['nome'], c['funzione'], c['default'])
            for c in data['canali']
        ]
        return FixtureModello(data['nome'], canali)

    @staticmethod
    def salva_modelli(modelli: list[FixtureModello]):
        """Salva i profili delle fixture su file JSON."""
        DATA_PATH.mkdir(exist_ok=True)
        data = [DataManager._modello_to_dict(m) for m in modelli]
        try:
            with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Errore durante il salvataggio dei modelli: {e}")

    @staticmethod
    def carica_modelli() -> list[FixtureModello]:
        """Carica i profili delle fixture da file JSON."""
        if not PROFILE_FILE.exists():
            return []
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [DataManager._dict_to_modello(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []
        except Exception as e:
            print(f"Errore inatteso durante il caricamento dei modelli: {e}")
            return []

    @staticmethod
    def salva_progetto(progetto: Progetto):
        """Salva l'intero stato del progetto nel file di default."""
        DataManager._save_project_to_path(progetto, str(PROJECT_FILE))
        print(f"Progetto salvato in {PROJECT_FILE}")

    @staticmethod
    def carica_progetto() -> Progetto:
        """Carica lo stato del progetto. Se non esiste, crea un progetto vuoto."""
        if not PROJECT_FILE.exists():
            return Progetto.crea_vuoto()
        
        try:
            return DataManager._load_project_from_path(str(PROJECT_FILE))
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"Errore durante il caricamento del progetto. Creazione progetto vuoto. Errore: {e}")
            return Progetto.crea_vuoto()

    # --- METODI PER SALVATAGGIO/CARICAMENTO ARBITRARIO (USATI DAL MENU FILE) ---

    @staticmethod
    def _save_project_to_path(progetto: Progetto, path: str):
        """Salva l'intero stato del progetto su un percorso file arbitrario."""
        data_to_save = {
            "universi": [
                {
                    'id': u_stato.id_universo,
                    'nome': u_stato.nome,
                    'istanze': [
                        {'modello_nome': i.modello_nome, 'addr': i.indirizzo_inizio, 'x': i.x, 'y': i.y, 'nome_utente': i.nome_utente}
                        for i in u_stato.istanze_stato
                    ],
                    'scene': [
                        {'nome': s.nome, 'valori_canali': s.valori_canali}
                        for s in u_stato.scene
                    ],
                    'chasers': [
                        {
                            'nome': c.nome,
                            'passi': [
                                {
                                    'scena_nome': p.scena.nome,
                                    'tempo_permanenza': p.tempo_permanenza,
                                    'tempo_fade_in': p.tempo_fade_in,
                                    'tempo_fade_out': p.tempo_fade_out
                                }
                                for p in c.passi
                            ]
                        }
                        for c in u_stato.chasers
                    ],
                    'midi_mappings': [
                        {
                            'midi_type': m.midi_type,
                            'midi_number': m.midi_number,
                            'value': m.value,
                            'action_type': m.action_type,
                            'action_index': m.action_index,
                            'internal_only': getattr(m, 'internal_only', False) # AGGIUNTO per salvare il nuovo flag
                        }
                        for m in u_stato.midi_mappings
                    ],
                    'midi_channel': u_stato.midi_channel,
                    'midi_controller_port_name': u_stato.midi_controller_port_name,
                    'dmx_port_name': u_stato.dmx_port_name
                }
                for u_stato in progetto.universi_stato
            ]
        }
        
        # Gestione del file di output (creazione della directory se necessario)
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
        except Exception as e:
            raise Exception(f"Errore durante il salvataggio del progetto DMX: {e}")

    @staticmethod
    def _load_project_from_path(path: str) -> Progetto:
        """Carica un nuovo stato di progetto DMX da un percorso file arbitrario."""
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                 raise ValueError("Il file di progetto è vuoto.")
            data = json.loads(content)
                
        universi_stato = []
        
        for u_data in data.get("universi", []):
            # Ricostruzione istanze
            istanze_stato = [
                IstanzaFixtureStato(
                    modello_nome=i['modello_nome'], 
                    indirizzo_inizio=i['addr'], 
                    x=i['x'], 
                    y=i['y'],
                    nome_utente=i.get('nome_utente', "")
                ) 
                for i in u_data.get('istanze', [])
            ]
            
            # Ricostruzione scene
            scene_list = [
                Scena(s['nome'], {int(k): v for k, v in s['valori_canali'].items()})
                for s in u_data.get('scene', [])
            ]
            scene_map = {s.nome: s for s in scene_list}
            
            # Ricostruzione chasers
            chasers_list = []
            for c_data in u_data.get('chasers', []):
                passi = []
                for p_data in c_data.get('passi', []):
                    scena_nome = p_data.get('scena_nome')
                    scena = scene_map.get(scena_nome)
                    if scena:
                        passi.append(PassoChaser(
                            scena=scena, 
                            tempo_permanenza=p_data.get('tempo_permanenza', 1.0), 
                            tempo_fade_in=p_data.get('tempo_fade_in', 0.0), 
                            tempo_fade_out=p_data.get('tempo_fade_out', 0.0)
                        ))
                if passi: 
                    chasers_list.append(Chaser(nome=c_data.get('nome', "Sequenza Senza Nome"), passi=passi))

            # Ricostruzione midi mappings
            midi_mappings_list = [
                MidiMapping(
                    midi_type=m_data.get('midi_type', 'note'),
                    midi_number=m_data.get('midi_number', 0),
                    value=m_data.get('value', 0),
                    action_type=m_data.get('action_type', 'stop'),
                    action_index=m_data.get('action_index', -1),
                    internal_only=m_data.get('internal_only', False) # AGGIUNTO per caricare il nuovo flag
                )
                for m_data in u_data.get('midi_mappings', [])
            ]

            universi_stato.append(UniversoStato(
                id_universo=u_data.get('id', 1),
                nome=u_data.get('nome', "Universo Senza Nome"),
                istanze_stato=istanze_stato,
                scene=scene_list,
                chasers=chasers_list,
                midi_mappings=midi_mappings_list,
                midi_channel=u_data.get('midi_channel', 0),
                midi_controller_port_name=u_data.get('midi_controller_port_name', ""),
                dmx_port_name=u_data.get('dmx_port_name', "COM5")
            ))
            
        if not universi_stato:
             return Progetto.crea_vuoto()
             
        return Progetto(universi_stato=universi_stato)

    # --- METODO AGGIUNTO: Copia file ---
    def _copy_file_to_song_folder(self, song_name: str, source_path: str) -> str:
        """Copia il file sorgente in una sottocartella dedicata alla canzone e restituisce il nuovo percorso assoluto."""
        song_media_dir = Path(self.songs_dir) / song_name
        song_media_dir.mkdir(exist_ok=True) # Crea la cartella data/songs/[song_name]/

        file_name = Path(source_path).name
        destination_path = song_media_dir / file_name
        
        # Copia il file solo se la sorgente non è già la destinazione
        if Path(source_path).resolve() != destination_path.resolve():
            try:
                # Usa shutil.copy2 per preservare i metadati
                shutil.copy2(source_path, destination_path)
                print(f"File copiato in: {destination_path}")
            except Exception as e:
                print(f"ATTENZIONE: Errore durante la copia del file {source_path}: {e}")
                # In caso di errore di copia, restituisce il percorso originale
                return source_path

        # Restituisce il percorso assoluto della copia locale
        return str(destination_path.resolve())


    # --- GESTIONE CANZONI / PLAYLISTS (Metodi di istanza) ---
    
    def get_songs(self):
        """Restituisce la lista dei nomi delle canzoni salvate."""
        if not os.path.exists(self.songs_dir):
            os.makedirs(self.songs_dir, exist_ok=True)
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
        # Aggiunta la chiave "video_file"
        data = {"name": name, "audio_tracks": [], "midi_tracks": [], "video_file": None, "lyrics": [], "lyrics_txt": None}
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
        # Il campo video_file viene caricato e rimane nel dizionario data
        
        if "video_file" not in data:
            data["video_file"] = None

        return data

    def save_song(self, name, data=None):
        """Salva lo stato corrente della canzone sul file .scn."""
        path = os.path.join(self.songs_dir, f"{name}{self.song_extension}")

        if data is None:
            
            # --- FIX: Evita l'auto-sovrascrittura della cache (self.midi_tracks) ---
            # 1. Ottieni i metadati non gestiti dalla cache (video_file, lyrics_txt)
            current_metadata = {}
            if os.path.exists(path):
                 with open(path, "r", encoding="utf-8") as f:
                     try:
                         # Non vogliamo chiamare load_song qui, quindi leggiamo solo i metadati dal file
                         file_content = json.load(f)
                         current_metadata["video_file"] = file_content.get("video_file", None)
                         current_metadata["lyrics_txt"] = file_content.get("lyrics_txt", None)
                     except json.JSONDecodeError:
                          pass

            # 2. Ricostruisci il dizionario "data" usando la cache in-memory aggiornata 
            #    e i metadati appena letti dal disco.
            data = {
                "name": name,
                "audio_tracks": self.audio_tracks.get(name, []), 
                "midi_tracks": self.midi_tracks.get(name, []),   
                "video_file": current_metadata.get("video_file", None),
                "lyrics": self.lyrics.get(name, []),              
                "lyrics_txt": current_metadata.get("lyrics_txt", None)
            }
        
        # [ORIGINAL CODE - UPDATE CACHE IF 'data' ARGUMENT IS PROVIDED]
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
            
        # Pulisce anche la cartella media dedicata al brano
        song_media_dir = Path(self.songs_dir) / name
        if song_media_dir.exists() and song_media_dir.is_dir():
            try:
                shutil.rmtree(song_media_dir)
                print(f"Cartella media brano eliminata: {song_media_dir}")
            except Exception as e:
                print(f"ATTENZIONE: Impossibile eliminare la cartella media del brano {name}: {e}")
                

        self.audio_tracks.pop(name, None)
        self.midi_tracks.pop(name, None)
        self.lyrics.pop(name, None)

    # --- NUOVI METODI VIDEO ---
    def set_video_file(self, song_name: str, file_path: str | None):
        """Salva il percorso del file video, copiandolo localmente se necessario."""
        song_data = self.load_song(song_name)
        if song_data is None:
            return
            
        new_file_path = file_path
        if file_path:
             new_file_path = self._copy_file_to_song_folder(song_name, file_path) # Copia file

        song_data["video_file"] = new_file_path
        self.save_song(song_name, song_data)

    def get_video_file(self, song_name: str) -> str | None:
        """Restituisce il percorso del file video associato."""
        song_data = self.load_song(song_name)
        if not song_data:
            return None
        return song_data.get("video_file", None)
    # ---------------------------

    # --- GESTIONE TRACCE AUDIO ---
    def add_audio_track(self, song_name, file_path, output_index=0, channels=2, channels_used=2, output_start_channel=1, bpm=None):
        """Aggiunge una traccia audio con i dettagli dei canali usati e il BPM, copiando il file localmente."""
        
        new_file_path = self._copy_file_to_song_folder(song_name, file_path) # Copia file

        self.audio_tracks.setdefault(song_name, []).append({
            "file": new_file_path, # Usa il nuovo percorso
            "output": output_index,
            "channels": channels,         
            "channels_used": channels_used, 
            "output_start_channel": output_start_channel, 
            "bpm": bpm 
        })
        self.save_song(song_name)

    def remove_audio_track(self, song_name, index):
        """Rimuove una traccia audio dall'array in cache."""
        if song_name in self.audio_tracks and 0 <= index < len(self.audio_tracks[song_name]):
            self.audio_tracks[song_name].pop(index)
            self.save_song(song_name)

    def update_audio_track_output(self, song_name, index, output_index, channels_used, output_start_channel=1, bpm=None):
        """Aggiorna l'output, i canali utilizzati e il BPM per una traccia audio specifica."""
        
        # 1. Load full state from disk (and update cache)
        song_data = self.load_song(song_name)
        if song_data is None: return

        # 2. Update the in-memory cache with the specific change
        if song_name in self.audio_tracks and 0 <= index < len(self.audio_tracks[song_name]):
            track = self.audio_tracks[song_name][index]
            track["output"] = output_index
            track["channels_used"] = channels_used
            track["output_start_channel"] = output_start_channel
            if bpm is not None:
                 track["bpm"] = bpm 
                 
            # Update the full data object with the new cache content
            song_data["audio_tracks"] = self.audio_tracks.get(song_name, [])
            
            # 3. Save the full data explicitly
            self.save_song(song_name, song_data)


    # --- GESTIONE TRACCE MIDI ---
    def add_midi_track(self, song_name, channel, port=None, file_path=None):
        """Aggiunge una traccia MIDI con percorso del file, copiando il file localmente."""
        
        # [MODIFICATO] Solo copia se la porta NON è la porta interna
        new_file_path = file_path
        if file_path and port != INTERNAL_DMX_PORT:
            new_file_path = self._copy_file_to_song_folder(song_name, file_path) # Copia file
            
        self.midi_tracks.setdefault(song_name, []).append({
            "file": new_file_path, # Usa il nuovo percorso
            "channel": channel, 
            "port": port
        })
        self.save_song(song_name)

    def remove_midi_track(self, song_name, index):
        """Rimuove una traccia MIDI dall'array in cache."""
        if song_name in self.midi_tracks and 0 <= index < len(self.midi_tracks[song_name]):
            self.midi_tracks[song_name].pop(index)
            self.save_song(song_name)

    def update_midi_track_output(self, song_name, index, port_name, channel):
        """Aggiorna la porta e il canale per una traccia MIDI specifica."""
        
        # 1. Load full state from disk (and update cache)
        song_data = self.load_song(song_name)
        if song_data is None: return

        # 2. Update the in-memory cache with the specific change
        if song_name in self.midi_tracks and 0 <= index < len(self.midi_tracks[song_name]):
            self.midi_tracks[song_name][index]["port"] = port_name
            self.midi_tracks[song_name][index]["channel"] = channel
            
            # Update the full data object with the new cache content
            song_data["midi_tracks"] = self.midi_tracks.get(song_name, [])
            
            # 3. Save the full data explicitly
            self.save_song(song_name, song_data)


    # --- GESTIONE LYRICS ---
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

        if lyrics and isinstance(lyrics[0], str):
            lyrics = [{"line": l, "time": 0.0} for l in lyrics]

        return lyrics, txt

    # --- GESTIONE PLAYLISTS ---
    def get_playlists(self):
        """Restituisce la lista dei nomi delle playlist."""
        if not os.path.exists(self.playlists_dir):
            os.makedirs(self.playlists_dir, exist_ok=True)
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