"""
FluxUI Component Library
Premium 'Inspector-Style' Widgets for FluxDFT.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QFrame, QLineEdit, QSpinBox, 
    QDoubleSpinBox, QComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False

# --- THEME CONSTANTS ---
C_BG_MAIN = "#0d0d12"    # Deepest background
C_BG_PANEL = "#15151b"   # Sidebar/Panel background
C_BG_CARD = "#1a1a24"    # Card background
C_BORDER = "#272730"     # Subtle borders
C_ACCENT = "#7c4dff"     # Primary Purple
C_ACCENT_HOVER = "#9f7aff"
C_TEXT_PRI = "#ffffff"
C_TEXT_SEC = "#a0a0b0"
C_TEXT_MUTED = "#6c7086" # Muted/dimmed text
C_SUCCESS = "#00e676"    # Green
C_WARNING = "#ffea00"    # Yellow
C_DANGER = "#ff1744"     # Red
C_INFO = "#2979ff"       # Blue

FONTS = {
    "h1": QFont("Segoe UI", 16, QFont.Weight.Bold),
    "h2": QFont("Segoe UI", 12, QFont.Weight.Bold),
    "body": QFont("Segoe UI", 10),
    "mono": QFont("Consolas", 10),
    "mono_sm": QFont("Consolas", 9),
}

class FPanel(QFrame):
    """Base panel with consistent background."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background: {C_BG_PANEL}; border: none;")

class FSection(QWidget):
    """Section header with title and line."""
    def __init__(self, title: str, icon: str = None):
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 16, 0, 8)
        l.setSpacing(10)
        
        if HAS_ICONS and icon:
            ic = QLabel()
            ic.setPixmap(qta.icon(icon, color=C_ACCENT).pixmap(16, 16))
            l.addWidget(ic)
            
        t = QLabel(title.upper())
        t.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        t.setStyleSheet(f"color: {C_ACCENT}; letter-spacing: 1px;")
        l.addWidget(t)
        
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C_BORDER};")
        l.addWidget(line)

class FProperty(QWidget):
    """A standard property row: [Label] -> [Widget]."""
    def __init__(self, label: str, widget: QWidget, tooltip: str = ""):
        super().__init__()
        l = QHBoxLayout(self)
        l.setContentsMargins(0, 4, 0, 4)
        l.setSpacing(16)
        
        lbl = QLabel(label)
        lbl.setFont(FONTS["body"])
        lbl.setStyleSheet(f"color: {C_TEXT_SEC};")
        if tooltip:
            lbl.setToolTip(tooltip)
        
        l.addWidget(lbl)
        l.addStretch()
        
        # Style the input widget uniformly
        self._style_widget(widget)
        widget.setFixedWidth(160) # consistent width for inputs
        l.addWidget(widget)

    def _style_widget(self, w):
        base_style = f"""
            background: {C_BG_MAIN};
            color: {C_TEXT_PRI};
            border: 1px solid {C_BORDER};
            border-radius: 4px;
            padding: 4px 8px;
            selection-background-color: {C_ACCENT};
        """
        if isinstance(w, (QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox)):
            w.setStyleSheet(base_style)
            w.setMinimumHeight(32)

class FBadge(QLabel):
    """Small colored tag."""
    def __init__(self, text: str, color: str = C_INFO):
        super().__init__(f" {text} ")
        self.setFont(FONTS["mono_sm"])
        self.setStyleSheet(f"""
            background: {color}22; 
            color: {color}; 
            border: 1px solid {color}44;
            border-radius: 4px;
            padding: 2px 4px;
        """)
        self.setFixedSize(self.sizeHint())

class FButton(QPushButton):
    """Styled button."""
    def __init__(self, text: str, primary: bool = False, icon: str = None):
        super().__init__(text)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(40)
        self.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        
        if HAS_ICONS and icon:
            c = C_BG_MAIN if primary else C_TEXT_PRI
            self.setIcon(qta.icon(icon, color=c))
        
        if primary:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C_ACCENT};
                    color: {C_BG_MAIN};
                    border: none;
                    border-radius: 6px;
                }}
                QPushButton:hover {{ background-color: {C_ACCENT_HOVER}; }}
            """)
        else:
            self.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C_BG_MAIN};
                    color: {C_TEXT_PRI};
                    border: 1px solid {C_BORDER};
                    border-radius: 6px;
                }}
                QPushButton:hover {{ border: 1px solid {C_TEXT_SEC}; }}
            """)
