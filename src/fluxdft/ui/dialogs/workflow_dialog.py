"""
Workflow Submission Dialog.

Allows users to configure and submit workflows to the FluxDFT Execution Engine.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QComboBox, QDoubleSpinBox, QCheckBox, 
    QFrame, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...workflows.spec import RelaxationSpec, BandStructureSpec
from ...execution.engine import WorkflowEngine
from ...core.structure_loader import StructureLoader
from ...utils.config import Config

class WorkflowSubmissionDialog(QDialog):
    """
    Dialog to configure and submit a workflow.
    """
    
    def __init__(self, template_key: str, parent=None):
        super().__init__(parent)
        self.template_key = template_key
        self.setWindowTitle("Configure Workflow")
        self.setMinimumWidth(500)
        self.engine = WorkflowEngine()
        self.structure = None
        
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(16)
        self.layout.setContentsMargins(24, 24, 24, 24)
        
        # Header
        header = QLabel(f"Configure {template_key.replace('_', ' ').title()}")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        self.layout.addWidget(header)
        
        # Structure Selection
        self._create_structure_section()
        
        # Parameters Section (Dynamic based on template)
        self._create_params_section()
        
        self.layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        submit_btn = QPushButton("Submit Job")
        submit_btn.setObjectName("primary")
        submit_btn.clicked.connect(self._on_submit)
        
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(submit_btn)
        self.layout.addLayout(btn_layout)
        
        # Load Stylesheet
        self.setStyleSheet("""
            QDialog { background-color: #1e1e2e; color: #cdd6f4; }
            QLabel { color: #cdd6f4; }
            QComboBox, QDoubleSpinBox, QLineEdit {
                background-color: #313244;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 4px;
                color: #cdd6f4;
            }
            QPushButton {
                background-color: #45475a;
                color: #cdd6f4;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #585b70; }
            QPushButton#primary {
                background-color: #89b4fa;
                color: #1e1e2e;
                font-weight: bold;
            }
            QPushButton#primary:hover { background-color: #b4befe; }
        """)

    def _create_structure_section(self):
        frame = QFrame()
        frame.setStyleSheet("background-color: #181825; border-radius: 8px; padding: 12px;")
        layout = QVBoxLayout(frame)
        
        lbl = QLabel("Input Structure")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        # File picker
        self.file_btn = QPushButton("Load Structure File...")
        self.file_btn.clicked.connect(self._load_structure)
        layout.addWidget(self.file_btn)
        
        self.struct_label = QLabel("No structure loaded")
        self.struct_label.setStyleSheet("color: #f38ba8;")
        layout.addWidget(self.struct_label)
        
        self.layout.addWidget(frame)

    def _create_params_section(self):
        self.params_widgets = {}
        
        frame = QFrame()
        frame.setStyleSheet("background-color: #181825; border-radius: 8px; padding: 12px;")
        layout = QVBoxLayout(frame)
        
        lbl = QLabel("Parameters")
        lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        layout.addWidget(lbl)
        
        if "relax" in self.template_key or self.template_key == "vc_relaxation":
            # Relaxation Params
            
            # Precision
            p_layout = QHBoxLayout()
            p_layout.addWidget(QLabel("Precision:"))
            prec_cb = QComboBox()
            prec_cb.addItems(["low", "medium", "high", "production"])
            prec_cb.setCurrentText("medium")
            p_layout.addWidget(prec_cb)
            self.params_widgets["precision"] = prec_cb
            layout.addLayout(p_layout)
            
            # Force Conv
            f_layout = QHBoxLayout()
            f_layout.addWidget(QLabel("Target Forces (Ry/bohr):"))
            force_sb = QDoubleSpinBox()
            force_sb.setDecimals(5)
            force_sb.setRange(1e-6, 1e-2)
            force_sb.setValue(1e-4) # default
            force_sb.setSingleStep(1e-4)
            f_layout.addWidget(force_sb)
            self.params_widgets["target_forces"] = force_sb
            layout.addLayout(f_layout)
            
        elif "band" in self.template_key:
             # Bands Params
            d_layout = QHBoxLayout()
            d_layout.addWidget(QLabel("K-Point Density (per A^-1):"))
            dens_sb = QDoubleSpinBox()
            dens_sb.setRange(10, 100)
            dens_sb.setValue(20)
            d_layout.addWidget(dens_sb)
            self.params_widgets["line_density"] = dens_sb
            layout.addLayout(d_layout)
            
        else:
            layout.addWidget(QLabel("No configurable parameters for this template."))
            
        self.layout.addWidget(frame)

    def _load_structure(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Open Structure", "", "Structure Files (*.cif *.xyz *.POSCAR *.in)"
        )
        if filename:
            try:
                # Use our core loader (assuming it exists, otherwise pymatgen directly)
                from pymatgen.core import Structure
                self.structure = Structure.from_file(filename)
                self.struct_label.setText(f"Loaded: {self.structure.formula}")
                self.struct_label.setStyleSheet("color: #a6e3a1;")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load structure:\n{e}")

    def _on_submit(self):
        if not self.structure:
            QMessageBox.warning(self, "Missing Input", "Please load a structure first.")
            return

        try:
            # Create Spec
            spec = None
            name = f"{self.template_key}_{self.structure.formula.replace(' ', '')}"
            
            if "relax" in self.template_key:
                precision = self.params_widgets["precision"].currentText()
                forces = self.params_widgets["target_forces"].value()
                
                spec = RelaxationSpec(
                    structure=self.structure,
                    name=name,
                    relax_cell=("vc" in self.template_key),
                    precision=precision,
                    target_forces=forces
                )
                
            elif "band" in self.template_key:
                 density = self.params_widgets["line_density"].value()
                 spec = BandStructureSpec(
                     structure=self.structure,
                     name=name,
                     line_density=int(density)
                 )
            
            else:
                 # Generic fallback
                 spec = RelaxationSpec(structure=self.structure, name=name)

            # Submit
            run_id = self.engine.submit(spec)
            
            QMessageBox.information(
                self, 
                "Submission Successful", 
                f"Job submitted successfully!\nRun ID: {run_id}\n\nCheck 'Jobs' tab for progress."
            )
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Submission Error", f"Failed to submit workflow:\n{e}")
