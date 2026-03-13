"""
Convergence Wizard Panel for FluxDFT.
UI for automated convergence testing of DFT parameters.
"""

from pathlib import Path
from typing import Optional, List, Dict

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QComboBox, QFrame, QSpinBox, QDoubleSpinBox,
    QProgressBar, QFileDialog, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QColor

from ..workflows.convergence_wizard import ConvergenceWizard, ConvergenceTest, ConvergenceRunner
from .flux_ui import (
    FPanel, FSection, FProperty, FButton,
    C_BG_MAIN, C_BG_PANEL, C_BG_CARD, C_BORDER, C_ACCENT,
    C_TEXT_PRI, C_TEXT_SEC, C_TEXT_MUTED,
    C_SUCCESS, C_WARNING, C_DANGER, FONTS
)

try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


class ConvergencePanel(QWidget):
    """Convergence testing wizard panel."""
    
    apply_recommended_requested = pyqtSignal(dict)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.wizard = ConvergenceWizard()
        self.runner = None
        self._build_ui()
    
    def _build_ui(self):
        self.setStyleSheet(f"background: {C_BG_MAIN};")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Header (FPanel)
        header = FPanel()
        hl = QHBoxLayout(header)
        hl.setContentsMargins(20, 16, 20, 16)
        
        if HAS_ICONS:
            try:
                ic = QLabel()
                ic.setPixmap(qta.icon("fa5s.chart-line", color=C_ACCENT).pixmap(24, 24))
                hl.addWidget(ic)
            except: pass
            
        t = QLabel("Convergence Wizard")
        t.setFont(FONTS["h1"])
        t.setStyleSheet(f"color: {C_TEXT_PRI};")
        hl.addWidget(t)
        hl.addStretch()
        layout.addWidget(header)
        
        # Content Scroll
        from PyQt6.QtWidgets import QScrollArea
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: {C_BG_MAIN}; border: none;")
        
        content = QWidget()
        cl = QVBoxLayout(content)
        cl.setContentsMargins(24, 24, 24, 24)
        cl.setSpacing(24)
        
        desc = QLabel("Automatically run sequential tests to find optimal parameter values.")
        desc.setStyleSheet(f"color: {C_TEXT_SEC};")
        cl.addWidget(desc)
        
        # Tests Section
        cl.addWidget(FSection("Test Parameters", "fa5s.vials"))
        
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)
        
        # Card 1: Ecutwfc
        cards_layout.addWidget(self._create_test_card(
            "Energy Cutoff", "ecutwfc", 
            [("Start", 30, "Ry"), ("End", 100, "Ry"), ("Step", 10, "Ry")], True
        ))
        
        # Card 2: K-points
        cards_layout.addWidget(self._create_test_card(
            "K-Point Grid", "kpoints", 
            [("Start", 2, ""), ("End", 12, ""), ("Step", 2, "")], False
        ))
        
        # Card 3: Smearing
        cards_layout.addWidget(self._create_test_card(
            "Smearing", "degauss", 
            [("Start", 0.01, "Ry"), ("End", 0.05, "Ry"), ("Step", 0.01, "Ry")], False
        ))
        
        cl.addLayout(cards_layout)
        
        # Input Section
        cl.addWidget(FSection("Execution Configuration", "fa5s.cogs"))
        
        input_panel = FPanel()
        il = QHBoxLayout(input_panel)
        il.setContentsMargins(16, 16, 16, 16)
        
        lbl = QLabel("Base Input File:")
        lbl.setStyleSheet(f"color: {C_TEXT_SEC}; font-weight: bold;")
        il.addWidget(lbl)
        
        self.input_path = QLineEdit()
        self.input_path.setPlaceholderText("Select a .in script to test...")
        self.input_path.setStyleSheet(f"""
            QLineEdit {{
                background: {C_BG_CARD}; color: {C_TEXT_PRI};
                border: 1px solid {C_BORDER}; border-radius: 6px; padding: 8px;
            }}
        """)
        il.addWidget(self.input_path)
        
        browse_btn = FButton("Browse", icon="fa5s.folder-open")
        browse_btn.clicked.connect(self._browse_input)
        il.addWidget(browse_btn)
        
        cl.addWidget(input_panel)
        
        # Progress Section
        self.progress_frame = FPanel()
        self.progress_frame.setVisible(False)
        pl = QVBoxLayout(self.progress_frame)
        pl.setContentsMargins(16, 16, 16, 16)
        
        self.progress_label = QLabel("Initializing tests...")
        self.progress_label.setStyleSheet(f"color: {C_ACCENT}; font-weight: bold;")
        pl.addWidget(self.progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet(f"""
            QProgressBar {{
                background: {C_BORDER}; border: none; border-radius: 4px; height: 10px;
            }}
            QProgressBar::chunk {{
                background: {C_ACCENT}; border-radius: 4px;
            }}
        """)
        self.progress_bar.setTextVisible(False)
        pl.addWidget(self.progress_bar)
        cl.addWidget(self.progress_frame)
        
        # Results Section
        cl.addWidget(FSection("Results Dashboard", "fa5s.chart-bar"))
        
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(["Test", "Parameter Value", "Total Energy (Ry)", "ΔEnergy", "Status"])
        self.results_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.results_table.verticalHeader().setVisible(False)
        self.results_table.setMinimumHeight(200)
        self.results_table.setStyleSheet(f"""
            QTableWidget {{
                background: {C_BG_PANEL}; color: {C_TEXT_PRI};
                gridline-color: {C_BORDER}; border: 1px solid {C_BORDER}; border-radius: 8px;
            }}
            QTableWidget::item {{ padding: 8px; }}
            QHeaderView::section {{
                background: {C_BG_MAIN}; color: {C_TEXT_SEC}; font-weight: bold;
                padding: 8px; border: none; border-bottom: 1px solid {C_BORDER};
            }}
        """)
        cl.addWidget(self.results_table)
        
        # Recommendation Area
        rec_layout = QHBoxLayout()
        self.recommendation_label = QLabel("")
        self.recommendation_label.setStyleSheet(f"""
            color: {C_SUCCESS}; padding: 12px; background: {C_SUCCESS}11;
            border: 1px solid {C_SUCCESS}44; border-radius: 6px; font-weight: bold;
        """)
        self.recommendation_label.setVisible(False)
        rec_layout.addWidget(self.recommendation_label)
        
        self.apply_rec_btn = FButton("Apply to Editor", primary=True, icon="fa5s.magic")
        self.apply_rec_btn.setVisible(False)
        self.apply_rec_btn.clicked.connect(self._apply_recommendations)
        rec_layout.addWidget(self.apply_rec_btn)
        
        cl.addLayout(rec_layout)
        
        cl.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Bottom Actions
        actions = FPanel()
        al = QHBoxLayout(actions)
        al.setContentsMargins(20, 16, 20, 16)
        
        gen_btn = FButton("Generate Files Only", icon="fa5s.file-export")
        gen_btn.clicked.connect(self._generate_files)
        al.addWidget(gen_btn)
        al.addStretch()
        
        run_btn = FButton("Run Auto-Convergence", primary=True, icon="fa5s.play")
        run_btn.setMinimumWidth(250)
        run_btn.clicked.connect(self._run_tests)
        al.addWidget(run_btn)
        
        layout.addWidget(actions)
        
    def _create_test_card(self, title: str, test_type: str, params: list, default_on: bool) -> QWidget:
        card = FPanel()
        card.setStyleSheet(f"""
            #FPanel {{
                background: {C_BG_CARD};
                border: 1px solid {C_BORDER};
                border-radius: 8px;
            }}
        """)
        vl = QVBoxLayout(card)
        vl.setContentsMargins(16, 16, 16, 16)
        
        # Header with checkbox
        hl = QHBoxLayout()
        chk = QCheckBox(title)
        chk.setChecked(default_on)
        chk.setFont(FONTS["h2"])
        chk.setStyleSheet(f"""
            QCheckBox {{ color: {C_TEXT_PRI}; }}
            QCheckBox::indicator {{
                width: 18px; height: 18px; border-radius: 4px; border: 2px solid {C_BORDER}; background: {C_BG_MAIN};
            }}
            QCheckBox::indicator:checked {{ background: {C_ACCENT}; border-color: {C_ACCENT}; }}
        """)
        setattr(self, f"{test_type}_enabled", chk)
        hl.addWidget(chk)
        hl.addStretch()
        vl.addLayout(hl)
        
        # Line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {C_BORDER};")
        vl.addWidget(line)
        
        # Inputs using FProperty concepts manually since we need inline units
        import math
        for label, default, unit in params:
            row = QHBoxLayout()
            row.setSpacing(10)
            
            lbl = QLabel(label)
            lbl.setFixedWidth(40)
            lbl.setStyleSheet(f"color: {C_TEXT_SEC};")
            row.addWidget(lbl)
            
            if isinstance(default, float):
                spin = QDoubleSpinBox()
                spin.setDecimals(2)
                spin.setRange(0.01, 1000.0)
                spin.setSingleStep(0.01 if default < 1.0 else 10.0)
            else:
                spin = QSpinBox()
                spin.setRange(1, 1000)
                
            spin.setValue(default)
            spin.setStyleSheet(f"""
                QAbstractSpinBox {{
                    background: {C_BG_MAIN}; color: {C_TEXT_PRI};
                    border: 1px solid {C_BORDER}; border-radius: 4px; padding: 6px;
                }}
            """)
            setattr(self, f"{test_type}_{label.lower()}", spin)
            row.addWidget(spin)
            
            if unit:
                ulbl = QLabel(unit)
                ulbl.setStyleSheet(f"color: {C_TEXT_MUTED};")
                row.addWidget(ulbl)
            
            row.addStretch()
            vl.addLayout(row)
            
        vl.addStretch()
        return card
    
    def _browse_input(self):
        """Browse for input file."""
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Input File", "",
            "QE Input (*.in *.pw);;All Files (*)"
        )
        if path:
            self.input_path.setText(path)
    
    def _generate_files(self):
        """Generate test input files."""
        if not self.input_path.text():
            QMessageBox.warning(self, "No Input", "Please select a base input file first.")
            return
        
        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if not output_dir:
            return
            
        self._setup_wizard_tests()
        
        try:
            input_path = Path(self.input_path.text())
            self.wizard.base_input = input_path.read_text()
            self.wizard.work_dir = Path(output_dir)
            
            files = self.wizard.generate_inputs()
            total = sum(len(f) for f in files.values())
            
            QMessageBox.information(
                self, "Files Generated",
                f"Generated {total} test input files in:\n{output_dir}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            
    def _setup_wizard_tests(self):
        self.wizard.tests = []
        if hasattr(self, 'ecutwfc_enabled') and self.ecutwfc_enabled.isChecked():
            start = self.ecutwfc_start.value()
            end = self.ecutwfc_end.value()
            step = self.ecutwfc_step.value()
            self.wizard.add_ecutwfc_test(min_cutoff=start, max_cutoff=end, step=step)
            
        if hasattr(self, 'kpoints_enabled') and self.kpoints_enabled.isChecked():
            start = self.kpoints_start.value()
            end = self.kpoints_end.value()
            step = self.kpoints_step.value()
            self.wizard.add_kpoint_test(min_k=start, max_k=end, step=step)
            
        if hasattr(self, 'degauss_enabled') and self.degauss_enabled.isChecked():
            start = self.degauss_start.value()
            end = self.degauss_end.value()
            step = self.degauss_step.value()
            # Calculate n_points roughly based on step
            n_points = max(2, int((end - start) / step) + 1)
            self.wizard.add_degauss_test(min_deg=start, max_deg=end, n_points=n_points)

    def _run_tests(self):
        """Run convergence tests dynamically."""
        if not self.wizard.generated_inputs:
            QMessageBox.warning(self, "No Files", "Please generate test files first before running.")
            return
            
        if self.runner and self.runner.isRunning():
            self.runner.cancel()
            self.progress_label.setText("Cancelling...")
            return

        # Prepare UI
        self.results_table.setRowCount(0)
        self.progress_frame.setVisible(True)
        self.progress_bar.setValue(0)
        
        # Start Runner
        self.runner = ConvergenceRunner(self.wizard)
        self.runner.progress.connect(self._on_progress)
        self.runner.point_finished.connect(self._on_point_finished)
        self.runner.finished.connect(self._on_tests_finished)
        self.runner.error.connect(self._on_error)
        self.runner.start()

    def _on_progress(self, current: int, total: int, message: str):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.progress_label.setText(message)

    def _on_point_finished(self, param: str, value: float, energy: float):
        row = self.results_table.rowCount()
        self.results_table.insertRow(row)
        
        # Fill table
        self.results_table.setItem(row, 0, QTableWidgetItem(str(param)))
        self.results_table.setItem(row, 1, QTableWidgetItem(f"{value:.4f}"))
        self.results_table.setItem(row, 2, QTableWidgetItem(f"{energy:.6f}"))
        
        # Calculate Delta E if not first row for param
        delta_str = "-"
        status_str = "Calculating..."
        status_color = C_WARNING
        
        # Find previous point for same parameter
        prev_energy = None
        for i in range(row - 1, -1, -1):
            if self.results_table.item(i, 0).text() == param:
                prev_energy = float(self.results_table.item(i, 2).text())
                break
                
        if prev_energy is not None:
            delta = abs(energy - prev_energy)
            delta_str = f"{delta:.6f}"
            
            # Simple threshold check
            threshold = 0.001
            if delta < threshold:
                status_str = "Converged ✓"
                status_color = C_SUCCESS
            else:
                status_str = "Running..."
        else:
            status_str = "Baseline"
            status_color = C_TEXT_MUTED
            
        self.results_table.setItem(row, 3, QTableWidgetItem(delta_str))
        
        status_item = QTableWidgetItem(status_str)
        status_item.setForeground(QColor(status_color))
        self.results_table.setItem(row, 4, status_item)

    def _on_tests_finished(self):
        self.progress_label.setText("All convergence tests completed successfully!")
        self.progress_bar.setValue(self.progress_bar.maximum())
        
        # Optionally show recommendation label
        summaries = self.wizard.get_summary()
        self.recommended_data = {}
        if summaries:
            recs = []
            for param, data in summaries.items():
                status = "✓" if data['converged'] else "!"
                recs.append(f"{status} {param}: Recommended = <b>{data['recommended']:.4f}</b>")
                self.recommended_data[param] = data['recommended']
            
            self.recommendation_label.setText(" | ".join(recs))
            self.recommendation_label.setVisible(True)
            self.apply_rec_btn.setVisible(True)

    def _apply_recommendations(self):
        if hasattr(self, 'recommended_data') and self.recommended_data:
            self.apply_recommended_requested.emit(self.recommended_data)
            
            # Show brief visual feedback
            original_text = self.apply_rec_btn.text()
            self.apply_rec_btn.setText("Applied!")
            self.apply_rec_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {C_SUCCESS};
                    color: {C_BG_MAIN};
                    border: none;
                    border-radius: 6px;
                }}
            """)
            
            # Reset button after 2 seconds
            import threading
            def reset():
                self.apply_rec_btn.setText(original_text)
                self.apply_rec_btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {C_ACCENT};
                        color: {C_BG_MAIN};
                        border: none;
                        border-radius: 6px;
                    }}
                    QPushButton:hover {{ background-color: #9f7aff; }}
                """)
            threading.Timer(2.0, reset).start()

    def _on_error(self, message: str):
        self.progress_label.setText("Error during execution!")
        self.progress_label.setStyleSheet(f"color: {C_DANGER};")
        QMessageBox.critical(self, "Execution Error", message)
