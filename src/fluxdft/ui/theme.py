"""
FluxDFT Theme Manager.

Provides a cohesive dark theme and icon management using QtAwesome.
"""

from dataclasses import dataclass
from typing import Dict, Any, Optional

from PyQt6.QtGui import QColor, QPalette, QIcon
from PyQt6.QtWidgets import QApplication
import qtawesome as qta


@dataclass
class ThemeColors:
    """Dracula/Nord inspired dark theme palette."""
    background: str = "#1e1e2e"       # Base background
    surface: str = "#252535"          # Panels/Widgets
    surface_highlight: str = "#313244" # Input fields/lighter panels
    
    text_primary: str = "#cdd6f4"
    text_secondary: str = "#a6adc8"
    
    accent: str = "#89b4fa"           # Blue
    success: str = "#a6e3a1"          # Green
    warning: str = "#f9e2af"          # Yellow
    error: str = "#f38ba8"            # Red
    
    border: str = "#313244"
    selection: str = "#45475a"


class ThemeManager:
    """Manages application theme and icons."""
    
    def __init__(self):
        self.colors = ThemeColors()
    
    def apply_theme(self, app: QApplication):
        """Apply the global dark theme to the application."""
        app.setStyle("Fusion")
        
        # 1. Palette
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window, QColor(self.colors.background))
        palette.setColor(QPalette.ColorRole.WindowText, QColor(self.colors.text_primary))
        palette.setColor(QPalette.ColorRole.Base, QColor(self.colors.surface))
        palette.setColor(QPalette.ColorRole.AlternateBase, QColor(self.colors.surface_highlight))
        palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(self.colors.surface))
        palette.setColor(QPalette.ColorRole.ToolTipText, QColor(self.colors.text_primary))
        palette.setColor(QPalette.ColorRole.Text, QColor(self.colors.text_primary))
        palette.setColor(QPalette.ColorRole.Button, QColor(self.colors.surface))
        palette.setColor(QPalette.ColorRole.ButtonText, QColor(self.colors.text_primary))
        palette.setColor(QPalette.ColorRole.BrightText, QColor(self.colors.accent))
        palette.setColor(QPalette.ColorRole.Link, QColor(self.colors.accent))
        palette.setColor(QPalette.ColorRole.Highlight, QColor(self.colors.accent))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(self.colors.background))
        app.setPalette(palette)
        
        # 2. Stylesheet
        app.setStyleSheet(self._get_stylesheet())

    def _get_stylesheet(self) -> str:
        """Get global QSS stylesheet."""
        c = self.colors
        return f"""
            QWidget {{
                color: {c.text_primary};
                font-family: "Segoe UI", "Roboto", sans-serif;
                font-size: 10pt;
            }}
            
            /* Group Boxes */
            QGroupBox {{
                border: 1px solid {c.border};
                border-radius: 6px;
                margin-top: 1.5em; /* leave space at the top for the title */
                padding: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 5px;
                color: {c.accent};
            }}
            
            /* Buttons */
            QPushButton {{
                background-color: {c.surface_highlight};
                border: 1px solid {c.border};
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: {c.selection};
                border-color: {c.accent};
            }}
            QPushButton:pressed {{
                background-color: {c.accent};
                color: {c.background};
            }}
            QPushButton#primary {{
                background-color: {c.accent};
                color: {c.background};
                font-weight: bold;
            }}
            QPushButton#primary:hover {{
                background-color: #b4befe; /* lighter blue */
            }}
            QPushButton#danger {{
                background-color: {c.surface_highlight};
                color: {c.error};
                border-color: {c.error};
            }}
            QPushButton#danger:hover {{
                background-color: {c.error};
                color: {c.background};
            }}

            /* Inputs */
            QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
                background-color: {c.surface};
                border: 1px solid {c.border};
                border-radius: 4px;
                padding: 4px 8px;
                selection-background-color: {c.accent};
            }}
            QLineEdit:focus, QTextEdit:focus, QSpinBox:focus {{
                border: 1px solid {c.accent};
            }}
            
            /* Tables */
            QTableWidget {{
                background-color: {c.surface};
                border: 1px solid {c.border};
                gridline-color: {c.border};
                outline: none;
            }}
            QHeaderView::section {{
                background-color: {c.surface_highlight};
                padding: 4px;
                border: none;
                font-weight: bold;
                color: {c.text_secondary};
            }}
            QTableWidget::item:selected {{
                background-color: {c.selection};
                color: {c.text_primary};
            }}
            
            /* Scrollbars */
            QScrollBar:vertical {{
                border: none;
                background: {c.background};
                width: 10px;
                margin: 0px;
            }}
            QScrollBar::handle:vertical {{
                background: {c.surface_highlight};
                min-height: 20px;
                border-radius: 5px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            
            /* Tab Widget */
            QTabWidget::pane {{
                border: 1px solid {c.border};
                border-radius: 4px;
                background: {c.surface};
            }}
            QTabBar::tab {{
                background: {c.background};
                border: 1px solid {c.border};
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                color: {c.text_secondary};
            }}
            QTabBar::tab:selected {{
                background: {c.surface};
                color: {c.accent};
                border-bottom-color: {c.surface}; /* blend with pane */
            }}
        """

    def get_icon(self, name: str, color: Optional[str] = None) -> QIcon:
        """Get a FontAwesome icon by name (e.g., 'fa5s.play')."""
        if color is None:
            color = self.colors.text_primary
        return qta.icon(name, color=color)

# Singleton instance
theme_manager = ThemeManager()
