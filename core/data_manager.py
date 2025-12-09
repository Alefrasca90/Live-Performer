# core/data_manager.py (DataManager per DMX Project e Fixture Profiles)

import json
from pathlib import Path
from core.dmx_models import FixtureModello, CanaleDMX, Scena, Chaser, PassoChaser
from core.project_models import Progetto, UniversoStato, IstanzaFixtureStato, MidiMapping

# Assumiamo che la cartella 'data' sia nella root del progetto unificato
DATA_PATH = Path(__file__).parent.parent / "data"
PROFILE_FILE = DATA_PATH / "fixture_profiles.json"
PROJECT_FILE = DATA_PATH / "project.json"

class DataManager:
    
    @staticmethod
    def _modello_to_dict(modello: FixtureModello) -> dict:
        canali = [
            {'nome': c.nome, 'funzione': c.funzione, 'default': c.valore_default}
            for c in modello.descrizione_canali
        ]
        return {
            'nome': modello.nome,
            'canali': canali
        }

    @staticmethod
    def _dict_to_modello(data: dict) -> FixtureModello:
        canali = [
            CanaleDMX(c['nome'], c['funzione'], c['default'])
            for c in data['canali']
        ]
        return FixtureModello(data['nome'], canali)

    @staticmethod
    def salva_modelli(modelli: list[FixtureModello]):
        """Salva i profili delle fixture su file JSON."""
        DATA_PATH.mkdir(exist_ok=True)
        data = [DataManager._modello_to_dict(m) for m in modelli]
        try:
            with open(PROFILE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"Errore durante il salvataggio dei modelli: {e}")

    @staticmethod
    def carica_modelli() -> list[FixtureModello]:
        """Carica i profili delle fixture da file JSON."""
        if not PROFILE_FILE.exists():
            return []
        try:
            with open(PROFILE_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return [DataManager._dict_to_modello(d) for d in data]
        except (json.JSONDecodeError, KeyError):
            return []
        except Exception as e:
            print(f"Errore inatteso durante il caricamento dei modelli: {e}")
            return []

    # --- Gestione Progetto ---

    @staticmethod
    def salva_progetto(progetto: Progetto):
        """Salva l'intero stato del progetto."""
        DATA_PATH.mkdir(exist_ok=True)
        
        data_to_save = {
            "universi": []
        }
        
        for u_stato in progetto.universi_stato:
            # Serializzazione Istanze (Stato)
            istanze_ser = [
                {'modello_nome': i.modello_nome, 'addr': i.indirizzo_inizio, 'x': i.x, 'y': i.y, 'nome_utente': i.nome_utente}
                for i in u_stato.istanze_stato
            ]
            
            # Serializzazione Scene
            scene_ser = [
                {'nome': s.nome, 'valori_canali': s.valori_canali}
                for s in u_stato.scene
            ]

            # Serializzazione Chaser
            chasers_ser = [
                {
                    'nome': c.nome,
                    'passi': [
                        {
                            'scena_nome': p.scena.nome,
                            'tempo_permanenza': p.tempo_permanenza,
                            'tempo_fade_in': p.tempo_fade_in,
                            'tempo_fade_out': p.tempo_fade_out
                        }
                        for p in c.passi
                    ]
                }
                for c in u_stato.chasers
            ]
            
            # Serializzazione Mappatura MIDI
            midi_mappings_ser = [
                {
                    'midi_type': m.midi_type,
                    'midi_number': m.midi_number,
                    'value': m.value,
                    'action_type': m.action_type,
                    'action_index': m.action_index
                }
                for m in u_stato.midi_mappings
            ]

            data_to_save["universi"].append({
                'id': u_stato.id_universo,
                'nome': u_stato.nome,
                'istanze': istanze_ser,
                'scene': scene_ser,
                'chasers': chasers_ser,
                'midi_mappings': midi_mappings_ser,
                'midi_channel': u_stato.midi_channel,
                'midi_controller_port_name': u_stato.midi_controller_port_name,
                'dmx_port_name': u_stato.dmx_port_name # <-- AGGIUNTO
            })

        try:
            with open(PROJECT_FILE, 'w', encoding='utf-8') as f:
                json.dump(data_to_save, f, indent=4)
            print(f"Progetto salvato in {PROJECT_FILE}")
        except Exception as e:
            print(f"Errore durante il salvataggio del progetto: {e}")

    @staticmethod
    def carica_progetto() -> Progetto:
        """Carica lo stato del progetto. Se non esiste, crea un progetto vuoto."""
        if not PROJECT_FILE.exists():
            return Progetto.crea_vuoto()
            
        try:
            with open(PROJECT_FILE, 'r', encoding='utf-8') as f:
                # Modifica per risolvere l'errore di file vuoto
                content = f.read().strip()
                if not content:
                     print(f"AVVISO: Il file {PROJECT_FILE.name} è vuoto o contiene solo spazi bianchi. Creazione progetto vuoto.")
                     return Progetto.crea_vuoto()
                data = json.loads(content)
                
            universi_stato = []
            
            # Qui si richiede l'accesso a DMXDataManager, ma il file deve essere caricato con alias nel main.
            
            for u_data in data.get("universi", []):
                istanze_stato = [
                    IstanzaFixtureStato(
                        modello_nome=i['modello_nome'], 
                        indirizzo_inizio=i['addr'], 
                        x=i['x'], 
                        y=i['y'],
                        nome_utente=i.get('nome_utente', "")
                    ) 
                    for i in u_data.get('istanze', [])
                ]
                
                scene_list = [
                    Scena(s['nome'], {int(k): v for k, v in s['valori_canali'].items()})
                    for s in u_data.get('scene', [])
                ]

                scene_map = {s.nome: s for s in scene_list}
                
                chasers_list = []
                for c_data in u_data.get('chasers', []):
                    passi = []
                    for p_data in c_data.get('passi', []):
                        scena_nome = p_data.get('scena_nome')
                        tempo_perm = p_data.get('tempo_permanenza', 1.0)
                        tempo_fi = p_data.get('tempo_fade_in', 0.0)
                        tempo_fo = p_data.get('tempo_fade_out', 0.0)
                        
                        scena = scene_map.get(scena_nome)
                        if scena:
                            passi.append(PassoChaser(
                                scena=scena, 
                                tempo_permanenza=tempo_perm, 
                                tempo_fade_in=tempo_fi, 
                                tempo_fade_out=tempo_fo
                            ))
                            
                    if passi: 
                        chasers_list.append(Chaser(nome=c_data.get('nome', "Sequenza Senza Nome"), passi=passi))

                # Caricamento Mappatura MIDI
                midi_mappings_list = []
                for m_data in u_data.get('midi_mappings', []):
                    midi_mappings_list.append(MidiMapping(
                        midi_type=m_data.get('midi_type', 'note'),
                        midi_number=m_data.get('midi_number', 0),
                        value=m_data.get('value', 0),
                        action_type=m_data.get('action_type', 'stop'),
                        action_index=m_data.get('action_index', -1)
                    ))

                midi_channel = u_data.get('midi_channel', 0) 
                midi_controller_port_name = u_data.get('midi_controller_port_name', "") 
                dmx_port_name = u_data.get('dmx_port_name', "COM5") # <-- AGGIUNTO

                universi_stato.append(UniversoStato(
                    id_universo=u_data.get('id', 1),
                    nome=u_data.get('nome', "Universo Senza Nome"),
                    istanze_stato=istanze_stato,
                    scene=scene_list,
                    chasers=chasers_list,
                    midi_mappings=midi_mappings_list,
                    midi_channel=midi_channel,
                    midi_controller_port_name=midi_controller_port_name,
                    dmx_port_name=dmx_port_name # <-- AGGIUNTO
                ))
                
            if not universi_stato:
                 return Progetto.crea_vuoto()
                 
            return Progetto(universi_stato=universi_stato)
            
        except (json.JSONDecodeError, KeyError, Exception) as e:
            print(f"Errore durante il caricamento del progetto. Creazione progetto vuoto. Errore: {e}")
            return Progetto.crea_vuoto()