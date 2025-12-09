# ui/mixins/project_and_view_mixin.py (COMPLETO E AGGIORNATO)

from PyQt6.QtWidgets import QMessageBox, QInputDialog 
from PyQt6.QtCore import Qt

# Import dei componenti Core del Progetto e Gestione Dati
from core.dmx_models import FixtureModello, CanaleDMX, IstanzaFixture
from core.dmx_universe import UniversoDMX
from core.data_manager import DataManager
from core.project_models import Progetto, UniversoStato, IstanzaFixtureStato 


class ProjectAndViewMixin:
    """Gestisce la persistenza, i modelli, la gestione dell'universo e le finestre secondarie."""
    
    # --- Project Lifecycle & Persistence ---
    
    def closeEvent(self, event):
        """Salva il progetto e chiude le connessioni."""
        self._salva_stato_progetto()
        self.dmx_comm.disconnect()
        if self.stage_view:
            self.stage_view.close()
        event.accept()

    def _crea_modello_esempio(self) -> list[FixtureModello]:
        """Crea un modello di fixture di esempio (PAR LED RGBW)."""
        par_modello = FixtureModello(
            "PAR LED RGBW (5ch)", 
            [
                CanaleDMX("Dimmer", "Intensità", 255), 
                CanaleDMX("Rosso", "Colore"),
                CanaleDMX("Verde", "Colore"),
                CanaleDMX("Blu", "Colore"),
                CanaleDMX("Bianco", "Colore"),
            ]
        )
        return [par_modello]
        
    def _aggiungi_modelli_virtuali(self):
        """Aggiunge modelli virtuali per fixture complesse (Algam) se il modello genitore esiste."""
        if any(m.nome == "Algam Stage Bar 24Ch" for m in self.fixture_modelli) and \
           not any(m.nome == "Algam PAR Singolo (Virtuale)" for m in self.fixture_modelli):
            
            # Modello 1: PAR Singolo (4 canali RGB+Dimmer per la simulazione)
            par_modello = FixtureModello(
                "Algam PAR Singolo (Virtuale)", 
                [
                    CanaleDMX("Red", "Colore"),
                    CanaleDMX("Green", "Colore"),
                    CanaleDMX("Blue", "Colore"),
                    CanaleDMX("Dimmer", "Intensità"),
                ]
            )
            self.fixture_modelli.append(par_modello)
            
            # Modello 2: LED Bianco (1 canale Flash per la simulazione)
            white_modello = FixtureModello(
                "Algam LED Bianco (Virtuale)", 
                [
                    CanaleDMX("White Flash", "Flash"),
                ]
            )
            self.fixture_modelli.append(white_modello)
            
            # Salvo i nuovi modelli virtuali
            DataManager.salva_modelli(self.fixture_modelli)
            
    def _crea_nuovo_universo(self, id: int, nome: str):
         """Crea un nuovo UniversoDMX e il suo stato Progetto associato."""
         nuovo_universo = UniversoDMX(id_universo=id)
         nuovo_universo.nome = nome
         self.universi[id] = nuovo_universo
         
         nuovo_stato = UniversoStato(id_universo=id, nome=nome, istanze_stato=[], scene=[], chasers=[], midi_mappings=[])
         self.progetto.universi_stato.append(nuovo_stato)
         
         return nuovo_universo

    def _ricostruisci_universi(self):
        """Ricrea gli oggetti UniversoDMX e IstanzaFixture dai dati dello stato salvato."""
        self.universi.clear()
        model_map = {m.nome: m for m in self.fixture_modelli}
        
        for u_stato in self.progetto.universi_stato:
            nuovo_universo = UniversoDMX(id_universo=u_stato.id_universo)
            nuovo_universo.nome = u_stato.nome
            
            for stato_fixture in u_stato.istanze_stato:
                modello = model_map.get(stato_fixture.modello_nome)
                if modello:
                    istanza = IstanzaFixture(modello, stato_fixture.indirizzo_inizio)
                    nuovo_universo.fixture_assegnate.append(istanza)
                    
            nuovo_universo.aggiorna_canali_universali()
            self.universi[nuovo_universo.id_universo] = nuovo_universo
            
        if not self.universi:
            self._crea_nuovo_universo(1, "Universo Principale")

    def _salva_stato_progetto(self):
        """Aggiorna lo stato del progetto con i dati correnti e salva su disco."""
        
        u_stato_map = {u.id_universo: u for u in self.progetto.universi_stato}
        
        for id_universo, universo in self.universi.items():
            u_stato = u_stato_map.get(id_universo)
            if not u_stato: continue
            
            istanze_stato_correnti = []
            
            # Mappa degli stati esistenti per recuperare il nome utente se non è in Stage View
            stato_esistente_map = {i.indirizzo_inizio: i for i in u_stato.istanze_stato}
            
            for istanza in universo.fixture_assegnate:
                # Cerca lo stato esistente, sia per posizione che per nome utente
                stato_esistente = stato_esistente_map.get(istanza.indirizzo_inizio)
                
                pos_x, pos_y = 0, 0
                nome_utente = ""
                
                if self.stage_view:
                    # Recupera posizione E NOME UTENTE da Stage View (DraggableLightWidget.fixture_stato)
                    widget = self.stage_view.light_widgets.get(istanza.indirizzo_inizio) 
                    if widget:
                        pos_x, pos_y = widget.x(), widget.y()
                        # Si assume che il widget abbia sempre l'ultimo stato salvato/trascinato
                        nome_utente = widget.fixture_stato.nome_utente
                elif stato_esistente:
                    # Recupera posizione E NOME UTENTE dallo stato precedente se Stage View è chiusa
                    pos_x, pos_y = stato_esistente.x, stato_esistente.y
                    nome_utente = stato_esistente.nome_utente
                
                # Qui si salvano solo le istanze presenti nell'universo DMX corrente.
                istanze_stato_correnti.append(IstanzaFixtureStato(
                    modello_nome=istanza.modello.nome, 
                    indirizzo_inizio=istanza.indirizzo_inizio, 
                    x=pos_x, 
                    y=pos_y,
                    nome_utente=nome_utente 
                ))
            
            u_stato.istanze_stato = istanze_stato_correnti
            
            if id_universo == self.universo_attivo.id_universo:
                # Assicurati che self.scene_list e self.chaser_list esistano e siano aggiornati
                if hasattr(self, 'scene_list'):
                    u_stato.scene = self.scene_list 
                if hasattr(self, 'chaser_list'): 
                    u_stato.chasers = self.chaser_list 
            
        DataManager.salva_progetto(self.progetto)
        # QMessageBox.information(self, "Salvataggio", "Progetto salvato con successo.") <-- Rimosso

    def _update_fixture_position(self, stato: IstanzaFixtureStato):
        """Metodo chiamato dalla StageView per aggiornare la posizione e il nome di una fixture."""
        for u_stato in self.progetto.universi_stato:
            if u_stato.id_universo == self.universo_attivo.id_universo:
                for i_stato in u_stato.istanze_stato:
                    if i_stato.indirizzo_inizio == stato.indirizzo_inizio:
                        i_stato.x = stato.x
                        i_stato.y = stato.y
                        i_stato.nome_utente = stato.nome_utente
                        return
                        
    # --- Modello Utility & UI Update ---
    
    def _get_model_names(self):
        """Restituisce una stringa formattata con i nomi dei modelli fixture caricati."""
        if self.fixture_modelli:
            return "\n".join([f"- {m.nome} ({m.numero_canali}ch)" for m in self.fixture_modelli])
        return "(Nessun modello caricato)"

    # Rimossa _popola_combo_modelli, la logica è nel Dialog

    def _update_assigned_list_ui(self):
        """Aggiorna la QListWidget con le fixture assegnate."""
        # 'self.assigned_list_widget' and 'self.btn_remove_instance' must exist
        if not hasattr(self, 'assigned_list_widget'):
            return
            
        self.assigned_list_widget.clear()
        
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo))
        stato_map = {s.indirizzo_inizio: s for s in u_stato.istanze_stato}
        
        if hasattr(self, 'btn_remove_instance'):
            if not self.universo_attivo.fixture_assegnate:
                self.assigned_list_widget.addItem("(Universo vuoto)")
                self.btn_remove_instance.setDisabled(True)
                return
            
            self.btn_remove_instance.setDisabled(False)
        else:
            if not self.universo_attivo.fixture_assegnate:
                 self.assigned_list_widget.addItem("(Universo vuoto)")
                 return
                 
        for f in self.universo_attivo.fixture_assegnate:
            start, end = f.get_indirizzi_universali()
            
            # Usa il nome utente se disponibile
            stato = stato_map.get(f.indirizzo_inizio)
            display_name = stato.nome_utente if stato and stato.nome_utente else f.modello.nome
            
            item_text = f"{display_name} @{start}-{end}"
            self.assigned_list_widget.addItem(item_text)

    # --- View Management ---

    def _open_stage_view(self):
        """Abre o porta in primo piano la finestra Stage View."""
        # Importiamo StageViewDialog qui per evitare potenziali dipendenze circolari all'avvio
        from ui.views.stage_view import StageViewDialog 
        
        u_stato = next((u for u in self.progetto.universi_stato if u.id_universo == self.universo_attivo.id_universo), None)
        
        if not self.stage_view:
            # StageViewDialog ha bisogno di parent per _update_fixture_position
            self.stage_view = StageViewDialog(
                parent=self, 
                istanze_stato=u_stato.istanze_stato if u_stato else []
            )
            self.stage_view.show()
            self.stage_view.activateWindow() # <--- DO FOCUS ALL'APERTURA
        else:
            self.stage_view.clear_and_repopulate(u_stato.istanze_stato if u_stato else [])
            self.stage_view.show()
            self.stage_view.activateWindow() # <--- DO FOCUS AL RIAPRIRE

    def _open_fixture_editor(self):
        """Permette di selezionare un modello esistente da modificare o di crearne uno nuovo."""
        # Importiamo FixtureEditorDialog qui
        from ui.components.fixture_editor import FixtureEditorDialog 
        
        modelli_editabili = [m for m in self.fixture_modelli if "Virtuale" not in m.nome]
        opzioni_modello = [m.nome for m in modelli_editabili]
        
        if not opzioni_modello:
            modello_da_modificare = None
        else:
            opzioni_modello.insert(0, "Crea Nuovo Modello...")
            
            modello_selezionato, ok = QInputDialog.getItem(
                self, 
                "Modifica Modelli Fixture", 
                "Seleziona un modello da modificare o scegli di crearne uno nuovo:",
                opzioni_modello,
                0, 
                False
            )
            
            if not ok:
                return

            if modello_selezionato == "Crea Nuovo Modello...":
                modello_da_modificare = None
            else:
                modello_da_modificare = next((m for m in modelli_editabili if m.nome == modello_selezionato), None)

        dialog = FixtureEditorDialog(self, modello_esistente=modello_da_modificare)
        dialog.model_saved.connect(self._handle_new_model) 
        dialog.exec()
        
    def _handle_new_model(self, nuovo_modello: FixtureModello):
        """Gestisce il salvataggio di un nuovo o modificato modello di fixture."""
        found = False
        for i, modello in enumerate(self.fixture_modelli):
            if modello.nome == nuovo_modello.nome:
                self.fixture_modelli[i] = nuovo_modello 
                found = True
                break
        if not found:
            self.fixture_modelli.append(nuovo_modello)
            
        DataManager.salva_modelli(self.fixture_modelli)
        
        # Non serve più popolare la combo modelli.
        QMessageBox.information(self, "Successo", f"Modello '{nuovo_modello.nome}' salvato e disponibile.")