# ui/mixins/dmx_comm_mixin.py

from PyQt6.QtWidgets import QMessageBox 
from PyQt6.QtCore import Qt
from core.dmx_comm import DMXController 

class DMXCommunicationMixin:
    """Gestisce la connessione fisica DMX e l'aggiornamento dello stato UI."""
    
    def _toggle_dmx_output(self, state: int):
        """Abilita o disabilita l'uscita DMX in base allo stato del checkbox."""
        if state == Qt.CheckState.Checked.value:
            self.dmx_comm.enable()
        else:
            self.dmx_comm.disable()
            
        self._update_dmx_status_ui()

    def _handle_dmx_connection(self):
        """Gestisce la riconnessione al controller DMX."""
        self.dmx_comm.disconnect()
        self.dmx_comm.connect()
        self._update_dmx_status_ui()
        
        ports = DMXController.list_available_ports()
        port_list_str = "\n".join(ports) if ports else "Nessuna porta seriale trovata."
        QMessageBox.information(self, "Porte Seriale Trovate", 
                                f"Porta configurata: {self.dmx_comm.port_name}\n\nNota: Per collegarsi, l'hardware DMX deve usare la porta '{self.dmx_comm.port_name}'\n\nPorte disponibili:\n{port_list_str}")

    def _update_dmx_status_ui(self):
        """Aggiorna l'etichetta dello stato DMX nell'interfaccia utente."""
        # 'self.status_label' and 'self.refresh_ports_btn' must exist, ensured in _crea_pannello_controllo
        if not hasattr(self, 'status_label'):
            return
            
        if not self.dmx_comm.is_enabled:
            self.status_label.setText("DISABILITATO (OFFLINE)")
            self.status_label.setStyleSheet("color: orange; font-weight: bold;")
            self.refresh_ports_btn.setDisabled(True)
        elif self.dmx_comm.is_connected:
            self.status_label.setText(f"CONNESSO: {self.dmx_comm.port_name}")
            self.status_label.setStyleSheet("color: lightgreen; font-weight: bold;")
            self.refresh_ports_btn.setDisabled(False)
        else:
            self.status_label.setText("NON CONNESSO")
            self.status_label.setStyleSheet("color: red; font-weight: bold;")
            self.refresh_ports_btn.setDisabled(False)