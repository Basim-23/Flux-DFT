"""
Premium Job Manager for FluxDFT.

Production-grade job monitoring with:
- Card-based job display with status indicators
- Real-time output streaming with QE highlighting
- Action buttons for results viewing
- Integration with plotting subsystem

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, Dict
from pathlib import Path
from datetime import datetime
import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QPushButton, QLabel, QTextEdit, QFileDialog, QMessageBox,
    QProgressBar, QFrame, QScrollArea, QMenu
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QColor, QTextCharFormat, QSyntaxHighlighter, QTextDocument

from ..core.job_runner import JobRunner, Job, JobStatus

# Try to import qtawesome for premium icons
try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False

import logging
logger = logging.getLogger(__name__)


# ============================================================================
# QE OUTPUT SYNTAX HIGHLIGHTER
# ============================================================================

class QEOutputHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for Quantum ESPRESSO output."""
    
    def __init__(self, document: QTextDocument):
        super().__init__(document)
        self._setup_formats()
    
    def _setup_formats(self):
        self.formats = {}
        
        # Convergence (green)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#a6e3a1"))
        fmt.setFontWeight(QFont.Weight.Bold)
        self.formats['convergence'] = fmt
        
        # Energy (cyan)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#89dceb"))
        self.formats['energy'] = fmt
        
        # Warning (yellow)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#f9e2af"))
        self.formats['warning'] = fmt
        
        # Error (red)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#f38ba8"))
        fmt.setFontWeight(QFont.Weight.Bold)
        self.formats['error'] = fmt
        
        # Iteration (blue)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#89b4fa"))
        self.formats['iteration'] = fmt
    
    def highlightBlock(self, text: str):
        t = text.lower()
        if 'convergence' in t and 'achieved' in t:
            self.setFormat(0, len(text), self.formats['convergence'])
        elif 'error' in t or 'stopping' in t:
            self.setFormat(0, len(text), self.formats['error'])
        elif 'warning' in t:
            self.setFormat(0, len(text), self.formats['warning'])
        elif text.strip().startswith('iteration') or 'scf correction' in t:
            self.setFormat(0, len(text), self.formats['iteration'])
        elif 'total energy' in t or '!' in text:
            self.setFormat(0, len(text), self.formats['energy'])


# ============================================================================
# JOB WORKER THREAD
# ============================================================================

class JobWorker(QThread):
    """Worker thread for running QE jobs."""
    
    output_received = pyqtSignal(str)
    job_finished = pyqtSignal(object)
    progress_update = pyqtSignal(int)
    
    def __init__(self, runner: JobRunner, job: Job):
        super().__init__()
        self.runner = runner
        self.job = job
        self.iteration_count = 0
    
    def run(self):
        self.runner.run_job(
            self.job,
            on_output=self._on_output,
            on_complete=self._on_complete,
            blocking=True,
        )
    
    def _on_output(self, line: str):
        self.output_received.emit(line)
        if 'iteration' in line.lower() and '#' in line:
            self.iteration_count += 1
            self.progress_update.emit(min(95, self.iteration_count * 2))
    
    def _on_complete(self, job: Job):
        self.progress_update.emit(100 if job.status == JobStatus.COMPLETED else 0)
        self.job_finished.emit(job)


# ============================================================================
# JOB CARD WIDGET
# ============================================================================

