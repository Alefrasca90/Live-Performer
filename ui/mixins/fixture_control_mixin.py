# ui/mixins/fixture_control_mixin.py (COMPLETO E AGGIORNATO)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QMessageBox, QSpinBox, QSizePolicy, QSlider, 
    QSpacerItem, QPushButton # AGGIUNTO QPushButton
)
from PyQt6.QtCore import Qt, QTimer
# Import Core Models
from core.dmx_models import IstanzaFixture, FixtureModello
from core.project_models import IstanzaFixtureStato 

# Import widget locale
from ui.components.widgets import FixtureGroupBox 

class FixtureControlMixin:
    """Gestisce la creazione e l'interazione con i controlli fader delle fixture."""
    
    # Le variabili di stato del clipboard saranno inizializzate sulla MainWindow
    # Ma per sicurezza le inizializziamo qui in popola_controlli_fader se non esistono.
    
    def popola_controlli_fader(self):
        """Crea i fader utilizzando il widget FixtureGroupBox (Accordion). Chiamato solo all'avvio o al cambio di fixture."""
        
        # Inizializza il clipboard interno se non è già stato fatto
        if not hasattr(self, 'fixture_clipboard'):
             self.fixture_clipboard = {}
        
        # Pulizia del layout
        # 'self.fader_layout' must exist, ensured in _setup_ui
        for i in reversed(range(self.fader_layout.count())): 
            widget = self.fader_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Rimuove lo spacer alla fine
        if self.fader_layout.itemAt(self.fader_layout.count() - 1) and self.fader_layout.itemAt(self.fader_layout.count() - 1).spacerItem():
            self.fader_layout.removeItem(self.fader_layout.itemAt(self.fader_layout.count() - 1))

        # Recupera tutte le istanze stato per associare il nome utente e l'indice
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo))
        stato_map = {s.indirizzo_inizio: s for s in u_stato.istanze_stato}
        
        for idx, instance in enumerate(self.universo_attivo.fixture_assegnate):
            start, end = instance.get_indirizzi_universali()
            
            # Recupera il nome utente dall'istanza stato corrispondente
            stato = stato_map.get(instance.indirizzo_inizio)
            
            # Determina il nome da visualizzare nel Fader Group Box
            display_name = ""
            if stato and stato.nome_utente:
                display_name = stato.nome_utente 
            else:
                # Logica esistente per nomi virtuali/default se non c'è un nome utente
                instance_name = instance.modello.nome
                if "Virtuale" in instance_name:
                     parent_addr = instance.indirizzo_inizio
                     if self.universo_attivo.fixture_assegnate:
                         first_instance_addr = self.universo_attivo.fixture_assegnate[0].indirizzo_inizio
                     else:
                         first_instance_addr = 0
                     
                     if "PAR" in instance_name:
                         if parent_addr >= first_instance_addr:
                            section = (parent_addr - first_instance_addr) // 5 + 1
                            display_name = f"Algam PAR {section}"
                     elif "Bianco" in instance_name:
                         if parent_addr >= first_instance_addr + 20:
                            section = (parent_addr - (first_instance_addr + 20)) + 1
                            display_name = f"Algam LED White {section}"
                # Se ancora vuoto, usa Modello come fallback
                if not display_name:
                     display_name = instance.modello.nome


            content_widget = QWidget()
            vbox = QVBoxLayout(content_widget)
            
            # --- NUOVO: Pulsanti di Controllo (Copia/Incolla) ---
            control_layout = QHBoxLayout()
            
            copy_btn = QPushButton("📋 Copia Valori")
            # Passa l'istanza corrente al metodo di copia
            copy_btn.clicked.connect(lambda _, inst=instance: self._copy_fixture_values(inst))
            control_layout.addWidget(copy_btn)

            paste_btn = QPushButton("📌 Incolla Valori")
            # Passa l'istanza corrente al metodo di incolla
            paste_btn.clicked.connect(lambda _, inst=instance: self._paste_fixture_values(inst))
            control_layout.addWidget(paste_btn)
            
            vbox.addLayout(control_layout)
            # ----------------------------------------
            
            for i, canale in enumerate(instance.modello.descrizione_canali):
                hlayout = QHBoxLayout()
                
                label = QLabel(f"DMX {start+i}. {canale.nome}: {instance.valori_correnti[i]}")
                label.setObjectName(f"FaderLabel_{start+i}") 
                label.setFixedWidth(120)
                hlayout.addWidget(label)
                
                slider = QSlider(Qt.Orientation.Horizontal)
                slider.setRange(0, 255)
                slider.setValue(instance.valori_correnti[i]) 
                
                # Connessione al gestore di cambio valore
                slider.valueChanged.connect(
                    lambda val, inst=instance, ch_idx=i, lbl=label: 
                        self.gestisci_cambio_valore_dmx(inst, ch_idx, val, lbl)
                )
                
                hlayout.addWidget(slider)
                vbox.addLayout(hlayout)
                
            accordion_group = FixtureGroupBox(
                title=f"{display_name} @{start}-{end}",
                content_widget=content_widget
            )
            # Diamo un objectName anche al gruppo per futura eventuale identificazione
            accordion_group.setObjectName(f"FixtureGroupBox_{instance.indirizzo_inizio}") 
            self.fader_layout.addWidget(accordion_group)
        
        self.fader_layout.addItem(QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)) 
        
    def _copy_fixture_values(self, source_instance: IstanzaFixture):
        """Copia i valori correnti della fixture e i nomi dei canali nel clipboard interno."""
        self.fixture_clipboard.clear()
        
        # Mappa i valori con il nome del canale
        for i, valore in enumerate(source_instance.valori_correnti):
            canale_nome = source_instance.modello.descrizione_canali[i].nome
            # Usiamo il nome del canale (Es: 'Rosso', 'Dimmer') come chiave per la corrispondenza.
            self.fixture_clipboard[canale_nome] = valore
            
        QMessageBox.information(self, 
                                "Copia Effettuata", 
                                f"Copiati {len(self.fixture_clipboard)} valori da '{source_instance.modello.nome}' ({source_instance.indirizzo_inizio}).")

    def _paste_fixture_values(self, target_instance: IstanzaFixture):
        """Incolla i valori dal clipboard nella fixture di destinazione, ignorando i canali non corrispondenti."""
        if not self.fixture_clipboard:
            QMessageBox.warning(self, "Incolla Fallito", "Nessun valore copiato. Usa prima il pulsante 'Copia Valori'.")
            return
            
        copied_count = len(self.fixture_clipboard)
        pasted_count = 0
        
        for i, target_channel in enumerate(target_instance.modello.descrizione_canali):
            channel_name = target_channel.nome
            
            if channel_name in self.fixture_clipboard:
                new_value = self.fixture_clipboard[channel_name]
                
                # Applica il valore all'istanza
                target_instance.set_valore_canale(i, new_value)
                pasted_count += 1
                
        if pasted_count > 0:
            # 1. Aggiorna l'universo DMX e Stage View
            self.universo_attivo.aggiorna_canali_universali()
            self._aggiorna_valori_fader()
            self.aggiorna_simulazione_luce(target_instance)
            self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)
            
            # 2. Mostra successo
            QMessageBox.information(self, 
                                    "Incolla Effettuato", 
                                    f"Incollati {pasted_count} di {copied_count} valori in '{target_instance.modello.nome}' ({target_instance.indirizzo_inizio}).")
        else:
            # Se la fixture è compatibile (stessi canali), ma tutti a 0/default, potrebbe non esserci corrispondenza
            QMessageBox.warning(self, 
                                "Incolla Parziale/Fallito", 
                                f"Nessun canale corrispondente trovato da incollare. Canali copiati: {', '.join(self.fixture_clipboard.keys())}")

    def _aggiorna_valori_fader(self):
        """
        Aggiorna solo i valori dei fader e delle etichette senza ricreare i widget.
        Questo metodo è chiamato da Scene/Chaser.
        """
        
        if not hasattr(self, 'fader_layout'):
            return

        for idx, instance in enumerate(self.universo_attivo.fixture_assegnate):
            
            # Ignoriamo lo Spacer all'ultimo indice, se presente
            if idx >= self.fader_layout.count(): continue
            
            item = self.fader_layout.itemAt(idx)
            if not item: continue
            
            accordion_group = item.widget()
            if not accordion_group or not isinstance(accordion_group, FixtureGroupBox): continue
            
            content_widget = accordion_group.content_widget
            vbox = content_widget.layout()
            
            if not vbox: continue
            
            start, _ = instance.get_indirizzi_universali()
            
            # Controlla la presenza del layout di controllo (Copia/Incolla)
            # L'indice 0 è il layout Copia/Incolla, gli indici successivi sono i canali
            
            # Aggiorna ogni canale (riga nel vbox)
            for i in range(instance.modello.numero_canali):
                # Tenendo conto del layout di controllo (indice 0)
                hlayout_item = vbox.itemAt(i + 1) # +1 per saltare il control_layout
                if not hlayout_item: continue
                
                hlayout = hlayout_item.layout()
                if not hlayout: continue
                
                valore = instance.valori_correnti[i]
                
                # 1. Trova e aggiorna il QLabel (Indice 0 del hlayout)
                label_item = hlayout.itemAt(0)
                label = label_item.widget()
                if label:
                    canale_nome = instance.modello.get_canale_per_indice(i).nome
                    dmx_address = start + i
                    label.setText(f"DMX {dmx_address}. {canale_nome}: {valore}")
                        
                # 2. Trova e aggiorna il QSlider (Indice 1 del hlayout)
                slider_item = hlayout.itemAt(1)
                if slider_item:
                    slider = slider_item.widget()
                    if slider and hasattr(slider, 'setValue'):
                        try:
                            slider.blockSignals(True)
                            slider.setValue(valore)
                        finally:
                            slider.blockSignals(False)
        
    def gestisci_cambio_valore_dmx(self, fixture_instance: IstanzaFixture, indice_canale: int, valore: int, label_widget: QLabel):
        """Gestisce la modifica di un fader DMX da parte dell'utente."""
        
        # 'self.chaser_timer' must exist, ensured in MainWindow.__init__
        if self.chaser_timer.isActive():
            self._ferma_chaser(show_message=False) # Non mostriamo il messaggio qui
            
            # Usiamo singleShot per non bloccare l'interfaccia 
            QTimer.singleShot(10, lambda: QMessageBox.information(self, "Controllo Manuale", "Chaser interrotto per controllo manuale."))
            
        start, _ = fixture_instance.get_indirizzi_universali()
        canale_nome = fixture_instance.modello.get_canale_per_indice(indice_canale).nome
        dmx_address = start + indice_canale
        label_widget.setText(f"DMX {dmx_address}. {canale_nome}: {valore}")
        
        self.universo_attivo.set_valore_fixture(fixture_instance, indice_canale, valore)
        
        self.aggiorna_simulazione_luce(fixture_instance)
        
        # 'self.dmx_comm' must exist, ensured in MainWindow.__init__
        self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)

    def aggiorna_simulazione_luce(self, instance: IstanzaFixture):
        """
        Aggiorna il colore nel widget StageView (Stage View) usando la miscelazione additiva
        per simulare il colore finale (RGB + W, A, UV).
        """
        valori = instance.valori_correnti
        
        # Accumulatori in virgola mobile (0.0 - 255.0 * N_CANALI)
        total_r, total_g, total_b = 0.0, 0.0, 0.0
        max_dimmer_val = 255.0 # Dimmer predefinito al massimo se non trovato
        
        # Fattori RGB per i colori secondari (normalizzati a 1.0, poi scalati da 'val')
        # Amber (Warm: 255, 210, 100)
        AMBER_RGB_RATIO = (1.0, 210/255, 100/255) 
        # UV (Deep Purple/Blue: 100, 0, 255)
        UV_RGB_RATIO = (100/255, 0.0, 1.0) 
        
        # --- 1. Accumulazione dei valori Colore/Dimmer ---
        
        # === LOGICA PER LED BIANCO VIRTUALE (Prioritaria) ===
        if instance.modello.nome == "Algam LED Bianco (Virtuale)" and valori:
            white_level = float(valori[0])
            total_r, total_g, total_b = white_level, white_level, white_level
            max_dimmer_val = 255.0 
        # === FINE LOGICA LED BIANCO ===
        
        # Logica Generale
        else:
            for i, canale in enumerate(instance.modello.descrizione_canali):
                nome = canale.nome.lower()
                val = float(valori[i])
                
                # Dimmer Master
                if 'dimmer' in nome or 'intensità' in canale.funzione.lower():
                    # Sovrascrive il dimmer master, prendendo il valore più alto trovato
                    max_dimmer_val = max(max_dimmer_val, val) 
                    
                # Miscelazione Additiva dei Canali Colore (RGB)
                elif 'rosso' in nome or 'red' in nome or nome == 'r':
                    total_r += val
                elif 'verde' in nome or 'green' in nome or nome == 'g':
                    total_g += val
                elif 'blu' in nome or 'blue' in nome or nome == 'b':
                    total_b += val
                
                # Miscelazione Additiva dei Canali Secondari (W, A, UV)
                elif 'bianco' in nome or 'white' in nome or nome == 'w':
                    total_r += val
                    total_g += val
                    total_b += val
                elif 'ambra' in nome or 'amber' in nome or nome == 'a':
                    total_r += val * AMBER_RGB_RATIO[0]
                    total_g += val * AMBER_RGB_RATIO[1]
                    total_b += val * AMBER_RGB_RATIO[2]
                elif 'uv' in nome or 'ultraviolet' in nome:
                    total_r += val * UV_RGB_RATIO[0]
                    total_g += val * UV_RGB_RATIO[1]
                    total_b += val * UV_RGB_RATIO[2]
        
        # --- 2. Applicazione e Finalizzazione ---
        
        # Capping dei valori a 255.0
        final_r_raw = min(255.0, total_r)
        final_g_raw = min(255.0, total_g)
        final_b_raw = min(255.0, total_b)
        
        # Dimmer Factor (scalato da 0.0 a 1.0)
        dimmer_fattore = max_dimmer_val / 255.0
        
        # Applicazione del Dimmer
        final_r = final_r_raw * dimmer_fattore
        final_g = final_g_raw * dimmer_fattore
        final_b = final_b_raw * dimmer_fattore

        if self.stage_view:
            self.stage_view.update_light_color(instance.indirizzo_inizio, final_r, final_g, final_b)
            
    # Firma modificata per accettare il nome utente
    def _aggiungi_istanza_core(self, selected_model: FixtureModello, start_addr: int, nome_utente: str):
        """Logica centrale per aggiungere una nuova istanza fixture (o un gruppo di virtuali) all'universo DMX."""

        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo))
        
        try:
            # === LOGICA PER FIXTURE COMPLESSE: Algam Stage Bar 24Ch ===
            if selected_model.nome == "Algam Stage Bar 24Ch":
                
                par_model = next((m for m in self.fixture_modelli if m.nome == "Algam PAR Singolo (Virtuale)"), None)
                white_model = next((m for m in self.fixture_modelli if m.nome == "Algam LED Bianco (Virtuale)"), None)
                
                if not par_model or not white_model:
                     raise Exception("Modelli virtuali per Algam Stage Bar non trovati. Riprova a riavviare l'applicazione.")
                
                sub_fixtures = [
                    (0, par_model),      
                    (5, par_model),      
                    (10, par_model),     
                    (15, par_model),     
                    (20, white_model),   
                    (21, white_model),   
                    (22, white_model),   
                    (23, white_model),   
                ]
                
                # Se l'utente ha specificato un nome per il "gruppo", lo usiamo come prefisso
                group_name_prefix = nome_utente if nome_utente else selected_model.nome 
                
                for offset, model in sub_fixtures:
                    addr = start_addr + offset
                    
                    nuova_istanza = IstanzaFixture(model, addr)
                    self.universo_attivo.aggiungi_fixture(nuova_istanza)
                    
                    x_pos = (offset % 5) * 100
                    y_pos = (offset // 5) * 100
                    
                    # Generiamo un nome specifico per la sub-fixture
                    sub_name = f"{group_name_prefix} - Sub@{offset + 1}" # Usiamo l'offset + 1 come numero di canale relativo
                    
                    # Salviamo lo stato con il nome generato
                    u_stato.istanze_stato.append(IstanzaFixtureStato(model.nome, addr, x_pos, y_pos, nome_utente=sub_name))

                QMessageBox.information(self, "Successo", f"Fixture '{selected_model.nome}' scomposta in 8 istanze virtuali a partire dall'indirizzo {start_addr}.")
                
            # === LOGICA STANDARD ===
            else:
                nuova_istanza = IstanzaFixture(selected_model, start_addr)
                self.universo_attivo.aggiungi_fixture(nuova_istanza)
                
                # Salviamo lo stato con il nome utente fornito (può essere vuoto)
                u_stato.istanze_stato.append(IstanzaFixtureStato(selected_model.nome, start_addr, 0, 0, nome_utente=nome_utente))
                
                QMessageBox.information(self, "Successo", f"Fixture '{selected_model.nome}' aggiunta all'indirizzo {start_addr}.")
            
            # --- Aggiornamento UI e DMX (Comune) ---
            self.popola_controlli_fader()
            self._update_assigned_list_ui() # <-- Defined in ProjectAndViewMixin
            
            if self.stage_view:
                 self.stage_view.clear_and_repopulate(u_stato.istanze_stato) 
                 
            self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)
            
        except ValueError as e:
            QMessageBox.critical(self, "Errore di Assegnazione", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Errore Generico", f"Errore durante l'aggiunta della fixture: {e}")

    def _rimuovi_istanza_da_universo(self):
        """Rimuove la fixture selezionata dalla lista delle assegnate."""
        # 'self.assigned_list_widget' must exist, ensured in _crea_pannello_controllo
        selected_items = self.assigned_list_widget.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Errore", "Seleziona una fixture da rimuovere.")
            return

        index_to_remove = self.assigned_list_widget.row(selected_items[0])
        
        if index_to_remove < 0 or index_to_remove >= len(self.universo_attivo.fixture_assegnate):
             QMessageBox.critical(self, "Errore", "Indice non valido.")
             return
        
        fixture_to_remove = self.universo_attivo.fixture_assegnate.pop(index_to_remove)
        self.universo_attivo.aggiorna_canali_universali()
        
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo))
        addr_to_remove = fixture_to_remove.indirizzo_inizio
        
        u_stato.istanze_stato = [
            i for i in u_stato.istanze_stato if i.indirizzo_inizio != addr_to_remove
        ]
        
        self.popola_controlli_fader()
        self._update_assigned_list_ui()
        
        if self.stage_view:
            self.stage_view.clear_and_repopulate(u_stato.istanze_stato)
        
        self.dmx_comm.send_dmx_packet(self.universo_attivo.array_canali)
        
        QMessageBox.information(self, "Rimozione", f"Fixture '{fixture_to_remove.modello.nome}' (DMX {addr_to_remove}) rimossa con successo.")