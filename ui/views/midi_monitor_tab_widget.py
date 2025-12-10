# ui/views/midi_monitor_tab_widget.py

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QSplitter, QGroupBox
from PyQt6.QtCore import Qt

# Import core components and the shared monitor widget
from core.midi_comm import MIDIController 
from engines.midi_engine import MidiEngine
from ui.components.midi_monitor_widget import MidiMonitorWidget 

class MidiMonitorTabWidget(QWidget):
    """
    Widget che ospita i monitor MIDI in ingresso e in uscita affiancati nel tab "MIDI Monitor".
    Riceve le istanze dei motori MIDI per connettere i segnali.
    """
    def __init__(self, midi_controller: MIDIController, midi_engine: MidiEngine, parent=None):
        super().__init__(parent)
        self.midi_controller = midi_controller
        self.midi_engine = midi_engine
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)

        # 1. MIDI Input Monitor (Ingresso)
        input_group = QGroupBox("MIDI Input Monitor (Segnali in Ingresso)")
        input_layout = QVBoxLayout(input_group)
        self.input_monitor = MidiMonitorWidget()
        input_layout.addWidget(self.input_monitor)
        splitter.addWidget(input_group)

        # 2. MIDI Output Monitor (Uscita)
        output_group = QGroupBox("MIDI Output Monitor (Segnali in Uscita)")
        output_layout = QVBoxLayout(output_group)
        self.output_monitor = MidiMonitorWidget()
        output_layout.addWidget(self.output_monitor)
        splitter.addWidget(output_group)
        
    def connect_signals(self):
        # 1. Connessione Segnale MIDI IN (dal controller hardware)
        self.midi_controller.midi_message.connect(self._log_midi_input_message)
        
        # [CRITICO] 2. Connessione per i segnali MIDI INTERNI (dal file del brano)
        # Questo intercetta l'emissione del MidiEngine per la diagnostica nel monitor.
        if hasattr(self.midi_engine, 'internal_midi_to_dmx'):
             self.midi_engine.internal_midi_to_dmx.connect(self._log_internal_midi_dmx_message)
        
        # 3. Connessione Segnale MIDI OUT (dall'engine di riproduzione file/clock)
        self.midi_engine.midi_message_sent.connect(self.output_monitor.add_message)

    def _log_midi_input_message(self, msg):
        """Formatta e aggiunge il messaggio MIDI IN dalla sorgente hardware."""
        log_text = ""
        # mido usa channel 0-15
        channel_display = getattr(msg, 'channel', -1) + 1 

        if msg.type == 'note_on' and msg.velocity > 0:
            log_text = f"嫉 ON | CH {channel_display:02} | Note {msg.note:03} | Vel {msg.velocity:03} [HARDWARE]"
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            log_text = f"嫉 OFF | CH {channel_display:02} | Note {msg.note:03} [HARDWARE]"
        elif msg.type == 'control_change':
            if msg.control == 121 or msg.control == 123:
                 log_text = f"字 CC | CH {channel_display:02} | Num {msg.control:03} | Val {msg.value:03} [DRIVER RESET]"
            else:
                 log_text = f"字 CC | CH {channel_display:02} | Num {msg.control:03} | Val {msg.value:03} [HARDWARE]" 
        elif msg.type == 'program_change':
            log_text = f"朕 PC | CH {channel_display:02} | Num {msg.program + 1:03} [HARDWARE]"
        else:
             log_text = f"叱 {msg.type.upper()} | {str(msg)} [HARDWARE]" 

        if log_text:
            self.input_monitor.add_message(0.0, f"(SYNC) {log_text}") 

    def _log_internal_midi_dmx_message(self, msg, is_dmx_trigger: bool):
        """[NUOVO SLOT] Formatata e aggiunge il messaggio MIDI dalla traccia file interna."""
        if not is_dmx_trigger:
             return # Ignora se non è specificamente un trigger DMX interno
             
        log_text = ""
        
        channel_display = msg.channel + 1
        
        if msg.type == 'note_on' and msg.velocity > 0:
            log_text = f"嫉 ON | CH {channel_display:02} | Note {msg.note:03} | Vel {msg.velocity:03} [DMX INTERNAL]"
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            log_text = f"嫉 OFF | CH {channel_display:02} | Note {msg.note:03} [DMX INTERNAL]"
        elif msg.type == 'control_change':
            log_text = f"字 CC | CH {channel_display:02} | Num {msg.control:03} | Val {msg.value:03} [DMX INTERNAL]"
        elif msg.type == 'program_change':
            log_text = f"朕 PC | CH {channel_display:02} | Num {msg.program + 1:03} [DMX INTERNAL]"
        else:
             log_text = f"叱 {msg.type.upper()} | {str(msg)} [DMX INTERNAL]"

        if log_text:
            self.input_monitor.add_message(0.0, f"(SYNC) {log_text}") 


    def cleanup(self):
        # Disconnette i segnali per prevenire memory leak o crash
        try:
             self.midi_controller.midi_message.disconnect(self._log_midi_input_message)
        except TypeError:
             pass
        try:
             self.midi_engine.midi_message_sent.disconnect(self.output_monitor.add_message)
        except TypeError:
             pass
        # [NUOVO] Disconnette il segnale interno
        if hasattr(self.midi_engine, 'internal_midi_to_dmx'):
            try:
                self.midi_engine.internal_midi_to_dmx.disconnect(self._log_internal_midi_dmx_message)
            except TypeError:
                pass