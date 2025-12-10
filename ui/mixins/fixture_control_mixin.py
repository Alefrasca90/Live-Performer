# ui/mixins/fixture_control_mixin.py (COMPLETO E AGGIORNATO)

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QMessageBox, QSpinBox, QSizePolicy, QSlider, 
    QSpacerItem, QPushButton, QGroupBox # AGGIUNTO QGroupBox per Master Dimmer
)
from PyQt6.QtCore import Qt, QTimer
import threading # NUOVO: Import per il threading
# Import Core Models
from core.dmx_models import IstanzaFixture, FixtureModello
from core.project_models import IstanzaFixtureStato 

# Import widget locale
from ui.components.widgets import FixtureGroupBox 

class FixtureControlMixin:
    """Gestisce la creazione e l'interazione con i controlli fader delle fixture."""
    
    # Le variabili di stato del clipboard saranno inzializzate sulla MainWindow
    # Ma per sicurezza le inzializziamo qui in popola_controlli_fader se non esistono.

    def _get_channel_dimmer_map(self) -> dict[int, str]:
        """Crea una mappa {dmx_addr (1-512): 'DIMMER'/'OTHER'} per le fixture assegnate. [NUOVO]"""
        dimmer_map = {}
        if not hasattr(self, 'universo_attivo'):
             return dimmer_map

        for instance in self.universo_attivo.fixture_assegnate: 
            start_addr, _ = instance.get_indirizzi_universali()
            for i, canale in enumerate(instance.modello.descrizione_canali):
                dmx_addr = start_addr + i
                # Logica per identificare i canali dimmer: nome contiene 'dimmer' o funzione contiene 'intensità'
                nome = canale.nome.lower()
                funzione = canale.funzione.lower()
                is_dimmer = ('dimmer' in nome or 'intensità' in funzione)
                
                if 1 <= dmx_addr <= 512:
                    # Non ci interessa il tipo, ma solo se è gestito da una fixture
                    dimmer_map[dmx_addr] = 'CONTROLLED'
        return dimmer_map


    def _apply_master_dimmer_to_array_only(self, dmx_array: list[int]) -> list[int]:
        """
        Applica il Master Dimmer (MDA) come moltiplicatore percentuale
        a TUTTI i canali DMX attivi, simulando l'effetto su tutti i canali
        che contribuiscono all'intensità (Dimmer, Colore, Strobe). [CORRETTO]
        """
        if not hasattr(self, 'master_dimmer_value') or self.master_dimmer_value == 255:
             return dmx_array
             
        master_dimmer_value = self.master_dimmer_value
        dimmer_factor = master_dimmer_value / 255.0
        
        new_dmx_array = dmx_array[:]
        
        # Non è necessario usare la mappa, in quanto l'MD agisce su tutti i valori
        # DMX della fixture in modo non selettivo.
        
        for i in range(512):
            original_value = dmx_array[i] # Valore non dimmato (raw HTP/LTP)
            
            # Applica la scala percentuale a tutti i valori
            new_value = max(0, min(255, int(original_value * dimmer_factor)))
            new_dmx_array[i] = new_value

        return new_dmx_array

    def _apply_master_dimmer(self, value: int):
        """Applica il valore del Master Dimmer (0-255) e gestisce l'aggiornamento DMX/UI."""
        self.master_dimmer_value = value
        
        # 1. L'universo DMX deve essere prima aggiornato dai valori NON dimmati (HTP/LTP)
        self.universo_attivo.aggiorna_canali_universali()
        
        # 2. Ottieni l'array dimmato dal Master Dimmer (MDA)
        dimmed_array = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
        
        # 3. Sostituisci l'array nell'universo DMX (questo valore è quello che verrà inviato)
        self.universo_attivo.array_canali = dimmed_array

        # 4. [MODIFICATO - THREADING] Invia il pacchetto DMX in un thread separato
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
        
        # 5. Aggiorna la simulazione luce e i fader UI (queste operazioni devono restare nel main thread)
        self._push_dmx_to_instances()
        for instance in self.universo_attivo.fixture_assegnate:
             self.aggiorna_simulazione_luce(instance)
        self._aggiorna_valori_fader()
        
    def _send_debounced_dimmer_update(self, value: int):
        """Metodo di supporto per debouncing il Master Dimmer DMX send."""
        # Se il timer non è stato inizializzato, lo fa ora (nel caso estremo)
        if not hasattr(self, '_master_dimmer_debounce_timer'):
             return

        # Memorizza l'ultimo valore e riavvia il timer
        self._master_dimmer_value_to_send = value
        if not self._master_dimmer_debounce_timer.isActive():
            # Il timer chiama _apply_master_dimmer, che ora usa un thread per l'I/O
            self._master_dimmer_debounce_timer.start()


    def _gestisci_cambio_valore_master_dmx(self, value: int, label_widget: QLabel):
        """Gestisce la modifica del Master Dimmer da parte dell'utente."""
        if self.chaser_timer.isActive():
            self._ferma_chaser(show_message=False)
            QTimer.singleShot(10, lambda: QMessageBox.information(self, "Controllo Manuale", "Chaser interrotto per controllo manuale."))
            
        # Aggiornamento immediato della UI (Label)
        label_widget.setText(f"Dimmer Master: {value}")
        
        # Lancia l'aggiornamento DMX in modalità debounced
        self._send_debounced_dimmer_update(value)
        

    def popola_controlli_fader(self):
        """Crea i fader utilizzando il widget FixtureGroupBox (Accordion). Chiamato solo all'avvio o al cambio di fixture."""
        
        # Inizializza il clipboard interno se non è già stato fatto
        if not hasattr(self, 'fixture_clipboard'):
             self.fixture_clipboard = {}
             
        # [NUOVO] Inizializza il Master Dimmer se non esiste (default 255 = 100%)
        if not hasattr(self, 'master_dimmer_value'):
             self.master_dimmer_value = 255
        
        # [NUOVO] Inizializza il debouncing timer e la variabile di stato
        if not hasattr(self, '_master_dimmer_value_to_send'):
             self._master_dimmer_value_to_send = self.master_dimmer_value

        if not hasattr(self, '_master_dimmer_debounce_timer'):
            self._master_dimmer_debounce_timer = QTimer(self)
            self._master_dimmer_debounce_timer.setSingleShot(True)
            self._master_dimmer_debounce_timer.setInterval(20) # 20ms debounce (50 FPS rate)
            # Connetti il timer al metodo che esegue l'aggiornamento completo
            self._master_dimmer_debounce_timer.timeout.connect(lambda: self._apply_master_dimmer(self._master_dimmer_value_to_send))
        
        # Pulizia del layout
        # 'self.fader_layout' must exist, ensured in _setup_ui
        for i in reversed(range(self.fader_layout.count())): 
            widget = self.fader_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # Rimuove lo spacer alla fine
        if self.fader_layout.itemAt(self.fader_layout.count() - 1) and self.fader_layout.itemAt(self.fader_layout.count() - 1).spacerItem():
            self.fader_layout.removeItem(self.fader_layout.itemAt(self.fader_layout.count() - 1))
            
        # --- [NUOVO] 0. Master Dimmer Control ---
        master_group = QGroupBox("Master Dimmer")
        master_layout = QVBoxLayout(master_group)
        
        master_fader_layout = QHBoxLayout()
        self.master_label = QLabel(f"Dimmer Master: {self.master_dimmer_value}")
        self.master_label.setFixedWidth(120)
        
        self.master_slider = QSlider(Qt.Orientation.Horizontal)
        self.master_slider.setRange(0, 255)
        self.master_slider.setValue(self.master_dimmer_value)
        
        # Connessione al nuovo gestore
        self.master_slider.valueChanged.connect(
            lambda val, lbl=self.master_label: self._gestisci_cambio_valore_master_dmx(val, lbl)
        )
        
        master_fader_layout.addWidget(self.master_label)
        master_fader_layout.addWidget(self.master_slider)
        master_layout.addLayout(master_fader_layout)
        
        self.fader_layout.addWidget(master_group)
        # --- FINE Master Dimmer Control ---

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
            # 1. Aggiorna l'universo DMX (non dimmato)
            self.universo_attivo.aggiorna_canali_universali()
            
            # 2. Applica il Master Dimmer
            self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
            
            # 3. [MODIFICATO] Invia DMX in un thread separato
            dmx_data_copy = self.universo_attivo.array_canali[:]
            threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
            
            # 4. Aggiorna UI e Stage View
            self._aggiorna_valori_fader()
            self.aggiorna_simulazione_luce(target_instance)
            
            # 5. Mostra successo
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

        # [NUOVO] Aggiorna il Master Dimmer UI (è sempre il primo elemento del layout)
        if hasattr(self, 'master_slider') and self.fader_layout.count() > 0 and self.universo_attivo:
             # Se il Master Dimmer è nel layout, aggiorna il suo valore
             if self.master_slider.value() != self.master_dimmer_value:
                  try:
                       self.master_slider.blockSignals(True)
                       self.master_slider.setValue(self.master_dimmer_value)
                       self.master_label.setText(f"Dimmer Master: {self.master_dimmer_value}")
                  finally:
                       self.master_slider.blockSignals(False)

        # L'indice 0 del fader_layout è ora Master Dimmer Group. Le fixture partono da 1.
        for idx, instance in enumerate(self.universo_attivo.fixture_assegnate):
            
            # Ignoriamo lo Spacer all'ultimo indice, se presente
            if idx + 1 >= self.fader_layout.count(): continue
            
            item = self.fader_layout.itemAt(idx + 1) # <--- MODIFICATO l'indice per il Master Dimmer Group
            
            accordion_group = item.widget()
            if not accordion_group or not isinstance(accordion_group, FixtureGroupBox): continue
            
            content_widget = accordion_group.content_widget
            vbox = content_widget.layout()
            
            if not vbox: continue
            
            start, _ = instance.get_indirizzi_universali()
            
            # Aggiorna ogni canale (riga nel vbox)
            for i in range(instance.modello.numero_canali):
                # Tenendo conto del layout di controllo (indice 0)
                hlayout_item = vbox.itemAt(i + 1) # +1 per saltare il control_layout
                if not hlayout_item: continue
                
                hlayout = hlayout_item.layout()
                if not hlayout: continue
                
                # Valore letto dall'istanza (che a sua volta è stato aggiornato da _push_dmx_to_instances)
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
                    # Verifica che l'elemento non sia None e che sia un widget (es. un QSlider)
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
        
        # 1. Imposta il valore sul modello e aggiorna l'array universale (NON dimmato, ma con HTP/LTP)
        self.universo_attivo.set_valore_fixture(fixture_instance, indice_canale, valore)
        
        # 2. Applica il Master Dimmer (MDA)
        self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
        
        self.aggiorna_simulazione_luce(fixture_instance)
        
        # 3. [MODIFICATO] Invia DMX in un thread separato
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()

    def aggiorna_simulazione_luce(self, instance: IstanzaFixture):
        """
        Aggiorna il colore nel widget StageView (Stage View) usando la miscelazione additiva
        per simulare il colore finale (RGB + W, A, UV). [CORRETTO per MDA]
        
        Nota: i valori in instance.valori_correnti sono i valori DMX finali (già scalati dall'MDA).
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
                val = float(valori[i]) # Valore DMX finale (già scalato)
                
                # Dimmer Master
                if 'dimmer' in nome or 'intensità' in canale.funzione.lower():
                    # Sovrascrive il dimmer master, prendendo il valore più alto trovato
                    # Questo valore è GIA' SCALATO dall'MDA o è il valore di scena/fader scalato.
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
        
        # Capping dei valori a 255.0 (I valori qui sono già scalati dall'MDA)
        final_r_raw = min(255.0, total_r)
        final_g_raw = min(255.0, total_g)
        final_b_raw = min(255.0, total_b)
        
        # Non si applica più il fattore dimmer finale (per evitare doppio dimming)
        
        if self.stage_view:
            self.stage_view.update_light_color(instance.indirizzo_inizio, final_r_raw, final_g_raw, final_b_raw)
            
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
                 
            # Applica il Master Dimmer prima di inviare
            self.universo_attivo.aggiorna_canali_universali()
            self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
            
            # [MODIFICATO] Invia DMX in un thread separato
            dmx_data_copy = self.universo_attivo.array_canali[:]
            threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
            
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
        
        # Rigenera l'array universale (non dimmato)
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
        
        # Applica il Master Dimmer prima di inviare
        self.universo_attivo.array_canali = self._apply_master_dimmer_to_array_only(self.universo_attivo.array_canali)
        
        # [MODIFICATO] Invia DMX in un thread separato
        dmx_data_copy = self.universo_attivo.array_canali[:]
        threading.Thread(target=self.dmx_comm.send_dmx_packet, args=(dmx_data_copy,)).start()
        
        QMessageBox.information(self, "Rimozione", f"Fixture '{fixture_to_remove.modello.nome}' (DMX {addr_to_remove}) rimossa con successo.")