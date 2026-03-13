"""
Visualization Module for FluxDFT.
Premium 'Inspector-Style' Plotting Interface.
"""

from typing import Optional, List, Tuple
from pathlib import Path
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QPushButton, QComboBox, QLabel, QFileDialog,
    QSpinBox, QDoubleSpinBox, QCheckBox, QGroupBox,
    QFormLayout, QSplitter, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt

import numpy as np

# Matplotlib
import matplotlib
matplotlib.use('QtAgg')
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qtagg import NavigationToolbar2QT as NavigationToolbar
from matplotlib.figure import Figure
import matplotlib.pyplot as plt

try:
    import qtawesome as qta
except ImportError:
    pass

from ..core.output_parser import OutputParser, BandStructure, DOS, PWOutput
from .flux_ui import (
    FPanel, FSection, FProperty, FBadge, FButton,
    C_BG_MAIN, C_BG_PANEL, C_BORDER, C_ACCENT, C_TEXT_PRI, C_TEXT_SEC, FONTS,
    C_SUCCESS, C_WARNING, C_INFO
)

logger = logging.getLogger(__name__)

class PlotCanvas(FigureCanvas):
    """Matplotlib canvas with Flux theme."""
    
    def __init__(self, parent=None, figsize=(10, 6), dpi=100):
        plt.style.use('dark_background')
        self.fig = Figure(figsize=figsize, dpi=dpi, facecolor=C_BG_MAIN)
        super().__init__(self.fig)
        
        self.axes = self.fig.add_subplot(111)
        self._style_axes()
    
    def _style_axes(self):
        self.axes.set_facecolor(C_BG_MAIN)
        self.axes.tick_params(colors=C_TEXT_SEC, labelsize=9)
        for spine in self.axes.spines.values():
            spine.set_color(C_BORDER)
        self.axes.xaxis.label.set_color(C_TEXT_SEC)
        self.axes.yaxis.label.set_color(C_TEXT_SEC)
        self.axes.title.set_color(C_TEXT_PRI)
        self.axes.grid(True, color=C_BORDER, alpha=0.3)

    def clear(self):
        self.axes.clear()
        self._style_axes()


class BasePlotTab(QWidget):
    """Base class for Inspector-style Plot Tabs."""
    
    def __init__(self, title: str, icon: str = None):
        super().__init__()
        self.parser = OutputParser()
        self._build_ui(title, icon)
        
    def _build_ui(self, title, icon):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(1)
        
        # === INSPECTOR (LEFT) ===
        self.inspector = FPanel()
        self.inspector.setFixedWidth(320)
        self.insp_layout = QVBoxLayout(self.inspector)
        self.insp_layout.setContentsMargins(20, 20, 20, 20)
        self.insp_layout.setSpacing(0)
        
        self.insp_layout.addWidget(QLabel(title, styleSheet=f"color:{C_TEXT_PRI}; font-size:16px; font-weight:bold; margin-bottom:20px;"))
        
        # Load Data Section
        self.insp_layout.addWidget(FSection("Data Source", "fa5s.database"))
        self.btn_load = FButton("Load Data File...", icon="fa5s.folder-open")
        self.btn_load.clicked.connect(self._load_data)
        self.insp_layout.addWidget(self.btn_load)
        self.lbl_file = QLabel("No file loaded")
        self.lbl_file.setStyleSheet(f"color: {C_TEXT_SEC}; font-style: italic; margin-top:8px; margin-bottom:16px;")
        self.lbl_file.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.insp_layout.addWidget(self.lbl_file)
        
        # Config Section (Subclasses add to this)
        self.insp_layout.addWidget(FSection("Plot Settings", "fa5s.sliders-h"))
        self.config_container = QWidget()
        self.config_layout = QVBoxLayout(self.config_container)
        self.config_layout.setContentsMargins(0, 0, 0, 0)
        self.insp_layout.addWidget(self.config_container)
        
        self.insp_layout.addStretch()
        
        # Export
        self.btn_export = FButton("Export Plot", primary=True, icon="fa5s.image")
        self.btn_export.clicked.connect(self._export)
        self.insp_layout.addWidget(self.btn_export)
        
        root.addWidget(self.inspector)
        
        # === PREVIEW (RIGHT) ===
        preview = QWidget()
        preview.setStyleSheet(f"background: {C_BG_MAIN};")
        p_layout = QVBoxLayout(preview)
        p_layout.setContentsMargins(0, 0, 0, 0)
        
        self.canvas = PlotCanvas()
        self.toolbar = NavigationToolbar(self.canvas, self)
        self.toolbar.setStyleSheet(f"background: {C_BG_PANEL}; border-bottom: 1px solid {C_BORDER};")
        
        p_layout.addWidget(self.toolbar)
        p_layout.addWidget(self.canvas)
        
        root.addWidget(preview)

    def add_config(self, label: str, widget: QWidget):
        self.config_layout.addWidget(FProperty(label, widget))

    def _load_data(self):
        raise NotImplementedError
        
    def load_file(self, path: Path):
        """Public method to load file programmatically."""
        # Override in subclasses if specific logic needed, but generally they call parser
        pass

    def _update_plot(self):
        raise NotImplementedError

    def _export(self):
        path, _ = QFileDialog.getSaveFileName(self, "Export Plot", "plot.png", "Images (*.png *.pdf *.svg)")
        if path:
            self.canvas.fig.savefig(path, dpi=300, facecolor=C_BG_MAIN)


