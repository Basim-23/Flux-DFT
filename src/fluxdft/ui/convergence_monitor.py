"""
Real-Time Convergence Monitor for FluxDFT.

Live visualization of DFT convergence using pyqtgraph for
real-time data streaming from QE output files.

Features:
- Live SCF energy convergence plot
- Force/stress convergence for relaxation
- Electronic iteration tracking
- Log streaming with syntax highlighting
- ETA estimation

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Callable, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
import re
import time
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QLabel, QProgressBar, QTextEdit, QGroupBox,
    QPushButton, QComboBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, QFileSystemWatcher, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QTextCursor

import numpy as np

logger = logging.getLogger(__name__)

# Try to import pyqtgraph
try:
    import pyqtgraph as pg
    HAS_PYQTGRAPH = True
except ImportError:
    HAS_PYQTGRAPH = False
    logger.warning("pyqtgraph not available - using matplotlib fallback")


@dataclass
class ConvergenceData:
    """Container for parsed convergence data."""
    scf_iterations: List[int] = field(default_factory=list)
    scf_energies: List[float] = field(default_factory=list)
    scf_delta_e: List[float] = field(default_factory=list)
    
    ionic_iterations: List[int] = field(default_factory=list)
    ionic_energies: List[float] = field(default_factory=list)
    ionic_forces: List[float] = field(default_factory=list)
    ionic_pressures: List[float] = field(default_factory=list)
    
    fermi_energy: Optional[float] = None
    is_converged: bool = False
    total_time: float = 0.0
    
    def reset(self):
        """Clear all data."""
        self.scf_iterations.clear()
        self.scf_energies.clear()
        self.scf_delta_e.clear()
        self.ionic_iterations.clear()
        self.ionic_energies.clear()
        self.ionic_forces.clear()
        self.ionic_pressures.clear()
        self.fermi_energy = None
        self.is_converged = False
        self.total_time = 0.0


class QEOutputParser:
    """
    Parser for Quantum ESPRESSO output files.
    
    Extracts convergence data in real-time as the file is written.
    """
    
    # Regex patterns for QE output
    PATTERNS = {
        'scf_energy': re.compile(r'total energy\s+=\s+([-\d.]+)\s+Ry'),
        'scf_delta_e': re.compile(r'estimated scf accuracy\s+<\s+([\d.E+-]+)\s+Ry'),
        'scf_iteration': re.compile(r'iteration #\s*(\d+)'),
        'fermi': re.compile(r'the Fermi energy is\s+([-\d.]+)\s+ev'),
        'force_max': re.compile(r'Total force\s+=\s+([\d.]+)'),
        'pressure': re.compile(r'total\s+stress.*?P=\s*([-\d.]+)', re.DOTALL),
        'converged': re.compile(r'convergence has been achieved'),
        'ionic_step': re.compile(r'number of scf cycles\s+=\s+(\d+)'),
        'total_energy': re.compile(r'!\s+total energy\s+=\s+([-\d.]+)\s+Ry'),
        'cpu_time': re.compile(r'PWSCF\s+:\s+([^C]+)CPU'),
    }
    
    def __init__(self):
        self.data = ConvergenceData()
        self._last_position = 0
        self._scf_counter = 0
        self._ionic_counter = 0
    
    def reset(self):
        """Reset parser state."""
        self.data.reset()
        self._last_position = 0
        self._scf_counter = 0
        self._ionic_counter = 0
    
    def parse_incremental(self, filepath: Path) -> ConvergenceData:
        """
        Parse new content since last read.
        
        Args:
            filepath: Path to QE output file.
            
        Returns:
            Updated ConvergenceData.
        """
        if not filepath.exists():
            return self.data
        
        with open(filepath, 'r', errors='ignore') as f:
            f.seek(self._last_position)
            new_content = f.read()
            self._last_position = f.tell()
        
        if new_content:
            self._parse_content(new_content)
        
        return self.data
    
    def parse_full(self, filepath: Path) -> ConvergenceData:
        """Parse entire file."""
        self.reset()
        
        if not filepath.exists():
            return self.data
        
        with open(filepath, 'r', errors='ignore') as f:
            content = f.read()
            self._last_position = f.tell()
        
        self._parse_content(content)
        return self.data
    
    def _parse_content(self, content: str):
        """Parse content and update data."""
        lines = content.split('\n')
        
        for line in lines:
            # SCF iteration
            match = self.PATTERNS['scf_iteration'].search(line)
            if match:
                self._scf_counter = int(match.group(1))
            
            # SCF energy (per iteration)
            match = self.PATTERNS['scf_energy'].search(line)
            if match:
                energy = float(match.group(1)) * 13.6057  # Ry to eV
                self.data.scf_iterations.append(self._scf_counter)
                self.data.scf_energies.append(energy)
            
            # SCF accuracy (delta E)
            match = self.PATTERNS['scf_delta_e'].search(line)
            if match:
                delta = float(match.group(1)) * 13.6057
                self.data.scf_delta_e.append(delta)
            
            # Final total energy (ionic step)
            match = self.PATTERNS['total_energy'].search(line)
            if match:
                energy = float(match.group(1)) * 13.6057
                self._ionic_counter += 1
                self.data.ionic_iterations.append(self._ionic_counter)
                self.data.ionic_energies.append(energy)
            
            # Fermi energy
            match = self.PATTERNS['fermi'].search(line)
            if match:
                self.data.fermi_energy = float(match.group(1))
            
            # Max force
            match = self.PATTERNS['force_max'].search(line)
            if match:
                self.data.ionic_forces.append(float(match.group(1)))
            
            # Pressure
            match = self.PATTERNS['pressure'].search(line)
            if match:
                self.data.ionic_pressures.append(float(match.group(1)))
            
            # Convergence achieved
            if self.PATTERNS['converged'].search(line):
                self.data.is_converged = True


class ConvergencePlotWidget(QWidget):
    """
    Real-time convergence plotting widget using pyqtgraph.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        if HAS_PYQTGRAPH:
            self._init_pyqtgraph(layout)
        else:
            self._init_fallback(layout)
    
    def _init_pyqtgraph(self, layout):
        """Initialize pyqtgraph plots."""
        # Configure pyqtgraph
        pg.setConfigOptions(antialias=True)
        
        # Create graphics layout
        self.graphics_widget = pg.GraphicsLayoutWidget()
        layout.addWidget(self.graphics_widget)
        
        # Energy plot
        self.energy_plot = self.graphics_widget.addPlot(
            row=0, col=0,
            title="Total Energy"
        )
        self.energy_plot.setLabel('left', 'Energy', units='eV')
        self.energy_plot.setLabel('bottom', 'SCF Iteration')
        self.energy_plot.showGrid(x=True, y=True, alpha=0.3)
        self.energy_curve = self.energy_plot.plot(
            pen=pg.mkPen(color='#2196F3', width=2),
            symbol='o',
            symbolSize=6,
            symbolBrush='#2196F3'
        )
        
        # Delta E plot (log scale)
        self.delta_plot = self.graphics_widget.addPlot(
            row=1, col=0,
            title="SCF Accuracy (ΔE)"
        )
        self.delta_plot.setLabel('left', 'ΔE', units='eV')
        self.delta_plot.setLabel('bottom', 'SCF Iteration')
        self.delta_plot.setLogMode(y=True)
        self.delta_plot.showGrid(x=True, y=True, alpha=0.3)
        self.delta_curve = self.delta_plot.plot(
            pen=pg.mkPen(color='#4CAF50', width=2),
            symbol='o',
            symbolSize=6,
            symbolBrush='#4CAF50'
        )
        
        # Convergence threshold line
        self.conv_threshold = pg.InfiniteLine(
            pos=-8,  # log10(1e-8) = -8
            angle=0,
            pen=pg.mkPen(color='#f44336', style=Qt.DashLine, width=1),
            label='Threshold'
        )
        self.delta_plot.addItem(self.conv_threshold)
        
        # Force plot (for relaxation)
        self.force_plot = self.graphics_widget.addPlot(
            row=0, col=1,
            title="Maximum Force"
        )
        self.force_plot.setLabel('left', 'Force', units='Ry/Bohr')
        self.force_plot.setLabel('bottom', 'Ionic Step')
        self.force_plot.showGrid(x=True, y=True, alpha=0.3)
        self.force_curve = self.force_plot.plot(
            pen=pg.mkPen(color='#FF9800', width=2),
            symbol='s',
            symbolSize=6,
            symbolBrush='#FF9800'
        )
        
        # Ionic energy plot
        self.ionic_plot = self.graphics_widget.addPlot(
            row=1, col=1,
            title="Ionic Energy"
        )
        self.ionic_plot.setLabel('left', 'Energy', units='eV')
        self.ionic_plot.setLabel('bottom', 'Ionic Step')
        self.ionic_plot.showGrid(x=True, y=True, alpha=0.3)
        self.ionic_curve = self.ionic_plot.plot(
            pen=pg.mkPen(color='#9C27B0', width=2),
            symbol='d',
            symbolSize=6,
            symbolBrush='#9C27B0'
        )
    
    def _init_fallback(self, layout):
        """Fallback when pyqtgraph is not available."""
        label = QLabel("Install pyqtgraph for real-time plots:\npip install pyqtgraph")
        label.setAlignment(Qt.AlignCenter)
        layout.addWidget(label)
        
        # Create placeholder curves
        self.energy_curve = None
        self.delta_curve = None
        self.force_curve = None
        self.ionic_curve = None
    
    def update_data(self, data: ConvergenceData):
        """Update plots with new data."""
        if not HAS_PYQTGRAPH:
            return
        
        # SCF energy
        if data.scf_iterations and data.scf_energies:
            self.energy_curve.setData(
                data.scf_iterations, 
                data.scf_energies
            )
        
        # Delta E
        if data.scf_delta_e:
            x = list(range(1, len(data.scf_delta_e) + 1))
            self.delta_curve.setData(x, data.scf_delta_e)
        
        # Force
        if data.ionic_forces:
            x = list(range(1, len(data.ionic_forces) + 1))
            self.force_curve.setData(x, data.ionic_forces)
        
        # Ionic energy
        if data.ionic_iterations and data.ionic_energies:
            self.ionic_curve.setData(
                data.ionic_iterations,
                data.ionic_energies
            )
    
    def clear(self):
        """Clear all plots."""
        if HAS_PYQTGRAPH:
            self.energy_curve.setData([], [])
            self.delta_curve.setData([], [])
            self.force_curve.setData([], [])
            self.ionic_curve.setData([], [])


