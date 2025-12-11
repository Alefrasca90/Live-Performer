# ui/mixins/scene_chaser_mixin.py (COMPLETO E AGGIORNATO per click singolo/doppio)

from PyQt6.QtWidgets import QMessageBox 
from PyQt6.QtCore import QTimer, Qt
from core.dmx_models import Scena, PassoChaser, Chaser
from core.project_models import UniversoStato
import time 
import threading 
from core.dmx_models import ActiveScene 
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSlider, QGroupBox, QPushButton 


# Frequenza del timer di fade (in Hz)
FADE_RATE_HZ = 100 

class SceneChaserMixin:
    """Gestisce la creazione, salvataggio e riproduzione di Scene e Chaser."""
    
    # Variabili di stato per il Fading
    _FADE_DATA = {} 
    _FADE_TICK_MS = 1000 / FADE_RATE_HZ
    
    # [NUOVO] Lista di ActiveScene
    active_scenes: list[ActiveScene] = []

    def _ricostruisci_scene_chasers(self, u_stato: UniversoStato):
        """Carica le scene e chaser per l'universo attivo."""
        self.scene_list: list[Scena] = u_stato.scene
        self.chaser_list: list[Chaser] = u_stato.chasers 
        self.chaser_attivo: Chaser | None = None
        
        # [NUOVO] Ricostruisci ActiveScene dalla serializzazione
        self.active_scenes = self._rebuild_active_scenes(u_stato.active_scenes_data)
        
        if hasattr(self, 'scene_list_widget'):
            self._update_scene_list_ui()
        if hasattr(self, 'chaser_list_widget'): 
            self._update_chaser_list_ui()
        if hasattr(self, 'active_scenes_layout'):
             self._update_active_scenes_ui()
             
    def _rebuild_active_scenes(self, active_scenes_data: list[dict]) -> list[ActiveScene]:
        """Ricostruisce gli oggetti ActiveScene dai dati serializzati. [NUOVO]"""
        rebuilt_scenes = []
        scene_map = {s.nome: s for s in self.scene_list}
        
        for data in active_scenes_data:
            scena_nome = data.get('scena_nome')
            # Manteniamo il valore salvato, ma non è più modificabile dalla UI
            master_value = data.get('master_value', 255) 
            scena = scene_map.get(scena_nome)
            if scena:
                # Forza Master a 255 in ActiveScene, mantenendo la vecchia struttura dati
                rebuilt_scenes.append(ActiveScene(scena, master_value=255)) 
                
        return rebuilt_scenes

    # --- Metodi Pubblici per MIDI/Helper ---

    def apply_scene_by_index(self, index: int):
        """Aggiunge una scena alla lista attiva in base all'indice (0-based) dalla lista salvata. [MODIFICATO]"""
        if 0 <= index < len(self.scene_list):
            scena_da_applicare = self.scene_list[index]
            # Master value è FISSATO a 255 per le scene attive
            self._add_scene_to_active(scena_da_applicare, master_value=255) 
            self.setWindowTitle(f"DMX Controller - Scena MIDI: {scena_da_applicare.nome}")
        else:
             print(f"MIDI Error: Indice scena {index} fuori limite.")


    def start_chaser_by_index(self, index: int):
        """Avvia un chaser in base all'indice (0-based) dalla lista salvata."""
        if 0 <= index < len(self.chaser_list):
            chaser_to_start = self.chaser_list[index]
            
            if not chaser_to_start.passi:
                print(f"MIDI Error: Chaser {chaser_to_start.nome} è vuoto.")
                return

            if self.chaser_attivo and self.chaser_attivo.nome == chaser_to_start.nome:
                 # Se è già attivo, fermalo per consentire l'avvio della stessa sequenza
                 self._ferma_chaser(show_message=False)
                 return

            if self.chaser_timer.isActive() or self.fade_timer.isActive():
                 self._ferma_chaser(show_message=False)
            
            self.chaser_attivo = chaser_to_start
            self._FADE_DATA.clear()
            # Riavvia il chaser dal primo passo (next_passo lo farà ciclare)
            self.chaser_attivo.indice_corrente = len(self.chaser_attivo.passi) - 1 
            self._esegui_passo_chaser() 
            self.setWindowTitle(f"DMX Controller - CHASER ATTIVO MIDI: {chaser_to_start.nome}")
            self._update_chaser_list_ui()
        else:
            print(f"MIDI Error: Indice chaser {index} fuori limite.")


    # --- Scene Logic (HTP/MERGE) ---
    
    def _add_scene_to_active(self, scene: Scena, master_value: int = 255):
        """Aggiunge una scena alla lista delle scene attive (se non è già presente). [NUOVO]"""
        if self.chaser_attivo:
            self._ferma_chaser(show_message=False)

        # Controlla se la scena è già attiva
        found = False
        for active_scene in self.active_scenes:
            if active_scene.scena.nome == scene.nome:
                # Il master è fisso a 255 per le scene attive
                active_scene.master_value = 255 
                found = True
                break
        
        if not found:
             # Usa master_value FISSATO a 255 per le scene attive
             self.active_scenes.append(ActiveScene(scene, master_value=255)) 
             
        self._update_active_scenes_ui()
        self._merge_and_send_dmx()
        
    def _remove_active_scene(self, index: int):
        """Rimuove una scena attiva e rifonde l'output DMX. [NUOVO]"""
        if 0 <= index < len(self.active_scenes):
            del self.active_scenes[index]
            self._update_active_scenes_ui()
            self._merge_and_send_dmx()
            
    def _merge_and_send_dmx(self):
        """Metodo per chiamare la fusione HTP, inviare DMX e aggiornare la UI. [MODIFICATO]"""
        if not hasattr(self, '_merge_active_scenes'):
             print("ERRORE: _merge_active_scenes non disponibile. Impossibile fondere le scene.")
             return
             
        # 1. Fondi le scene attive (i valori DMX vengono scritti in universo_attivo.array_canali)
        self._merge_active_scenes(self.active_scenes)
        
        # 2. Aggiorna UI (Fader e Stage View)
        self._aggiorna_ui_fader_e_stage() 

        # 3. Invia DMX in un thread separato
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
             
        self._save_active_scenes()


    def _save_active_scenes(self):
        """Serializza le scene attive nello stato del progetto. [NUOVO]"""
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        if u_stato:
             # Manteniamo il master_value per la persistenza, anche se è fisso a 255
             u_stato.active_scenes_data = [{'scena_nome': s.scena.nome, 'master_value': s.master_value} for s in self.active_scenes]
             self._salva_stato_progetto()


    def _update_active_scenes_ui(self):
        """Aggiorna la QListWidget e il layout delle scene attive. [NUOVO]"""
        if not hasattr(self, 'active_scenes_layout'):
            return
            
        # Pulisci il layout esistente
        for i in reversed(range(self.active_scenes_layout.count())): 
            item = self.active_scenes_layout.itemAt(i)
            # Pulizia per il vecchio formato (widget singolo o layout)
            if item.widget():
                 item.widget().deleteLater()
            elif item.layout():
                 sub_layout = item.layout()
                 for j in reversed(range(sub_layout.count())):
                      widget = sub_layout.itemAt(j).widget()
                      if widget: widget.deleteLater()
                 # Rimuovi il layout stesso
                 self.active_scenes_layout.removeItem(item)

        if not self.active_scenes:
            self.active_scenes_layout.addWidget(QLabel("Nessuna Scena Attiva"))
            return

        # Ricrea i widget per le scene attive
        for idx, active_scene in enumerate(self.active_scenes):
            scene_widget = QWidget()
            # Layout orizzontale per nome e pulsante X
            h_layout = QHBoxLayout(scene_widget)
            h_layout.setContentsMargins(0, 0, 0, 0)
            
            # 1. Label e pulsante Rimuovi
            # Rimosso il riferimento al master_value.
            label_text = f"{active_scene.scena.nome}" 
            label = QLabel(label_text)
            
            # Pulsante X con connessione al metodo di rimozione
            btn_remove = QPushButton("X")
            btn_remove.setFixedSize(20, 20)
            # Connessione: il lambda è necessario per passare l'indice corretto
            btn_remove.clicked.connect(lambda _, index=idx: self._remove_active_scene(index))
            
            h_layout.addWidget(label, 1)
            h_layout.addWidget(btn_remove)

            # Aggiungi l'intero widget (contenente label e pulsante X) al layout principale.
            self.active_scenes_layout.addWidget(scene_widget)


    def _build_active_scenes_control(self):
        """Costruisce il pannello per la gestione delle scene attive. [NUOVO]"""
        scenes_group = QGroupBox("Scene Attive (Programmer)")
        
        # Layout per la lista dinamica
        self.active_scenes_layout = QVBoxLayout() 
        self.active_scenes_layout.setContentsMargins(5, 15, 5, 5) # Margini per il QVBoxLayout
        self.active_scenes_layout.setSpacing(5)

        # Wrapper per la lista dinamica 
        wrapper = QWidget()
        wrapper.setLayout(self.active_scenes_layout)
        
        main_layout = QVBoxLayout(scenes_group)
        main_layout.addWidget(wrapper, 1)
        main_layout.setContentsMargins(5, 5, 5, 5) # Margini per il QGroupBox

        # Carica lo stato iniziale
        self._update_active_scenes_ui()
        
        return scenes_group


    # --- Scene Logic ---

    def _view_scene_for_editing(self, scena: Scena):
        """[NUOVO] Applica la scena direttamente ai fader e aggiorna la UI, svuotando le scene attive.
           Usato per 'vedere' il contenuto di una scena prima di modificarla."""
        
        # 1. Ferma eventuali Chaser
        if self.chaser_attivo:
            self._ferma_chaser(show_message=False)
            
        # 2. Svuota il Programmer (Active Scenes)
        self.active_scenes.clear()
        self._update_active_scenes_ui() 
        self._save_active_scenes() # Persist the cleared state
        
        # 3. Applica la scena direttamente ai valori correnti della fixture
        self.universo_attivo.applica_scena(scena) 

        # 4. Inizia il ciclo di aggiornamento DMX/UI
        self.universo_attivo.aggiorna_canali_universali()
        
        # 5. Applica il Master Dimmer
        if hasattr(self, '_apply_master_dimmer_to_array_only'):
             self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
        
        # 6. Aggiorna UI (Fader e Stage View)
        self._aggiorna_ui_fader_e_stage() 
        
        # 7. Invia DMX
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
        
        self.setWindowTitle(f"DMX Controller - Scena Caricata per Modifica: {scena.nome}")
        

    def _cattura_scena_corrente(self):
        """
        Crea una nuova Scena dallo stato corrente e la salva,
        o sovrascrive una scena esistente con lo stesso nome.
        [MODIFICATO]
        """
        scene_name = self.scene_name_input.text().strip()
        if not scene_name:
            QMessageBox.warning(self, "Errore", "Inserisci un nome per la Scena.")
            return

        # 1. Cattura lo stato DMX corrente nell'oggetto Scena
        nuova_scena = self.universo_attivo.cattura_scena(scene_name)
        
        # 2. Cerca una scena esistente con lo stesso nome
        scena_esistente = next((s for s in self.scene_list if s.nome == scene_name), None)
        
        message = "" # Variabile per il messaggio di successo

        if scena_esistente:
            # 3. Chiedi conferma per sovrascrivere
            reply = QMessageBox.question(self, 'Sovrascrivi Scena', 
                f"La Scena '{scene_name}' esiste già. Vuoi sovrascriverla con lo stato DMX corrente?", 
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                # 4. Sovrascrivi (sostituisci l'oggetto Scena nella lista)
                index = self.scene_list.index(scena_esistente)
                self.scene_list[index] = nuova_scena
                message = f"Scena '{scene_name}' sovrascritta con successo."
            else:
                return # Operazione annullata
        else:
            # 5. Nuova scena
            self.scene_list.append(nuova_scena)
            message = f"Scena '{scene_name}' salvata con successo."
        
        self._update_scene_list_ui()
        self.scene_name_input.clear()
        
        self._salva_stato_progetto()
        
        QTimer.singleShot(10, lambda: QMessageBox.information(self, "Scena Salvata", message))

    # [NUOVO METODO] Handle single click per l'attivazione/layering
    def _handle_scene_single_click_for_activation(self, item):
        """
        Gestisce il click singolo sulla lista scene.
        Aggiunge la scena selezionata allo stack 'Active Scenes' (Programmer)
        per il Layering.
        """
        if not hasattr(self, 'scene_list_widget'):
            return
            
        # Trova l'indice dall'oggetto QListWidgetItem cliccato
        index = self.scene_list_widget.row(item)
        
        if index < 0 or index >= len(self.scene_list):
            return

        scena_da_applicare = self.scene_list[index]
        
        # Chiama il metodo di aggiunta allo stack Active Scenes (Layering)
        self._add_scene_to_active(scena_da_applicare, master_value=255)
        
        # Rimosso il QMessageBox per evitare interruzioni continue
        print(f"Scena '{scena_da_applicare.nome}' aggiunta al Programmer.")


    def _handle_scene_double_click_for_editing(self):
        """
        [MODIFICATO] Carica la scena selezionata nei fader per la visualizzazione/modifica.
        (Questa funzione gestisce il segnale doubleClicked).
        """
        if not hasattr(self, 'scene_list_widget'):
            return
            
        selected_items = self.scene_list_widget.selectedItems()
        if not selected_items:
            return

        index = self.scene_list_widget.row(selected_items[0])
        scena_da_applicare = self.scene_list[index]
        
        # Chiama la logica per caricare la scena nei fader
        self._view_scene_for_editing(scena_da_applicare)
        
        QTimer.singleShot(10, lambda: QMessageBox.information(self, "Scena Caricata", f"Scena '{scena_da_applicare.nome}' caricata nei fader per la modifica. Sovrascrivi cliccando 'Salva'."))


    def _update_scene_list_ui(self):
        """Aggiorna la QListWidget che mostra le scene salvate."""
        if not hasattr(self, 'scene_list_widget'):
            return
            
        self.scene_list_widget.clear()
        for s in self.scene_list:
            self.scene_list_widget.addItem(f"{s.nome} ({len(s.valori_canali)}ch)")

    
    def _cancella_scena_selezionata(self):
        """Cancella la scena selezionata."""
        if not hasattr(self, 'scene_list_widget'):
            return
            
        selected_items = self.scene_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Errore", "Seleziona una scena da cancellare.")
            return

        index = self.scene_list_widget.row(selected_items[0])
        del self.scene_list[index]
        self._update_scene_list_ui()
        
        self._salva_stato_progetto()
        
        QTimer.singleShot(10, lambda: QMessageBox.information(self, "Cancellazione", "Scena cancellata con successo."))
        
    # --- Chaser List Logic ---
    
    def _update_chaser_list_ui(self):
        """Aggiorna la QListWidget che mostra i chaser salvati."""
        if not hasattr(self, 'chaser_list_widget'):
            return
            
        self.chaser_list_widget.clear()
        for c in self.chaser_list:
            status = " (ATTIVO)" if self.chaser_attivo and c.nome == self.chaser_attivo.nome else ""
            self.chaser_list_widget.addItem(f"{c.nome} ({len(c.passi)} passi){status}")
            
    def _handle_chaser_saved(self, new_chaser: Chaser):
        """Aggiunge/Sostituisce un chaser salvato dal dialogo."""
        found = False
        for i, chaser in enumerate(self.chaser_list):
            if chaser.nome == new_chaser.nome:
                self.chaser_list[i] = new_chaser # Sovrascrive
                found = True
                break
        if not found:
            self.chaser_list.append(new_chaser)
            
        self._update_chaser_list_ui()
        self._salva_stato_progetto() 
        QTimer.singleShot(10, lambda: QMessageBox.information(self, "Sequenza Salvata", f"Sequenza '{new_chaser.nome}' salvata/aggiornata."))

    def _cancella_chaser_selezionato(self):
        """Cancella il chaser selezionato."""
        if not hasattr(self, 'chaser_list_widget'): 
            return
            
        selected_items = self.chaser_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Errore", "Seleziona una sequenza da cancellare.")
            return

        index = self.chaser_list_widget.row(selected_items[0])
        if 0 <= index >= len(self.chaser_list):
             QMessageBox.critical(self, "Errore", "Indice sequenza non valido.")
             return

        chaser_to_remove = self.chaser_list[index]
        
        if self.chaser_attivo and self.chaser_attivo.nome == chaser_to_remove.nome:
            self._ferma_chaser(show_message=False)
            self.chaser_attivo = None
            
        del self.chaser_list[index]
        self._update_chaser_list_ui()
        self._salva_stato_progetto()
        QTimer.singleShot(10, lambda: QMessageBox.information(self, "Cancellazione", f"Sequenza '{chaser_to_remove.nome}' cancellata con successo."))


    # --- Chaser Runtime Logic ---

    def _avvia_chaser(self):
        """Avvia il chaser selezionato dalla lista."""
        if self.chaser_timer.isActive() or self.fade_timer.isActive():
            QMessageBox.warning(self, "Avvio Fallito", "Il Chaser è già in esecuzione.")
            return
            
        if not hasattr(self, 'chaser_list_widget'): 
            QMessageBox.critical(self, "Errore", "Componente Chaser non inizializzato.")
            return
            
        selected_items = self.chaser_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Avvio Fallito", "Seleziona una Sequenza Chaser da avviare.")
            return
            
        index = self.chaser_list_widget.row(selected_items[0])
        chaser_to_start = self.chaser_list[index]
        
        if not chaser_to_start.passi:
            QMessageBox.warning(self, "Avvio Fallito", "La Sequenza selezionata non contiene passi.")
            return
            
        self.chaser_attivo = chaser_to_start
        
        self._FADE_DATA.clear()
        
        self.chaser_attivo.indice_corrente = len(self.chaser_attivo.passi) - 1 
        
        self._esegui_passo_chaser() 
        
        self.setWindowTitle(f"DMX Controller - CHASER ATTIVO: {self.chaser_attivo.nome}")
        self._update_chaser_list_ui()
        
    def _ferma_chaser(self, show_message: bool = True):
        """Ferma il chaser se in esecuzione. [MODIFICATO]"""
        if self.chaser_timer.isActive():
            self.chaser_timer.stop()
        if self.fade_timer.isActive():
            self.fade_timer.stop()
        
        self._FADE_DATA.clear()
        
        # [NUOVO] Se il chaser viene fermato, rimuovi tutte le scene attive (se non provenienti dal fader manuale)
        if self.chaser_attivo:
            self.active_scenes.clear()
            self._merge_and_send_dmx()
        
        self.setWindowTitle(f"DMX Controller - Universo {self.universo_attivo.id_universo}")
        self.chaser_attivo = None 
        self._update_chaser_list_ui() 
            
        if show_message:
            QTimer.singleShot(10, lambda: QMessageBox.information(self, "Stop Chaser", "Sequenza interrotta."))

    def _esegui_passo_chaser(self):
        """Esegue il passo successivo (Fade In + Hold) del chaser e aggiorna il timer."""
        if not self.chaser_attivo:
            self._ferma_chaser(show_message=False)
            return

        try:
            passo = self.chaser_attivo.next_passo()
            
            # 1. Prepara per il Fade In
            if passo.tempo_fade_in > 0.0:
                self._start_fade(passo.scena, passo.tempo_fade_in)
                
                self.chaser_timer.stop()
                
                # Calcola il ritardo totale prima di eseguire il prossimo passo
                total_delay_ms = int((passo.tempo_fade_in + passo.tempo_permanenza) * 1000)
                
                if total_delay_ms > 0:
                    QTimer.singleShot(total_delay_ms, self._esegui_passo_chaser)
                else:
                    QTimer.singleShot(10, self._esegui_passo_chaser)
                
                
                self.setWindowTitle(f"DMX Controller - CHASER ATTIVO: {self.chaser_attivo.nome} | Passo: {passo.scena.nome} (Fade In {passo.tempo_fade_in:.1f}s)")
                
                return 

            else:
                # 2. Nessun Fade In, applicazione istantanea (NON dimmata)
                self.universo_attivo.applica_scena(passo.scena)
                
                # 3. [NUOVO] Applica il Master Dimmer
                if hasattr(self, '_apply_master_dimmer_to_array_only'):
                     self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
                
                # 4. [MODIFICATO - THREADING] Invia DMX in un thread separato
                dmx_data_copy = self.universo_attivo.array_canali[:]
                threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()

                self._aggiorna_ui_fader_e_stage() 

                # 5. Imposta Hold Time
                tempo_totale_ms = int(passo.tempo_permanenza * 1000)
                if tempo_totale_ms > 0:
                     self.chaser_timer.setInterval(tempo_totale_ms) 
                     self.chaser_timer.start()
                else:
                    self.chaser_timer.stop()
                    QTimer.singleShot(10, self._esegui_passo_chaser)


                self.setWindowTitle(f"DMX Controller - CHASER ATTIVO: {self.chaser_attivo.nome} | Passo: {passo.scena.nome} (Hold {passo.tempo_permanenza:.1f}s)")
                
        except IndexError:
            self._ferma_chaser()
    
    def _start_fade(self, target_scena: Scena, fade_time: float):
        """Avvia l'interpolazione graduale dei valori DMX."""
        
        if fade_time <= 0.0:
            self.universo_attivo.applica_scena(target_scena)
            
            # [NUOVO] Applica il Master Dimmer
            if hasattr(self, '_apply_master_dimmer_to_array_only'):
                 self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)

            # [MODIFICATO - THREADING] Invia DMX in un thread separato
            dmx_data_copy = self.universo_attivo.array_canali[:]
            threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()

            self._aggiorna_ui_fader_e_stage()
            return
        
        # 1. Prepara i valori di partenza (valori attuali, potenzialmente già dimmati)
        start_values = self.universo_attivo.array_canali[:] 
        
        # 2. Calcola i valori di destinazione (NON dimmati, per l'interpolazione lineare)
        target_raw_values = self.universo_attivo.array_canali[:]
        
        for dmx_addr, val in target_scena.valori_canali.items():
             target_raw_values[dmx_addr - 1] = val
        
        # 3. [NUOVO] Applica il Master Dimmer ai valori di destinazione
        if hasattr(self, '_apply_master_dimmer_to_array_only'):
             target_values = self._apply_master_dimmer_to_array_only(target_raw_values)
        else:
             target_values = target_raw_values
        

        self._FADE_DATA = {
            'start_values': start_values,
            'target_values': target_values, # <--- Ora dimmati
            'duration_ms': fade_time * 1000,
            'start_time': time.time(),
            'target_scene_name': target_scena.nome
        }
        
        self.fade_timer.start()


    def _fade_tick(self):
        """Funzione chiamata dal fade_timer per interpolare i valori DMX."""
        if not self._FADE_DATA:
            self.fade_timer.stop()
            return
        
        data = self._FADE_DATA
        elapsed_time = (time.time() - data['start_time']) * 1000 
        
        progress = min(1.0, elapsed_time / data['duration_ms']) 
        
        new_dmx_array = self.universo_attivo.array_canali[:] 
        
        # 1. Interpolazione (tra due array dimmati)
        for i in range(512):
            start = data['start_values'][i]
            target = data['target_values'][i]
            
            diff = target - start
            new_value = start + int(diff * progress)
            new_dmx_array[i] = new_value

        # 2. Aggiornamento DMX
        self.universo_attivo.array_canali = new_dmx_array
        self._aggiorna_ui_fader_e_stage() 
        
        # 3. [MODIFICATO - THREADING] Invia DMX in un thread separato
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
        
        # 4. Controllo Fine Fade
        if progress >= 1.0:
            self.fade_timer.stop()
            self._FADE_DATA.clear()
            
            scene_name = data.get('target_scene_name', 'Scena Sconosciuta') 
            if self.chaser_attivo:
                self.setWindowTitle(f"DMX Controller - CHASER ATTIVO: {self.chaser_attivo.nome} | Passo: {scene_name} (Hold)")

    
    def _push_dmx_to_instances(self):
        """Sincronizza i valori DMX dall'array raw agli oggetti IstanzaFixture."""
        # NOTA: Questo metodo legge i valori DMX *dimmati* da array_canali 
        # e li salva in fixture.valori_correnti. Questo non è ideale per l'editing
        # ma è necessario per la coerenza del fader slider.
        for fixture in self.universo_attivo.fixture_assegnate:
            start_addr, _ = fixture.get_indirizzi_universali()
            start_idx = start_addr - 1
            
            for i in range(fixture.modello.numero_canali):
                # Aggiorna l'array interno dell'istanza dalla posizione corretta nell'array DMX
                fixture.valori_correnti[i] = self.universo_attivo.array_canali[start_idx + i]

    def _aggiorna_ui_fader_e_stage(self):
        """
        [MODIFICATO: ESECUZIONE SINCRONA] Aggiorna i valori UI (Fader, Stage View) in modo sincrono.
        """
        
        # 1. Sincronizza i valori dall'array DMX agli oggetti IstanzaFixture (dimmati)
        self._push_dmx_to_instances()
        
        # 2. Aggiorna i valori dei fader (legge dagli oggetti IstanzaFixture)
        if hasattr(self, '_aggiorna_valori_fader'):
            self._aggiorna_valori_fader()
        
        # 3. Aggiorna la simulazione luce (Stage View)
        if hasattr(self, 'aggiorna_simulazione_luce'):
            for instance in self.universo_attivo.fixture_assegnate:
                self.aggiorna_simulazione_luce(instance)
                
    def _build_active_scenes_control(self):
        """Costruisce il pannello per la gestione delle scene attive. [NUOVO]"""
        scenes_group = QGroupBox("Scene Attive (Programmer)")
        
        # Layout per la lista dinamica
        self.active_scenes_layout = QVBoxLayout() 
        self.active_scenes_layout.setContentsMargins(5, 15, 5, 5) # Margini per il QVBoxLayout
        self.active_scenes_layout.setSpacing(5)

        # Wrapper per la lista dinamica 
        wrapper = QWidget()
        wrapper.setLayout(self.active_scenes_layout)
        
        main_layout = QVBoxLayout(scenes_group)
        main_layout.addWidget(wrapper, 1)
        main_layout.setContentsMargins(5, 5, 5, 5) # Margini per il QGroupBox

        # Carica lo stato iniziale
        self._update_active_scenes_ui()
        
        return scenes_group