# core/dmx_models.py

class CanaleDMX:
    def __init__(self, nome: str, funzione: str, valore_default: int = 0):
        self.nome = nome
        self.funzione = funzione
        self.valore_default = valore_default

    def __repr__(self):
        return f"CanaleDMX(nome='{self.nome}', funzione='{self.funzione}', default={self.valore_default})"
        
    def __eq__(self, other):
        if not isinstance(other, CanaleDMX):
            return NotImplemented
        return (self.nome == other.nome and 
                self.funzione == other.funzione and 
                self.valore_default == other.valore_default)


class FixtureModello:
    def __init__(self, nome: str, descrizione_canali: list['CanaleDMX']):
        self.nome = nome
        self.descrizione_canali = descrizione_canali
        self.numero_canali = len(descrizione_canali)

    def get_canale_per_indice(self, indice: int) -> 'CanaleDMX':
        """Restituisce la descrizione del canale in base all'indice (da 0 a N-1)."""
        if 0 <= indice < self.numero_canali:
            return self.descrizione_canali[indice]
        raise IndexError("Indice canale fuori limite per questa Fixture.")

    def __repr__(self):
        return f"FixtureModello(nome='{self.nome}', canali={self.numero_canali})"


class IstanzaFixture:
    def __init__(self, modello: 'FixtureModello', indirizzo_inizio: int):
        if not 1 <= indirizzo_inizio <= 512:
            raise ValueError("L'indirizzo di inizio DMX deve essere tra 1 e 512.")
            
        self.modello = modello
        self.indirizzo_inizio = indirizzo_inizio
        
        # Array dei valori DMX correnti per questa istanza
        self.valori_correnti = [
            c.valore_default for c in self.modello.descrizione_canali
        ]

    def get_indirizzi_universali(self) -> tuple[int, int]:
        """Restituisce l'intervallo di indirizzi DMX occupati (da 1 a 512)."""
        inizio = self.indirizzo_inizio
        fine = inizio + self.modello.numero_canali - 1
        return (inizio, fine)

    def set_valore_canale(self, indice_canale: int, valore: int):
        """Imposta il valore DMX (0-255) di un canale specifico della fixture."""
        if not 0 <= valore <= 255:
            raise ValueError("Il valore DMX deve essere tra 0 e 255.")
            
        self.valori_correnti[indice_canale] = valore

    def __repr__(self):
        return f"IstanzaFixture(modello='{self.modello.nome}', start_addr={self.indirizzo_inizio})"

# ----------------------------------------------------
# CLASSI SCENE E CHASER (AGGIORNATE)
# ----------------------------------------------------

class Scena:
    """
    Rappresenta un'istantanea dei valori DMX per tutte le fixture.
    """
    def __init__(self, nome: str, valori_canali: dict[int, int]):
        """
        :param nome: Nome della Scena.
        :param valori_canali: Dizionario {indirizzo_dmx (1-512): valore_dmx (0-255)}.
        """
        self.nome = nome
        self.valori_canali = valori_canali 

    def __repr__(self):
        return f"Scena(nome='{self.nome}', canali_salvati={len(self.valori_canali)})"


class PassoChaser:
    """Definisce un singolo passo all'interno di un Chaser con tempi di fade."""
    def __init__(self, scena: Scena, tempo_permanenza: float, tempo_fade_in: float = 0.0, tempo_fade_out: float = 0.0):
        """
        :param scena: La Scena da applicare in questo passo.
        :param tempo_permanenza: Tempo in secondi in cui la Scena rimane attiva.
        :param tempo_fade_in: Tempo in secondi per il fade-in della scena.
        :param tempo_fade_out: Tempo in secondi per il fade-out prima di passare al passo successivo.
        """
        self.scena = scena
        self.tempo_permanenza = tempo_permanenza
        self.tempo_fade_in = tempo_fade_in
        self.tempo_fade_out = tempo_fade_out # Nota: Questo è usato all'inizio del prossimo passo

class Chaser:
    """
    Rappresenta una sequenza di Scene riprodotte in automatico.
    """
    def __init__(self, nome: str, passi: list[PassoChaser]):
        self.nome = nome
        self.passi = passi
        self.indice_corrente = 0 

    def next_passo(self) -> PassoChaser:
        """Avanza al passo successivo, ciclando alla fine."""
        if not self.passi:
            raise IndexError("Il Chaser non contiene passi.")
            
        passo = self.passi[self.indice_corrente]
        self.indice_corrente = (self.indice_corrente + 1) % len(self.passi)
        return passo

    def __repr__(self):
        return f"Chaser(nome='{self.nome}', passi={len(self.passi)})"

class ActiveScene:
    """Rappresenta una Scena attiva con un livello Master (Submaster)."""
    def __init__(self, scena: Scena, master_value: int = 255):
        self.scena = scena
        self.master_value = master_value
        
    def __repr__(self):
        return f"ActiveScene(nome='{self.scena.nome}', master={self.master_value})"