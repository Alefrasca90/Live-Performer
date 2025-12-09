# core/dmx_comm.py 

import serial
import serial.tools.list_ports
import time

class DMXController:
    """
    Gestisce la comunicazione seriale per inviare i pacchetti DMX.
    """
    def __init__(self, port_name: str, baudrate: int = 250000):
        self.port_name = port_name
        self.baudrate = baudrate
        self.serial_port = None
        self.is_connected = False
        self.is_enabled = True  # <-- Inizializzato come ATTIVO
        
        # Buffer di 513 byte: [Start Code (0x00)] + [Dati 1..512]
        self.dmx_buffer = bytearray([0] * 513)

    def connect(self) -> bool:
        """Tenta di stabilire la connessione seriale, solo se abilitato."""
        if not self.is_enabled:
            print("DMX Controller disabilitato. Connessione saltata.")
            return False

        if self.is_connected:
            self.disconnect()
            
        try:
            self.serial_port = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_TWO, 
                timeout=0.1
            )
            self.is_connected = self.serial_port.is_open
            print(f"Connessione DMX stabilita su {self.port_name}")
            return self.is_connected
        except serial.SerialException as e:
            # Stampiamo l'errore solo se è una porta specificata
            if self.port_name:
                print(f"Errore di connessione DMX sulla porta {self.port_name}: {e}")
            self.is_connected = False
            return False

    def disable(self):
        """Disabilita il controller e chiude la porta."""
        self.is_enabled = False
        self.disconnect()
        print("DMX Controller disattivato.")

    def enable(self):
        """Abilita il controller e tenta la riconnessione."""
        self.is_enabled = True
        self.connect()

    def disconnect(self):
        """Chiude la connessione seriale."""
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.is_connected = False
            
    def send_dmx_packet(self, dmx_array: list[int]):
        """
        Invia il pacchetto DMX completo.
        Verifica se il controller è abilitato e connesso.
        """
        if not self.is_enabled:
            return
            
        if not self.is_connected:
            return

        # 1. Costruisce il buffer
        for i in range(512):
            if i < len(dmx_array):
                self.dmx_buffer[i + 1] = dmx_array[i]
            else:
                self.dmx_buffer[i + 1] = 0
        
        try:
            # 2. Protocollo di invio DMX seriale
            self.serial_port.break_condition = True
            time.sleep(0.000088)
            self.serial_port.break_condition = False
            time.sleep(0.000012) 
            self.serial_port.write(self.dmx_buffer)
            
        except serial.SerialException as e:
            print(f"Errore durante l'invio del pacchetto DMX: {e}. Riconnessione necessaria.")
            self.disconnect()

    @staticmethod
    def list_available_ports() -> list[str]:
        """Restituisce una lista delle porte seriali disponibili."""
        ports = serial.tools.list_ports.comports()
        return [f"{p.device} ({p.description})" for p in ports]