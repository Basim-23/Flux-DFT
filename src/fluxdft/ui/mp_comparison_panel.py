"""
Materials Project Panel - Enhanced Version.
Professional table-based interface with rich details.
"""

from typing import Optional, List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QScrollArea, QTableWidget, QTableWidgetItem,
    QHeaderView, QSplitter, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..integrations.mp_client import MaterialsProjectClient, MPMaterial
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


class SearchWorker(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)
    
    def __init__(self, client, formula):
        super().__init__()
        self.client = client
        self.formula = formula
    
    def run(self):
        try:
            results = self.client.search_by_formula(self.formula)
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))


class CifFetchWorker(QThread):
    """Background worker to fetch CIF data from Materials Project."""
    finished = pyqtSignal(str, str) # formula, cif_data
    error = pyqtSignal(str)
    
    def __init__(self, client, material_id, formula):
        super().__init__()
        self.client = client
        self.material_id = material_id
        self.formula = formula
        
    def run(self):
        try:
            cif_data = self.client.get_cif(self.material_id)
            if cif_data:
                self.finished.emit(self.formula, cif_data)
            else:
                self.error.emit(f"Could not fetch CIF for {self.formula}")
        except Exception as e:
            self.error.emit(str(e))


class MPComparisonPanel(QWidget):
    """Enhanced Materials Project panel."""
    
    load_requested = pyqtSignal(str, str)  # formula, cif_content

    def __init__(self, api_key: Optional[str] = None, parent=None):
        super().__init__(parent)
        self.client = MaterialsProjectClient(api_key=api_key)
        self.current_results: List[MPMaterial] = []
        self.selected_material = None
        self.cif_worker = None
        self._build_ui()
    
    def _build_ui(self):
        self.setStyleSheet(f"background: {C_BG_MAIN};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)
        
        # Header
        header = QHBoxLayout()
        
        if HAS_ICONS:
            try:
                icon = QLabel()
                icon.setPixmap(qta.icon("fa5s.database", color=C_ACCENT).pixmap(28, 28))
                header.addWidget(icon)
            except:
                pass
        
        title = QLabel("Materials Project Database")
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {C_TEXT_PRI};")
        header.addWidget(title)
        header.addStretch()
        
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet(f"color: {C_TEXT_MUTED};")
        header.addWidget(self.status_label)
        
        layout.addLayout(header)
        
        # Search section
        search_frame = QFrame()
        search_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
        """)
        search_layout = QVBoxLayout(search_frame)
        search_layout.setContentsMargins(16, 16, 16, 16)
        search_layout.setSpacing(12)
        
        # Search row
        search_row = QHBoxLayout()
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Enter formula (Si, GaAs, Fe2O3, LiFePO4)...")
        self.search_input.setMinimumHeight(44)
        self.search_input.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG_MAIN};
                color: {C_TEXT_PRI};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                padding: 10px 16px;
                font-size: 14px;
            }}
            QLineEdit:focus {{
                border-color: {C_ACCENT};
            }}
        """)
        self.search_input.returnPressed.connect(self._on_search)
        search_row.addWidget(self.search_input)
        
        search_btn = QPushButton("Search")
        if HAS_ICONS:
            try:
                search_btn.setIcon(qta.icon("fa5s.search", color="white"))
            except:
                pass
        search_btn.setMinimumHeight(44)
        search_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 8px;
                padding: 0 24px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #9d7aff;
            }}
        """)
        search_btn.clicked.connect(self._on_search)
        search_row.addWidget(search_btn)
        
        search_layout.addLayout(search_row)
        
        # Quick buttons
        quick_row = QHBoxLayout()
        quick_label = QLabel("Quick search:")
        quick_label.setStyleSheet(f"color: {C_TEXT_MUTED}; font-size: 12px;")
        quick_row.addWidget(quick_label)
        
        for formula in ["Si", "Fe", "Cu", "GaAs", "TiO2", "BaTiO3"]:
            btn = QPushButton(formula)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: {C_BG_CARD};
                    color: {C_TEXT_SEC};
                    border: 1px solid {C_BORDER};
                    border-radius: 4px;
                    padding: 4px 12px;
                }}
                QPushButton:hover {{
                    color: {C_ACCENT};
                    border-color: {C_ACCENT};
                }}
            """)
            btn.clicked.connect(lambda checked, f=formula: self._quick_search(f))
            quick_row.addWidget(btn)
        quick_row.addStretch()
        search_layout.addLayout(quick_row)
        
        layout.addWidget(search_frame)
        
        # Main content splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Results table
        table_frame = QFrame()
        table_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
        """)
        table_layout = QVBoxLayout(table_frame)
        table_layout.setContentsMargins(12, 12, 12, 12)
        
        table_header = QLabel("Results")
        table_header.setStyleSheet(f"color: {C_TEXT_SEC}; font-weight: bold;")
        table_layout.addWidget(table_header)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Formula", "MP ID", "Space Group", "Band Gap", "Stable"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.selectionModel().selectionChanged.connect(self._on_selection)
        self.table.setStyleSheet(f"""
            QTableWidget {{
                background: {C_BG_CARD};
                color: {C_TEXT_PRI};
                border: none;
                border-radius: 6px;
                gridline-color: {C_BORDER};
            }}
            QTableWidget::item {{
                padding: 8px;
            }}
            QTableWidget::item:selected {{
                background: {C_ACCENT};
            }}
            QHeaderView::section {{
                background: {C_BG_PANEL};
                color: {C_TEXT_MUTED};
                padding: 10px;
                border: none;
                font-weight: bold;
            }}
        """)
        table_layout.addWidget(self.table)
        
        splitter.addWidget(table_frame)
        
        # Details panel
        details_frame = QFrame()
        details_frame.setStyleSheet(f"""
            QFrame {{
                background: {C_BG_PANEL};
                border: 1px solid {C_BORDER};
                border-radius: 10px;
            }}
        """)
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(16, 16, 16, 16)
        
        details_header = QLabel("Material Details")
        details_header.setStyleSheet(f"color: {C_TEXT_SEC}; font-weight: bold;")
        details_layout.addWidget(details_header)
        
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG_CARD};
                color: {C_TEXT_PRI};
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-family: 'Consolas', monospace;
            }}
        """)
        self.details_text.setPlaceholderText("Select a material to view details...")
        details_layout.addWidget(self.details_text)
        
        # Action buttons
        btn_row = QHBoxLayout()
        
        copy_btn = QPushButton("Copy Data")
        if HAS_ICONS:
            try:
                copy_btn.setIcon(qta.icon("fa5s.copy", color=C_TEXT_SEC))
            except:
                pass
        copy_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_BG_CARD};
                color: {C_TEXT_PRI};
                border: 1px solid {C_BORDER};
                border-radius: 6px;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                border-color: {C_ACCENT};
            }}
        """)
        copy_btn.clicked.connect(self._copy_data)
        btn_row.addWidget(copy_btn)
        
        self.load_btn = QPushButton("Send to Project")
        if HAS_ICONS:
            try:
                self.load_btn.setIcon(qta.icon("fa5s.file-import", color="white"))
            except:
                pass
        self.load_btn.setStyleSheet(f"""
            QPushButton {{
                background: {C_ACCENT};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #9d7aff;
            }}
        """)
        self.load_btn.clicked.connect(self._load_structure)
        btn_row.addWidget(self.load_btn)
        
        btn_row.addStretch()
        details_layout.addLayout(btn_row)
        
        splitter.addWidget(details_frame)
        splitter.setSizes([450, 350])
        
        layout.addWidget(splitter)
    
    def _quick_search(self, formula: str):
        self.search_input.setText(formula)
        self._on_search()
    
    def _on_search(self):
        formula = self.search_input.text().strip()
        if not formula:
            return
        
        self.status_label.setText(f"Searching '{formula}'...")
        self.status_label.setStyleSheet(f"color: {C_WARNING};")
        
        self.worker = SearchWorker(self.client, formula)
        self.worker.finished.connect(self._on_results)
        self.worker.error.connect(self._on_error)
        self.worker.start()
    
    def _on_results(self, results: List[MPMaterial]):
        self.current_results = results
        self.status_label.setText(f"Found {len(results)} result(s)")
        self.status_label.setStyleSheet(f"color: {C_SUCCESS};")
        
        self.table.setRowCount(len(results))
        for row, mat in enumerate(results):
            # Formula
            item = QTableWidgetItem(mat.formula_pretty)
            item.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
            self.table.setItem(row, 0, item)
            
            # MP ID
            self.table.setItem(row, 1, QTableWidgetItem(mat.material_id))
            
            # Space group
            self.table.setItem(row, 2, QTableWidgetItem(mat.spacegroup))
            
            # Band gap
            bg = f"{mat.band_gap:.2f} eV" if mat.band_gap > 0 else "Metal"
            bg_item = QTableWidgetItem(bg)
            bg_item.setForeground(QColor(C_SUCCESS if mat.band_gap > 0 else C_WARNING))
            self.table.setItem(row, 3, bg_item)
            
            # Stable
            stable = QTableWidgetItem("✓ Yes" if mat.is_stable else "✗ No")
            stable.setForeground(QColor(C_SUCCESS if mat.is_stable else C_DANGER))
            self.table.setItem(row, 4, stable)
        
        if results:
            self.table.selectRow(0)
    
    def _on_error(self, error: str):
        self.status_label.setText("Error")
        self.status_label.setStyleSheet(f"color: {C_DANGER};")
        QMessageBox.warning(self, "Error", error)
    
    def _on_selection(self):
        rows = self.table.selectedIndexes()
        if not rows:
            return
        
        row = rows[0].row()
        if row < len(self.current_results):
            self.selected_material = self.current_results[row]
            self._show_details(self.selected_material)
    
    def _show_details(self, mat: MPMaterial):
        stable_str = "Yes ✓" if mat.is_stable else "No ✗"
        metal_str = "Yes (Metal)" if mat.is_metal else "No"
        
        text = f"""
