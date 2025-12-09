# ui/stage_view.py (SOVRASCRIVI COMPLETAMENTE)

from PyQt6.QtWidgets import QDialog, QWidget, QHBoxLayout, QLabel, QFrame, QVBoxLayout
from PyQt6.QtCore import Qt, QPoint, pyqtSignal
from PyQt6.QtGui import QMouseEvent

# Import corretto per la struttura unificata: IstanzaFixtureStato è un modello core.
from core.project_models import IstanzaFixtureStato 

class DraggableLightWidget(QFrame):
    """Widget che simula una luce, può essere trascinato e ne salva la posizione."""
    
    moved = pyqtSignal(IstanzaFixtureStato) 

    def __init__(self, fixture_stato: IstanzaFixtureStato, parent=None):
        super().__init__(parent)
        self.fixture_stato = fixture_stato
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        
        # 1. Aumento l'altezza per far spazio all'etichetta sotto (80 per il cerchio + 20 per l'etichetta)
        self.setGeometry(fixture_stato.x, fixture_stato.y, 80, 100) 
        self.setObjectName(f"LightWidgetContainer_{fixture_stato.indirizzo_inizio}")
        
        # Layout principale verticale per impilare luce e nome
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(2) # Piccolo spazio tra cerchio e nome
        
        # 2. Area del Cerchio (il QFrame originale)
        self.light_circle = QFrame(self)
        self.light_circle.setFixedSize(80, 80) # Dimensioni fisse per il cerchio
        self.light_circle.setObjectName(f"Light_{fixture_stato.indirizzo_inizio}")
        main_layout.addWidget(self.light_circle)
        
        # 3. Etichetta del Nome (sotto il cerchio)
        modello_nome_breve = fixture_stato.modello_nome.replace(" (Virtuale)", "")
        
        # Usa il nome utente se fornito, altrimenti il nome breve del modello
        if fixture_stato.nome_utente:
            label_text = f"{fixture_stato.nome_utente} @{fixture_stato.indirizzo_inizio}"
        else:
            label_text = f"{modello_nome_breve} @{fixture_stato.indirizzo_inizio}"
            
        self.label = QLabel(label_text)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(self.label)

        self._old_pos = None
        self._set_widget_style(0, 0, 0)

    def _set_widget_style(self, r, g, b):
        r = max(0, min(255, int(r)))
        g = max(0, min(255, int(g))) 
        b = max(0, min(255, int(b)))
        
        luminosity = (r * 0.299 + g * 0.587 + b * 0.114)
        text_color = "white" if luminosity < 128 else "black"
        
        # Applica lo stile del testo solo all'etichetta del nome (sotto)
        self.label.setStyleSheet(f"color: white; font-weight: bold; background-color: transparent;")
        
        # Applica lo stile di luce al QFrame interno (il cerchio)
        self.light_circle.setStyleSheet(f"""
            QFrame#{self.light_circle.objectName()} {{
                background-color: rgb({r}, {g}, {b});
                border: 3px solid #555;
                border-radius: 40px; 
            }}
        """)
        
    def mousePressEvent(self, event: QMouseEvent):
        # La logica di trascinamento rimane sul contenitore principale (self)
        if event.button() == Qt.MouseButton.LeftButton:
            self._old_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._old_pos is not None:
            delta = event.pos() - self._old_pos
            new_pos = self.pos() + delta
            if self.parent():
                parent_rect = self.parent().rect()
                new_x = max(0, min(new_pos.x(), parent_rect.width() - self.width()))
                new_y = max(0, min(new_pos.y(), parent_rect.height() - self.height()))
                self.move(new_x, new_y)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._old_pos is not None:
            self._old_pos = None
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            
            # Quando il widget viene rilasciato, salviamo la posizione. Il nome è già nel fixture_stato.
            self.fixture_stato.x = self.x()
            self.fixture_stato.y = self.y()
            
            self.moved.emit(self.fixture_stato)
            

class StageViewDialog(QDialog):
    """Finestra di visualizzazione scenica ridimensionabile."""
    def __init__(self, parent=None, istanze_stato: list[IstanzaFixtureStato] = None):
        super().__init__(parent)
        self.setWindowTitle("Stage View (Trascinamento)")
        self.resize(800, 600)
        
        # 1. Layout principale del Dialog
        main_layout = QHBoxLayout(self) 
        
        # 2. Stage area: Contenitore per le luci
        self.stage_area = QWidget()
        self.stage_area.setMinimumSize(400, 300)
        self.stage_area.setStyleSheet("background-color: #222; border: 1px dashed #444;")
        
        # La Stage Area non deve avere un layout per permettere il posizionamento assoluto
        
        main_layout.addWidget(self.stage_area)

        self.light_widgets: dict[int, DraggableLightWidget] = {} 
        
        if istanze_stato:
            self._popola_stage(istanze_stato)
        
        # Rimosso il flag Qt.WindowType.WindowStaysOnTopHint per permettere alle altre finestre di sovrapporsi
        self.setWindowFlags(self.windowFlags())


    def _popola_stage(self, istanze_stato: list[IstanzaFixtureStato]):
        """Crea i widget luci trascinabili."""
        main_window_parent = self.parent()

        for stato in istanze_stato:
            if stato.indirizzo_inizio not in self.light_widgets:
                light_widget = DraggableLightWidget(stato, parent=self.stage_area) 
                light_widget.show()
                self.light_widgets[stato.indirizzo_inizio] = light_widget
                
                if main_window_parent:
                     # NOTA: La MainWindow deve avere il metodo _update_fixture_position (definito in ProjectAndViewMixin)
                     # Se il parent non è la MainWindow, la connessione fallirà, ma non darà errore se il parent non è None
                     light_widget.moved.connect(main_window_parent._update_fixture_position)

    def update_light_color(self, addr_inizio: int, r: float, g: float, b: float):
        """Aggiorna il colore di un widget luce specifico."""
        widget = self.light_widgets.get(addr_inizio)
        if widget:
            widget._set_widget_style(r, g, b)
            
    def clear_and_repopulate(self, istanze_stato: list[IstanzaFixtureStato]):
        """Rimuove tutti i widget e li ricrea, usato dopo il cambio di Universo."""
        for widget in list(self.light_widgets.values()):
            try:
                # Disconnette il segnale per evitare riferimenti alla vecchia MainWindow
                widget.moved.disconnect() 
            except TypeError:
                pass
            widget.deleteLater()
            
        self.light_widgets.clear()
        
        self._popola_stage(istanze_stato)