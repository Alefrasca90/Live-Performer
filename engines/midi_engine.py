from PyQt6.QtCore import QObject, pyqtSignal
import mido
import threading
import time
import os 
from core.data_manager import INTERNAL_DMX_PORT 


# MidiEngine ora deve ereditare da QObject per usare i segnali PyQt
class MidiEngine(QObject):
    """
    Gestisce l’invio e la gestione delle porte MIDI, includendo i controlli di playback.
    """
    # Signal per notificare i messaggi MIDI in uscita: (timestamp: float, message: str)
    midi_message_sent = pyqtSignal(float, str) 
    # [MODIFICATO] Segnale per inviare messaggi MIDI grezzi al router DMX interno, con flag di bypass
    internal_midi_to_dmx = pyqtSignal(object, bool) 

    def __init__(self, parent=None): 
        super().__init__(parent)
        self.driver = None
        # Assicurati che mido sia disponibile o gestito da un wrapper (come da midi_comm.py)
        # Qui usiamo la versione del file fornito (senza la gestione dell'errore di import)
        try:
             self.outputs = mido.get_output_names()
        except NameError:
             self.outputs = []
        except ImportError:
             self.outputs = []

        self.tracks = {}  # { song: [ {file, channel, port} ] }
        self.default_port = None
        
        # --- MIDI CLOCK STATE ---
        self.midi_clock_port = None 
        self._current_song_bpm = 120.0 
        self.midi_clock_running = False
        self.clock_thread = None
        
        # --- MIDI PLAYBACK FILE STATE ---
        self.playback_threads = {} # { song_name: [list of running threads] }
        self.playback_running = False
        
        # --- PLAYBACK STATE ---
        self.playing = False
        self.paused = False


    # -------------------------------------------------------------
    # GESTIONE DRIVER E OUTPUT
    # -------------------------------------------------------------

    def refresh_outputs(self):
        try:
             import mido
             self.outputs = mido.get_output_names()
        except ImportError:
             self.outputs = []


    def set_driver(self, driver_name, port_name):
        self.driver = driver_name
        self.default_port = port_name
        self.refresh_outputs()

    # -------------------------------------------------------------
    # GESTIONE TRACCE E AGGIORNAMENTO
    # -------------------------------------------------------------

    def add_track(self, song_name, channel, port_name, file_path=None):
        self.tracks.setdefault(song_name, []).append({
            "file": file_path,
            "channel": channel,
            "port": port_name
        })

    def remove_track(self, song_name, index):
        if song_name in self.tracks and 0 <= index < len(self.tracks[song_name]):
            self.tracks[song_name].pop(index)

    def update_track_output(self, song_name, index, port_name, channel):
        """Aggiorna la porta e il canale per una traccia MIDI specifica."""
        if song_name in self.tracks and 0 <= index < len(self.tracks[song_name]):
            self.tracks[song_name][index]["port"] = port_name
            self.tracks[song_name][index]["channel"] = channel

    # -------------------------------------------------------------
    # MIDI CLOCK IMPLEMENTATION
    # -------------------------------------------------------------
    
    def _midi_clock_thread(self, bpm: float):
        """Thread che invia i messaggi di clock MIDI (24 PPQN)."""
        
        interval_s = (60.0 / bpm) / 24.0 if bpm > 0 else (60.0 / 120.0) / 24.0
        
        if not self.midi_clock_port:
             self.midi_clock_running = False
             return
             
        try:
            with mido.open_output(self.midi_clock_port, autoreset=True) as out:
                if not self.paused:
                    out.send(mido.Message('start')) 
                    self.midi_message_sent.emit(0.0, f"[CLOCK] START clock su {self.midi_clock_port}")

                while self.midi_clock_running:
                    out.send(mido.Message('clock'))
                    time.sleep(interval_s)

        except Exception as e:
            print(f"Errore nel thread MIDI Clock su {self.midi_clock_port}: {e}")
            self.midi_clock_running = False
            
        if not self.paused and self.midi_clock_port:
             try:
                 with mido.open_output(self.midi_clock_port) as out:
                      out.send(mido.Message('stop'))
                      self.midi_message_sent.emit(0.0, f"[CLOCK] STOP clock su {self.midi_clock_port}")
             except Exception:
                 pass

    # -------------------------------------------------------------
    # THREAD DI PLAYBACK FILE MIDI
    # -------------------------------------------------------------

    def _midi_file_playback_thread(self, song_name: str, track_data: dict, master_bpm: float):
        """
        Thread dedicato a riprodurre un singolo file MIDI associato a una traccia.
        """
        file_path = track_data.get("file")
        port_name = track_data["port"]
        channel = track_data["channel"]
        file_name = os.path.basename(file_path) if file_path else "N/D"

        if not file_path or not os.path.exists(file_path):
             self.midi_message_sent.emit(0.0, f"[ERRORE {file_name}] File MIDI non trovato al percorso: {file_path}")
             return

        try:
            midi_file = mido.MidiFile(file_path)
            
            is_internal_dmx = (port_name == INTERNAL_DMX_PORT)
            
            if is_internal_dmx:
                # --- LOGICA INTERNA (ROUTING AL DMX) ---
                self.midi_message_sent.emit(0.0, f"[{file_name}] Avvio playback INTERNO per DMX, canale {channel}...")
                
                start_time = time.time()
                # [FIX CRITICO] Rimosso 'tempo=mido.bpm2tempo(master_bpm)'
                for msg in midi_file.play(meta_messages=False):
                    if not self.playback_running: break
                        
                    msg.channel = channel 
                    self.internal_midi_to_dmx.emit(msg, True) 
                    
                    current_time = time.time() - start_time
                    self.midi_message_sent.emit(current_time, f"[INTERNAL] {msg}") 
                
            else:
                # --- LOGICA ESTERNA (HARDWARE MIDI) ---
                self.midi_message_sent.emit(0.0, f"[{file_name}] Tentativo di apertura porta '{port_name}'...")
                
                with mido.open_output(port_name, autoreset=True) as out:
                    start_time = time.time()
                    first_message = True 
                    
                    # [FIX CRITICO] Rimosso 'tempo=mido.bpm2tempo(master_bpm)'
                    for msg in midi_file.play(meta_messages=False):
                        
                        if not self.playback_running: break
                            
                        msg.channel = channel 
                        out.send(msg)
                        
                        current_time = time.time() - start_time
                        
                        if first_message:
                             self.midi_message_sent.emit(current_time, f"[{file_name}] **SEQUENZA INIZIATA** - Primo messaggio inviato: {msg}")
                             first_message = False

                        self.midi_message_sent.emit(current_time, f"[{file_name}] {msg}")
                        
            self.midi_message_sent.emit(time.time() - (start_time if 'start_time' in locals() else 0.0), f"[{file_name}] Fine playback.")
            
        # [FIX] Gestione delle eccezioni generiche
        except Exception as e:
            # Cattura errori generici di file o di connessione porta MIDI
            error_msg = f"[{file_name}] ERRORE CRITICO: {type(e).__name__}: {e}"
            self.midi_message_sent.emit(0.0, f"[ERRORE] {error_msg}")
            
    # -------------------------------------------------------------
    # PLAYBACK CONTROL
    # -------------------------------------------------------------
    
    def send_note(self, port_name, channel, note, velocity=64):
        """Invia un singolo messaggio Note On."""
        # [MODIFICATO] Salta se è la porta interna
        if port_name == INTERNAL_DMX_PORT:
            return
            
        try:
            with mido.open_output(port_name) as out:
                msg = mido.Message("note_on", note=note, velocity=velocity, channel=channel)
                out.send(msg)
        except Exception as e:
            print(f"Errore invio MIDI su porta {port_name}: {e}")

    def send_all_notes_off(self, song_name):
        """Invia un Control Change per spegnere tutte le note attive (All Notes Off), ignorando la porta interna."""
        if song_name not in self.tracks:
            return

        self.playback_running = False 
        
        if song_name in self.playback_threads:
            self.playback_threads[song_name] = []


        for track in self.tracks[song_name]:
            port_name = track["port"]
            channel = track["channel"]
            
            # [MODIFICATO] Salta se la porta è quella interna DMX
            if port_name == INTERNAL_DMX_PORT:
                 continue
                 
            try:
                # Controller 123: All Notes Off
                msg = mido.Message('control_change', channel=channel, control=123, value=0)
                with mido.open_output(port_name, autoreset=True) as out:
                    out.send(msg)
                    self.midi_message_sent.emit(0.0, f"[CC] All Notes Off su {port_name}, canale {channel}")
            except Exception as e:
                print(f"Errore invio All Notes Off su {port_name}: {e}")
    
    def start_playback(self, song_name, bpm: float | None = None):
        """Avvia la riproduzione MIDI (Clock e File) e il Clock MIDI (se abilitato), usando il BPM specificato."""
        if self.playing and not self.paused:
            return
            
        is_resume = self.paused
        
        self.playing = True
        self.paused = False
        self.playback_running = True # Abilita l'esecuzione dei thread file

        if bpm is not None: 
             self._current_song_bpm = bpm
        
        # 1. Gestione MIDI Clock
        if self.midi_clock_port:
            
            if is_resume:
                try:
                    with mido.open_output(self.midi_clock_port) as out:
                         out.send(mido.Message('continue'))
                         self.midi_message_sent.emit(0.0, f"[CLOCK] CONTINUE clock su {self.midi_clock_port}")
                except Exception:
                    pass
            
            if not self.midi_clock_running:
                 self.midi_clock_running = True
                 self.clock_thread = threading.Thread(target=self._midi_clock_thread, 
                                                      args=(self._current_song_bpm,), 
                                                      daemon=True)
                 self.clock_thread.start()

        # 2. Gestione Playback File MIDI
        midi_file_tracks = [t for t in self.tracks.get(song_name, []) if t.get("file")]
        
        file_count = len(midi_file_tracks)
        self.midi_message_sent.emit(0.0, f"[DEBUG] Trovate {file_count} tracce MIDI con file.")
        
        if midi_file_tracks and not is_resume: 
            
            self.playback_threads[song_name] = []
            
            # Avvia un thread per OGNI file MIDI
            for track_data in midi_file_tracks:
                
                file_name = os.path.basename(track_data['file']) if track_data.get('file') else 'N/D'
                port_name = track_data['port']
                
                # [MODIFICATO] VALIDATION CHECK: Permette la porta interna
                if port_name not in self.outputs and port_name != INTERNAL_DMX_PORT:
                    self.midi_message_sent.emit(0.0, f"[ERRORE] Porta MIDI '{port_name}' non trovata per '{file_name}'. Controlla le impostazioni.")
                    continue
                
                self.midi_message_sent.emit(0.0, f"[DEBUG] Inizio thread per '{file_name}' (Porta: {port_name})...")

                t = threading.Thread(target=self._midi_file_playback_thread, 
                                     args=(song_name, track_data, self._current_song_bpm),
                                     daemon=True)
                t.start()
                self.playback_threads[song_name].append(t)
        
        elif is_resume and song_name in self.playback_threads and self.playback_threads[song_name]:
            # Poiché non supportiamo il seek, forziamo uno stop/restart
            self.midi_message_sent.emit(0.0, f"[AVVISO] Resume File MIDI non supportato, riavvio traccia.")
            self.stop_playback(song_name)
            self.start_playback(song_name, bpm=self._current_song_bpm)


    def pause_playback(self, song_name):
        """Mette in pausa la riproduzione MIDI (Clock e File), spegne le note e il Clock."""
        if not self.playing or self.paused:
            return
            
        self.paused = True
        self.send_all_notes_off(song_name)
        
        # 1. Gestione MIDI Clock
        if self.midi_clock_running and self.midi_clock_port:
             try:
                 with mido.open_output(self.midi_clock_port) as out:
                      out.send(mido.Message('stop'))
                      self.midi_message_sent.emit(0.0, f"[CLOCK] STOP (Pause) clock su {self.midi_clock_port}")
             except Exception:
                 pass
                 
        # 2. Gestione Playback File MIDI
        self.playback_running = False


    def stop_playback(self, song_name):
        """Ferma la riproduzione MIDI (Clock e File) e resetta lo stato e il Clock."""
        if not self.playing:
            return
            
        self.playing = False
        self.paused = False
        self.send_all_notes_off(song_name)
        
        # 1. Gestione MIDI Clock
        if self.midi_clock_running:
             self.midi_clock_running = False 
        self.clock_thread = None

        # 2. Gestione Playback File MIDI
        self.playback_running = False
        # Assicurati che i thread terminino (gestito da self.playback_running = False nel thread)
        self.playback_threads[song_name] = []