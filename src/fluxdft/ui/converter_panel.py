"""
FluxDFT Converter & HPC Panel
Premium 'Inspector-Style' Layout Implementation.
"""

from pathlib import Path
from typing import Optional, Dict, Any, List
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTextEdit, QFileDialog, QComboBox,
    QSpinBox, QLineEdit, QTabWidget, QMessageBox,
    QDoubleSpinBox, QScrollArea, QFrame, QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QPalette, QColor, QIcon

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False

from ..core.structure_importer import StructureImporter, ImportedStructure
from ..core.scf_generator import (
    generate_scf_config, generate_scf_input_text, analyze_structure_for_scf
)
from .flux_ui import (
    FPanel, FSection, FProperty, FBadge, FButton,
    C_BG_MAIN, C_BG_PANEL, C_BORDER, C_ACCENT, C_TEXT_PRI, C_TEXT_SEC, FONTS,
    C_SUCCESS, C_WARNING, C_INFO
)

logger = logging.getLogger(__name__)

# --- MAIN COMPONENTS ---

class ConverterPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Tabs container with custom style
        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {C_BG_MAIN}; }}
            QTabBar::tab {{
                background: {C_BG_PANEL};
                color: {C_TEXT_SEC};
                padding: 12px 20px;
                border: none;
                margin-right: 2px;
            }}
            QTabBar::tab:selected {{
                background: {C_BG_MAIN};
                color: {C_ACCENT};
                border-top: 2px solid {C_ACCENT};
            }}
        """)
        
        tabs.addTab(StructureTab(), "Structure Converter")
        tabs.addTab(HpcTab(), "HPC Scripts")
        layout.addWidget(tabs)


class StructureTab(QWidget):
    def __init__(self):
        super().__init__()
        self.importer = StructureImporter()
        self.structure = None
        self._build_ui()

    def _build_ui(self):
        # MAIN SPLIT LAYOUT
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1) # Gap filled by background

        # === LEFT INSPECTOR PANEL ===
        inspector_frame = FPanel()
        inspector_frame.setFixedWidth(350)
        insp_layout = QVBoxLayout(inspector_frame)
        insp_layout.setContentsMargins(20, 20, 20, 20)
        insp_layout.setSpacing(0)

        # 1. Header
        l_title = QLabel("Configuration")
        l_title.setFont(FONTS["h2"])
        l_title.setStyleSheet(f"color: {C_TEXT_PRI}; margin-bottom: 20px;")
        insp_layout.addWidget(l_title)

        # Scroll Area for properties
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")
        scroll_content = QWidget()
        self.form_layout = QVBoxLayout(scroll_content)
        self.form_layout.setContentsMargins(0, 0, 4, 0) # minimal margins
        self.form_layout.setSpacing(0)
        
        # -- File --
        self.form_layout.addWidget(FSection("Source", "fa5s.file-import"))
        self.btn_load = FButton("Load Structure File", icon="fa5s.folder-open")
        self.btn_load.clicked.connect(self._load)
        self.form_layout.addWidget(self.btn_load)
        self.lbl_filename = QLabel("No file loaded")
        self.lbl_filename.setStyleSheet(f"color: {C_TEXT_SEC}; font-style: italic; margin-top: 8px;")
        self.lbl_filename.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.form_layout.addWidget(self.lbl_filename)

        # -- Analysis --
        self.form_layout.addWidget(FSection("Analysis", "fa5s.microscope"))
        self.badges_layout = QHBoxLayout() # Container for dynamic badges
        self.badges_layout.setSpacing(8)
        self.form_layout.addLayout(self.badges_layout)
        self.lbl_analysis_ph = QLabel("Waiting for structure...")
        self.lbl_analysis_ph.setStyleSheet(f"color: {C_BORDER};")
        self.form_layout.addWidget(self.lbl_analysis_ph)

        # -- Parameters --
        self.form_layout.addWidget(FSection("Parameters", "fa5s.sliders-h"))
        
        self.calc_type = QComboBox()
        self.calc_type.addItems(["scf", "relax", "vc-relax", "nscf", "bands"])
        self.form_layout.addWidget(FProperty("Calculation", self.calc_type))
        
        self.w_ecut = QDoubleSpinBox()
        self.w_ecut.setRange(10, 500); self.w_ecut.setValue(50); self.w_ecut.setSuffix(" Ry")
        self.form_layout.addWidget(FProperty("Cutoff (wfc)", self.w_ecut))
        
        self.w_mixing = QDoubleSpinBox()
        self.w_mixing.setRange(0.01, 0.9); self.w_mixing.setValue(0.3); self.w_mixing.setSingleStep(0.05)
        self.form_layout.addWidget(FProperty("Mixing Beta", self.w_mixing))
        
        self.w_smearing = QComboBox()
        self.w_smearing.addItems(["cold", "gaussian", "mp", "mv"])
        self.form_layout.addWidget(FProperty("Smearing", self.w_smearing))

        self.form_layout.addStretch()
        scroll.setWidget(scroll_content)
        insp_layout.addWidget(scroll)

        # Generate Action (Sticky Bottom)
        self.btn_gen = FButton("Generate Input", primary=True, icon="fa5s.bolt")
        self.btn_gen.clicked.connect(self._generate)
        insp_layout.addWidget(self.btn_gen)
        
        root.addWidget(inspector_frame)

        # === RIGHT PREVIEW PANEL ===
        preview_frame = QWidget()
        preview_frame.setStyleSheet(f"background: {C_BG_MAIN};")
        prev_layout = QVBoxLayout(preview_frame)
        prev_layout.setContentsMargins(20, 20, 20, 20)
        
        # Header
        r_header = QHBoxLayout()
        r_title = QLabel("Generated Input")
        r_title.setFont(FONTS["h2"])
        r_title.setStyleSheet(f"color: {C_TEXT_PRI};")
        r_header.addWidget(r_title)
        r_header.addStretch()
        r_btn_save = FButton("Save to File...", icon="fa5s.save")
        r_btn_save.setFixedWidth(140)
        r_btn_save.setFixedHeight(32)
        r_btn_save.clicked.connect(self._save)
        r_header.addWidget(r_btn_save)
        prev_layout.addLayout(r_header)

        # Editor
        self.editor = QTextEdit()
        self.editor.setFont(FONTS["mono"])
        self.editor.setPlaceholderText("INPUT_PW.in preview...")
        self.editor.setStyleSheet(f"""
            QTextEdit {{
                background: {C_BG_PANEL};
                color: {C_ACCENT};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
                padding: 16px;
                line-height: 1.5;
            }}
        """)
        prev_layout.addWidget(self.editor)
        
        root.addWidget(preview_frame)

    def _load(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Structure", "", "Structure Files (*.cif *.poscar *.xyz *.json)")
        if not path: return
        
        try:
            self.lbl_filename.setText(Path(path).name)
            self.structure = self.importer.import_file(Path(path))
            
            # Run Analysis
            elements = self.structure.elements
            res = analyze_structure_for_scf(elements, self.structure.n_atoms)
            
            # Update Badges
            self._clear_badges()
            self.lbl_analysis_ph.hide()
            
            if res['requires_dft_u']: self._add_badge("DFT+U", C_ACCENT)
            if res['is_magnetic']: self._add_badge("MAGNETIC", C_WARNING)
            if res['is_metallic']: self._add_badge("METAL", C_INFO)
            else: self._add_badge("INSULATOR", C_SUCCESS)
            
            # Defaults
            self.w_ecut.setValue(res['recommended_ecutwfc'])
            
        except Exception as e:
            QMessageBox.critical(self, "Import Error", str(e))

    def _clear_badges(self):
        for i in reversed(range(self.badges_layout.count())): 
            self.badges_layout.itemAt(i).widget().setParent(None)

    def _add_badge(self, text, color):
        self.badges_layout.addWidget(FBadge(text, color))

    def _generate(self):
        if not self.structure: return
        try:
            overrides = {
                'ecutwfc': self.w_ecut.value(),
                'mixing_beta': self.w_mixing.value(),
                'smearing': self.w_smearing.currentText()
            }
            config = generate_scf_config(
                self.structure.elements, 
                self.structure.n_atoms, 
                overrides['ecutwfc'], 
                overrides
            )
            data = self.importer.to_qe_format(self.structure)
            txt = generate_scf_input_text(data, config, self.calc_type.currentText())
            self.editor.setPlainText(txt)
        except Exception as e:
            QMessageBox.warning(self, "Generation Error", str(e))

    def _save(self):
        if not self.editor.toPlainText(): return
        path, _ = QFileDialog.getSaveFileName(self, "Save Input", "pw.in", "QE Input (*.in)")
        if path: Path(path).write_text(self.editor.toPlainText())


class HpcTab(QWidget):
    def __init__(self):
        super().__init__()
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)

        # INSPECTOR
        insp = FPanel()
        insp.setFixedWidth(350)
        il = QVBoxLayout(insp)
        il.setContentsMargins(20, 20, 20, 20)
        
        il.addWidget(QLabel("Job Settings", styleSheet=f"color:{C_TEXT_PRI}; font-size:16px; font-weight:bold; margin-bottom:20px;"))
        
        il.addWidget(FSection("Scheduler", "fa5s.server"))
        self.i_sched = QComboBox(); self.i_sched.addItems(["SLURM", "PBS", "SGE"])
        il.addWidget(FProperty("System", self.i_sched))
        self.i_name = QLineEdit("qe_calc"); 
        il.addWidget(FProperty("Job Name", self.i_name))
        
        il.addWidget(FSection("Resources", "fa5s.microchip"))
        self.i_nodes = QSpinBox(); self.i_nodes.setRange(1, 999); self.i_nodes.setValue(1)
        il.addWidget(FProperty("Nodes", self.i_nodes))
        self.i_tasks = QSpinBox(); self.i_tasks.setRange(1, 256); self.i_tasks.setValue(32)
        il.addWidget(FProperty("Tasks/Node", self.i_tasks))
        self.i_time = QLineEdit("24:00:00")
        il.addWidget(FProperty("Wall Time", self.i_time))
        
        il.addStretch()
        btn = FButton("Generate Script", primary=True, icon="fa5s.code")
        btn.clicked.connect(self._gen)
        il.addWidget(btn)
        
        root.addWidget(insp)

        # PREVIEW
        prev = QWidget()
        prev.setStyleSheet(f"background: {C_BG_MAIN};")
        pl = QVBoxLayout(prev)
        pl.setContentsMargins(20, 20, 20, 20)
        
        ph = QHBoxLayout()
        ph.addWidget(QLabel("Script Preview", styleSheet=f"color:{C_TEXT_PRI}; font-size:16px; font-weight:bold;"))
        ph.addStretch()
        sv = FButton("Save...", icon="fa5s.save"); sv.setFixedWidth(120); sv.setFixedHeight(32)
        sv.clicked.connect(self._save)
        ph.addWidget(sv)
        pl.addLayout(ph)
        
        self.editor = QTextEdit()
        self.editor.setFont(FONTS["mono"])
        self.editor.setStyleSheet(f"background:{C_BG_PANEL}; color:{C_WARNING}; border:1px solid {C_BORDER}; border-radius:8px; padding:16px;")
        pl.addWidget(self.editor)
        
        root.addWidget(prev)

    def _gen(self):
        s = self.i_sched.currentText()
        txt = f"#!/bin/bash\n# {s} Submission for {self.i_name.text()}\n"
        txt += f"#NODES={self.i_nodes.value()} TASKS={self.i_tasks.value()} TIME={self.i_time.text()}\n\n"
        txt += "module load intel mpi\nmpirun pw.x -in input.in > output.out"
        self.editor.setPlainText(txt)

    def _save(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save", "submit.sh")
        if path: Path(path).write_text(self.editor.toPlainText())
