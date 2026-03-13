"""
Keyboard Shortcuts Overlay for FluxDFT.
Shows all available keyboard shortcuts in a semi-transparent overlay.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent

from .flux_ui import C_BG_PANEL, C_BORDER, C_ACCENT, C_TEXT_PRI, C_TEXT_SEC


class ShortcutsOverlay(QWidget):
    """Semi-transparent overlay showing all keyboard shortcuts."""
    
    SHORTCUTS = [
        # Navigation
        ("Ctrl+Tab", "Next Tab"),
        ("Ctrl+Shift+Tab", "Previous Tab"),
        ("Ctrl+W", "Close Tab"),
        
        # File Operations
        ("Ctrl+N", "New Project"),
        ("Ctrl+O", "Open File"),
        ("Ctrl+S", "Save"),
        
        # Actions
        ("Ctrl+R", "Run Calculation"),
        ("Ctrl+E", "Export"),
        
        # View
        ("F11", "Toggle Fullscreen"),
        ("?", "Show/Hide Shortcuts"),
        ("Escape", "Close Overlay"),
    ]
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self._build_ui()
        self.hide()
    
    def _build_ui(self):
        # Full-screen semi-transparent background
        self.setStyleSheet("background: rgba(0, 0, 0, 0.8);")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Center card
        card = QFrame()
        card.setFixedSize(500, 450)
        card.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 16px;
            }}
        """)
        
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(32, 24, 32, 24)
        card_layout.setSpacing(20)
        
        # Header
        header = QLabel("⌨️ Keyboard Shortcuts")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet(f"color: {C_TEXT_PRI};")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(header)
        
        # Shortcuts Grid
        grid = QGridLayout()
        grid.setSpacing(12)
        
        for i, (keys, desc) in enumerate(self.SHORTCUTS):
            row = i // 2
            col = (i % 2) * 2
            
            key_label = QLabel(keys)
            key_label.setStyleSheet(f"""
                background: {C_ACCENT};
                color: white;
                padding: 6px 12px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
            """)
            key_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            key_label.setFixedWidth(140)
            
            desc_label = QLabel(desc)
            desc_label.setStyleSheet(f"color: {C_TEXT_SEC}; font-size: 13px;")
            
            grid.addWidget(key_label, row, col)
            grid.addWidget(desc_label, row, col + 1)
        
        card_layout.addLayout(grid)
        card_layout.addStretch()
        
        # Footer
        footer = QLabel("Press Escape or ? to close")
        footer.setStyleSheet(f"color: {C_TEXT_SEC}; font-style: italic;")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(footer)
        
        # Center the card
        layout.addStretch()
        h_layout = QHBoxLayout()
        h_layout.addStretch()
        h_layout.addWidget(card)
        h_layout.addStretch()
        layout.addLayout(h_layout)
        layout.addStretch()
    
    def toggle(self):
        """Toggle visibility."""
        if self.isVisible():
            self.hide()
        else:
            # Resize to parent
            if self.parent():
                self.setGeometry(self.parent().rect())
            self.show()
            self.raise_()
    
    def keyPressEvent(self, event: QKeyEvent):
        """Close on Escape or ?"""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Question):
            self.hide()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Close on click outside card."""
        self.hide()
