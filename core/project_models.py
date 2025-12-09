# core/project_models.py 

from core.dmx_models import IstanzaFixture, Scena, Chaser

class IstanzaFixtureStato:
    """Modello per salvare l'istanza fixture con la sua posizione in Stage View."""
    def __init__(self, modello_nome: str, indirizzo_inizio: int, x: int = 0, y: int = 0, nome_utente: str = ""): 
        self.modello_nome = modello_nome
        self.indirizzo_inizio = indirizzo_inizio
        self.x = x
        self.y = y
        self.nome_utente = nome_utente 
        
    def __repr__(self):
        return f"IstanzaFixtureStato(modello='{self.modello_nome}', addr={self.indirizzo_inizio}, pos=({self.x}, {self.y}), nome='{self.nome_utente}')"

class MidiMapping:
    """Modello per salvare una mappatura MIDI specifica a una Scena/Chaser."""
    def __init__(self, midi_type: str, midi_number: int, value: int, action_type: str, action_index: int, internal_only: bool = False):
        # midi_type: 'note', 'cc', 'pc'
        self.midi_type = midi_type
        # midi_number: Note/CC/PC number
        self.midi_number = midi_number
        # value: Valore specifico (es. Velocity > 0 per Note On, Soglia per CC, Program Number per PC)
        self.value = value
        # action_type: 'scene', 'chaser', 'stop'
        self.action_type = action_type
        # action_index: Indice della scena o chaser (0-based)
        self.action_index = action_index
        # [NUOVO] Indica se il messaggio deve essere consumato internamente (per DMX) e NON inviato sull'uscita MIDI.
        self.internal_only = internal_only
        
    def __repr__(self):
        return f"MidiMapping({self.midi_type}:{self.midi_number}/{self.value} -> {self.action_type}:{self.action_index}, internal_only={self.internal_only})"

class UniversoStato:
    """Salva la configurazione di un Universo DMX."""
    def __init__(self, id_universo: int, nome: str, istanze_stato: list[IstanzaFixtureStato], scene: list[Scena], chasers: list[Chaser], midi_mappings: list[MidiMapping], midi_channel: int = 0, midi_controller_port_name: str = "", dmx_port_name: str = "COM5"):
        self.id_universo = id_universo
        self.nome = nome
        self.istanze_stato = istanze_stato
        self.scene = scene
        self.chasers = chasers
        self.midi_mappings = midi_mappings
        self.midi_channel = midi_channel # 0 = ALL, 1-16 = Canale Specifico
        # L'attributo è ora 'midi_controller_port_name' per salvare la porta MIDI usata
        self.midi_controller_port_name = midi_controller_port_name 
        self.dmx_port_name = dmx_port_name # NUOVO: Porta DMX (Es: COM5)  
    def __repr__(self):
        return f"UniversoStato(ID={self.id_universo}, nome='{self.nome}', fixture_count={len(self.istanze_stato)})"

class Progetto:
    """Contenitore per lo stato completo dell'applicazione."""
    def __init__(self, universi_stato: list[UniversoStato]):
        self.universi_stato = universi_stato
        
    @classmethod
    def crea_vuoto(cls):
        """Crea un progetto con un universo di default e mappings vuoti."""
        default_universe = UniversoStato(id_universo=1, nome="Universo Principale", 
                                          istanze_stato=[], scene=[], chasers=[], midi_mappings=[], midi_channel=0, midi_controller_port_name="", dmx_port_name="COM5") 
        return cls(universi_stato=[default_universe])