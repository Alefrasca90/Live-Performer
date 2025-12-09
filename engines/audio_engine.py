# engines/audio_engine.py

import sounddevice as sd
import soundfile as sf
import threading
import time
import numpy as np
import os

class AudioEngine:
    """
    Gestisce la riproduzione audio multi-traccia in tempo reale.
    Funziona come master clock per la sincronizzazione MIDI e Lyrics.
    """

    def __init__(self):
        self.driver = None
        self.outputs = []
        # Struttura dati per le tracce: {song: [ {file, output, channels, channels_used, output_start_channel} ]}
        self.tracks = {}
        
        # --- PLAYBACK & SYNC ---
        self.stream = None
        self.playing_song = None
        self.start_time = 0.0
        self.pause_time = 0.0
        self.current_pos_frames = 0
        self.sample_rate = 0
        self.max_duration_frames = 0
        
        self.refresh_outputs()

    # -------------------------------------------------------------
    # GESTIONE DRIVER E OUTPUT
    # -------------------------------------------------------------
    
    def refresh_outputs(self):
        """Aggiorna la lista dei dispositivi di output audio disponibili."""
        devices = sd.query_devices()
        outputs = []
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                outputs.append({
                    "index": i,
                    "name": dev['name'],
                    "channels": dev['max_output_channels']
                })
        self.outputs = outputs

    def set_driver(self, driver_index=None):
        """Imposta il driver selezionato e filtra gli output."""
        self.driver = driver_index
        self.outputs = self.get_outputs()

    def get_output_names(self, required_channels=None):
        """Restituisce una lista formattata dei device compatibili."""
        names = []
        for out in self.outputs:
            if required_channels is None or out['channels'] >= required_channels:
                names.append(
                    f"{out['index']} - {out['name']} ({out['channels']} ch)"
                )
        return names

    def get_output_channels(self, output_index):
        """Restituisce il numero massimo di canali di un dispositivo."""
        for out in self.outputs:
            if out["index"] == output_index:
                return out["channels"]
        return 1

    def get_outputs(self):
        """Restituisce la lista dei device audio filtrati per il driver selezionato."""
        devices = sd.query_devices()
        filtered = []
        for i, dev in enumerate(devices):
            if dev['max_output_channels'] > 0:
                if self.driver is None or dev['hostapi'] == self.driver:
                    filtered.append({
                        "index": i,
                        "name": dev['name'],
                        "channels": dev['max_output_channels']
                    })
        return filtered

    # -------------------------------------------------------------
    # GESTIONE TRACCE E AGGIORNAMENTO
    # -------------------------------------------------------------
    
    def add_track(self, song_name, file_path, output_index, channels_used=None, output_start_channel=1):
        """Aggiunge una traccia all'engine (richiamato da DataManager)."""
        channels = self.get_output_channels(output_index)
        
        self.tracks.setdefault(song_name, []).append({
            "file": file_path,
            "output": output_index,
            "channels": channels,
            "channels_used": channels_used if channels_used is not None else channels,
            "output_start_channel": output_start_channel # Canale di partenza sull'output device
        })

    def remove_track(self, song_name, index):
        """Rimuove una traccia dall'engine."""
        if song_name in self.tracks and 0 <= index < len(self.tracks[song_name]):
            self.tracks[song_name].pop(index)

    def update_track_output(self, song_name, index, output_index, channels_used=None, output_start_channel=None):
        """Aggiorna l'output e i canali utilizzati per una traccia specifica."""
        if song_name in self.tracks and 0 <= index < len(self.tracks[song_name]):
            track = self.tracks[song_name][index]
            track["output"] = output_index
            
            if channels_used is not None:
                track["channels_used"] = channels_used
            
            if output_start_channel is not None:
                track["output_start_channel"] = output_start_channel
            
            track["channels"] = self.get_output_channels(output_index)
            

    def update_track_output_midi(self, song_name, index, port_name, channel):
        """Metodo placeholder per il MIDI (per simmetria con SongEditorWidget)."""
        pass
        
    # -------------------------------------------------------------
    # PLAYBACK E CALLBACK (MASTER CLOCK)
    # -------------------------------------------------------------
    
    def _audio_callback(self, outdata, frames, time_info, status):
        """Callback chiamato da sounddevice per riempire il buffer audio (Multitraccia Mixing)."""
        if status:
            print(f"Status AudioEngine: {status}") 

        song_tracks = self.tracks.get(self.playing_song, [])
        if not song_tracks:
            outdata.fill(0)
            return

        mix_buffer = np.zeros_like(outdata, dtype=np.float32)
        is_end_of_file = False
        
        # Determina il numero di canali nello stream di output
        output_channels = outdata.shape[1] 

        for track_data in song_tracks:
            file_path = track_data["file"]
            
            # Parametri di mappaggio della traccia
            channels_to_use_by_user = track_data.get("channels_used", 1)
            output_start_channel = track_data.get("output_start_channel", 1) # Indice base 1
            
            # Calcola l'indice di partenza (base 0) e quanti canali copiare sul mix buffer
            start_idx_mix = output_start_channel - 1
            
            # Se la mappatura sfora l'output stream, salta
            if start_idx_mix >= output_channels:
                 continue
            
            # Limita i canali da usare se sfora la fine del mix buffer
            channels_to_copy_to_mix = min(channels_to_use_by_user, output_channels - start_idx_mix)


            try:
                # Apertura e seek del file (ATTENZIONE: in produzione, aprire i file una sola volta)
                with sf.SoundFile(file_path, 'r') as f:
                    f.seek(self.current_pos_frames)
                    data = f.read(frames, dtype='float32', always_2d=True)
                
                # Gestione fine file e padding
                if data.shape[0] < frames:
                    is_end_of_file = True
                    pad_frames = frames - data.shape[0]
                    data = np.pad(data, ((0, pad_frames), (0, 0)), 'constant')
                
                temp_buffer = np.zeros_like(outdata, dtype=np.float32)
                
                # Canali disponibili nel file sorgente
                channels_from_file = data.shape[1]

                # Quanti canali del file copiare (minimo tra i canali disponibili nel file e quelli che verranno mappati sul mix buffer)
                file_channels_to_copy = min(channels_from_file, channels_to_copy_to_mix)

                # Copia e mixaggio
                # Copia i primi `file_channels_to_copy` canali del file nel `temp_buffer`
                # a partire dall'indice `start_idx_mix`.
                temp_buffer[:, start_idx_mix:start_idx_mix + file_channels_to_copy] = data[:, :file_channels_to_copy]

                # Mixaggio (attenuato a 0.5 per evitare clipping)
                mix_buffer += temp_buffer * 0.5 

            except Exception as e:
                print(f"Errore lettura traccia {file_path}: {e}")
                pass
        
        outdata[:] = mix_buffer
        self.current_pos_frames += frames
        
        # L'AudioEngine si ferma solo se l'end of file è vero E abbiamo superato la durata massima.
        if is_end_of_file and self.current_pos_frames >= self.max_duration_frames:
            self.stop_playback(self.playing_song)


    def start_playback(self, song_name, start_time_s=0.0):
        """Avvia o riprende la riproduzione. Gestisce Salto (seek) o Pausa (resume)."""
        if self.stream and self.stream.active:
            return
        
        self.playing_song = song_name
        song_tracks = self.tracks.get(song_name, [])
        if not song_tracks:
            return

        # Determinazione dei parametri del file principale (traccia 0)
        try:
            info = sf.info(song_tracks[0]['file'])
            self.sample_rate = info.samplerate
            self.max_duration_frames = info.frames
            output_index = song_tracks[0]['output']
            stream_channels = self.get_output_channels(output_index)
        except Exception as e:
            print(f"Errore nel caricamento dei parametri del file principale: {e}")
            return
        
        # **NUOVA LOGICA DI SICUREZZA PER IL MASTER CLOCK**
        if self.max_duration_frames <= 0:
             FALLBACK_DURATION_FRAMES = self.sample_rate * 3600 if self.sample_rate > 0 else 44100 * 3600 
             self.max_duration_frames = FALLBACK_DURATION_FRAMES
             print("AVVISO: Durata Master Audio non valida. Uso durata fittizia per sync MIDI/Lyrics.")
        # -----------------------------------------------------------------


        # Calcolo del tempo di partenza (start_ts)
        start_ts = start_time_s
        if start_ts == 0.0 and self.pause_time > 0.0:
            start_ts = self.pause_time

        self.current_pos_frames = int(start_ts * self.sample_rate)
        self.start_time = time.time() - start_ts
        self.pause_time = 0.0

        if self.current_pos_frames >= self.max_duration_frames:
             self.current_pos_frames = 0
             self.start_time = time.time()
             start_ts = 0.0

        # Avvia lo stream
        try:
            self.stream = sd.OutputStream(
                samplerate=self.sample_rate,
                device=output_index,
                channels=stream_channels,
                callback=self._audio_callback,
                dtype='float32'
            )
            self.stream.start()
            
        except sd.PortAudioError as e:
            print(f"ERRORE CRITICO AVVIO AUDIO (sounddevice): {e}")
            print(f"IMPOSSIBILE APRIRE IL DEVICE: {output_index}. Controlla i driver audio.")
            self.stop_playback(song_name) 
            return
        except Exception as e:
            print(f"ERRORE GENERICO DURANTE L'AVVIO: {e}")
            self.stop_playback(song_name) 
            return


    def pause_playback(self, song_name):
        """Mette in pausa la riproduzione e memorizza la posizione."""
        if self.stream and self.stream.active:
            self.pause_time = time.time() - self.start_time
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
    def stop_playback(self, song_name):
        """Ferma la riproduzione e resetta la posizione a zero."""
        if self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        self.playing_song = None
        self.current_pos_frames = 0
        self.start_time = 0.0
        self.pause_time = 0.0
        

    # -------------------------------------------------------------
    # METODI DI SINCRONIZZAZIONE (MASTER CLOCK PER LYRICS PROMPTER)
    # -------------------------------------------------------------

    def is_stopped(self) -> bool:
        """Controlla se lo stream è stato fermato o non è mai stato avviato."""
        return self.stream is None or not self.stream.active

    def get_current_time(self) -> float:
        """Restituisce il tempo di riproduzione corrente in secondi."""
        if self.stream and self.stream.active:
            # Tempo corrente basato sull'orologio di sistema per alta risoluzione
            return time.time() - self.start_time
        elif self.pause_time > 0.0:
            return self.pause_time
        return 0.0

    def get_duration(self) -> float:
        """Restituisce la durata totale della canzone corrente in secondi."""
        if self.playing_song and self.sample_rate > 0 and self.max_duration_frames > 0:
            return self.max_duration_frames / self.sample_rate
        return 0.0