══════════════════════════════════════
  {mat.formula_pretty}
══════════════════════════════════════

IDENTIFICATION
  Material ID:     {mat.material_id}
  Formula:         {mat.formula}
  Space Group:     {mat.spacegroup}
  Crystal System:  {mat.crystal_system}

ELECTRONIC PROPERTIES
  Band Gap:        {mat.band_gap:.3f} eV
  Is Metal:        {metal_str}
  Is Magnetic:     {"Yes" if mat.is_magnetic else "No"}

STRUCTURAL PROPERTIES
  Volume:          {mat.volume:.2f} Å³
  Density:         {mat.density:.3f} g/cm³

THERMODYNAMICS
  Formation E:     {mat.formation_energy:.4f} eV/atom
  E Above Hull:    {mat.energy_above_hull:.4f} eV/atom
  Stable:          {stable_str}
"""
        self.details_text.setPlainText(text.strip())
    
    def _copy_data(self):
        if not self.selected_material:
            return
        
        from PyQt6.QtWidgets import QApplication
        mat = self.selected_material
        text = f"{mat.formula_pretty} ({mat.material_id})\nBand Gap: {mat.band_gap:.3f} eV\nVolume: {mat.volume:.2f} Å³"
        QApplication.clipboard().setText(text)
        self.status_label.setText("Copied!")

    def _load_structure(self):
        if not self.selected_material:
            return
            
        mat = self.selected_material
        
        self.status_label.setText(f"Fetching CIF for {mat.formula_pretty}...")
        self.status_label.setStyleSheet(f"color: {C_WARNING};")
        self.load_btn.setEnabled(False)
        
        self.cif_worker = CifFetchWorker(self.client, mat.material_id, mat.formula_pretty)
        self.cif_worker.finished.connect(self._on_cif_fetched)
        self.cif_worker.error.connect(self._on_cif_error)
        self.cif_worker.start()

    def _on_cif_fetched(self, formula: str, cif_data: str):
        self.status_label.setText(f"Loaded {formula} structure")
        self.status_label.setStyleSheet(f"color: {C_SUCCESS};")
        self.load_btn.setEnabled(True)
        self.load_requested.emit(formula, cif_data)
        
    def _on_cif_error(self, error: str):
        self.status_label.setText("Error fetching CIF")
        self.status_label.setStyleSheet(f"color: {C_DANGER};")
        self.load_btn.setEnabled(True)
        QMessageBox.warning(self, "Fetch Error", error)
