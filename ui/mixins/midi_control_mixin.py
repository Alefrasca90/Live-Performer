# ui/mixins/midi_control_mixin.py (COMPLETO E AGGIORNATO per logica mappatura)

from PyQt6.QtWidgets import QMessageBox
from PyQt6.QtCore import Qt, QTimer
# Assicurati che questi import siano corretti per la tua struttura
from core.midi_comm import MIDIController 
from core.project_models import MidiMapping

class MIDIControlMixin:
    """Gestisce l'interfaccia e la logica per il controllo MIDI."""
    
    def _load_midi_settings(self, new_port_name: str | None = None):
        """
        Carica le mappature MIDI e il canale filtro dallo stato del progetto.
        Tenta di connettersi alla porta specificata o alla porta salvata.
        """
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        
        # 1. Caricamento impostazioni dallo stato
        if u_stato:
             self.midi_mappings: list[MidiMapping] = u_stato.midi_mappings
             self.midi_channel_filter = u_stato.midi_channel
             # Recupera il nome della porta MIDI
             saved_port = getattr(u_stato, 'midi_controller_port_name', '')
        else:
             self.midi_mappings = []
             self.midi_channel_filter = 0
             saved_port = ""
        
        # 2. Determina la porta da connettere
        # Se new_port_name è passato (dal dialogo), usalo. Altrimenti usa la porta salvata.
        port_to_connect = new_port_name if new_port_name is not None else saved_port
        
        # 3. Aggiorna e tenta la connessione
        self.midi_controller.input_port_name = port_to_connect

        # Tenta la connessione solo se la porta non è vuota e non è un messaggio di errore
        if port_to_connect and "(Libreria MIDI" not in port_to_connect and "(Driver MIDI" not in port_to_connect:
             self.midi_controller.connect()
        else:
             self.midi_controller.disconnect()
        
        # 4. Inizializzazione mappature di default (se vuote) 
        if not self.midi_mappings and self.universo_attivo and len(self.universo_attivo.fixture_assegnate) > 0:
             # Usiamo le liste di Scene/Chaser caricate in SceneChaserMixin (se esistono)
             if hasattr(self, 'scene_list') and self.scene_list:
                 self.midi_mappings.append(MidiMapping(midi_type='note', midi_number=48, value=1, action_type='scene', action_index=0, internal_only=True)) # Note C3 -> Scena 1 (Aggiunto internal_only per default)
             if hasattr(self, 'chaser_list') and self.chaser_list:
                 self.midi_mappings.append(MidiMapping(midi_type='cc', midi_number=10, value=65, action_type='chaser', action_index=0, internal_only=True)) # CC 10 > 64 -> Chaser 1 (Aggiunto internal_only per default)
             self.midi_mappings.append(MidiMapping(midi_type='note', midi_number=60, value=1, action_type='stop', action_index=-1, internal_only=True)) # Note C4 -> Stop (Aggiunto internal_only per default)
             
        # [NUOVO] Invia le mappature al MidiEngine per la soppressione dei messaggi.
        if hasattr(self, 'midi_engine') and hasattr(self.midi_engine, 'set_dmx_mappings'):
             self.midi_engine.set_dmx_mappings(self.midi_mappings) 


    def _handle_midi_message(self, msg):
        """Callback eseguita nel thread principale per processare CC/PC/Note in base alle mappature."""
        
        # 0. FILTRO CANALE MIDI
        # Mido usa channel 0-15 (corrispondente a 1-16)
        midi_channel_mido = getattr(msg, 'channel', -1) 
        
        if self.midi_channel_filter != 0:
             # Controlla se il canale del messaggio (0-15) corrisponde al filtro (1-16)
             if midi_channel_mido + 1 != self.midi_channel_filter:
                 return # Ignora il messaggio

        # 1. Estrazione dei dati MIDI per la ricerca
        midi_type = msg.type
        midi_number = None
        value = None
        
        if midi_type == 'note_on':
            # Solo se è Note ON (velocity > 0)
            if msg.velocity > 0:
                midi_number = msg.note
                value = msg.velocity 
            else:
                # Ignora Note OFF (velocity = 0) in questa fase di estrazione
                return 
            
        elif midi_type == 'control_change':
            midi_number = msg.control
            value = msg.value
            
        elif midi_type == 'program_change':
            # Program number è 0-indexed, mappiamo 1-indexed per PC# 1-128
            midi_number = msg.program + 1 
            value = -1 # Valore non usato per PC
            
        else:
            return 

        # 2. Ricerca della mappatura
        for mapping in self.midi_mappings:
            is_match = False
            
            # --- Regole di Match ---
            
            # Match tipo e numero
            if mapping.midi_type == 'note' and midi_type == 'note_on' and midi_number == mapping.midi_number:
                # Note: Match se la nota è corretta. Il valore/velocity è la soglia.
                if value >= mapping.value:
                    is_match = True
                    
            elif mapping.midi_type == 'cc' and midi_type == 'control_change' and midi_number == mapping.midi_number:
                # CC: Match solo se il valore ricevuto (value) è >= del valore di soglia impostato (mapping.value)
                if value >= mapping.value:
                    is_match = True
                        
            elif mapping.midi_type == 'pc' and midi_type == 'program_change' and midi_number == mapping.midi_number:
                # PC: Corrisponde se il numero è corretto
                is_match = True

            # --- Esecuzione Azione ---
            if is_match:
                # 3. Esegue l'azione basata sull'indice
                
                # Assicuriamo che le liste esistano
                scene_list = getattr(self, 'scene_list', [])
                chaser_list = getattr(self, 'chaser_list', [])
                
                if mapping.action_type == 'scene':
                    if 0 <= mapping.action_index < len(scene_list):
                        # Usa la funzione per applicare per indice
                        self.apply_scene_by_index(mapping.action_index)
                        self.setWindowTitle(f"DMX Controller - Scena MIDI: {scene_list[mapping.action_index].nome}")
                    
                elif mapping.action_type == 'chaser':
                    if 0 <= mapping.action_index < len(chaser_list):
                        # Usa la funzione per avviare per indice
                        self.start_chaser_by_index(mapping.action_index)
                    
                elif mapping.action_type == 'stop':
                    self._ferma_chaser()
                    self.setWindowTitle("DMX Controller - MIDI STOP")
                
                return # Termina dopo l'esecuzione
    
    # [NUOVO] Metodo per gestire il salvataggio dal dialogo
    def _handle_midi_mappings_saved(self, new_mappings: list, new_channel_filter: int, new_port_name: str):
        """Gestisce il salvataggio dei nuovi dati dal dialogo di mappatura."""
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        if u_stato:
            u_stato.midi_mappings = new_mappings
            u_stato.midi_channel = new_channel_filter
            u_stato.midi_controller_port_name = new_port_name
            
            self._salva_stato_progetto()
            self._load_midi_settings(new_port_name=new_port_name) # Ricarica e riconnette con le nuove impostazioni
            
            # Invia le mappature aggiornate al MidiEngine
            if hasattr(self, 'midi_engine') and hasattr(self.midi_engine, 'set_dmx_mappings'):
                self.midi_engine.set_dmx_mappings(new_mappings)

        QMessageBox.information(self, "Successo", "Mappature MIDI salvate e applicate.")