class LogViewerWidget(QTextEdit):
    """
    Colored log viewer for QE output.
    
    Highlights errors, warnings, and important information.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setFont(QFont("Consolas", 9))
        self.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: none;
            }
        """)
        
        # Syntax highlighting patterns
        self._patterns = [
            (re.compile(r'error', re.I), '#f44336'),       # Red
            (re.compile(r'warning', re.I), '#ff9800'),     # Orange
            (re.compile(r'convergence', re.I), '#4CAF50'), # Green
            (re.compile(r'total energy', re.I), '#2196F3'), # Blue
            (re.compile(r'iteration', re.I), '#9C27B0'),   # Purple
        ]
        
        self._last_position = 0
    
    def append_text(self, text: str):
        """Append text with syntax highlighting."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        for line in text.split('\n'):
            if not line:
                continue
            
            # Determine color
            color = '#d4d4d4'  # Default
            for pattern, col in self._patterns:
                if pattern.search(line):
                    color = col
                    break
            
            # Insert with color
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            cursor.setCharFormat(fmt)
            cursor.insertText(line + '\n')
        
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
    
    def load_from_file(self, filepath: Path, incremental: bool = True):
        """Load content from file."""
        if not filepath.exists():
            return
        
        with open(filepath, 'r', errors='ignore') as f:
            if incremental:
                f.seek(self._last_position)
            content = f.read()
            self._last_position = f.tell()
        
        if content:
            self.append_text(content)
    
    def clear_log(self):
        """Clear log content."""
        self.clear()
        self._last_position = 0


class ConvergenceMonitor(QWidget):
    """
    Main convergence monitoring widget.
    
    Combines plots, log viewer, and status information.
    
    Usage:
        >>> monitor = ConvergenceMonitor()
        >>> monitor.start_monitoring("/path/to/pw.out")
    """
    
    # Signals
    convergence_achieved = pyqtSignal()
    error_detected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        
        # Monitoring state
        self._output_file: Optional[Path] = None
        self._parser = QEOutputParser()
        self._is_monitoring = False
        
        # Timer for periodic updates
        self._update_timer = QTimer(self)
        self._update_timer.timeout.connect(self._update)
        self._update_interval = 1000  # ms
        
        # File watcher for immediate updates
        self._file_watcher = QFileSystemWatcher(self)
        self._file_watcher.fileChanged.connect(self._on_file_changed)
    
    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Header with status
        header = QHBoxLayout()
        
        self.status_label = QLabel("[Idle] Not monitoring")
        self.status_label.setStyleSheet("font-weight: bold; color: #6c7086;")
        header.addWidget(self.status_label)
        
        header.addStretch()
        
        self.start_btn = QPushButton("Start")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #34d399; }
        """)
        self.start_btn.clicked.connect(self._toggle_monitoring)
        header.addWidget(self.start_btn)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: #6c7086;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #7c7f93; }
        """)
        self.clear_btn.clicked.connect(self.clear)
        header.addWidget(self.clear_btn)
        
        layout.addLayout(header)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p% converging...")
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)
        
        # Main content splitter
        splitter = QSplitter(Qt.Vertical)
        
        # Plots
        self.plot_widget = ConvergencePlotWidget()
        splitter.addWidget(self.plot_widget)
        
        # Log viewer
        log_group = QGroupBox("Output Log")
        log_layout = QVBoxLayout(log_group)
        self.log_viewer = LogViewerWidget()
        log_layout.addWidget(self.log_viewer)
        splitter.addWidget(log_group)
        
        # Set splitter sizes
        splitter.setSizes([400, 200])
        layout.addWidget(splitter)
        
        # Info panel
        info_layout = QHBoxLayout()
        
        self.energy_label = QLabel("Energy: --")
        info_layout.addWidget(self.energy_label)
        
        self.fermi_label = QLabel("Ef: --")
        info_layout.addWidget(self.fermi_label)
        
        self.iterations_label = QLabel("Iterations: 0")
        info_layout.addWidget(self.iterations_label)
        
        self.time_label = QLabel("Time: --")
        info_layout.addWidget(self.time_label)
        
        layout.addLayout(info_layout)
    
    def start_monitoring(self, output_file: Path | str):
        """
        Start monitoring an output file.
        
        Args:
            output_file: Path to QE output file.
        """
        self._output_file = Path(output_file)
        self._parser.reset()
        self._is_monitoring = True
        
        # Add to file watcher
        if self._output_file.exists():
            self._file_watcher.addPath(str(self._output_file))
            # Parse existing content
            self._parser.parse_full(self._output_file)
            self.log_viewer.load_from_file(self._output_file, incremental=False)
            self._update_display()
        
        # Start timer
        self._update_timer.start(self._update_interval)
        
        self.status_label.setText(f"[Running] {self._output_file.name}")
        self.status_label.setStyleSheet("font-weight: bold; color: #89b4fa;")
        self.start_btn.setText("Stop")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #f38ba8;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #f5a6ba; }
        """)
        
        logger.info(f"Started monitoring {self._output_file}")
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self._is_monitoring = False
        self._update_timer.stop()
        
        if self._output_file:
            self._file_watcher.removePath(str(self._output_file))
        
        self.status_label.setText("[Stopped]")
        self.status_label.setStyleSheet("font-weight: bold; color: #6c7086;")
        self.start_btn.setText("Start")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover { background: #34d399; }
        """)
        
        logger.info("Stopped monitoring")
    
    def _toggle_monitoring(self):
        """Toggle monitoring state."""
        if self._is_monitoring:
            self.stop_monitoring()
        elif self._output_file:
            self.start_monitoring(self._output_file)
    
    @pyqtSlot()
    def _on_file_changed(self, path: str):
        """Handle file change event."""
        if path == str(self._output_file):
            self._update()
    
    @pyqtSlot()
    def _update(self):
        """Update display with new data."""
        if not self._is_monitoring or not self._output_file:
            return
        
        # Parse new content
        data = self._parser.parse_incremental(self._output_file)
        
        # Update log viewer
        self.log_viewer.load_from_file(self._output_file, incremental=True)
        
        # Update display
        self._update_display()
        
        # Check for convergence
        if data.is_converged:
            self.convergence_achieved.emit()
            self.status_label.setText("[Converged]")
            self.status_label.setStyleSheet("font-weight: bold; color: #a6e3a1;")
            self.progress_bar.setValue(100)
            self.stop_monitoring()
    
    def _update_display(self):
        """Update all display elements."""
        data = self._parser.data
        
        # Update plots
        self.plot_widget.update_data(data)
        
        # Update info labels
        if data.scf_energies:
            self.energy_label.setText(f"Energy: {data.scf_energies[-1]:.6f} eV")
        
        if data.fermi_energy:
            self.fermi_label.setText(f"Ef: {data.fermi_energy:.4f} eV")
        
        self.iterations_label.setText(f"Iterations: {len(data.scf_iterations)}")
        
        # Estimate progress (rough heuristic)
        if data.scf_delta_e:
            # Log scale progress
            current = np.log10(max(data.scf_delta_e[-1], 1e-12))
            target = -8  # log10(1e-8)
            start = -2   # log10(1e-2)
            progress = max(0, min(100, 100 * (start - current) / (start - target)))
            self.progress_bar.setValue(int(progress))
    
    def clear(self):
        """Clear all data and plots."""
        self._parser.reset()
        self.plot_widget.clear()
        self.log_viewer.clear_log()
        self.progress_bar.setValue(0)
        self.energy_label.setText("Energy: --")
        self.fermi_label.setText("Ef: --")
        self.iterations_label.setText("Iterations: 0")
    
    def set_output_file(self, filepath: Path | str):
        """Set output file without starting monitoring."""
        self._output_file = Path(filepath)
