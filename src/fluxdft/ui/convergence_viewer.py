"""
Convergence Viewer for FluxDFT.

Plots SCF convergence (energy vs iteration) from QE output.
"""

from pathlib import Path
from typing import List, Tuple, Optional
import re

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QMessageBox, QComboBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

try:
    import matplotlib
    matplotlib.use('QtAgg')
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


class ConvergenceViewer(QWidget):
    """SCF Convergence plotter for QE output files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.output_file: Optional[Path] = None
        self.auto_refresh = False
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._refresh_plot)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the convergence viewer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        
        # Header
        header = QLabel("SCF Convergence")
        header.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        header.setStyleSheet("color: #a855f7;")
        layout.addWidget(header)
        
        # Toolbar
        toolbar = QHBoxLayout()
        
        load_btn = QPushButton("Load Output File")
        load_btn.clicked.connect(self._load_output)
        load_btn.setStyleSheet("""
            QPushButton {
                background-color: #16162a;
                border: 1px solid #252540;
                border-radius: 6px;
                padding: 6px 12px;
                color: #c0c0d0;
            }
            QPushButton:hover {
                background-color: #1f1f3a;
                border-color: #7c3aed;
            }
        """)
        toolbar.addWidget(load_btn)
        
        self.plot_type = QComboBox()
        self.plot_type.addItems(["Energy vs Iteration", "Energy Change", "Estimated Error"])
        self.plot_type.currentIndexChanged.connect(self._update_plot)
        toolbar.addWidget(self.plot_type)
        
        self.auto_refresh_btn = QPushButton("Auto-Refresh")
        self.auto_refresh_btn.setCheckable(True)
        self.auto_refresh_btn.clicked.connect(self._toggle_auto_refresh)
        self.auto_refresh_btn.setStyleSheet(load_btn.styleSheet())
        toolbar.addWidget(self.auto_refresh_btn)
        
        toolbar.addStretch()
        layout.addLayout(toolbar)
        
        # Plot area
        if HAS_MATPLOTLIB:
            self.figure = Figure(figsize=(8, 5), facecolor='#0d0d14')
            self.canvas = FigureCanvasQTAgg(self.figure)
            layout.addWidget(self.canvas)
            
            self.ax = self.figure.add_subplot(111)
            self._style_axes()
        else:
            no_mpl = QLabel("Matplotlib not available.\nInstall with: pip install matplotlib")
            no_mpl.setStyleSheet("color: #f59e0b;")
            no_mpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(no_mpl)
        
        # Info label
        self.info_label = QLabel("No output file loaded")
        self.info_label.setStyleSheet("color: #808098;")
        layout.addWidget(self.info_label)
    
    def _style_axes(self):
        """Apply dark theme to matplotlib axes."""
        self.ax.set_facecolor('#0d0d14')
        self.ax.spines['bottom'].set_color('#3f3f5a')
        self.ax.spines['top'].set_color('#3f3f5a')
        self.ax.spines['left'].set_color('#3f3f5a')
        self.ax.spines['right'].set_color('#3f3f5a')
        self.ax.tick_params(colors='#c0c0d0')
        self.ax.xaxis.label.set_color('#c0c0d0')
        self.ax.yaxis.label.set_color('#c0c0d0')
        self.ax.title.set_color('#e4e4ef')
    
    def _load_output(self):
        """Load a QE output file."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open QE Output File",
            "",
            "Output Files (*.out *.log);;All Files (*)"
        )
        
        if filepath:
            self.output_file = Path(filepath)
            self._parse_and_plot()
    
    def load_output_file(self, filepath: str):
        """Load output file programmatically."""
        self.output_file = Path(filepath)
        self._parse_and_plot()
    
    def _parse_output(self) -> Tuple[List[float], List[float]]:
        """Parse SCF energies from output file."""
        if not self.output_file or not self.output_file.exists():
            return [], []
        
        energies = []
        iterations = []
        
        try:
            with open(self.output_file, 'r') as f:
                content = f.read()
            
            # Pattern for SCF energy: "total energy = -XXX.XXXX Ry"
            pattern = r"total energy\s*=\s*([-\d.]+)\s*Ry"
            matches = re.findall(pattern, content)
            
            for i, energy in enumerate(matches):
                iterations.append(i + 1)
                energies.append(float(energy))
        
        except Exception as e:
            print(f"Parse error: {e}")
        
        return iterations, energies
    
    def _parse_and_plot(self):
        """Parse output and update plot."""
        if not HAS_MATPLOTLIB:
            return
        
        iterations, energies = self._parse_output()
        
        if not energies:
            self.info_label.setText("No SCF data found in file")
            return
        
        self.iterations = iterations
        self.energies = energies
        self._update_plot()
        
        final_energy = energies[-1]
        n_iter = len(energies)
        self.info_label.setText(f"Iterations: {n_iter} | Final Energy: {final_energy:.6f} Ry")
    
    def _update_plot(self):
        """Update the plot based on selected type."""
        if not HAS_MATPLOTLIB or not hasattr(self, 'energies'):
            return
        
        self.ax.clear()
        self._style_axes()
        
        plot_type = self.plot_type.currentIndex()
        
        if plot_type == 0:
            # Energy vs Iteration
            self.ax.plot(self.iterations, self.energies, 'o-', color='#7c3aed', linewidth=2, markersize=6)
            self.ax.set_xlabel('Iteration')
            self.ax.set_ylabel('Total Energy (Ry)')
            self.ax.set_title('SCF Convergence')
        
        elif plot_type == 1:
            # Energy change
            if len(self.energies) > 1:
                changes = [self.energies[i] - self.energies[i-1] for i in range(1, len(self.energies))]
                self.ax.semilogy(self.iterations[1:], [abs(c) for c in changes], 'o-', color='#10b981', linewidth=2)
                self.ax.set_xlabel('Iteration')
                self.ax.set_ylabel('|ΔE| (Ry)')
                self.ax.set_title('Energy Change per Iteration')
        
        elif plot_type == 2:
            # Estimated error (deviation from final)
            final = self.energies[-1]
            errors = [abs(e - final) for e in self.energies]
            self.ax.semilogy(self.iterations, errors, 'o-', color='#f59e0b', linewidth=2)
            self.ax.set_xlabel('Iteration')
            self.ax.set_ylabel('|E - E_final| (Ry)')
            self.ax.set_title('Convergence to Final Energy')
        
        self.ax.grid(True, alpha=0.3, color='#3f3f5a')
        self.figure.tight_layout()
        self.canvas.draw()
    
    def _toggle_auto_refresh(self):
        """Toggle automatic refresh for live monitoring."""
        self.auto_refresh = self.auto_refresh_btn.isChecked()
        
        if self.auto_refresh:
            self.refresh_timer.start(2000)  # Refresh every 2 seconds
        else:
            self.refresh_timer.stop()
    
    def _refresh_plot(self):
        """Refresh the plot (for auto-refresh)."""
        if self.output_file:
            self._parse_and_plot()
