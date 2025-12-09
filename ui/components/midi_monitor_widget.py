from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLabel
from PyQt6.QtCore import Qt

class MidiMonitorWidget(QWidget):
    """
    Widget per visualizzare i messaggi MIDI in uscita in tempo reale.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        
        layout = QVBoxLayout(self)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        # Limita la dimensione per non sovraccaricare la memoria
        self.log_display.setMaximumBlockCount(100) 
        
        layout.addWidget(self.log_display)
        self.setMinimumHeight(150)

    def add_message(self, timestamp: float, message: str):
        """Aggiunge un messaggio al log, formattato."""
        if timestamp > 0.001:
            time_str = f"({timestamp:.3f}s)"
        else:
             time_str = "(SYNC)"
             
        self.log_display.appendPlainText(f"{time_str} {message}")
        
    def clear_log(self):
         self.log_display.clear()