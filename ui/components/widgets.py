# ui/widgets.py

from PyQt6.QtWidgets import QGroupBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt

class FixtureGroupBox(QGroupBox):
    """Un QGroupBox personalizzato che può essere espanso/compresso (Accordion)."""
    
    def __init__(self, title: str, content_widget: QWidget, parent=None):
        super().__init__(title, parent)
        self.content_widget = content_widget
        
        self.toggle_btn = QPushButton("Mostra Controlli")
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setChecked(False) 
        self.toggle_btn.toggled.connect(self._toggle_content)
        
        layout = QVBoxLayout(self)
        self.setTitle("") 

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel(title), 1)
        title_layout.addWidget(self.toggle_btn)
        
        layout.addLayout(title_layout)
        layout.addWidget(self.content_widget)
        
        self.content_widget.hide()
        layout.setContentsMargins(5, 5, 5, 5)
        
    def _toggle_content(self, checked: bool):
        self.content_widget.setVisible(checked)
        self.toggle_btn.setText("Nascondi Controlli" if checked else "Mostra Controlli")