"""
Property Dashboard for FluxDFT.
Premium 'Inspector-Style' Results Viewer.
"""

from typing import Optional, Dict, List, Any
from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QFrame, QScrollArea, QGroupBox, QTabWidget,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from .flux_ui import (
    FPanel, FSection, FProperty, FBadge, FButton,
    C_BG_MAIN, C_BG_PANEL, C_BORDER, C_ACCENT, C_TEXT_PRI, C_TEXT_SEC, 
    C_SUCCESS, C_WARNING, C_DANGER, C_INFO, FONTS
)

logger = logging.getLogger(__name__)


class PropertyCard(QFrame):
    """Premium property display card."""
    
    def __init__(self, name: str, value: Any = None, unit: str = "", color: str = C_ACCENT):
        super().__init__()
        self.color = color
        self.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                border-left: 3px solid {color};
            }}
            QFrame:hover {{ border-color: {color}; }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        
        lbl = QLabel(name.upper())
        lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        lbl.setStyleSheet(f"color: {C_TEXT_SEC}; letter-spacing: 1px; border:none; background:transparent;")
        layout.addWidget(lbl)
        
        self.val_lbl = QLabel("--")
        self.val_lbl.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        self.val_lbl.setStyleSheet(f"color: {color}; border:none; background:transparent;")
        layout.addWidget(self.val_lbl)
        
        if unit:
            u = QLabel(unit)
            u.setStyleSheet(f"color: {C_TEXT_SEC}; font-size: 10px; border:none; background:transparent;")
            layout.addWidget(u)

        self.set_value(value)
    
    def set_value(self, value: Any):
        if value is None:
            txt = "--"
        elif isinstance(value, float):
             txt = f"{value:.4f}"
        else:
             txt = str(value)
        self.val_lbl.setText(txt)


class PropertyDashboard(QWidget):
    """Premium results dashboard."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header
        header = FPanel()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        
        t = QLabel("Calculation Results")
        t.setFont(FONTS["h1"])
        t.setStyleSheet(f"color: {C_TEXT_PRI};")
        hl.addWidget(t)
        hl.addStretch()
        
        b_ex = FButton("Export Report", primary=True, icon="fa5s.file-pdf")
        hl.addWidget(b_ex)
        layout.addWidget(header)
        
        # Main Scroll
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {C_BG_MAIN}; border: none;")
        
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(24)
        
        # Energy Section
        cl.addWidget(FSection("Electronic Structure", "fa5s.bolt"))
        grid_e = QGridLayout()
        grid_e.setSpacing(16)
        
        self.card_etot = PropertyCard("Total Energy", color=C_ACCENT, unit="eV")
        self.card_efermi = PropertyCard("Fermi Energy", color=C_INFO, unit="eV")
        self.card_bg = PropertyCard("Band Gap", color=C_SUCCESS, unit="eV")
        self.card_vol = PropertyCard("Volume", color=C_WARNING, unit="Å³")
        
        grid_e.addWidget(self.card_etot, 0, 0)
        grid_e.addWidget(self.card_efermi, 0, 1)
        grid_e.addWidget(self.card_bg, 0, 2)
        grid_e.addWidget(self.card_vol, 0, 3)
        cl.addLayout(grid_e)
        
        # Forces Section
        cl.addWidget(FSection("Forces & Stress", "fa5s.arrows-alt"))
        
        self.force_table = QTableWidget()
        self._style_table(self.force_table)
        self.force_table.setColumnCount(4)
        self.force_table.setHorizontalHeaderLabels(["Element", "Fx", "Fy", "Fz"])
        self.force_table.setMinimumHeight(200)
        cl.addWidget(self.force_table)
        
        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)

    def _style_table(self, table):
        table.setStyleSheet(f"""
            QTableWidget {{
                background: {C_BG_PANEL};
                color: {C_TEXT_PRI};
                gridline-color: {C_BORDER};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
            QHeaderView::section {{
                background: {C_BG_MAIN};
                color: {C_TEXT_SEC};
                padding: 8px;
                border: none;
                border-bottom: 1px solid {C_BORDER};
            }}
        """)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)

    def set_results(self, res: Dict[str, Any]):
        """Update dashboard."""
        if 'total_energy' in res: self.card_etot.set_value(res['total_energy'])
        if 'fermi_energy' in res: self.card_efermi.set_value(res['fermi_energy'])
        if 'volume' in res: self.card_vol.set_value(res['volume'])
        if 'band_gap' in res: self.card_bg.set_value(res['band_gap'])
