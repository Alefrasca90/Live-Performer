# core/dmx_universe.py

from .dmx_models import IstanzaFixture, Scena # <-- Import Scena

class UniversoDMX:
    def __init__(self, id_universo: int = 1):
        self.id_universo = id_universo
        self.array_canali = [0] * 512 
        self.fixture_assegnate: list[IstanzaFixture] = []

    def verifica_sovrapposizione(self, nuova_istanza: IstanzaFixture) -> bool:
        """
        Verifica se la nuova istanza si sovrappone a una fixture esistente.
        """
        nuovo_inizio, nuovo_fine = nuova_istanza.get_indirizzi_universali()
        
        if nuovo_fine > 512:
            return True 
            
        for esistente in self.fixture_assegnate:
            esistente_inizio, esistente_fine = esistente.get_indirizzi_universali()
            
            if nuovo_inizio <= esistente_fine and nuovo_fine >= esistente_inizio:
                return True 
        
        return False

    def aggiungi_fixture(self, istanza: IstanzaFixture):
        """Aggiunge una fixture all'universo solo se non ci sono sovrapposizioni."""
        if self.verifica_sovrapposizione(istanza):
            start, end = istanza.get_indirizzi_universali()
            raise ValueError(f"Sovrapposizione indirizzo DMX: I canali {start}-{end} sono già parzialmente occupati.")
            
        self.fixture_assegnate.append(istanza)
        self.aggiorna_canali_universali()
        
    def cattura_scena(self, nome_scena: str) -> Scena:
        """
        Cattura lo stato corrente dell'Universo DMX come una Scena.
        """
        valori = {}
        
        for fixture in self.fixture_assegnate:
            start_addr, _ = fixture.get_indirizzi_universali()
            
            for i, valore in enumerate(fixture.valori_correnti):
                dmx_addr = start_addr + i
                # Usiamo l'indirizzo DMX (1-512) come chiave
                valori[dmx_addr] = valore
                
        return Scena(nome=nome_scena, valori_canali=valori)
        
    def applica_scena(self, scena: Scena):
        """
        Applica i valori di una Scena all'Universo e alle istanze fixture.
        """
        for fixture in self.fixture_assegnate:
            start_addr, end_addr = fixture.get_indirizzi_universali()
            
            for i in range(fixture.modello.numero_canali):
                dmx_addr = start_addr + i
                
                if dmx_addr in scena.valori_canali:
                    nuovo_valore = scena.valori_canali[dmx_addr]
                    
                    # Imposta il valore direttamente sull'istanza fixture
                    fixture.set_valore_canale(i, nuovo_valore)
        
        # Aggiorna l'array universale con i nuovi valori
        self.aggiorna_canali_universali()

    def aggiorna_canali_universali(self):
        """
        Popola l'array_canali (i 512 byte grezzi) prendendo i dati 
        dalle fixture assegnate. 
        """
        self.array_canali = [0] * 512
        
        for fixture in self.fixture_assegnate:
            start_idx_universale = fixture.indirizzo_inizio - 1 
            
            for i, valore in enumerate(fixture.valori_correnti):
                target_index = start_idx_universale + i
                
                if 0 <= target_index < 512:
                    self.array_canali[target_index] = valore

    def set_valore_fixture(self, fixture_instance: IstanzaFixture, indice_canale: int, valore: int):
        """Imposta il valore di un canale specifico e aggiorna l'universo."""
        fixture_instance.set_valore_canale(indice_canale, valore)
        self.aggiorna_canali_universali()
        
    def __repr__(self):
        return f"UniversoDMX(ID={self.id_universo}, fixture_count={len(self.fixture_assegnate)})"