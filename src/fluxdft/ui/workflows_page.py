"""
Premium Workflows Page for FluxDFT.

Production-grade workflow management with:
- Split layout: Templates | Active Jobs
- Real-time job monitoring
- QE Binary configuration

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QGridLayout, QScrollArea, QSplitter,
    QProgressBar, QMessageBox, QFileDialog, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QColor
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# WORKFLOW CARD COMPONENT
# ============================================================================

class WorkflowCard(QFrame):
    """Premium workflow template card with gradient accent and step visualization."""
    
    run_requested = pyqtSignal(dict)  # Emits workflow config
    
    def __init__(self, workflow_data: dict, parent=None):
        super().__init__(parent)
        self.data = workflow_data
        title = workflow_data['title']
        description = workflow_data['desc']
        color = workflow_data['color']
        steps = workflow_data['steps']
        duration = workflow_data.get('duration', '')
        
        self.setFixedHeight(160)
        self.setMinimumWidth(280)
        
        self.setStyleSheet(f"""
            WorkflowCard {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1e2e, stop:1 #252536);
                border: 1px solid #313244;
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
            WorkflowCard:hover {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #252536, stop:1 #2a2a3c);
                border-color: {color};
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        
        # Header: Title + Duration badge
        header = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            color: {color}; 
            font-size: 14px; 
            font-weight: 600; 
            border: none;
            background: transparent;
        """)
        header.addWidget(title_label)
        header.addStretch()
        
        if duration:
            dur_badge = QLabel(duration)
            dur_badge.setStyleSheet("""
                color: #6c7086; 
                font-size: 10px; 
                background: #313244;
                padding: 2px 8px;
                border-radius: 8px;
            """)
            header.addWidget(dur_badge)
        layout.addLayout(header)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #a6adc8; font-size: 11px; border: none; background: transparent;")
        layout.addWidget(desc_label)
        
        # Step pills
        steps_layout = QHBoxLayout()
        steps_layout.setSpacing(4)
        for i, step in enumerate(steps[:4]):
            pill = QLabel(step)
            pill.setStyleSheet(f"""
                background: rgba({self._hex_to_rgb(color)}, 0.15);
                color: {color};
                font-size: 9px;
                padding: 3px 8px;
                border-radius: 10px;
                border: none;
            """)
            steps_layout.addWidget(pill)
            if i < len(steps) - 1 and i < 3:
                arrow = QLabel("→")
                arrow.setStyleSheet("color: #45475a; font-size: 10px; border: none; background: transparent;")
                steps_layout.addWidget(arrow)
        if len(steps) > 4:
            more = QLabel(f"+{len(steps)-4}")
            more.setStyleSheet("color: #6c7086; font-size: 9px; border: none; background: transparent;")
            steps_layout.addWidget(more)
        steps_layout.addStretch()
        layout.addLayout(steps_layout)
        
        layout.addStretch()
        
        # Run button
        run_btn = QPushButton("▶ Run Workflow")
        run_btn.setFixedHeight(32)
        run_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        run_btn.setStyleSheet(f"""
            QPushButton {{
                background: {color};
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                font-size: 11px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: {self._lighten(color)};
            }}
            QPushButton:pressed {{
                background: {self._darken(color)};
            }}
        """)
        run_btn.clicked.connect(lambda: self.run_requested.emit(self.data))
        layout.addWidget(run_btn)
    
    def _hex_to_rgb(self, hex_color: str) -> str:
        c = QColor(hex_color)
        return f"{c.red()}, {c.green()}, {c.blue()}"
    
    def _lighten(self, color: str) -> str:
        c = QColor(color)
        return QColor.fromHslF(c.hueF(), c.saturationF(), min(1, c.lightnessF() * 1.15)).name()
    
    def _darken(self, color: str) -> str:
        c = QColor(color)
        return QColor.fromHslF(c.hueF(), c.saturationF(), max(0, c.lightnessF() * 0.85)).name()


# ============================================================================
# ACTIVE JOB ITEM
# ============================================================================

class JobItemWidget(QFrame):
    """Widget for displaying an active/completed job."""
    
    def __init__(self, job_info: dict, parent=None):
        super().__init__(parent)
        self.job_info = job_info
        
        status = job_info.get('status', 'queued')
        name = job_info.get('name', 'Unknown Job')
        progress = job_info.get('progress', 0)
        
        status_colors = {
            'running': '#a6e3a1',
            'queued': '#f9e2af',
            'completed': '#89b4fa',
            'failed': '#f38ba8'
        }
        color = status_colors.get(status, '#6c7086')
        
        self.setStyleSheet(f"""
            JobItemWidget {{
                background: #1e1e2e;
                border: 1px solid #313244;
                border-left: 3px solid {color};
                border-radius: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)
        
        # Header: Name + Status badge
        header = QHBoxLayout()
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 500; border: none;")
        header.addWidget(name_label)
        header.addStretch()
        
        status_badge = QLabel(status.upper())
        status_badge.setStyleSheet(f"""
            color: {color};
            background: rgba({self._hex_to_rgb(color)}, 0.15);
            font-size: 9px;
            font-weight: bold;
            padding: 2px 8px;
            border-radius: 4px;
        """)
        header.addWidget(status_badge)
        layout.addLayout(header)
        
        # Progress bar (for running jobs)
        if status == 'running':
            progress_bar = QProgressBar()
            progress_bar.setValue(progress)
            progress_bar.setFixedHeight(6)
            progress_bar.setTextVisible(False)
            progress_bar.setStyleSheet(f"""
                QProgressBar {{
                    background: #313244;
                    border: none;
                    border-radius: 3px;
                }}
                QProgressBar::chunk {{
                    background: {color};
                    border-radius: 3px;
                }}
            """)
            layout.addWidget(progress_bar)
    
    def _hex_to_rgb(self, hex_color: str) -> str:
        c = QColor(hex_color)
        return f"{c.red()}, {c.green()}, {c.blue()}"


# ============================================================================
# QE CONFIGURATION PANEL
# ============================================================================

class QEConfigPanel(QFrame):
    """Panel for configuring Quantum ESPRESSO binary paths."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.qe_path = None
        
        self.setStyleSheet("""
            QEConfigPanel {
                background: #181825;
                border: 1px solid #313244;
                border-radius: 8px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("⚙ QE Configuration")
        title.setStyleSheet("color: #cdd6f4; font-size: 12px; font-weight: 600; border: none;")
        header.addWidget(title)
        
        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet("color: #f38ba8; font-size: 14px; border: none;")
        header.addWidget(self.status_dot)
        header.addStretch()
        layout.addLayout(header)
        
        # Path input
        path_layout = QHBoxLayout()
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("Path to QE bin/ directory...")
        self.path_input.setStyleSheet("""
            QLineEdit {
                background: #1e1e2e;
                border: 1px solid #45475a;
                border-radius: 4px;
                padding: 6px 10px;
                color: #cdd6f4;
                font-size: 11px;
            }
        """)
        path_layout.addWidget(self.path_input, 1)
        
        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet("""
            QPushButton {
                background: #45475a;
                color: #cdd6f4;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10px;
            }
            QPushButton:hover { background: #585b70; }
        """)
        browse_btn.clicked.connect(self._browse)
        path_layout.addWidget(browse_btn)
        
        verify_btn = QPushButton("Verify")
        verify_btn.setStyleSheet("""
            QPushButton {
                background: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover { background: #b4befe; }
        """)
        verify_btn.clicked.connect(self._verify)
        path_layout.addWidget(verify_btn)
        
        layout.addLayout(path_layout)
        
        # Status message
        self.status_label = QLabel("QE not configured")
        self.status_label.setStyleSheet("color: #6c7086; font-size: 10px; border: none;")
        layout.addWidget(self.status_label)
    
    def _browse(self):
        directory = QFileDialog.getExistingDirectory(self, "Select QE bin directory")
        if directory:
            self.path_input.setText(directory)
    
    def _verify(self):
        path = Path(self.path_input.text())
        pw_exe = path / "pw.x"
        
        # On Windows, check for .exe as well
        if not pw_exe.exists():
            pw_exe = path / "pw.x.exe"
        
        if pw_exe.exists():
            self.qe_path = path
            self.status_dot.setStyleSheet("color: #a6e3a1; font-size: 14px; border: none;")
            self.status_label.setText(f"✓ Found pw.x at {pw_exe}")
            self.status_label.setStyleSheet("color: #a6e3a1; font-size: 10px; border: none;")
        else:
            self.status_dot.setStyleSheet("color: #f38ba8; font-size: 14px; border: none;")
            self.status_label.setText(f"✗ pw.x not found in {path}")
            self.status_label.setStyleSheet("color: #f38ba8; font-size: 10px; border: none;")


# ============================================================================
# MAIN WORKFLOWS PAGE
# ============================================================================

class WorkflowsPage(QWidget):
    """Premium workflows page with split layout."""
    
    def __init__(self, job_runner=None, parent=None):
        super().__init__(parent)
        self.job_runner = job_runner  # Shared runner from MainWindow
        self.active_jobs = []  # List of job info dicts
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Main header bar
        header_bar = QFrame()
        header_bar.setFixedHeight(64)
        header_bar.setStyleSheet("""
            QFrame {
                background: #181825;
                border-bottom: 1px solid #313244;
            }
        """)
        header_layout = QHBoxLayout(header_bar)
        header_layout.setContentsMargins(24, 0, 24, 0)
        
        title = QLabel("Workflows")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4; border: none;")
        header_layout.addWidget(title)
        
        subtitle = QLabel("Multi-step DFT calculation pipelines")
        subtitle.setStyleSheet("color: #6c7086; font-size: 11px; margin-left: 12px; border: none;")
        header_layout.addWidget(subtitle)
        
        header_layout.addStretch()
        
        # New workflow button
        new_btn = QPushButton("+ Custom Workflow")
        new_btn.setStyleSheet("""
            QPushButton {
                background: #3b82f6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background: #60a5fa; }
        """)
        header_layout.addWidget(new_btn)
        
        layout.addWidget(header_bar)
        
        # Main content with splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("""
            QSplitter::handle {
                background: #313244;
                width: 1px;
            }
        """)
        
        # ============ LEFT PANEL: Workflow Templates ============
        left_panel = QWidget()
        left_panel.setStyleSheet("background: #11111b;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(16, 16, 8, 16)
        left_layout.setSpacing(12)
        
        # Section header
        templates_header = QLabel("WORKFLOW TEMPLATES")
        templates_header.setStyleSheet("color: #6c7086; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        left_layout.addWidget(templates_header)
        
        # Scrollable grid of workflow cards
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #181825;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                min-height: 20px;
                border-radius: 4px;
            }
        """)
        
        grid_container = QWidget()
        grid_container.setStyleSheet("background: transparent;")
        grid = QGridLayout(grid_container)
        grid.setSpacing(12)
        grid.setContentsMargins(0, 0, 8, 0)
        
        # Workflow definitions
        workflows = [
            {"title": "Band Structure", "desc": "Electronic bands with DOS analysis", "color": "#3b82f6", 
             "steps": ["SCF", "NSCF", "bands.x", "Plot"], "duration": "~30m", "type": "band_structure"},
            {"title": "Projected DOS", "desc": "Atom & orbital resolved density of states", "color": "#8b5cf6", 
             "steps": ["SCF", "NSCF", "projwfc.x"], "duration": "~25m", "type": "pdos"},
            {"title": "Geometry Optimization", "desc": "Relax positions and cell parameters", "color": "#10b981", 
             "steps": ["vc-relax", "SCF"], "duration": "~1h", "type": "vc_relax"},
            {"title": "Fermi Surface", "desc": "3D Fermi surface for metallic systems", "color": "#06b6d4", 
             "steps": ["SCF", "NSCF", "fs.x"], "duration": "~45m", "type": "fermi_surface"},
            {"title": "Equation of State", "desc": "Energy vs Volume for bulk modulus", "color": "#f59e0b", 
             "steps": ["SCF×N", "EOS Fit"], "duration": "~2h", "type": "eos"},
            {"title": "Phonon Dispersion", "desc": "Phonon bands and thermodynamics", "color": "#ec4899", 
             "steps": ["SCF", "ph.x", "q2r.x", "matdyn.x"], "duration": "~6h", "type": "phonon"},
            {"title": "K-point Convergence", "desc": "Test k-mesh density for accuracy", "color": "#a855f7", 
             "steps": ["SCF×N", "Analyze"], "duration": "~30m", "type": "kpoint_conv"},
            {"title": "Cutoff Convergence", "desc": "Optimize wavefunction cutoff", "color": "#d946ef", 
             "steps": ["SCF×N", "Analyze"], "duration": "~45m", "type": "cutoff_conv"},
        ]
        
        for i, wf in enumerate(workflows):
            card = WorkflowCard(wf)
            card.run_requested.connect(self._on_run_workflow)
            grid.addWidget(card, i // 2, i % 2)
        
        grid.setRowStretch(len(workflows) // 2 + 1, 1)
        scroll.setWidget(grid_container)
        left_layout.addWidget(scroll)
        
        splitter.addWidget(left_panel)
        
        # ============ RIGHT PANEL: Active Jobs + Config ============
        right_panel = QWidget()
        right_panel.setStyleSheet("background: #11111b;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 16, 16, 16)
        right_layout.setSpacing(12)
        
        # QE Configuration
        self.qe_config = QEConfigPanel()
        right_layout.addWidget(self.qe_config)
        
        # Active jobs header
        jobs_header = QHBoxLayout()
        jobs_title = QLabel("ACTIVE JOBS")
        jobs_title.setStyleSheet("color: #6c7086; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        jobs_header.addWidget(jobs_title)
        jobs_header.addStretch()
        
        self.job_count = QLabel("0 jobs")
        self.job_count.setStyleSheet("color: #45475a; font-size: 10px;")
        jobs_header.addWidget(self.job_count)
        right_layout.addLayout(jobs_header)
        
        # Jobs list (scroll area)
        self.jobs_scroll = QScrollArea()
        self.jobs_scroll.setWidgetResizable(True)
        self.jobs_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                background: #181825;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                min-height: 20px;
                border-radius: 4px;
            }
        """)
        
        self.jobs_container = QWidget()
        self.jobs_container.setStyleSheet("background: transparent;")
        self.jobs_layout = QVBoxLayout(self.jobs_container)
        self.jobs_layout.setContentsMargins(0, 0, 0, 0)
        self.jobs_layout.setSpacing(8)
        self.jobs_layout.addStretch()
        
        self.jobs_scroll.setWidget(self.jobs_container)
        right_layout.addWidget(self.jobs_scroll)
        
        # Empty state
        self.empty_label = QLabel("No active jobs\n\nSelect a workflow template to get started")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #45475a; font-size: 11px;")
        self.jobs_layout.insertWidget(0, self.empty_label)
        
        splitter.addWidget(right_panel)
        
        # Set splitter sizes
        splitter.setSizes([600, 350])
        layout.addWidget(splitter)
    
    def _on_run_workflow(self, workflow_data: dict):
        """Handle workflow run request."""
        workflow_type = workflow_data.get('type', 'unknown')
        workflow_title = workflow_data.get('title', 'Unknown')
        
        # Check if QE is configured
        if not self.qe_config.qe_path:
            QMessageBox.warning(
                self,
                "QE Not Configured",
                "Please configure the Quantum ESPRESSO path first.\n\n"
                "Set the path to your QE bin/ directory in the configuration panel."
            )
            return
        
        # Update shared runner's QE path
        if self.job_runner:
            self.job_runner.qe_path = self.qe_config.qe_path
        
        try:
            # Import dialog
            from .dialogs.workflow_dialog import WorkflowSubmissionDialog
            dialog = WorkflowSubmissionDialog(workflow_type, self)
            if dialog.exec():
                # Create job in shared runner if available
                if self.job_runner and dialog.structure:
                    job_name = f"{workflow_title} - {dialog.structure.formula}"
                    # For now, add to local display (full integration requires input file generation)
                    self._add_job({
                        'name': job_name,
                        'status': 'queued',
                        'progress': 0
                    })
                    logger.info(f"Job queued: {job_name}")
                else:
                    self._add_job({
                        'name': f"{workflow_title} - {dialog.structure.formula if dialog.structure else 'Unknown'}",
                        'status': 'queued',
                        'progress': 0
                    })
        except Exception as e:
            logger.error(f"Failed to open workflow dialog: {e}")
            QMessageBox.critical(self, "Error", f"Failed to open workflow dialog:\n{e}")
    
    def _add_job(self, job_info: dict):
        """Add a job to the active jobs panel."""
        # Remove empty state
        if self.empty_label.isVisible():
            self.empty_label.hide()
        
        # Create job widget
        job_widget = JobItemWidget(job_info)
        self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, job_widget)
        
        self.active_jobs.append(job_info)
        self.job_count.setText(f"{len(self.active_jobs)} job{'s' if len(self.active_jobs) != 1 else ''}")
