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
        
        # 2. Connessione Segnale MIDI OUT (dall'engine di riproduzione file/clock)
        self.midi_engine.midi_message_sent.connect(self.output_monitor.add_message)

    def _log_midi_input_message(self, msg):
        """Formatta e aggiunge il messaggio MIDI IN alla lista del monitor (Logic moved from DMXControlWidget/MainWindow)."""
        log_text = ""
        # Mido uses type 'note_on'/'note_off', 'control_change', 'program_change'

        if msg.type == 'note_on' and msg.velocity > 0:
            log_text = f"嫉 ON | CH {msg.channel + 1:02} | Note {msg.note:03} | Vel {msg.velocity:03}"
        elif msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0):
            log_text = f"嫉 OFF | CH {msg.channel + 1:02} | Note {msg.note:03}"
        elif msg.type == 'control_change':
            log_text = f"字 CC | CH {msg.channel + 1:02} | Num {msg.control:03} | Val {msg.value:03}"
        elif msg.type == 'program_change':
            log_text = f"朕 PC | CH {msg.channel + 1:02} | Num {msg.program + 1:03}"
        else:
             # Other messages like timing_clock, sysex, etc.
             log_text = f"叱 {msg.type.upper()} | {str(msg)}" 

        if log_text:
            # Si usa 0.0 come timestamp fittizio, in quanto il monitor IN non è sincronizzato
            self.input_monitor.add_message(0.0, log_text) 

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