class SCFPlotTab(BasePlotTab):
    """Enhanced SCF Convergence Plotter."""
    
    def __init__(self):
        self.output_data = None
        super().__init__("SCF Convergence", "fa5s.chart-line")
        
        # Controls
        self.c_type = QComboBox()
        self.c_type.addItems(["Total Energy", "Energy Change", "Accuracy"])
        self.c_type.currentTextChanged.connect(self._update_plot)
        self.add_config("Y Axis Metric", self.c_type)
        
        self.c_scale = QComboBox()
        self.c_scale.addItems(["Linear", "Logarithmic"])
        self.c_scale.setCurrentText("Logarithmic")
        self.c_scale.currentTextChanged.connect(self._update_plot)
        self.add_config("Scale", self.c_scale)
        
        self.c_grid = QComboBox()
        self.c_grid.addItems(["On", "Off"])
        self.c_grid.currentTextChanged.connect(self._update_plot)
        self.add_config("Grid", self.c_grid)

    def _load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Output", "", "QE Output (*.out *.log)")
        if path: self.load_file(Path(path))

    def load_file(self, path: Path):
        try:
            self.lbl_file.setText(path.name)
            self.output_data = self.parser.parse_pw_output(path)
            self._update_plot()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _update_plot(self):
        self.canvas.clear()
        if not self.output_data or not self.output_data.scf_steps:
            return

        ax = self.canvas.axes
        steps = self.output_data.scf_steps
        iters = [s.iteration for s in steps]
        
        metric = self.c_type.currentText()
        if metric == "Total Energy":
            y = [s.energy for s in steps]
            ylabel = "Total Energy (Ry)"
            color = C_ACCENT
        elif metric == "Energy Change":
            # calculate delta
            energies = [s.energy for s in steps]
            y = [0] + [abs(energies[i] - energies[i-1]) for i in range(1, len(energies))]
            ylabel = "|ΔE| (Ry)"
            color = C_INFO
        else: # Accuracy
            y = [s.accuracy for s in steps]
            ylabel = "Est. Accuracy (Ry)"
            color = C_SUCCESS

        scale = self.c_scale.currentText()
        if scale == "Logarithmic":
             ax.set_yscale("log")
        
        ax.plot(iters, y, 'o-', color=color, linewidth=2, markersize=5)
        ax.set_xlabel("Iteration")
        ax.set_ylabel(ylabel)
        ax.set_title(f"SCF Convergence - {metric}")
        
        if self.c_grid.currentText() == "On":
            ax.grid(True, alpha=0.3)
        else:
            ax.grid(False)
            
        self.canvas.draw()


