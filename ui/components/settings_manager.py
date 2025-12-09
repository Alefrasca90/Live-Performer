import json
import os

class SettingsManager:
    """
    Gestisce il caricamento e il salvataggio delle impostazioni dell'applicazione
    nel file settings.json, inclusa la configurazione multi-display.
    """
    def __init__(self):
        self.path = "settings.json"
        self.data = {
            "audio_driver": None,
            "midi_port": None,
            "main_window_screen": None,     
            "video_playback_screen": None,  
            "lyrics_prompter_screen": None, 
            "lyrics_bg_color": "#000000",
            "lyrics_font_color": "#FFFFFF",
            "lyrics_highlight_color": "#00FF00", 
            "lyrics_read_ahead_time": 1.0, 
            "lyrics_scrolling_mode": True,  
            # Manteniamo solo le impostazioni MIDI globali non per brano
            "midi_clock_enabled": False, 
            "midi_clock_port": None
        }
        self.load()

    def load(self):
        """Carica le impostazioni dal file e mantiene i valori di default per le nuove chiavi."""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                try:
                    loaded_data = json.load(f)
                    self.data.update(loaded_data)
                except json.JSONDecodeError:
                    print("Errore: file settings.json corrotto. Uso impostazioni di default.")
        
        # Logica di fallback per tutte le chiavi mancanti (omessa per brevità, ma presente nel codice originale)
        if "main_window_screen" not in self.data: self.data["main_window_screen"] = None
        if "video_playback_screen" not in self.data: self.data["video_playback_screen"] = None
        if "lyrics_prompter_screen" not in self.data: self.data["lyrics_prompter_screen"] = None
        if "lyrics_bg_color" not in self.data: self.data["lyrics_bg_color"] = "#000000"
        if "lyrics_font_color" not in self.data: self.data["lyrics_font_color"] = "#FFFFFF"
        if "lyrics_highlight_color" not in self.data: self.data["lyrics_highlight_color"] = "#00FF00"
        if "lyrics_read_ahead_time" not in self.data: self.data["lyrics_read_ahead_time"] = 1.0
        if "lyrics_scrolling_mode" not in self.data: self.data["lyrics_scrolling_mode"] = True
        if "midi_clock_enabled" not in self.data: self.data["midi_clock_enabled"] = False
        if "midi_clock_port" not in self.data: self.data["midi_clock_port"] = None


    def save(self):
        """Salva lo stato corrente delle impostazioni sul file."""
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)

    def set_audio_driver(self, driver):
        """Imposta il driver audio HostAPI (indice) e salva."""
        self.data["audio_driver"] = driver
        self.save()

    def set_midi_port(self, port):
        """Imposta il nome della porta MIDI e salva."""
        self.data["midi_port"] = port
        self.save()

    def set_screen_setting(self, key, value):
        """Imposta una singola chiave di impostazione schermo."""
        if key in self.data:
            self.data[key] = value
            self.save()

    def set_lyrics_setting(self, key, value):
        """Imposta una singola chiave di impostazione lyrics."""
        if key in self.data:
            self.data[key] = value
            self.save()
            
    # Metodi di shortcut (omessi per brevità)
    def set_main_window_screen(self, screen_name):
        self.set_screen_setting("main_window_screen", screen_name)

    def set_video_playback_screen(self, screen_name):
        self.set_screen_setting("video_playback_screen", screen_name)

    def set_lyrics_prompter_screen(self, screen_name):
        self.set_screen_setting("lyrics_prompter_screen", screen_name)

    def set_lyrics_bg_color(self, color):
        self.set_lyrics_setting("lyrics_bg_color", color)

    def set_lyrics_font_color(self, color):
        self.set_lyrics_setting("lyrics_font_color", color)
        
    def set_lyrics_highlight_color(self, color):
        self.set_lyrics_setting("lyrics_highlight_color", color)

    def set_lyrics_read_ahead_time(self, time):
        self.set_lyrics_setting("lyrics_read_ahead_time", time)

    def set_lyrics_scrolling_mode(self, enabled: bool):
        self.set_lyrics_setting("lyrics_scrolling_mode", enabled)
        
    # NUOVI METODI PER MIDI CLOCK (modificati)
    def set_midi_clock_enabled(self, enabled: bool):
        """Imposta se il MIDI Clock deve essere inviato."""
        self.set_lyrics_setting("midi_clock_enabled", enabled)
    
    def set_midi_clock_port(self, port_name: str | None):
        """Imposta la porta MIDI per l'invio del Clock (Sync)."""
        self.set_lyrics_setting("midi_clock_port", port_name)