"""
Pseudopotential Manager Panel - Smart Edition.
Connected, intelligent, and project-aware.
Copyright (c) 2024 Dr. Sherif Yahya & Basim Nasser. MIT License.
"""

from pathlib import Path
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QFrame, QGridLayout, QScrollArea,
    QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize, QRect, QRectF
from PyQt6.QtGui import QFont, QColor, QCursor, QPainter, QPen, QBrush, QPainterPath

from ..core.pseudo_manager import PseudopotentialManager, PSEUDO_PATTERNS
from ..core.smart_pseudo import SmartPseudoManager
from .flux_ui import (
    C_BG_MAIN, C_BG_PANEL, C_BG_CARD, C_BORDER, C_ACCENT,
    C_TEXT_PRI, C_TEXT_SEC, C_TEXT_MUTED,
    C_SUCCESS, C_WARNING, C_DANGER
)

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


ELEMENT_CATEGORIES = {
    'alkali': {'elements': ['Li', 'Na', 'K', 'Rb', 'Cs', 'Fr'], 'color': '#ff6b6b'},
    'alkaline': {'elements': ['Be', 'Mg', 'Ca', 'Sr', 'Ba', 'Ra'], 'color': '#ffa94d'},
    'transition': {'elements': [
        'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
        'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
        'La', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg'],
        'color': '#74c0fc'},
    'post_transition': {'elements': ['Al', 'Ga', 'In', 'Sn', 'Tl', 'Pb', 'Bi', 'Po'], 'color': '#91a7ff'},
    'metalloid': {'elements': ['B', 'Si', 'Ge', 'As', 'Sb', 'Te', 'At'], 'color': '#b197fc'},
    'nonmetal': {'elements': ['H', 'C', 'N', 'O', 'P', 'S', 'Se'], 'color': '#69db7c'},
    'halogen': {'elements': ['F', 'Cl', 'Br', 'I'], 'color': '#22b8cf'},
    'noble': {'elements': ['He', 'Ne', 'Ar', 'Kr', 'Xe', 'Rn'], 'color': '#faa2c1'},
}

PERIODIC_TABLE = [
    ['H',  '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   'He'],
    ['Li', 'Be', '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   'B',  'C',  'N',  'O',  'F',  'Ne'],
    ['Na', 'Mg', '',   '',   '',   '',   '',   '',   '',   '',   '',   '',   'Al', 'Si', 'P',  'S',  'Cl', 'Ar'],
    ['K',  'Ca', 'Sc', 'Ti', 'V',  'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn', 'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr'],
    ['Rb', 'Sr', 'Y',  'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn', 'Sb', 'Te', 'I',  'Xe'],
    ['Cs', 'Ba', 'La', 'Hf', 'Ta', 'W',  'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg', 'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn'],
]

def get_element_color(symbol: str) -> str:
    for cat_data in ELEMENT_CATEGORIES.values():
        if symbol in cat_data['elements']:
            return cat_data['color']
    return '#868e96'


class ElementCard(QWidget):
    """Custom-painted element card — guarantees visible text."""
    
    clicked = pyqtSignal()
    
    def __init__(self, symbol: str, parent=None):
        super().__init__(parent)
        self.symbol = symbol
        self.setFixedSize(52, 52)
        self.category_color = QColor(get_element_color(symbol))
        self.is_available = symbol in PSEUDO_PATTERNS
        self.is_installed = False
        self.is_selected = False
        self._hovered = False
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMouseTracking(True)
    
    def set_installed(self, installed: bool):
        self.is_installed = installed
        self.update()
        
    def set_selected(self, selected: bool):
        self.is_selected = selected
        self.update()
    
    def enterEvent(self, event):
        self._hovered = True
        self.update()
    
    def leaveEvent(self, event):
        self._hovered = False
        self.update()
        
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.is_available:
            self.clicked.emit()
    
    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        w, h = self.width(), self.height()
        
        # --- Determine colors ---
        if not self.is_available:
            bg = QColor("#18181b")
            text_col = QColor("#3f3f46")
            border_col = QColor("#222222")
            accent = QColor("#222222")
        elif self.is_installed:
            bg = QColor("#064e3b")
            text_col = QColor("#ffffff")
            border_col = QColor(C_SUCCESS)
            accent = QColor(C_SUCCESS)
        elif self.is_selected:
            bg = QColor(self.category_color)
            bg.setAlpha(70)
            text_col = QColor("#ffffff")
            border_col = self.category_color
            accent = self.category_color
        elif self._hovered:
            bg = QColor("#3f3f46")
            text_col = QColor("#ffffff")
            border_col = self.category_color
            accent = self.category_color
        else:
            bg = QColor("#27272a")
            text_col = QColor("#ffffff")
            border_col = QColor("#3f3f46")
            accent = self.category_color
        
        # --- Draw card background ---
        rect = QRectF(1, 1, w - 2, h - 2)
        p.setPen(QPen(border_col, 1.5))
        p.setBrush(QBrush(bg))
        p.drawRoundedRect(rect, 6, 6)
        
        # --- Bottom accent bar ---
        if self.is_available and not self.is_installed and not self.is_selected:
            bar_rect = QRectF(4, h - 5, w - 8, 3)
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QBrush(accent))
            p.drawRoundedRect(bar_rect, 1.5, 1.5)
        
        # --- Draw element symbol (GUARANTEED VISIBLE) ---
        font = QFont("Segoe UI", 15)
        font.setBold(True)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        p.setFont(font)
        p.setPen(QPen(text_col))
        
        text_rect = QRect(0, -1, w, h)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, self.symbol)
        
        # --- Installed checkmark ---
        if self.is_installed:
            check_font = QFont("Segoe UI", 8)
            p.setFont(check_font)
            p.setPen(QPen(QColor(C_SUCCESS)))
            p.drawText(QRect(w - 16, 2, 14, 14), Qt.AlignmentFlag.AlignCenter, "✓")
        
        p.end()


class AutoFixWorker(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal()
    
    def __init__(self, smart_manager, elements):
        super().__init__()
        self.smart_manager = smart_manager
        self.elements = elements
        
    def run(self):
        def callback(msg, pct):
            self.progress.emit(str(msg), pct)
        self.smart_manager.auto_fix_project(self.elements, callback)
        self.finished.emit()


class ProjectStatusWidget(QFrame):
    """Widget showing status of active project elements."""
    
    fix_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 10px;
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Header row
        header = QHBoxLayout()
        
        title = QLabel("Project Status")
        title_font = QFont("Segoe UI", 13, QFont.Weight.Bold)
        title.setFont(title_font)
        title.setStyleSheet(f"color: #cdd6f4; border: none;")
        header.addWidget(title)
        
        self.status_badge = QLabel("")
        self.status_badge.setStyleSheet(f"color: #6c7086; font-weight: bold; border: none; font-size: 12px;")
        header.addWidget(self.status_badge)
        header.addStretch()
        layout.addLayout(header)
        
        # Info label
        self.elements_label = QLabel("Load a structure to see project pseudopotential status.")
        self.elements_label.setWordWrap(True)
        self.elements_label.setStyleSheet(f"color: #a6adc8; font-size: 12px; border: none;")
        layout.addWidget(self.elements_label)
        
        # Fix button (hidden by default)
        self.fix_btn = QPushButton("⚡ Auto-Fix: Download Missing")
        self.fix_btn.setVisible(False)
        self.fix_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.fix_btn.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7c3aed, stop:1 #6366f1);
                color: white; border: none; border-radius: 6px;
                padding: 8px 16px; font-weight: bold; font-size: 12px;
            }}
            QPushButton:hover {{ background: #8b5cf6; }}
        """)
        self.fix_btn.clicked.connect(self.fix_requested.emit)
        layout.addWidget(self.fix_btn)

    def update_status(self, analysis: Dict):
        missing = analysis['missing']
        installed = analysis['installed']
        all_els = missing + installed
        
        if not all_els:
            self.elements_label.setText("Load a structure to see project pseudopotential status.")
            self.status_badge.setText("")
            self.fix_btn.setVisible(False)
            return
            
        if missing:
            self.status_badge.setText("⚠ INCOMPLETE")
            self.status_badge.setStyleSheet(f"color: {C_WARNING}; font-weight: bold; border: none; font-size: 12px;")
            self.elements_label.setText(
                f"Elements: {', '.join(all_els)}  •  Missing: {', '.join(missing)}"
            )
            self.elements_label.setStyleSheet(f"color: {C_WARNING}; border: none; font-size: 12px;")
            self.fix_btn.setVisible(True)
        else:
            self.status_badge.setText("✓ READY")
            self.status_badge.setStyleSheet(f"color: {C_SUCCESS}; font-weight: bold; border: none; font-size: 12px;")
            self.elements_label.setText(
                f"All {len(installed)} pseudopotentials installed: {', '.join(installed)}"
            )
            self.elements_label.setStyleSheet(f"color: {C_SUCCESS}; border: none; font-size: 12px;")
            self.fix_btn.setVisible(False)


class PseudoManagerPanel(QWidget):
    """Smart Pseudopotential Manager Panel."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.smart = SmartPseudoManager()
        self.element_cards: Dict[str, ElementCard] = {}
        self.selected_elements: List[str] = []
        self.active_project_elements: List[str] = []
        
        self._build_ui()
        self._refresh_status()
        
    def _build_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        
        # --- Scrollable Content ---
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setStyleSheet(f"""
            QScrollArea {{ background: #11111b; border: none; }}
            QScrollBar:vertical {{ background: #11111b; width: 8px; border: none; }}
            QScrollBar::handle:vertical {{ background: #313244; border-radius: 4px; min-height: 30px; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)
        
        content = QWidget()
        content.setStyleSheet("background: #11111b;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(16)
        
        # 1. Project Status
        self.project_status = ProjectStatusWidget()
        self.project_status.fix_requested.connect(self._auto_fix)
        layout.addWidget(self.project_status)
        
        # 2. Periodic Table Header
        header_row = QHBoxLayout()
        
        pt_label = QLabel("Periodic Table")
        pt_font = QFont("Segoe UI", 14, QFont.Weight.Bold)
        pt_label.setFont(pt_font)
        pt_label.setStyleSheet("color: #cdd6f4;")
        header_row.addWidget(pt_label)
        
        header_row.addStretch()
        
        self.count_label = QLabel("0 installed")
        count_font = QFont("Segoe UI", 11)
        self.count_label.setFont(count_font)
        self.count_label.setStyleSheet(f"color: {C_SUCCESS};")
        header_row.addWidget(self.count_label)
        
        layout.addLayout(header_row)
        
        # 3. Periodic Table Grid
        grid_container = QFrame()
        grid_container.setStyleSheet("background: transparent; border: none;")
        grid = QGridLayout(grid_container)
        grid.setSpacing(3)
        grid.setContentsMargins(0, 0, 0, 0)
        
        for r, row in enumerate(PERIODIC_TABLE):
            for c, symbol in enumerate(row):
                if symbol:
                    card = ElementCard(symbol)
                    card.clicked.connect(lambda s=symbol: self._toggle_element(s))
                    self.element_cards[symbol] = card
                    grid.addWidget(card, r, c)
        
        layout.addWidget(grid_container)
        
        # 4. Legend
        legend = QHBoxLayout()
        legend.setSpacing(16)
        legend_items = [
            ("Available", "#27272a", "#ffffff"),
            ("Installed", "#064e3b", C_SUCCESS),
            ("Selected", "#3b3060", "#b197fc"),
            ("Unavailable", "#18181b", "#3f3f46"),
        ]
        for label_text, bg, fg in legend_items:
            dot = QLabel("●")
            dot.setStyleSheet(f"color: {fg}; font-size: 10px;")
            legend.addWidget(dot)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"color: #6c7086; font-size: 11px;")
            legend.addWidget(lbl)
        legend.addStretch()
        layout.addLayout(legend)
        
        layout.addStretch()
        
        scroll.setWidget(content)
        main.addWidget(scroll)
        
        # --- Bottom Action Bar ---
        bar = QFrame()
        bar.setFixedHeight(56)
        bar.setStyleSheet("background: #181825; border-top: 1px solid #313244;")
        bar_layout = QHBoxLayout(bar)
        bar_layout.setContentsMargins(20, 8, 20, 8)
        
        self.download_btn = QPushButton("Download Selected")
        self.download_btn.setEnabled(False)
        self.download_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.download_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT}; color: white; border: none;
                padding: 8px 20px; border-radius: 6px;
                font-weight: bold; font-size: 12px;
            }}
            QPushButton:disabled {{ background: #313244; color: #45475a; }}
            QPushButton:hover {{ background: #9d7aff; }}
        """)
        self.download_btn.clicked.connect(self._manual_download)
        bar_layout.addWidget(self.download_btn)
        
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.refresh_btn.setStyleSheet(f"""
            QPushButton {{
                color: #a6adc8; background: transparent;
                border: 1px solid #313244; padding: 8px 16px;
                border-radius: 6px; font-size: 12px;
            }}
            QPushButton:hover {{ background: rgba(137,180,250,0.1); color: #cdd6f4; }}
        """)
        self.refresh_btn.clicked.connect(self._refresh_status)
        bar_layout.addWidget(self.refresh_btn)
        
        bar_layout.addStretch()
        
        # Selection count
        self.sel_label = QLabel("")
        self.sel_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        bar_layout.addWidget(self.sel_label)
        
        main.addWidget(bar)
        
        # Progress bar (hidden)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setFixedHeight(4)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{ background: #181825; border: none; }}
            QProgressBar::chunk {{ background: {C_ACCENT}; }}
        """)
        main.addWidget(self.progress_bar)

    # ==========================================================================
    # Smart Connection
    # ==========================================================================
    
    def on_structure_loaded(self, elements: List[str]):
        """Slot: called when StructureViewer loads a file."""
        analysis = self.smart.analyze_coverage(elements)
        self.project_status.update_status(analysis)
        self.active_project_elements = elements
        
        # Highlight project elements
        self._clear_selection()
        for el in elements:
            if el in self.element_cards:
                self.element_cards[el].set_selected(True)
                self.selected_elements.append(el)
        self._update_ui_state()

    # ==========================================================================
    # Actions
    # ==========================================================================

    def _auto_fix(self):
        if not self.active_project_elements:
            return
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        self.worker = AutoFixWorker(self.smart, self.active_project_elements)
        self.worker.progress.connect(self._update_progress)
        self.worker.finished.connect(self._on_fix_complete)
        self.worker.start()
        
    def _manual_download(self):
        if not self.selected_elements:
            return
        self.active_project_elements = self.selected_elements[:]
        self._auto_fix()

    def _update_progress(self, msg, pct):
        self.progress_bar.setValue(pct)
        
    def _on_fix_complete(self):
        self.progress_bar.setVisible(False)
        self._refresh_status()
        if self.active_project_elements:
            self.on_structure_loaded(self.active_project_elements)
        QMessageBox.information(self, "Done", "Pseudopotentials downloaded successfully.")

    def _refresh_status(self):
        self.smart.manager._scan_installed()
        count = 0
        for symbol, card in self.element_cards.items():
            installed = self.smart.manager.is_installed(symbol)
            card.set_installed(installed)
            if installed:
                count += 1
        self.count_label.setText(f"{count} installed")
        
    def _toggle_element(self, symbol):
        if self.smart.manager.is_installed(symbol):
            return
        
        if symbol in self.selected_elements:
            self.selected_elements.remove(symbol)
            self.element_cards[symbol].set_selected(False)
        else:
            self.selected_elements.append(symbol)
            self.element_cards[symbol].set_selected(True)
        self._update_ui_state()

    def _clear_selection(self):
        for el in self.selected_elements:
            if el in self.element_cards:
                self.element_cards[el].set_selected(False)
        self.selected_elements.clear()

    def _update_ui_state(self):
        n = len(self.selected_elements)
        self.download_btn.setEnabled(n > 0)
        self.sel_label.setText(f"{n} selected" if n > 0 else "")
