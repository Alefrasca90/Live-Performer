# core/midi_comm.py (Gestore MIDI Input)

import threading
import time
from typing import Callable, List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
import os 

# RICHIESTA DIPENDENZA ESTERNA: pip install mido python-rtmidi
try:
    import mido
    
    MIDI_BACKEND = os.environ.get('MIDI_BACKEND', 'mido.backends.rtmidi')
    
    try:
        mido.set_backend(MIDI_BACKEND) 
        MIDI_AVAILABLE = True
    except ImportError:
        try:
            mido.set_backend(None)
            MIDI_AVAILABLE = True
        except:
             MIDI_AVAILABLE = False
    except Exception:
        try:
            mido.set_backend(None)
            MIDI_AVAILABLE = True
        except:
             MIDI_AVAILABLE = False
             
except ImportError:
    MIDI_AVAILABLE = False
    pass

class MIDIController(QObject):
    """
    Gestore principale della comunicazione MIDI in ingresso (Input) per il controllo.
    """
    midi_message = pyqtSignal(object) 

    def __init__(self, input_port_name: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.input_port_name = input_port_name
        self.port = None
        self.is_listening = False
        self.is_connected = False 
        self._thread = None
        self.midi_channel_filter = 0 

    @staticmethod
    def list_input_ports() -> List[str]:
        """Restituisce una lista delle porte MIDI Input disponibili."""
        if not MIDI_AVAILABLE:
             return ["(Libreria MIDI 'mido' mancante o configurazione fallita)"] 
        try:
            ports = mido.get_input_names()
            backend = mido.backend.name.split('.')[-1] if mido.backend else 'default'
            
            if not ports:
                 return [f"(Driver MIDI: {backend} - Nessuna porta trovata)"]
                 
            return ports
        except Exception:
            return ["(Libreria MIDI non configurata o installata correttamente)"]

    def _listen_loop(self):
        """Loop in background per l'ascolto dei messaggi MIDI."""
        if not self.port:
            return
            
        print("MIDI listening thread started.")
        while self.is_listening and self.port:
            try:
                for msg in self.port.iter_pending():
                    self.midi_message.emit(msg)
                    
                time.sleep(0.001)
            except Exception as e:
                if self.is_listening:
                    print(f"Errore durante l'ascolto MIDI: {e}")
                self.is_listening = False
                break
        print("MIDI listening thread terminated.")

    def connect(self) -> bool:
        """Tenta di aprire e avviare l'ascolto sulla porta MIDI specificata."""
        if not MIDI_AVAILABLE:
            return False

        self.disconnect()

        if not self.input_port_name:
            return False

        try:
            self.port = mido.open_input(self.input_port_name)
            self.is_listening = True
            self.is_connected = True 
            
            self._thread = threading.Thread(target=self._listen_loop, daemon=True)
            self._thread.start()
            
            print(f"Connessione MIDI stabilita su {self.input_port_name}")
            return True
        except Exception as e:
            print(f"Errore di connessione MIDI sulla porta {self.input_port_name}: {e}")
            self.is_listening = False
            self.is_connected = False 
            return False

    def disconnect(self):
        """Chiude la connessione MIDI e ferma il thread di ascolto."""
        self.is_listening = False
        self.is_connected = False 
        if self.port:
            self.port.close()
            self.port = None
        
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=0.2) 
            self._thread = None