class BandPlotTab(BasePlotTab):
    """Band Structure Plotter."""
    
    def __init__(self):
        self.data = None
        super().__init__("Band Structure", "fa5s.wave-square")
        
        self.w_fermi = QDoubleSpinBox()
        self.w_fermi.setRange(-50, 50); self.w_fermi.setDecimals(4); self.w_fermi.setSuffix(" eV")
        self.w_fermi.valueChanged.connect(self._update_plot)
        self.add_config("Fermi Level", self.w_fermi)
        
        self.w_ymin = QDoubleSpinBox(); self.w_ymin.setRange(-50, 0); self.w_ymin.setValue(-10)
        self.w_ymin.valueChanged.connect(self._update_plot)
        self.add_config("E Min", self.w_ymin)
        
        self.w_ymax = QDoubleSpinBox(); self.w_ymax.setRange(0, 50); self.w_ymax.setValue(10)
        self.w_ymax.valueChanged.connect(self._update_plot)
        self.add_config("E Max", self.w_ymax)

    def _load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open Bands", "", "Gnuplot (*.gnu)")
        if path: self.load_file(Path(path))

    def load_file(self, path: Path):
        try:
            self.lbl_file.setText(path.name)
            self.data = self.parser.parse_bands_gnu(path)
            self.w_fermi.setValue(self.data.fermi_energy)
            self._update_plot()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _update_plot(self):
        self.canvas.clear()
        if not self.data: return
        
        ax = self.canvas.axes
        fermi = self.w_fermi.value()
        k_dist = self.data.kpoint_distances
        evals = self.data.eigenvalues - fermi
        
        for b in range(self.data.n_bands):
            ax.plot(k_dist, evals[:, b], color=C_ACCENT, linewidth=1.2, alpha=0.9)
            
        ax.axhline(0, color=C_DANGER, linestyle='--', alpha=0.7, label="Fermi Level")
        
        # High symmetry lines
        if self.data.high_symmetry_points:
            for x, label in self.data.high_symmetry_points:
                ax.axvline(x, color=C_BORDER, linestyle='-')
                ax.text(x, self.w_ymax.value() + 0.2, label, ha='center', color=C_TEXT_PRI)
        
        ax.set_ylim(self.w_ymin.value(), self.w_ymax.value())
        ax.set_xlim(k_dist[0], k_dist[-1])
        ax.set_ylabel("Energy (eV)")
        ax.set_title("Electronic Band Structure")
        
        self.canvas.draw()


class DOSPlotTab(BasePlotTab):
    """DOS Plotter."""
    
    def __init__(self):
        self.data = None
        super().__init__("Density of States", "fa5s.align-left")
        
        self.w_fermi = QDoubleSpinBox()
        self.w_fermi.setRange(-50, 50); self.w_fermi.setDecimals(4)
        self.w_fermi.valueChanged.connect(self._update_plot)
        self.add_config("Fermi Level", self.w_fermi)
        
        self.w_fill = QComboBox(); self.w_fill.addItems(["Yes", "No"])
        self.w_fill.currentTextChanged.connect(self._update_plot)
        self.add_config("Fill Area", self.w_fill)

    def _load_data(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open DOS", "", "DOS (*.dos *.dat)")
        if path: self.load_file(Path(path))

    def load_file(self, path: Path):
        try:
            self.lbl_file.setText(path.name)
            self.data = self.parser.parse_dos(path)
            self.w_fermi.setValue(self.data.fermi_energy)
            self._update_plot()
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _update_plot(self):
        self.canvas.clear()
        if not self.data: return
        
        ax = self.canvas.axes
        fermi = self.w_fermi.value()
        eng = self.data.energies - fermi
        fill = (self.w_fill.currentText() == "Yes")
        
        # Plot Up
        ax.plot(eng, self.data.dos, color=C_INFO, label="Total DOS")
        if fill: ax.fill_between(eng, self.data.dos, color=C_INFO, alpha=0.2)
        
        ax.axvline(0, color=C_DANGER, linestyle='--', label="Fermi Level")
        ax.set_xlabel("Energy (eV)")
        ax.set_ylabel("DOS (states/eV)")
        ax.set_title("Density of States")
        ax.legend()
        
        self.canvas.draw()


class VisualizationPanel(QWidget):
    """Main visualization dashboard."""
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ border: none; background: {C_BG_MAIN}; }}
            QTabBar::tab {{
                background: {C_BG_PANEL};
                color: {C_TEXT_SEC};
                padding: 10px 24px;
                border: none;
                margin-right: 2px;
                font-weight: bold;
            }}
            QTabBar::tab:selected {{
                background: {C_BG_MAIN};
                color: {C_ACCENT};
                border-top: 2px solid {C_ACCENT};
            }}
        """)
        
        self.scf_tab = SCFPlotTab()
        self.tabs.addTab(self.scf_tab, "Convergence")
        self.bands_tab = BandPlotTab()
        self.tabs.addTab(self.bands_tab, "Bands")
        self.dos_tab = DOSPlotTab()
        self.tabs.addTab(self.dos_tab, "DOS")
        
        layout.addWidget(self.tabs)
    
    def process_job_results(self, job_path: Path):
        """Automatically load results from a completed job."""
        # Check for output file (scf)
        if job_path.exists():
             self.scf_tab.load_file(job_path)
        
        # Check for bands (gnu) in same dir
        gnu_files = list(job_path.parent.glob("*.gnu"))
        if gnu_files:
            self.bands_tab.load_file(gnu_files[0])
            self.tabs.setCurrentWidget(self.bands_tab)
            
        # Check for DOS
        dos_files = list(job_path.parent.glob("*.dos"))
        if dos_files:
            self.dos_tab.load_file(dos_files[0])
            self.tabs.setCurrentWidget(self.dos_tab)