class JobCard(QFrame):
    """Premium job card with status and progress."""
    
    selected = pyqtSignal(object)
    action_requested = pyqtSignal(str, object)
    
    def __init__(self, job: Job, parent=None):
        super().__init__(parent)
        self.job = job
        self._is_selected = False
        self._setup_ui()
        self._update_status()
    
    def _setup_ui(self):
        self.setFixedHeight(80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(14)
        
        # Status indicator dot
        self.status_dot = QLabel()
        self.status_dot.setFixedSize(10, 10)
        layout.addWidget(self.status_dot)
        
        # Job info column
        info_col = QVBoxLayout()
        info_col.setSpacing(4)
        
        self.name_label = QLabel(self.job.name)
        self.name_label.setStyleSheet("color: #cdd6f4; font-size: 13px; font-weight: 600;")
        info_col.addWidget(self.name_label)
        
        details = QHBoxLayout()
        details.setSpacing(16)
        
        exe_lbl = QLabel(self.job.executable)
        exe_lbl.setStyleSheet("color: #89b4fa; font-size: 10px;")
        details.addWidget(exe_lbl)
        
        self.duration_label = QLabel("--")
        self.duration_label.setStyleSheet("color: #6c7086; font-size: 10px;")
        details.addWidget(self.duration_label)
        
        details.addStretch()
        info_col.addLayout(details)
        
        layout.addLayout(info_col, 1)
        
        # Progress bar (vertical)
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedSize(4, 50)
        self.progress_bar.setOrientation(Qt.Orientation.Vertical)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar { background: #313244; border: none; border-radius: 2px; }
            QProgressBar::chunk { background: #89b4fa; border-radius: 2px; }
        """)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        
        # Status badge
        self.status_badge = QLabel()
        self.status_badge.setFixedWidth(72)
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_badge)
    
    def _apply_style(self):
        border = "#89b4fa" if self._is_selected else "#2a2a3c"
        bg = "rgba(137, 180, 250, 0.08)" if self._is_selected else "rgba(30, 30, 46, 0.6)"
        self.setStyleSheet(f"""
            JobCard {{
                background: {bg};
                border: 1px solid {border};
                border-radius: 8px;
            }}
            JobCard:hover {{ border-color: #45475a; }}
        """)
    
    def set_selected(self, sel: bool):
        self._is_selected = sel
        self._apply_style()
    
    def _update_status(self):
        s = self.job.status
        cfg = {
            JobStatus.PENDING: ("#f9e2af", "QUEUED"),
            JobStatus.RUNNING: ("#89b4fa", "RUNNING"),
            JobStatus.COMPLETED: ("#a6e3a1", "DONE"),
            JobStatus.FAILED: ("#f38ba8", "FAILED"),
            JobStatus.CANCELLED: ("#6c7086", "STOPPED"),
        }
        color, text = cfg.get(s, ("#6c7086", "UNKNOWN"))
        
        self.status_dot.setStyleSheet(f"background: {color}; border-radius: 5px;")
        self.status_badge.setText(text)
        self.status_badge.setStyleSheet(f"""
            background: rgba({self._hex_rgb(color)}, 0.15);
            color: {color};
            font-size: 9px;
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
        """)
        
        self.progress_bar.setVisible(s == JobStatus.RUNNING)
        
        if self.job.started_at:
            end = self.job.completed_at or datetime.now()
            dur = (end - self.job.started_at).total_seconds()
            self.duration_label.setText(f"{dur:.1f}s")
    
    def _hex_rgb(self, hex_color: str) -> str:
        c = QColor(hex_color)
        return f"{c.red()}, {c.green()}, {c.blue()}"
    
    def set_progress(self, val: int):
        self.progress_bar.setValue(val)
    
    def refresh(self):
        self._update_status()
    
    def mousePressEvent(self, e):
        self.selected.emit(self.job)
        super().mousePressEvent(e)
    
    def contextMenuEvent(self, e):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu { background: #1e1e2e; border: 1px solid #313244; padding: 4px; }
            QMenu::item { padding: 8px 16px; color: #cdd6f4; }
            QMenu::item:selected { background: rgba(137, 180, 250, 0.15); }
        """)
        if self.job.status == JobStatus.COMPLETED:
            menu.addAction("View Results", lambda: self.action_requested.emit("results", self.job))
            menu.addAction("Generate Plots", lambda: self.action_requested.emit("plot", self.job))
        menu.addAction("Open Folder", lambda: self.action_requested.emit("folder", self.job))
        if self.job.status == JobStatus.RUNNING:
            menu.addSeparator()
            menu.addAction("Stop", lambda: self.action_requested.emit("stop", self.job))
        menu.exec(e.globalPos())


# ============================================================================
# PREMIUM JOB MANAGER PANEL
# ============================================================================

class JobManagerPanel(QWidget):
    """Premium job manager with split layout."""
    
    view_results_requested = pyqtSignal(object)
    generate_plots_requested = pyqtSignal(object)
    
    def __init__(self, job_runner=None, parent=None):
        super().__init__(parent)
        
        self.runner = job_runner if job_runner else JobRunner()
        self.workers: Dict[str, JobWorker] = {}
        self.job_cards: Dict[str, JobCard] = {}
        self.selected_job: Optional[Job] = None
        
        # Lazy-loaded post processor
        self.post_processor = None
        self._pp_init = False
        
        self._setup_ui()
        
        # Refresh timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._refresh)
        self.timer.start(2000)
    
    def _get_pp(self):
        if not self._pp_init:
            self._pp_init = True
            try:
                from ..core.output_parser import OutputParser
                from ..postprocessing.manager import PostProcessingManager
                self.post_processor = PostProcessingManager(OutputParser())
                self.post_processor.on_plots_ready = self._on_plots
                self.post_processor.on_error = lambda m: self._log(f"Plot error: {m}")
            except:
                pass
        return self.post_processor
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header
        header = QFrame()
        header.setFixedHeight(60)
        header.setStyleSheet("background: #181825; border-bottom: 1px solid #313244;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(24, 0, 24, 0)
        
        title = QLabel("Job Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        h_layout.addWidget(title)
        
        self.count_label = QLabel("0 jobs")
        self.count_label.setStyleSheet("color: #6c7086; font-size: 11px; margin-left: 12px;")
        h_layout.addWidget(self.count_label)
        
        h_layout.addStretch()
        
        # New job button
        new_btn = QPushButton("  New Job")
        if HAS_ICONS:
            new_btn.setIcon(qta.icon("mdi.plus", color="#1e1e2e"))
        new_btn.setStyleSheet("""
            QPushButton {
                background: #89b4fa;
                color: #1e1e2e;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton:hover { background: #b4befe; }
        """)
        new_btn.clicked.connect(self._new_job)
        h_layout.addWidget(new_btn)
        
        layout.addWidget(header)
        
        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #1a1a24; width: 1px; }")
        
        # === LEFT: Job List ===
        left = QFrame()
        left.setStyleSheet("background: #11111b;")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(16, 12, 8, 16)
        left_layout.setSpacing(10)
        
        # Controls
        ctrl = QHBoxLayout()
        
        run_btn = QPushButton("  Run")
        if HAS_ICONS:
            run_btn.setIcon(qta.icon("mdi.play", color="#1e1e2e"))
        run_btn.setStyleSheet("""
            QPushButton {
                background: #a6e3a1; color: #1e1e2e;
                border: none; border-radius: 4px;
                padding: 6px 16px; font-weight: bold; font-size: 10px;
            }
            QPushButton:hover { background: #94e2a5; }
        """)
        run_btn.clicked.connect(self._run_selected)
        ctrl.addWidget(run_btn)
        
        stop_btn = QPushButton("  Stop")
        if HAS_ICONS:
            stop_btn.setIcon(qta.icon("mdi.stop", color="#1e1e2e"))
        stop_btn.setStyleSheet("""
            QPushButton {
                background: #f38ba8; color: #1e1e2e;
                border: none; border-radius: 4px;
                padding: 6px 16px; font-weight: bold; font-size: 10px;
            }
            QPushButton:hover { background: #f5a0b8; }
        """)
        stop_btn.clicked.connect(self._stop_selected)
        ctrl.addWidget(stop_btn)
        
        ctrl.addStretch()
        left_layout.addLayout(ctrl)
        
        # Job list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { background: #181825; width: 6px; }
            QScrollBar::handle:vertical { background: #45475a; min-height: 20px; border-radius: 3px; }
        """)
        
        self.jobs_container = QWidget()
        self.jobs_container.setStyleSheet("background: transparent;")
        self.jobs_layout = QVBoxLayout(self.jobs_container)
        self.jobs_layout.setContentsMargins(0, 0, 4, 0)
        self.jobs_layout.setSpacing(6)
        self.jobs_layout.addStretch()
        
        scroll.setWidget(self.jobs_container)
        left_layout.addWidget(scroll)
        
        self.empty_label = QLabel("No jobs yet\n\nCreate a new job to get started")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setStyleSheet("color: #45475a; font-size: 11px;")
        self.jobs_layout.insertWidget(0, self.empty_label)
        
        splitter.addWidget(left)
        
        # === RIGHT: Output ===
        right = QFrame()
        right.setStyleSheet("background: #0d0d12;")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 12, 16, 16)
        right_layout.setSpacing(10)
        
        # Output header
        out_head = QHBoxLayout()
        out_title = QLabel("OUTPUT")
        out_title.setStyleSheet("color: #6c7086; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        out_head.addWidget(out_title)
        out_head.addStretch()
        
        clear_btn = QPushButton("Clear")
        clear_btn.setStyleSheet("QPushButton { background: transparent; color: #6c7086; border: none; font-size: 10px; } QPushButton:hover { color: #cdd6f4; }")
        clear_btn.clicked.connect(lambda: self.output.clear())
        out_head.addWidget(clear_btn)
        right_layout.addLayout(out_head)
        
        # Output text
        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        self.output.setStyleSheet("""
            QTextEdit {
                background: #0a0a0f;
                color: #a6adc8;
                border: 1px solid #1a1a24;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        self.highlighter = QEOutputHighlighter(self.output.document())
        right_layout.addWidget(self.output)
        
        # Action buttons
        actions = QHBoxLayout()
        actions.setSpacing(8)
        
        self.results_btn = QPushButton("  Results")
        if HAS_ICONS:
            self.results_btn.setIcon(qta.icon("mdi.chart-bar", color="#cdd6f4"))
        self.results_btn.setEnabled(False)
        self.results_btn.setStyleSheet(self._action_btn_style())
        self.results_btn.clicked.connect(self._view_results)
        actions.addWidget(self.results_btn)
        
        self.plot_btn = QPushButton("  Plots")
        if HAS_ICONS:
            self.plot_btn.setIcon(qta.icon("mdi.chart-line", color="#cdd6f4"))
        self.plot_btn.setEnabled(False)
        self.plot_btn.setStyleSheet(self._action_btn_style())
        self.plot_btn.clicked.connect(self._gen_plots)
        actions.addWidget(self.plot_btn)
        
        self.folder_btn = QPushButton("  Folder")
        if HAS_ICONS:
            self.folder_btn.setIcon(qta.icon("mdi.folder-open", color="#cdd6f4"))
        self.folder_btn.setEnabled(False)
        self.folder_btn.setStyleSheet(self._action_btn_style())
        self.folder_btn.clicked.connect(self._open_folder)
        actions.addWidget(self.folder_btn)
        
        actions.addStretch()
        right_layout.addLayout(actions)
        
        splitter.addWidget(right)
        splitter.setSizes([320, 500])
        layout.addWidget(splitter)
    
    def _action_btn_style(self):
        return """
            QPushButton {
                background: #232334;
                color: #cdd6f4;
                border: 1px solid #313244;
                border-radius: 4px;
                padding: 8px 14px;
                font-size: 10px;
            }
            QPushButton:hover:enabled { background: #2a2a3c; border-color: #45475a; }
            QPushButton:disabled { color: #45475a; border-color: #1a1a24; }
        """
    
    def _new_job(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select QE Input", "", "QE Input (*.in *.inp *.pwi);;All (*)")
        if not path:
            return
        p = Path(path)
        job = self.runner.create_job(name=p.stem, executable="pw.x", input_file=p, work_dir=p.parent)
        self._add_card(job)
        self._update_count()
    
    def _add_card(self, job: Job):
        if self.empty_label.isVisible():
            self.empty_label.hide()
        card = JobCard(job)
        card.selected.connect(self._select_job)
        card.action_requested.connect(self._handle_action)
        self.job_cards[job.id] = card
        self.jobs_layout.insertWidget(self.jobs_layout.count() - 1, card)
    
    def _select_job(self, job: Job):
        self.selected_job = job
        for c in self.job_cards.values():
            c.set_selected(c.job.id == job.id)
        
        if job.output_file.exists():
            try:
                self.output.setPlainText(job.output_file.read_text())
            except:
                pass
        
        done = job.status == JobStatus.COMPLETED
        self.results_btn.setEnabled(done)
        self.plot_btn.setEnabled(done and self._get_pp() is not None)
        self.folder_btn.setEnabled(True)
    
    def _handle_action(self, action: str, job: Job):
        if action == "results":
            self.view_results_requested.emit(job)
        elif action == "plot":
            self._plot_job(job)
        elif action == "folder":
            self._open_job_folder(job)
        elif action == "stop":
            self.runner.cancel_job(job)
            self._refresh()
    
    def _run_selected(self):
        if not self.selected_job:
            return
        job = self.selected_job
        if job.status == JobStatus.RUNNING:
            return
        
        worker = JobWorker(self.runner, job)
        worker.output_received.connect(self._log)
        worker.progress_update.connect(lambda p: self._update_progress(job.id, p))
        worker.job_finished.connect(self._on_done)
        self.workers[job.id] = worker
        worker.start()
        
        self.output.clear()
        self._log(f"[FluxDFT] Starting: {job.name}")
        self._log(f"[FluxDFT] Command: {job.executable} < {job.input_file}")
        self._log("-" * 50)
        self._refresh()
    
    def _stop_selected(self):
        if self.selected_job and self.selected_job.status == JobStatus.RUNNING:
            self.runner.cancel_job(self.selected_job)
            self._log("[FluxDFT] Job stopped")
            self._refresh()
    
    def _update_progress(self, jid: str, p: int):
        if jid in self.job_cards:
            self.job_cards[jid].set_progress(p)
    
    def _log(self, txt: str):
        self.output.append(txt)
        self.output.verticalScrollBar().setValue(self.output.verticalScrollBar().maximum())
    
    job_completed = pyqtSignal(object)  # Signal emitting the completed Job object

    def _on_done(self, job: Job):
        status = "completed" if job.status == JobStatus.COMPLETED else "failed"
        self._log(f"\n[FluxDFT] Job {status}")
        if job.id in self.workers:
            del self.workers[job.id]
        if job.status == JobStatus.COMPLETED:
            pp = self._get_pp()
            if pp:
                self._log("[FluxDFT] Generating plots...")
                pp.process_completed_job(job)
            
            # Emit signal for automation
            self._log("[FluxDFT] Automating results analysis...")
            self.job_completed.emit(job)
            
        self._refresh()
    
    def _on_plots(self, plots):
        self._log(f"[FluxDFT] {len(plots)} plots generated")
    
    def _refresh(self):
        for c in self.job_cards.values():
            c.refresh()
        self._update_count()
    
    def _update_count(self):
        n = len(self.runner.list_jobs())
        self.count_label.setText(f"{n} job{'s' if n != 1 else ''}")
    
    def _view_results(self):
        if self.selected_job:
            self.view_results_requested.emit(self.selected_job)
    
    def _gen_plots(self):
        if self.selected_job:
            self._plot_job(self.selected_job)
    
    def _plot_job(self, job: Job):
        pp = self._get_pp()
        if pp:
            self._log(f"\n[FluxDFT] Plotting {job.name}...")
            pp.process_completed_job(job)
    
    def _open_folder(self):
        if self.selected_job:
            self._open_job_folder(self.selected_job)
    
    def _open_job_folder(self, job: Job):
        if job.work_dir.exists():
            os.startfile(str(job.work_dir))
