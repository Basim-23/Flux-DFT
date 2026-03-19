"""
Main Window for FluxDFT.
Professional GUI with Docking Layout ("Scientific Workbench").
Copyright (c) 2026 Basim Nasser. MIT License.
"""

import sys
from pathlib import Path
from typing import Optional, Union
from datetime import datetime

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QStatusBar, QToolBar, QFileDialog, QMessageBox, QApplication,
    QDockWidget, QTabWidget, QScrollArea, QSizePolicy, QProgressBar,
    QSpacerItem, QDialog
)
from PyQt6.QtCore import Qt, QSize, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QAction, QFont, QColor, QPalette, QLinearGradient, QPainter, QBrush, QPen, QKeySequence, QShortcut

from ..utils.config import Config
from ..utils.constants import APP_NAME, APP_VERSION, APP_COPYRIGHT

# Try to import qtawesome for icons
try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


# =============================================================================
# PREMIUM STYLED COMPONENTS
# =============================================================================

class GlowButton(QPushButton):
    """Premium button with glow effect on hover."""
    
    def __init__(self, text: str, accent_color: str = "#3b82f6", parent=None):
        super().__init__(text, parent)
        self.accent_color = accent_color
        self.setMinimumHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._apply_style()
    
    def _apply_style(self):
        self.setStyleSheet(f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self.accent_color}, stop:1 {self._darken(self.accent_color)});
                color: white;
                border: none;
                border-radius: 8px;
                padding: 12px 24px;
                font-size: 13px;
                font-weight: 600;
            }}
            QPushButton:hover {{
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 {self._lighten(self.accent_color)}, stop:1 {self.accent_color});
            }}
            QPushButton:pressed {{
                background: {self._darken(self.accent_color)};
            }}
        """)
    
    def _darken(self, color: str, factor: float = 0.8) -> str:
        c = QColor(color)
        return QColor.fromHslF(c.hueF(), c.saturationF(), max(0, c.lightnessF() * factor)).name()
    
    def _lighten(self, color: str, factor: float = 1.2) -> str:
        c = QColor(color)
        return QColor.fromHslF(c.hueF(), c.saturationF(), min(1, c.lightnessF() * factor)).name()


class SidebarButton(QPushButton):
    """Premium sidebar navigation button."""
    
    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(48)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #a6adc8;
                border: none;
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover {
                background: rgba(137, 180, 250, 0.1);
                color: #cdd6f4;
            }
            QPushButton:checked {
                background: rgba(137, 180, 250, 0.15);
                color: #89b4fa;
                border-left: 3px solid #89b4fa;
            }
        """)


class MetricCard(QFrame):
    """Interactive metric card with click navigation."""
    
    def __init__(self, title: str, value: str, subtitle: str = "", 
                 color: str = "#3b82f6", action_key: str = "", homepage=None, parent=None):
        super().__init__(parent)
        self.action_key = action_key
        self.homepage = homepage
        self.color = color
        
        self.setMinimumSize(170, 90)
        self.setMaximumHeight(100)
        if action_key:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._base_style = f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d0d12, stop:1 #0a0a0f);
                border: 1px solid #1a1a24;
                border-radius: 12px;
                border-left: 3px solid {color};
            }}
        """
        self._hover_style = f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #121218, stop:1 #0d0d12);
                border: 1px solid {color}50;
                border-radius: 12px;
                border-left: 3px solid {color};
            }}
        """
        self.setStyleSheet(self._base_style)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        
        # Title
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #6c7086; font-size: 10px; font-weight: 500; text-transform: uppercase; letter-spacing: 1px; border: none;")
        layout.addWidget(title_label)
        
        # Value
        value_label = QLabel(value)
        value_label.setStyleSheet(f"color: {color}; font-size: 24px; font-weight: 700; border: none;")
        layout.addWidget(value_label)
        
        # Subtitle
        if subtitle:
            sub_label = QLabel(subtitle)
            sub_label.setStyleSheet("color: #45475a; font-size: 10px; border: none;")
            layout.addWidget(sub_label)
        
        layout.addStretch()
    
    def enterEvent(self, event):
        if self.action_key:
            self.setStyleSheet(self._hover_style)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self.setStyleSheet(self._base_style)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if self.action_key and self.homepage and hasattr(self.homepage, '_on_action'):
            self.homepage._on_action(self.action_key)
        super().mousePressEvent(event)


class ActionCard(QFrame):
    """Enhanced action card with icon, hover effects, and click handling."""
    
    def __init__(self, title: str, description: str, color: str = "#3b82f6", 
                 action_key: str = "", icon_name: str = "", homepage=None, parent=None):
        super().__init__(parent)
        self.action_key = action_key
        self.color = color
        self.homepage = homepage
        self._hovered = False
        
        self.setFixedSize(180, 110)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        self._base_style = f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0d0d12, stop:1 #0a0a0f);
                border: 1px solid #1a1a24;
                border-radius: 12px;
                border-top: 3px solid {color};
            }}
        """
        self._hover_style = f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #151520, stop:1 #0f0f15);
                border: 1px solid {color}40;
                border-radius: 12px;
                border-top: 3px solid {color};
            }}
        """
        self.setStyleSheet(self._base_style)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)
        
        # Icon + Title row
        header = QHBoxLayout()
        header.setSpacing(10)
        
        if icon_name and HAS_ICONS:
            try:
                icon_label = QLabel()
                icon_label.setPixmap(qta.icon(icon_name, color=color).pixmap(20, 20))
                icon_label.setFixedSize(20, 20)
                icon_label.setStyleSheet("border: none; background: transparent;")
                header.addWidget(icon_label)
            except:
                pass
        
        title_label = QLabel(title)
        title_label.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; border: none; background: transparent;")
        title_label.setWordWrap(True)
        header.addWidget(title_label, 1)
        
        layout.addLayout(header)
        
        # Description
        desc_label = QLabel(description)
        desc_label.setStyleSheet("color: #6c7086; font-size: 10px; border: none; background: transparent;")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
        
        layout.addStretch()
        
        # Arrow indicator
        arrow = QLabel("→")
        arrow.setStyleSheet(f"color: {color}50; font-size: 14px; border: none; background: transparent;")
        arrow.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(arrow)
    
    def enterEvent(self, event):
        self._hovered = True
        self.setStyleSheet(self._hover_style)
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        self._hovered = False
        self.setStyleSheet(self._base_style)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event):
        if self.homepage and hasattr(self.homepage, '_on_action'):
            self.homepage._on_action(self.action_key)
        super().mousePressEvent(event)


class FeatureCard(QFrame):
    """Large feature showcase card."""
    
    def __init__(self, title: str, features: list, color: str = "#3b82f6", parent=None):
        super().__init__(parent)
        
        self.setStyleSheet(f"""
            QFrame {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1e2e, stop:1 #181825);
                border: 1px solid #313244;
                border-radius: 16px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)
        
        # Header
        header = QLabel(title)
        header.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: 600; border: none;")
        layout.addWidget(header)
        
        # Feature list
        for feat in features:
            row = QHBoxLayout()
            check = QLabel("✓")
            check.setStyleSheet(f"color: {color}; font-size: 14px; font-weight: bold; border: none;")
            check.setFixedWidth(20)
            row.addWidget(check)
            
            text = QLabel(feat)
            text.setStyleSheet("color: #a6adc8; font-size: 12px; border: none;")
            row.addWidget(text)
            row.addStretch()
            
            layout.addLayout(row)
        
        layout.addStretch()


class StatusIndicator(QFrame):
    """System status indicator with dot and label."""
    
    def __init__(self, name: str, is_ok: bool, detail: str = "", parent=None):
        super().__init__(parent)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        
        # Status dot
        dot = QLabel("●")
        dot.setStyleSheet(f"color: {'#10b981' if is_ok else '#ef4444'}; font-size: 10px; border: none;")
        dot.setFixedWidth(16)
        layout.addWidget(dot)
        
        # Name
        name_label = QLabel(name)
        name_label.setStyleSheet("color: #cdd6f4; font-size: 12px; border: none;")
        layout.addWidget(name_label)
        
        layout.addStretch()
        
        # Status text
        status = QLabel("Ready" if is_ok else "Not configured")
        status.setStyleSheet(f"color: {'#10b981' if is_ok else '#6c7086'}; font-size: 11px; border: none;")
        layout.addWidget(status)


class Sidebar(QFrame):
    """Premium navigation sidebar with scroll support."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)
        
        self.setStyleSheet("""
            QFrame#sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #0d0d12, stop:1 #0a0a0f);
                border-right: 1px solid #1a1a24;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: #0d0d12;
                width: 6px;
            }
            QScrollBar::handle:vertical {
                background: #2a2a3a;
                border-radius: 3px;
            }
        """)
        
        # Content widget
        content = QWidget()
        content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(12, 20, 12, 20)
        layout.setSpacing(4)
        
        # Logo / Title
        title = QLabel(APP_NAME)
        title.setFont(QFont("Segoe UI", 20, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #89b4fa; border: none;")
        layout.addWidget(title)
        
        subtitle = QLabel("Professional DFT Interface")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #6c7086; font-size: 10px; border: none;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(20)
        
        # Section header
        section = QLabel("NAVIGATION")
        section.setStyleSheet("color: #45475a; font-size: 10px; font-weight: 600; letter-spacing: 2px; padding-left: 8px; border: none;")
        layout.addWidget(section)
        
        layout.addSpacing(8)
        
        # Navigation buttons with icons
        self.buttons = {}
        
        nav_items = [
            ("home", "Home", "fa5s.home"),
            ("input", "Input Editor", "fa5s.edit"),
            ("structure", "Structure", "fa5s.cube"),
            ("workflows", "Workflows", "fa5s.project-diagram"),
            ("jobs", "Jobs", "fa5s.tasks"),
            ("converter", "Converter", "fa5s.exchange-alt"),
            ("convergence", "Convergence", "fa5s.chart-line"),
            ("results", "Results", "fa5s.poll"),
            ("analysis", "Analysis", "fa5s.microscope"),
        ]
        
        for key, label, icon_name in nav_items:
            btn = SidebarButton(label)
            if HAS_ICONS:
                try:
                    btn.setIcon(qta.icon(icon_name, color="#6c7086"))
                except:
                    pass
            btn.clicked.connect(lambda checked, k=key: self._on_nav_click(k))
            self.buttons[key] = btn
            layout.addWidget(btn)
        
        layout.addSpacing(16)
        
        # Tools section
        tools_section = QLabel("TOOLS")
        tools_section.setStyleSheet("color: #45475a; font-size: 10px; font-weight: 600; letter-spacing: 2px; padding-left: 8px; border: none;")
        layout.addWidget(tools_section)
        
        layout.addSpacing(8)
        
        tools_items = [
            ("pseudopotentials", "Pseudopotentials", "fa5s.atom"),
            ("materials_project", "Materials Project", "fa5s.database"),
            ("reports", "Reports", "fa5s.file-pdf"),
            ("tutorials", "Tutorials", "fa5s.graduation-cap"),
        ]
        
        for key, label, icon_name in tools_items:
            btn = SidebarButton(label)
            if HAS_ICONS:
                try:
                    btn.setIcon(qta.icon(icon_name, color="#6c7086"))
                except:
                    pass
            btn.clicked.connect(lambda checked, k=key: self._on_nav_click(k))
            self.buttons[key] = btn
            layout.addWidget(btn)
        
        layout.addSpacing(16)
        
        # Settings section
        section2 = QLabel("SYSTEM")
        section2.setStyleSheet("color: #45475a; font-size: 10px; font-weight: 600; letter-spacing: 2px; padding-left: 8px; border: none;")
        layout.addWidget(section2)
        
        layout.addSpacing(8)
        
        settings_btn = SidebarButton("Settings")
        if HAS_ICONS:
            try:
                settings_btn.setIcon(qta.icon("fa5s.cog", color="#6c7086"))
            except:
                pass
        settings_btn.clicked.connect(lambda: self._on_nav_click("settings"))
        self.buttons["settings"] = settings_btn
        layout.addWidget(settings_btn)
        
        layout.addStretch()
        
        # Version info
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version_label.setStyleSheet("color: #45475a; font-size: 10px; border: none; margin-top: 10px;")
        layout.addWidget(version_label)
        
        scroll.setWidget(content)
        main_layout.addWidget(scroll)
        
        # Select home by default
        self.buttons["home"].setChecked(True)
        self.current_page = "home"
        
        self.on_page_changed = None
    
    def _on_nav_click(self, key: str):
        for k, btn in self.buttons.items():
            btn.setChecked(k == key)
        
        self.current_page = key
        
        if self.on_page_changed:
            self.on_page_changed(key)


# =============================================================================
# HOME PAGE - PREMIUM DASHBOARD
# =============================================================================

class HomePage(QWidget):
    """Premium home page with comprehensive dashboard."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = None
        self._setup_ui()
    
    def _setup_ui(self):
        # Main scroll area - hide all scrollbars for clean look
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(14)
        
        # === HERO SECTION ===
        hero = self._create_hero_section()
        layout.addWidget(hero)
        
        # === METRICS ROW ===
        metrics = self._create_metrics_section()
        layout.addLayout(metrics)
        
        # === QUICK ACTIONS ===
        actions_header = QLabel("Quick Actions")
        actions_header.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: 600;")
        layout.addWidget(actions_header)
        
        actions = self._create_actions_section()
        layout.addLayout(actions)
        
        # === STATUS ROW ===
        status_row = QHBoxLayout()
        status_row.setSpacing(24)
        
        # Quick status indicators
        try:
            config = Config().config
            qe_ok = Path(config.qe_path).exists() if config.qe_path else False
            pseudo_ok = Path(config.pseudo_dir).exists() if config.pseudo_dir else False
        except:
            qe_ok = pseudo_ok = False
        
        qe_status = QLabel(f"QE: {'Ready' if qe_ok else 'Not configured'}")
        qe_status.setStyleSheet(f"color: {'#10b981' if qe_ok else '#6c7086'}; font-size: 11px;")
        status_row.addWidget(qe_status)
        
        pseudo_status = QLabel(f"Pseudopotentials: {'Ready' if pseudo_ok else 'Not configured'}")
        pseudo_status.setStyleSheet(f"color: {'#10b981' if pseudo_ok else '#6c7086'}; font-size: 11px;")
        status_row.addWidget(pseudo_status)
        
        status_row.addStretch()
        
        # Settings button
        settings_btn = QPushButton("Open Settings")
        settings_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #89b4fa;
                border: 1px solid #89b4fa;
                border-radius: 6px;
                padding: 6px 16px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: rgba(137, 180, 250, 0.1);
            }
        """)
        settings_btn.clicked.connect(lambda: self._get_main_window()._on_settings() if self._get_main_window() else None)
        status_row.addWidget(settings_btn)
        
        layout.addLayout(status_row)
        
        scroll.setWidget(content)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)
    
    def _create_hero_section(self) -> QFrame:
        """Create enhanced hero banner with CTA buttons."""
        hero = QFrame()
        hero.setFixedHeight(160)
        hero.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0a0a12, stop:0.3 #0d1020, stop:0.7 #0a0a15, stop:1 #050508);
                border-radius: 16px;
                border: 1px solid #1a1a30;
            }
        """)
        
        layout = QVBoxLayout(hero)
        layout.setContentsMargins(32, 24, 32, 24)
        layout.setSpacing(8)
        
        # Welcome text - larger and bolder
        welcome = QLabel(f"Welcome to {APP_NAME}")
        welcome.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        welcome.setStyleSheet("color: #f0f0f8; border: none; background: transparent;")
        layout.addWidget(welcome)
        
        # Tagline with gradient effect simulated
        tagline = QLabel("Professional DFT Interface for Quantum ESPRESSO")
        tagline.setStyleSheet("color: #89b4fa; font-size: 14px; font-weight: 500; border: none; background: transparent;")
        layout.addWidget(tagline)
        
        layout.addStretch()
        
        # CTA buttons row
        btn_row = QHBoxLayout()
        btn_row.setSpacing(12)
        
        # Get Started button
        get_started = QPushButton("  Get Started")
        if HAS_ICONS:
            try:
                get_started.setIcon(qta.icon("fa5s.rocket", color="#ffffff"))
            except:
                pass
        get_started.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #3b82f6, stop:1 #2563eb);
                color: white;
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #60a5fa, stop:1 #3b82f6);
            }
        """)
        get_started.setCursor(Qt.CursorShape.PointingHandCursor)
        get_started.clicked.connect(lambda: self._on_action("input"))
        btn_row.addWidget(get_started)
        
        # View Tutorials button
        tutorials = QPushButton("  Tutorials")
        if HAS_ICONS:
            try:
                tutorials.setIcon(qta.icon("fa5s.graduation-cap", color="#89b4fa"))
            except:
                pass
        tutorials.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #89b4fa;
                border: 1px solid #89b4fa;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 12px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: rgba(137, 180, 250, 0.1);
            }
        """)
        tutorials.setCursor(Qt.CursorShape.PointingHandCursor)
        tutorials.clicked.connect(self._open_docs)
        btn_row.addWidget(tutorials)
        
        btn_row.addStretch()
        
        # Feature badges
        features_label = QLabel("SCF • Bands • DOS • Phonons • Optimization • HPC")
        features_label.setStyleSheet("color: #45475a; font-size: 11px; border: none; background: transparent;")
        btn_row.addWidget(features_label)
        
        layout.addLayout(btn_row)
        
        return hero
    
    def _create_metrics_section(self) -> QHBoxLayout:
        """Create interactive metrics cards row."""
        layout = QHBoxLayout()
        layout.setSpacing(16)
        
        # Load config for metrics
        try:
            config = Config().config
            recent_count = len(config.recent_files) if config.recent_files else 0
        except:
            recent_count = 0
        
        metrics = [
            ("Recent Projects", str(recent_count), "files loaded", "#3b82f6", "input"),
            ("Calculations", "0", "jobs completed", "#10b981", "jobs"),
            ("System Status", "Ready", "all services ok", "#8b5cf6", ""),
            ("Performance", "Optimal", "no issues", "#f59e0b", ""),
        ]
        
        for title, value, sub, color, action_key in metrics:
            card = MetricCard(title, value, sub, color, action_key, homepage=self)
            layout.addWidget(card)
        
        layout.addStretch()
        return layout
    
    def _create_actions_section(self) -> QVBoxLayout:
        """Create quick action cards in a responsive grid."""
        main_layout = QVBoxLayout()
        main_layout.setSpacing(12)
        
        # First row of actions
        row1 = QHBoxLayout()
        row1.setSpacing(12)
        
        actions_row1 = [
            ("New SCF", "Ground-state energy", "#10b981", "scf", "fa5s.atom"),
            ("Band Structure", "Electronic bands", "#3b82f6", "bands", "fa5s.project-diagram"),
            ("Density of States", "DOS analysis", "#8b5cf6", "dos", "fa5s.chart-area"),
            ("Relaxation", "Geometry optimization", "#f59e0b", "relax", "fa5s.compress-arrows-alt"),
        ]
        
        for title, desc, color, key, icon in actions_row1:
            card = ActionCard(title, desc, color, key, icon, homepage=self)
            row1.addWidget(card)
        row1.addStretch()
        main_layout.addLayout(row1)
        
        # Second row of actions
        row2 = QHBoxLayout()
        row2.setSpacing(12)
        
        actions_row2 = [
            ("Structure Viewer", "3D visualization", "#ec4899", "structure", "fa5s.cube"),
            ("Format Converter", "CIF, POSCAR, XYZ", "#06b6d4", "converter", "fa5s.exchange-alt"),
            ("Job Manager", "Run and monitor", "#84cc16", "jobs", "fa5s.tasks"),
            ("Analysis Tools", "Post-processing", "#a855f7", "analysis", "fa5s.chart-line"),
        ]
        
        for title, desc, color, key, icon in actions_row2:
            card = ActionCard(title, desc, color, key, icon, homepage=self)
            row2.addWidget(card)
        row2.addStretch()
        main_layout.addLayout(row2)
        
        return main_layout
    
    def _create_left_column(self) -> QVBoxLayout:
        """Create left column with features and recent projects."""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # Features section
        features_header = QLabel("Key Features")
        features_header.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: 600;")
        layout.addWidget(features_header)
        
        features_grid = QHBoxLayout()
        features_grid.setSpacing(16)
        
        feature_sets = [
            ("Input Generation", [
                "Visual input file editor",
                "Template-based workflows",
                "Syntax validation",
                "Parameter suggestions",
            ], "#3b82f6"),
            ("Analysis Tools", [
                "Publication-quality plots",
                "Band structure analysis",
                "DOS visualization",
                "Convergence tracking",
            ], "#10b981"),
        ]
        
        for title, feats, color in feature_sets:
            card = FeatureCard(title, feats, color)
            features_grid.addWidget(card)
        
        layout.addLayout(features_grid)
        
        # Recent projects
        recent_header = QLabel("Recent Projects")
        recent_header.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: 600;")
        layout.addWidget(recent_header)
        
        recent_frame = QFrame()
        recent_frame.setStyleSheet("""
            QFrame {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 12px;
            }
        """)
        
        recent_layout = QVBoxLayout(recent_frame)
        recent_layout.setContentsMargins(16, 16, 16, 16)
        recent_layout.setSpacing(4)
        
        try:
            config = Config().config
            recent_files = config.recent_files[:5] if config.recent_files else []
        except:
            recent_files = []
        
        if recent_files:
            for filepath in recent_files:
                name = Path(filepath).name
                item = QPushButton(name)
                item.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        border: none;
                        text-align: left;
                        padding: 10px 12px;
                        color: #a6adc8;
                        font-size: 12px;
                        border-radius: 6px;
                    }
                    QPushButton:hover {
                        background: rgba(137, 180, 250, 0.1);
                        color: #cdd6f4;
                    }
                """)
                item.setToolTip(filepath)
                # Connect to open file
                item.clicked.connect(lambda checked, fp=filepath: self._open_recent_file(fp))
                recent_layout.addWidget(item)
        else:
            no_recent = QLabel("No recent projects\n\nCreate or open a project to get started")
            no_recent.setStyleSheet("color: #6c7086; font-size: 12px; border: none; padding: 20px;")
            no_recent.setAlignment(Qt.AlignmentFlag.AlignCenter)
            recent_layout.addWidget(no_recent)
        
        layout.addWidget(recent_frame)
        layout.addStretch()
        
        return layout
    
    def _create_right_column(self) -> QVBoxLayout:
        """Create right column with status and tips."""
        layout = QVBoxLayout()
        layout.setSpacing(20)
        
        # System Status
        status_header = QLabel("System Status")
        status_header.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: 600;")
        layout.addWidget(status_header)
        
        status_frame = QFrame()
        status_frame.setStyleSheet("""
            QFrame {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 12px;
            }
        """)
        
        status_layout = QVBoxLayout(status_frame)
        status_layout.setContentsMargins(8, 12, 8, 12)
        status_layout.setSpacing(2)
        
        try:
            config = Config().config
            qe_path = Path(config.qe_path)
            pw_exists = (qe_path / "pw.x").exists() if qe_path.exists() else False
        except:
            pw_exists = False
            config = None
        
        status_items = [
            ("Quantum ESPRESSO", pw_exists),
            ("Pseudopotentials", config and Path(config.pseudo_dir).exists() if config else False),
            ("Work Directory", config and Path(config.work_dir).exists() if config else False),
            ("Materials Project API", config and bool(config.mp_api_key) if config else False),
        ]
        
        for name, is_ok in status_items:
            indicator = StatusIndicator(name, is_ok)
            status_layout.addWidget(indicator)
        
        layout.addWidget(status_frame)
        
        # Quick Tips
        tips_header = QLabel("Getting Started")
        tips_header.setStyleSheet("color: #cdd6f4; font-size: 16px; font-weight: 600;")
        layout.addWidget(tips_header)
        
        tips_frame = QFrame()
        tips_frame.setStyleSheet("""
            QFrame {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 12px;
            }
        """)
        
        tips_layout = QVBoxLayout(tips_frame)
        tips_layout.setContentsMargins(16, 16, 16, 16)
        tips_layout.setSpacing(12)
        
        tips = [
            ("1.", "Configure QE path in Settings"),
            ("2.", "Import or create a structure"),
            ("3.", "Set up calculation parameters"),
            ("4.", "Run and monitor your job"),
            ("5.", "Analyze results with built-in tools"),
        ]
        
        for num, text in tips:
            row = QHBoxLayout()
            
            num_label = QLabel(num)
            num_label.setStyleSheet("color: #89b4fa; font-size: 12px; font-weight: 600; border: none;")
            num_label.setFixedWidth(24)
            row.addWidget(num_label)
            
            text_label = QLabel(text)
            text_label.setStyleSheet("color: #a6adc8; font-size: 12px; border: none;")
            row.addWidget(text_label)
            row.addStretch()
            
            tips_layout.addLayout(row)
        
        layout.addWidget(tips_frame)
        
        # Documentation link
        docs_btn = GlowButton("View Documentation", "#6366f1")
        docs_btn.clicked.connect(self._open_docs)
        layout.addWidget(docs_btn)
        
        layout.addStretch()
        return layout
    
    def _get_main_window(self):
        """Get reference to main window."""
        if not self.main_window:
            parent = self.parent()
            while parent and not isinstance(parent, QMainWindow):
                parent = parent.parent()
            self.main_window = parent
        return self.main_window
    
    def _on_action(self, action_type: str):
        """Handle quick action card clicks."""
        mw = self._get_main_window()
        if not mw:
            return
        
        # Map action keys to tab opening methods
        action_map = {
            "input": "_open_input_tab",
            "scf": "_open_input_tab",
            "bands": "_open_workflows_tab",
            "dos": "_open_workflows_tab", 
            "relax": "_open_input_tab",
            "converter": "_open_converter_tab",
            "structure": "_open_structure_tab",
            "jobs": "_open_jobs_tab",
            "results": "_open_results_tab",
            "analysis": "_open_analysis_tab",
            "tutorials": "_open_tutorials_tab",
            "workflows": "_open_workflows_tab",
            "convergence": "_open_convergence_tab",
        }
        
        method_name = action_map.get(action_type)
        if method_name and hasattr(mw, method_name):
            getattr(mw, method_name)()
    
    def _open_recent_file(self, filepath: str):
        """Open a recent project file."""
        mw = self._get_main_window()
        if not mw:
            return
        
        from pathlib import Path
        fp = Path(filepath)
        
        if not fp.exists():
            QMessageBox.warning(self, "File Not Found", f"The file no longer exists:\n{filepath}")
            return
        
        # Determine file type and open appropriate editor
        ext = fp.suffix.lower()
        
        if ext in ['.in', '.inp', '.pw']:
            # QE input file - open in input editor
            mw._open_input_tab()
            # Try to load the file into the editor
            if "input" in mw.pages:
                editor = mw.pages["input"]
                if hasattr(editor, 'load_file'):
                    editor.load_file(fp)
                elif hasattr(editor, 'editor') and hasattr(editor.editor, 'load_file'):
                    editor.editor.load_file(fp)
        elif ext in ['.cif', '.xyz', '.poscar', '.vasp', '.xsf']:
            # Structure file - open in structure viewer
            mw._open_structure_tab()
        elif ext == '.out':
            # Output file - open in convergence monitor
            mw._open_convergence_tab()
            if "convergence" in mw.pages:
                monitor = mw.pages["convergence"]
                if hasattr(monitor, 'set_output_file'):
                    monitor.set_output_file(fp)
        
        mw.status_bar.showMessage(f"Opened: {filepath}")
    
    def _open_docs(self):
        """Open documentation or tutorials."""
        mw = self._get_main_window()
        if mw:
            mw._open_tutorials_tab()


# =============================================================================
# TUTORIALS PAGE
# =============================================================================

class TutorialsPage(QWidget):
    """Premium tutorials page with comprehensive DFT content."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(24)
        
        # Header
        header = QLabel("Tutorials and Learning")
        header.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)
        
        subtitle = QLabel("Step-by-step guides to help you master DFT calculations with FluxDFT")
        subtitle.setStyleSheet("color: #6c7086; font-size: 14px;")
        layout.addWidget(subtitle)
        
        layout.addSpacing(10)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(12)
        
        tutorials = [
            ("Getting Started", "Your first SCF calculation with Silicon", "beginner", "15 min"),
            ("Band Structure", "Calculate and plot electronic band structure", "beginner", "20 min"),
            ("Density of States", "Compute and visualize DOS and PDOS", "intermediate", "25 min"),
            ("Geometry Optimization", "Relax atomic positions and cell parameters", "intermediate", "30 min"),
            ("K-point Convergence", "Systematic convergence testing", "intermediate", "20 min"),
            ("Phonon Calculations", "Lattice dynamics with ph.x", "advanced", "45 min"),
            ("Equation of State", "Bulk modulus from E-V curve", "advanced", "35 min"),
            ("Remote HPC Submission", "Submit jobs to SLURM/PBS clusters", "advanced", "40 min"),
        ]
        
        for title, desc, level, duration in tutorials:
            card = self._create_tutorial_card(title, desc, level, duration)
            content_layout.addWidget(card)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_tutorial_card(self, title: str, desc: str, level: str, duration: str) -> QFrame:
        level_colors = {
            "beginner": "#10b981",
            "intermediate": "#f59e0b",
            "advanced": "#ef4444",
        }
        
        color = level_colors.get(level, "#3b82f6")
        
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #1e1e2e;
                border: 1px solid #313244;
                border-left: 4px solid {color};
                border-radius: 8px;
            }}
            QFrame:hover {{
                background: #252536;
                border-color: {color};
            }}
        """)
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.setFixedHeight(70)
        
        layout = QHBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 12)
        
        # Text content
        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: 600; border: none;")
        text_layout.addWidget(title_label)
        
        desc_label = QLabel(desc)
        desc_label.setStyleSheet("color: #6c7086; font-size: 12px; border: none;")
        text_layout.addWidget(desc_label)
        
        layout.addLayout(text_layout, 1)
        
        # Level badge
        level_badge = QLabel(level.upper())
        level_badge.setStyleSheet(f"""
            color: {color};
            font-size: 10px;
            font-weight: 600;
            padding: 4px 10px;
            border: 1px solid {color};
            border-radius: 10px;
            background: transparent;
        """)
        layout.addWidget(level_badge)
        
        # Duration
        duration_label = QLabel(duration)
        duration_label.setStyleSheet("color: #6c7086; font-size: 11px; border: none; margin-left: 10px;")
        layout.addWidget(duration_label)
        
        # Start button
        start_btn = QPushButton("Start")
        start_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {color};
                border: 1px solid {color};
                border-radius: 6px;
                padding: 8px 20px;
                font-size: 12px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {color};
                color: #1e1e2e;
            }}
        """)
        start_btn.clicked.connect(lambda: self._open_tutorial(title))
        layout.addWidget(start_btn)
        
        return card
    
    def _open_tutorial(self, title: str):
        """Open a full tutorial in a new dialog."""
        content = TUTORIAL_CONTENT.get(title, "Tutorial content not available.")
        
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Tutorial: {title}")
        dialog.setMinimumSize(800, 600)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #1e1e2e; }
            QScrollBar:vertical { background: #1e1e2e; width: 8px; }
            QScrollBar::handle:vertical { background: #45475a; border-radius: 4px; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
        """)
        
        text = QLabel(content)
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        text.setOpenExternalLinks(True)
        text.setStyleSheet("""
            QLabel {
                color: #cdd6f4;
                background: #1e1e2e;
                padding: 30px 40px;
                font-size: 13px;
                line-height: 1.6;
            }
        """)
        text.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        scroll.setWidget(text)
        layout.addWidget(scroll)
        
        close_btn = QPushButton("Close")
        close_btn.setStyleSheet("""
            QPushButton {
                background: #313244; color: #cdd6f4; border: none;
                padding: 10px; font-size: 13px;
            }
            QPushButton:hover { background: #45475a; }
        """)
        close_btn.clicked.connect(dialog.close)
        layout.addWidget(close_btn)
        
        dialog.exec()


# =============================================================================
# TUTORIAL CONTENT
# =============================================================================

TUTORIAL_CONTENT = {
    "Getting Started": """
<h1 style="color:#89b4fa;">Getting Started: Your First SCF Calculation</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">What is SCF?</h2>
<p>Self-Consistent Field (SCF) is the fundamental calculation in Density Functional Theory. 
It solves the Kohn-Sham equations iteratively until the electron density converges — meaning 
the input and output densities agree within a specified tolerance.</p>

<h2 style="color:#cba6f7;">Step 1: Load a Structure</h2>
<ol>
<li>Open the <b>Structure</b> tab from the sidebar</li>
<li>Click <b>Import</b> → select a <code>.cif</code> file (e.g., Silicon)</li>
<li>The 3D viewer will show the crystal structure</li>
</ol>

<h2 style="color:#cba6f7;">Step 2: Generate Input File</h2>
<ol>
<li>Open the <b>Input Editor</b> tab</li>
<li>Set <b>calculation</b> = <code>'scf'</code></li>
<li>Set <b>ecutwfc</b> = <code>40.0</code> Ry (wavefunction cutoff)</li>
<li>Set <b>ecutrho</b> = <code>320.0</code> Ry (density cutoff, 8× ecutwfc for PAW)</li>
<li>Set K-points to <code>4 4 4 1 1 1</code> (Monkhorst-Pack grid)</li>
</ol>

<h2 style="color:#cba6f7;">Example Input File</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&CONTROL
  calculation = 'scf',
  prefix = 'silicon',
  outdir = './tmp/',
  pseudo_dir = './pseudo/',
/
&SYSTEM
  ibrav = 2,
  celldm(1) = 10.26,
  nat = 2,
  ntyp = 1,
  ecutwfc = 40.0,
  ecutrho = 320.0,
/
&ELECTRONS
  conv_thr = 1.0d-8,
/
ATOMIC_SPECIES
  Si 28.086 Si.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  4 4 4 1 1 1
</pre>

<h2 style="color:#cba6f7;">Step 3: Run the Calculation</h2>
<ol>
<li>Open <b>Jobs</b> tab → click <b>Submit</b></li>
<li>Monitor convergence in the <b>Convergence</b> tab</li>
<li>When complete, check the total energy in the output</li>
</ol>

<h2 style="color:#cba6f7;">Key Concepts</h2>
<ul>
<li><b>ecutwfc</b> — Controls basis set size. Higher = more accurate but slower.</li>
<li><b>K-points</b> — Sampling of the Brillouin zone. More k-points = better accuracy.</li>
<li><b>conv_thr</b> — Convergence threshold (Ry). Default 1.0e-8 is good for most cases.</li>
</ul>
""",

    "Band Structure": """
<h1 style="color:#89b4fa;">Band Structure Calculation</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Overview</h2>
<p>A band structure calculation reveals the electronic band dispersion along high-symmetry 
paths in the Brillouin zone. This is essential for determining if a material is a metal, 
semiconductor, or insulator, and for measuring the band gap.</p>

<h2 style="color:#cba6f7;">Workflow</h2>
<p>Band structure requires <b>two</b> pw.x runs:</p>
<ol>
<li><b>SCF</b> — self-consistent calculation to get the charge density</li>
<li><b>NSCF/Bands</b> — non-self-consistent calculation along k-path</li>
</ol>

<h2 style="color:#cba6f7;">Step 1: SCF Calculation</h2>
<p>Run a standard SCF calculation first (see Getting Started tutorial).</p>

<h2 style="color:#cba6f7;">Step 2: Bands Calculation Input</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&CONTROL
  calculation = 'bands',
  prefix = 'silicon',
  outdir = './tmp/',
  pseudo_dir = './pseudo/',
/
&SYSTEM
  ibrav = 2,
  celldm(1) = 10.26,
  nat = 2, ntyp = 1,
  ecutwfc = 40.0,
  nbnd = 8,
/
&ELECTRONS /
ATOMIC_SPECIES
  Si 28.086 Si.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS crystal_b
  5
  0.500 0.500 0.500 20  ! L
  0.000 0.000 0.000 20  ! Γ
  0.500 0.000 0.500 20  ! X
  0.375 0.375 0.750 20  ! K
  0.000 0.000 0.000  1  ! Γ
</pre>

<h2 style="color:#cba6f7;">Step 3: Post-processing with bands.x</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&BANDS
  prefix = 'silicon',
  outdir = './tmp/',
  filband = 'silicon.bands.dat',
/
</pre>

<h2 style="color:#cba6f7;">Step 4: Visualize in FluxDFT</h2>
<ol>
<li>Open the <b>Results</b> tab</li>
<li>Load the <code>.bands.dat.gnu</code> file</li>
<li>The band structure will be plotted with high-symmetry labels</li>
</ol>

<h2 style="color:#cba6f7;">Understanding the Result</h2>
<ul>
<li><b>Band gap</b>: minimum energy between valence band max (VBM) and conduction band min (CBM)</li>
<li><b>Direct gap</b>: VBM and CBM at the same k-point</li>
<li><b>Indirect gap</b>: VBM and CBM at different k-points (like Silicon: Γ→X)</li>
</ul>
""",

    "Density of States": """
<h1 style="color:#89b4fa;">Density of States (DOS)</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">What is DOS?</h2>
<p>The Density of States tells you how many electronic states exist at each energy level. 
Peaks in the DOS correspond to flat bands; gaps correspond to band gaps.</p>

<h2 style="color:#cba6f7;">Workflow: SCF → NSCF → dos.x</h2>
<ol>
<li><b>SCF</b>: Get the converged charge density</li>
<li><b>NSCF</b>: Calculate eigenvalues on a dense k-mesh</li>
<li><b>dos.x</b>: Compute the DOS from eigenvalues</li>
</ol>

<h2 style="color:#cba6f7;">NSCF Input (dense k-mesh)</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&CONTROL
  calculation = 'nscf',
  prefix = 'silicon',
  outdir = './tmp/',
  pseudo_dir = './pseudo/',
/
&SYSTEM
  ibrav = 2, celldm(1) = 10.26,
  nat = 2, ntyp = 1,
  ecutwfc = 40.0,
  occupations = 'tetrahedra',
  nbnd = 16,
/
&ELECTRONS /
ATOMIC_SPECIES
  Si 28.086 Si.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  12 12 12 0 0 0
</pre>

<h2 style="color:#cba6f7;">dos.x Input</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&DOS
  prefix = 'silicon',
  outdir = './tmp/',
  fildos = 'silicon.dos',
  degauss = 0.01,
  Emin = -15.0, Emax = 10.0,
  DeltaE = 0.1,
/
</pre>

<h2 style="color:#cba6f7;">Projected DOS (PDOS)</h2>
<p>Use <code>projwfc.x</code> to decompose the DOS into orbital contributions (s, p, d):</p>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&PROJWFC
  prefix = 'silicon',
  outdir = './tmp/',
  filpdos = 'silicon.pdos',
  degauss = 0.01,
/
</pre>
""",

    "Geometry Optimization": """
<h1 style="color:#89b4fa;">Geometry Optimization</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Types of Relaxation</h2>
<ul>
<li><b>relax</b>: Optimize atomic positions (fixed cell shape)</li>
<li><b>vc-relax</b>: Optimize both atomic positions AND cell parameters</li>
</ul>

<h2 style="color:#cba6f7;">When to Use Each</h2>
<p><b>relax</b>: When the cell shape/size is well known (from experiment) but atomic positions need refinement.</p>
<p><b>vc-relax</b>: When predicting the equilibrium structure from scratch, computing lattice constants, or studying phase transitions.</p>

<h2 style="color:#cba6f7;">Example: vc-relax Input</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&CONTROL
  calculation = 'vc-relax',
  prefix = 'silicon',
  outdir = './tmp/',
  pseudo_dir = './pseudo/',
  forc_conv_thr = 1.0d-4,
  etot_conv_thr = 1.0d-5,
/
&SYSTEM
  ibrav = 2, celldm(1) = 10.20,
  nat = 2, ntyp = 1,
  ecutwfc = 50.0, ecutrho = 400.0,
/
&ELECTRONS
  conv_thr = 1.0d-8,
/
&IONS
  ion_dynamics = 'bfgs',
/
&CELL
  cell_dynamics = 'bfgs',
  press = 0.0,
/
ATOMIC_SPECIES
  Si 28.086 Si.pbe-n-kjpaw_psl.1.0.0.UPF
ATOMIC_POSITIONS crystal
  Si 0.00 0.00 0.00
  Si 0.25 0.25 0.25
K_POINTS automatic
  6 6 6 1 1 1
</pre>

<h2 style="color:#cba6f7;">Tips</h2>
<ul>
<li>Always check that forces are below <code>forc_conv_thr</code> at the end</li>
<li>Use a higher <code>ecutwfc</code> than for SCF (50+ Ry recommended)</li>
<li>For metals, always include smearing with <code>degauss</code></li>
</ul>
""",

    "K-point Convergence": """
<h1 style="color:#89b4fa;">K-point Convergence Testing</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Why Converge K-points?</h2>
<p>The k-point mesh controls how well you sample the Brillouin zone. 
Too few k-points → inaccurate energies and forces. Too many → wasted CPU time. 
The goal is to find the <b>minimum k-mesh</b> where the energy stops changing significantly.</p>

<h2 style="color:#cba6f7;">Procedure</h2>
<ol>
<li>Run SCF with k-mesh: 2×2×2, 4×4×4, 6×6×6, 8×8×8, 10×10×10</li>
<li>Record the total energy from each run</li>
<li>Plot total energy vs. k-mesh</li>
<li>Choose the mesh where energy changes by less than 1 meV/atom</li>
</ol>

<h2 style="color:#cba6f7;">Using the FluxDFT Convergence Wizard</h2>
<ol>
<li>Open the <b>Convergence</b> tab</li>
<li>Select <b>K-points</b> convergence test</li>
<li>Set the range (e.g., 2 to 12, step 2)</li>
<li>Click <b>Run Test</b> — FluxDFT will automatically generate and run all calculations</li>
<li>Results are plotted in real-time</li>
</ol>

<h2 style="color:#cba6f7;">Typical Convergence Criteria</h2>
<ul>
<li><b>Total energy</b>: converged to within 1 meV/atom</li>
<li><b>Forces</b>: converged to within 1 meV/Å (for relaxation)</li>
<li><b>Pressure</b>: converged to within 0.5 kbar (for vc-relax)</li>
</ul>

<h2 style="color:#cba6f7;">Tips</h2>
<ul>
<li>Metals need denser k-grids than semiconductors</li>
<li>For slab/molecule calculations, use 1 k-point in the non-periodic direction</li>
<li>Always converge both ecutwfc AND k-points independently</li>
</ul>
""",

    "Phonon Calculations": """
<h1 style="color:#89b4fa;">Phonon Calculations with ph.x</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Overview</h2>
<p>Phonon calculations compute lattice vibration frequencies using Density Functional 
Perturbation Theory (DFPT). The workflow involves four codes:</p>
<ol>
<li><b>pw.x</b> — SCF ground state</li>
<li><b>ph.x</b> — Phonon perturbation (dynamical matrices)</li>
<li><b>q2r.x</b> — Fourier transform to real-space force constants</li>
<li><b>matdyn.x</b> — Interpolate phonon dispersion along any path</li>
</ol>

<h2 style="color:#cba6f7;">Step 1: SCF</h2>
<p>Run a well-converged SCF calculation (dense k-mesh, tight conv_thr).</p>

<h2 style="color:#cba6f7;">Step 2: ph.x Input</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
phonons of Silicon
&INPUTPH
  prefix = 'silicon',
  outdir = './tmp/',
  fildyn = 'silicon.dyn',
  ldisp = .true.,
  nq1 = 4, nq2 = 4, nq3 = 4,
  tr2_ph = 1.0d-14,
/
</pre>

<h2 style="color:#cba6f7;">Step 3: q2r.x Input</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&INPUT
  fildyn = 'silicon.dyn',
  zasr = 'crystal',
  flfrc = 'silicon.fc',
/
</pre>

<h2 style="color:#cba6f7;">Step 4: matdyn.x (Dispersion)</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
&INPUT
  asr = 'crystal',
  flfrc = 'silicon.fc',
  flfrq = 'silicon.freq',
  q_in_band_form = .true.,
/
5
0.500 0.500 0.500 20  ! L
0.000 0.000 0.000 20  ! Gamma
0.500 0.000 0.500 20  ! X
0.375 0.375 0.750 20  ! K
0.000 0.000 0.000  1  ! Gamma
</pre>

<h2 style="color:#cba6f7;">Stability Analysis</h2>
<p><b>Imaginary frequencies</b> (negative values in output) indicate structural instability — 
the crystal will distort along that phonon mode. This is common in high-symmetry structures 
that are dynamically unstable.</p>
""",

    "Equation of State": """
<h1 style="color:#89b4fa;">Equation of State & Bulk Modulus</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Overview</h2>
<p>The Equation of State (EOS) relates a material's energy (or pressure) to its volume. 
By fitting the E–V curve to the Birch-Murnaghan equation, you can extract:</p>
<ul>
<li><b>V₀</b> — equilibrium volume</li>
<li><b>E₀</b> — minimum energy</li>
<li><b>B₀</b> — bulk modulus (material stiffness)</li>
<li><b>B₀'</b> — pressure derivative of bulk modulus</li>
</ul>

<h2 style="color:#cba6f7;">Procedure</h2>
<ol>
<li>Choose 7–11 volumes around the equilibrium (±5% of experimental V₀)</li>
<li>Run SCF at each volume (scale <code>celldm(1)</code>)</li>
<li>Collect total energies</li>
<li>Fit to the 3rd-order Birch-Murnaghan EOS</li>
</ol>

<h2 style="color:#cba6f7;">Birch-Murnaghan Equation</h2>
<p style="font-size:14px; color:#f9e2af;">
E(V) = E₀ + (9V₀B₀/16) { [(V₀/V)^(2/3) - 1]³·B₀' + [(V₀/V)^(2/3) - 1]² · [6 - 4(V₀/V)^(2/3)] }
</p>

<h2 style="color:#cba6f7;">Tips</h2>
<ul>
<li>Use at least 7 data points for a reliable fit</li>
<li>Ensure all calculations use the same ecutwfc and k-mesh</li>
<li>Compare your B₀ with experimental values to validate your setup</li>
<li>For Silicon: B₀ ≈ 97–99 GPa (experiment), DFT-PBE gives ~92 GPa</li>
</ul>
""",

    "Remote HPC Submission": """
<h1 style="color:#89b4fa;">Remote HPC Submission</h1>
<hr style="border:1px solid #313244;">

<h2 style="color:#cba6f7;">Overview</h2>
<p>FluxDFT can submit jobs directly to HPC clusters via SSH. It supports 
SLURM, PBS/Torque, and SGE job schedulers.</p>

<h2 style="color:#cba6f7;">Step 1: Configure Server</h2>
<ol>
<li>Go to <b>Settings → Remote Servers</b></li>
<li>Click <b>Add</b> and fill in:
    <ul>
    <li><b>Server Name</b>: e.g., "University Cluster"</li>
    <li><b>Hostname</b>: e.g., <code>hpc.university.edu</code></li>
    <li><b>Username</b>: your login</li>
    <li><b>SSH Key</b>: path to your <code>~/.ssh/id_rsa</code></li>
    <li><b>QE Path</b>: e.g., <code>/opt/qe-7.3/bin</code></li>
    <li><b>Scheduler</b>: SLURM / PBS / SGE</li>
    </ul>
</li>
</ol>

<h2 style="color:#cba6f7;">Step 2: Submit a Job</h2>
<ol>
<li>Prepare your input file in the <b>Input Editor</b></li>
<li>Go to <b>Jobs → Submit Remote</b></li>
<li>Select the server and set resources:
    <ul>
    <li>Number of nodes / cores</li>
    <li>Wall time</li>
    <li>Queue / partition</li>
    </ul>
</li>
<li>Click <b>Submit</b></li>
</ol>

<h2 style="color:#cba6f7;">Example SLURM Script (auto-generated)</h2>
<pre style="background:#11111b; padding:16px; border-radius:8px; color:#a6e3a1; font-family:Consolas;">
#!/bin/bash
#SBATCH --job-name=silicon_scf
#SBATCH --nodes=1
#SBATCH --ntasks=16
#SBATCH --time=02:00:00
#SBATCH --partition=compute

module load qe/7.3

mpirun -np 16 pw.x -in silicon.in > silicon.out
</pre>

<h2 style="color:#cba6f7;">Monitoring</h2>
<ul>
<li>FluxDFT polls the job status every 30 seconds</li>
<li>When complete, output files are automatically downloaded</li>
<li>Results appear in the <b>Results</b> and <b>Convergence</b> tabs</li>
</ul>
""",
}


# =============================================================================
# MAIN WINDOW
# =============================================================================

class MainWindow(QMainWindow):
    """Premium Scientific Workbench Window."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} — v{APP_VERSION}")
        self.resize(1600, 1000)
        self.setMinimumSize(1200, 800)
        
        # Load Config
        self.config = Config().config
        
        # Shared Job Runner for all pages
        from ..core.job_runner import JobRunner
        qe_path = self.config.qe_path if hasattr(self.config, 'qe_path') and self.config.qe_path else ""
        self.job_runner = JobRunner(qe_path=qe_path)
        
        # Central Workspace (Tabs)
        self.workspace = QTabWidget()
        self.workspace.setTabsClosable(True)
        self.workspace.setMovable(True)
        self.workspace.tabCloseRequested.connect(self._close_tab)
        self.workspace.setDocumentMode(True)
        self.workspace.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: #11111b;
            }
            QTabBar::tab {
                background: #1e1e2e;
                color: #6c7086;
                padding: 10px 20px;
                border: none;
                border-bottom: 2px solid transparent;
            }
            QTabBar::tab:selected {
                background: #181825;
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }
            QTabBar::tab:hover:!selected {
                background: #252536;
                color: #a6adc8;
            }
            QTabBar::close-button {
                image: none;
                subcontrol-origin: padding;
                subcontrol-position: right;
            }
        """)
        self.setCentralWidget(self.workspace)
        
        # Initialize Docks
        self._init_docks()
        
        # Initialize Toolbar
        self._init_toolbar()
        
        # Initialize Menubar
        self._init_menubar()
        
        # Initialize Statusbar
        self._init_statusbar()
        
        # Pages cache
        self.pages = {}
        
        # Enable drag-and-drop
        self.setAcceptDrops(True)
        
        # Setup keyboard shortcuts
        self._setup_shortcuts()
        
        # Open Home Tab
        self._open_home_tab()
    
    # =========================================================================
    # DRAG AND DROP
    # =========================================================================
    
    def dragEnterEvent(self, event):
        """Accept file drops."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()
    
    def dropEvent(self, event):
        """Handle dropped files."""
        for url in event.mimeData().urls():
            path = Path(url.toLocalFile())
            self._handle_dropped_file(path)
        event.acceptProposedAction()
    
    def _handle_dropped_file(self, path: Path):
        """Route dropped file to appropriate handler."""
        ext = path.suffix.lower()
        
        if ext in ('.cif', '.xyz', '.xsf', '.poscar'):
            # Structure files -> Structure Viewer
            self._open_structure_with_file(path)
        elif ext in ('.in', '.pw'):
            # Input files -> Input Editor
            self._open_input_with_file(path)
        elif ext in ('.out', '.log'):
            # Output files -> Visualization (SCF plot)
            self._open_visualization_with_file(path, mode='scf')
        elif ext == '.gnu':
            # Band structure -> Visualization (Bands plot)
            self._open_visualization_with_file(path, mode='bands')
        elif ext in ('.dos', '.dat'):
            # DOS files -> Visualization (DOS plot)
            self._open_visualization_with_file(path, mode='dos')
        else:
            self.status_bar.showMessage(f"Unknown file type: {ext}")
    
    def _open_structure_with_file(self, path: Union[str, Path]):
        """Open structure viewer with a file."""
        import pathlib
        if isinstance(path, str):
            path = pathlib.Path(path)
            
        try:
            from .structure_viewer import StructureViewer
            viewer = StructureViewer()
            if hasattr(viewer, 'set_structure'):
                viewer.set_structure(str(path))
            elif hasattr(viewer, 'load_structure'):
                viewer.load_structure(str(path))
            self.workspace.addTab(viewer, f"Structure: {path.name}")
            self.workspace.setCurrentWidget(viewer)
            self.status_bar.showMessage(f"Loaded structure: {path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load structure: {e}")
    
    def _open_input_with_file(self, path: Path):
        """Open input editor with a file."""
        try:
            from .input_editor import InputEditorWidget
            editor = InputEditorWidget()
            if hasattr(editor, 'load_file'):
                editor.load_file(str(path))
            self.workspace.addTab(editor, f"Input: {path.name}")
            self.workspace.setCurrentWidget(editor)
            self.status_bar.showMessage(f"Loaded input: {path.name}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load input: {e}")
    
    def _open_visualization_with_file(self, path: Path, mode: str = 'scf'):
        """Open visualization panel with a file."""
        self._open_visualization(mode=mode)
        panel = self.pages.get("visualization")
        if panel:
            if mode == 'scf' and hasattr(panel.scf_tab, 'load_file'):
                panel.scf_tab.load_file(path)
            elif mode == 'bands' and hasattr(panel.bands_tab, 'load_file'):
                panel.bands_tab.load_file(path)
            elif mode == 'dos' and hasattr(panel.dos_tab, 'load_file'):
                panel.dos_tab.load_file(path)
            self.status_bar.showMessage(f"Loaded plot data: {path.name}")
    
    def _setup_shortcuts(self):
        """Setup comprehensive keyboard shortcuts."""
        # Create shortcuts overlay
        from .shortcuts_overlay import ShortcutsOverlay
        self.shortcuts_overlay = ShortcutsOverlay(self)
        
        # ? to show shortcuts
        help_shortcut = QShortcut(QKeySequence("?"), self)
        help_shortcut.activated.connect(self.shortcuts_overlay.toggle)
        
        # Ctrl+W to close current tab
        close_shortcut = QShortcut(QKeySequence("Ctrl+W"), self)
        close_shortcut.activated.connect(self._close_current_tab)
        
        # Ctrl+Tab to next tab
        next_tab = QShortcut(QKeySequence("Ctrl+Tab"), self)
        next_tab.activated.connect(lambda: self.workspace.setCurrentIndex(
            (self.workspace.currentIndex() + 1) % self.workspace.count()
        ))
        
        # Ctrl+Shift+Tab to previous tab
        prev_tab = QShortcut(QKeySequence("Ctrl+Shift+Tab"), self)
        prev_tab.activated.connect(lambda: self.workspace.setCurrentIndex(
            (self.workspace.currentIndex() - 1) % self.workspace.count()
        ))
        
        # Ctrl+N = New Project
        new_shortcut = QShortcut(QKeySequence("Ctrl+N"), self)
        new_shortcut.activated.connect(self._on_new_project)
        
        # Ctrl+O = Open File
        open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        open_shortcut.activated.connect(self._on_open_project)
        
        # Ctrl+S = Save
        save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        save_shortcut.activated.connect(self._on_save_current)
        
        # Ctrl+R = Run
        run_shortcut = QShortcut(QKeySequence("Ctrl+R"), self)
        run_shortcut.activated.connect(self._on_run_current)
        
        # Ctrl+Shift+S = Screenshot
        screenshot_shortcut = QShortcut(QKeySequence("Ctrl+Shift+S"), self)
        screenshot_shortcut.activated.connect(self._take_screenshot)
        
        # F11 = Toggle Fullscreen
        fullscreen_shortcut = QShortcut(QKeySequence("F11"), self)
        fullscreen_shortcut.activated.connect(self._toggle_fullscreen)
    
    def _toggle_fullscreen(self):
        """Toggle fullscreen mode."""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()
    
    def _close_current_tab(self):
        """Close the currently active tab (except Home)."""
        index = self.workspace.currentIndex()
        if index >= 0 and self.workspace.tabText(index) != "Home":
            self._close_tab(index)
    
    def _init_docks(self):
        """Initialize docking panels."""
        
        # Explorer (Left)
        self.explorer_dock = QDockWidget("Explorer", self)
        self.explorer_dock.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea)
        self.explorer_dock.setFeatures(
            QDockWidget.DockWidgetFeature.DockWidgetMovable | 
            QDockWidget.DockWidgetFeature.DockWidgetFloatable
        )
        
        self.sidebar = Sidebar()
        self.sidebar.on_page_changed = self._on_sidebar_nav
        self.explorer_dock.setWidget(self.sidebar)
        self.explorer_dock.setTitleBarWidget(QWidget())  # Hide title bar
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.explorer_dock)
        
        # Inspector (Right) - Hidden by default
        self.inspector_dock = QDockWidget("Inspector", self)
        self.inspector_dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        self.inspector_dock.hide()
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.inspector_dock)
    
    def _init_toolbar(self):
        """Initialize main toolbar."""
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        toolbar.setStyleSheet("""
            QToolBar {
                background: #1e1e2e;
                border-bottom: 1px solid #313244;
                padding: 4px 8px;
                spacing: 8px;
            }
            QToolButton {
                background: transparent;
                color: #a6adc8;
                padding: 8px 16px;
                border-radius: 6px;
                font-size: 12px;
            }
            QToolButton:hover {
                background: rgba(137, 180, 250, 0.1);
                color: #cdd6f4;
            }
        """)
        self.addToolBar(toolbar)
        
        # Actions with icons
        new_act = QAction("New", self)
        if HAS_ICONS:
            try:
                new_act.setIcon(qta.icon("fa5s.file", color="#a6adc8"))
            except: pass
        new_act.triggered.connect(self._on_new_project)
        toolbar.addAction(new_act)
        
        open_act = QAction("Open", self)
        if HAS_ICONS:
            try:
                open_act.setIcon(qta.icon("fa5s.folder-open", color="#a6adc8"))
            except: pass
        open_act.triggered.connect(self._on_open_project)
        toolbar.addAction(open_act)
        
        toolbar.addSeparator()
        
        save_act = QAction("Save", self)
        if HAS_ICONS:
            try:
                save_act.setIcon(qta.icon("fa5s.save", color="#a6adc8"))
            except: pass
        save_act.triggered.connect(self._on_save_current)
        toolbar.addAction(save_act)
        
        toolbar.addSeparator()
        
        run_act = QAction("Run", self)
        if HAS_ICONS:
            try:
                run_act.setIcon(qta.icon("fa5s.play", color="#10b981"))
            except: pass
        run_act.triggered.connect(self._on_run_current)
        toolbar.addAction(run_act)
        
        toolbar.addSeparator()
        
        screenshot_act = QAction("Screenshot", self)
        screenshot_act.setToolTip("Capture full-quality screenshot (Ctrl+Shift+S)")
        if HAS_ICONS:
            try:
                screenshot_act.setIcon(qta.icon("fa5s.camera", color="#a6adc8"))
            except: pass
        screenshot_act.triggered.connect(self._take_screenshot)
        toolbar.addAction(screenshot_act)
    
    def _init_menubar(self):
        menubar = self.menuBar()
        menubar.setStyleSheet("""
            QMenuBar {
                background: #1e1e2e;
                color: #a6adc8;
                padding: 4px;
            }
            QMenuBar::item {
                padding: 6px 12px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background: rgba(137, 180, 250, 0.1);
                color: #cdd6f4;
            }
            QMenu {
                background: #1e1e2e;
                border: 1px solid #313244;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 24px;
                color: #a6adc8;
            }
            QMenu::item:selected {
                background: rgba(137, 180, 250, 0.1);
                color: #cdd6f4;
            }
        """)
        
        # File Menu
        file_menu = menubar.addMenu("File")
        file_menu.addAction("New Project", self._on_new_project)
        file_menu.addAction("Open Project", self._on_open_project)
        file_menu.addSeparator()
        
        screenshot_act = QAction("Screenshot", self)
        screenshot_act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        screenshot_act.triggered.connect(self._take_screenshot)
        file_menu.addAction(screenshot_act)
        
        file_menu.addSeparator()
        file_menu.addAction("Exit", self.close)
        
        # View Menu
        view_menu = menubar.addMenu("View")
        view_menu.addAction(self.explorer_dock.toggleViewAction())
        view_menu.addAction(self.inspector_dock.toggleViewAction())
        view_menu.addSeparator()
        view_menu.addAction("Take Screenshot", self._take_screenshot)
        
        # Help Menu
        help_menu = menubar.addMenu("Help")
        help_menu.addAction("About FluxDFT", self._on_about)
    
    def _init_statusbar(self):
        self.status_bar = QStatusBar()
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background: #181825;
                color: #6c7086;
                border-top: 1px solid #313244;
                padding: 4px;
            }
        """)
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _on_sidebar_nav(self, key: str):
        """Handle sidebar navigation."""
        handlers = {
            "home": self._open_home_tab,
            "input": self._open_input_tab,
            "structure": self._open_structure_tab,
            "workflows": self._open_workflows_tab,
            "jobs": self._open_jobs_tab,
            "converter": self._open_converter_tab,
            "convergence": self._open_convergence_tab,
            "results": self._open_results_tab,
            "analysis": self._open_analysis_tab,
            "pseudopotentials": self._open_pseudo_tab,
            "materials_project": self._open_mp_tab,
            "reports": self._open_reports_tab,
            "tutorials": self._open_tutorials_tab,
            "settings": self._on_settings,
        }
        
        handler = handlers.get(key)
        if handler:
            handler()
    
    def _open_home_tab(self):
        """Open or focus Home tab."""
        for i in range(self.workspace.count()):
            if self.workspace.tabText(i) == "Home":
                self.workspace.setCurrentIndex(i)
                return
        
        home = HomePage(self)
        home.main_window = self
        self.workspace.addTab(home, "Home")
        self.workspace.setCurrentWidget(home)
        self.pages["home"] = home
    
    def _open_input_tab(self):
        """Open Input Editor."""
        def create():
            try:
                from .input_editor import InputEditorWidget
                return InputEditorWidget()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Input Editor: {e}")
                return None
        self._focus_or_create_tab("input", "Input Editor", create)
    
    def _open_structure_tab(self):
        """Open Structure Viewer."""
        def create():
            try:
                from .structure_viewer import StructureViewer
                sv = StructureViewer()
                
                # Connect to Pseudo Manager if it exists
                if "pseudopotentials" in self.pages:
                    pseudo_panel = self.pages["pseudopotentials"]
                    sv.structure_loaded.connect(pseudo_panel.on_structure_loaded)
                    
                return sv
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Structure Viewer: {e}")
                return None
        self._focus_or_create_tab("structure", "Structure", create)

    def _open_pseudo_tab(self):
        """Open Pseudopotential Manager."""
        def create():
            try:
                from .pseudo_manager_panel import PseudoManagerPanel
                pm = PseudoManagerPanel()
                
                # Check for existing Structure Viewer and connect
                if "structure" in self.pages:
                    sv = self.pages["structure"]
                    # If structure is already loaded, trigger update manually
                    if sv.model:
                        try:
                            elements = [str(e) for e in sv.model.composition.elements]
                            pm.on_structure_loaded(elements)
                        except:
                            pass
                    # Connect for future updates
                    sv.structure_loaded.connect(pm.on_structure_loaded)
                    
                return pm
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Pseudo Manager: {e}")
                return None
        self._focus_or_create_tab("pseudopotentials", "Pseudopotentials", create)
    
    def _open_workflows_tab(self):
        """Open Workflows Tab."""
        def create():
            try:
                from .workflows_page import WorkflowsPage
                return WorkflowsPage(job_runner=self.job_runner)
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Workflows: {e}")
                return None
        self._focus_or_create_tab("workflows", "Workflows", create)
    
    def _focus_or_create_tab(self, key: str, tab_name: str, create_func):
        """Focus existing tab or create new one. Prevents duplicates."""
        # Check if already in pages cache
        if key in self.pages:
            widget = self.pages[key]
            idx = self.workspace.indexOf(widget)
            if idx >= 0:
                self.workspace.setCurrentIndex(idx)
                return widget
        
        # Check by tab name in workspace
        for i in range(self.workspace.count()):
            if self.workspace.tabText(i) == tab_name:
                self.workspace.setCurrentIndex(i)
                return self.workspace.widget(i)
        
        # Create new
        widget = create_func()
        if widget:
            self.workspace.addTab(widget, tab_name)
            self.workspace.setCurrentWidget(widget)
            self.pages[key] = widget
        return widget
    
    def _open_jobs_tab(self):
        """Open Job Manager."""
        def create():
            try:
                from .job_manager import JobManagerPanel
                widget = JobManagerPanel(job_runner=self.job_runner)
                widget.job_completed.connect(self._on_job_completed)
                return widget
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Job Manager: {e}")
                return None
        self._focus_or_create_tab("jobs", "Jobs", create)
    
    def _open_converter_tab(self):
        """Open Converter."""
        def create():
            try:
                from .converter_panel import ConverterPanel
                return ConverterPanel()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Converter: {e}")
                return None
        self._focus_or_create_tab("converter", "Converter", create)
    
    def _open_visualization(self, mode="scf"):
        """Shared method to open Visualization Panel."""
        def create():
            try:
                from .visualization import VisualizationPanel
                return VisualizationPanel()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Visualization: {e}")
                return None
        
        panel = self._focus_or_create_tab("visualization", "Visualization", create)
        
        # Set sub-tab based on mode
        if panel:
            if mode == "scf":
                panel.tabs.setCurrentIndex(0)
            elif mode == "bands":
                panel.tabs.setCurrentIndex(1)
            elif mode == "dos":
                panel.tabs.setCurrentIndex(2)

    def _open_convergence_tab(self):
        """Open Convergence Wizard."""
        def create():
            try:
                from .convergence_panel import ConvergencePanel
                panel = ConvergencePanel()
                panel.apply_recommended_requested.connect(self._apply_convergence_recommendations)
                return panel
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Convergence Wizard: {e}")
                return None
        self._focus_or_create_tab("convergence", "Convergence", create)

    def _apply_convergence_recommendations(self, data: dict):
        """Handle applying converged parameters to the active input editor."""
        try:
            # First, switch to the input editor tab
            self._open_input_tab()
            input_panel = self.pages.get("input")
            
            if input_panel and hasattr(input_panel, 'get_input_text'):
                current_text = input_panel.get_input_text()
                new_text = current_text
                
                # Update each recommended parameter in the text
                for param, value in data.items():
                    if param == "ecutwfc":
                        import re
                        new_text = re.sub(r'(?i)(ecutwfc\s*=\s*)([\d.]+)', f'\\g<1>{value:.2f}', new_text)
                    elif param == "degauss":
                        import re
                        new_text = re.sub(r'(?i)(degauss\s*=\s*)([\d.]+)', f'\\g<1>{value:.4f}', new_text)
                    elif param == "kpoints":
                        import re
                        # Basic replacement for K_POINTS automatic block
                        k_val = int(value)
                        new_text = re.sub(
                            r'(?i)(K_POINTS.*?\n)([\d\s]+)', 
                            f'\\1{k_val} {k_val} {k_val} 0 0 0\n', 
                            new_text, flags=re.DOTALL
                        )
                
                # Set the updated text back
                if hasattr(input_panel, 'set_input_text'):
                    input_panel.set_input_text(new_text)
                self.statusBar().showMessage(f"Applied converged parameters to editor!", 5000)
                
        except Exception as e:
            print(f"Failed to apply recommendations: {e}")

    def _open_results_tab(self):
        """Open Results Dashboard."""
        def create():
            try:
                from .property_dashboard import PropertyDashboard
                return PropertyDashboard()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Results: {e}")
                return None
        self._focus_or_create_tab("results", "Results", create)

    def _open_analysis_tab(self):
        self._open_visualization(mode="bands")
    
    def _open_mp_tab(self):
        """Open Materials Project Comparison."""
        def create():
            try:
                from .mp_comparison_panel import MPComparisonPanel
                panel = MPComparisonPanel()
                panel.load_requested.connect(self._load_mp_structure)
                return panel
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Materials Project: {e}")
                return None
        self._focus_or_create_tab("materials_project", "Materials Project", create)
        
    def _load_mp_structure(self, formula: str, cif_content: str):
        """Handle a structure sent from Materials Project."""
        import tempfile
        from pathlib import Path
        
        try:
            temp_dir = Path(tempfile.gettempdir())
            cif_path = temp_dir / f"{formula}_mp_import.cif"
            
            with open(cif_path, "w", encoding="utf-8") as f:
                f.write(cif_content)
            
            self._open_structure_with_file(str(cif_path))
            self.statusBar().showMessage(f"Loaded {formula} from Materials Project", 5000)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to load structure to project: {e}")
    
    def _open_reports_tab(self):
        """Open Report Generator."""
        def create():
            try:
                from .report_panel import ReportPanel
                return ReportPanel()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to load Report Generator: {e}")
                return None
        self._focus_or_create_tab("reports", "Reports", create)
    
    def _open_tutorials_tab(self):
        """Open Tutorials."""
        def create():
            return TutorialsPage()
        self._focus_or_create_tab("tutorials", "Tutorials", create)
    
    def _close_tab(self, index):
        """Close tab."""
        if self.workspace.tabText(index) != "Home":
            widget = self.workspace.widget(index)
            self.workspace.removeTab(index)
            widget.deleteLater()
    
    def _on_new_project(self):
        self._open_home_tab()
    
    def _on_open_project(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Open Project/Structure", "",
            "All Supported (*.in *.out *.cif *.xyz *.pw *.xsf);;QE Input (*.in);;Structure (*.cif *.xyz)"
        )
        if fname:
            self.status_bar.showMessage(f"Opened: {fname}")
    
    def _on_save_current(self):
        self.status_bar.showMessage("Save function - implementation pending")
    
    def _on_run_current(self):
        self.status_bar.showMessage("Run function - implementation pending")
    
    def _on_settings(self):
        """Open settings dialog."""
        try:
            from .dialogs.settings_dialog import SettingsDialog
            dialog = SettingsDialog(self)
            dialog.exec()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Failed to open Settings: {e}")
    
    def _take_screenshot(self):
        """Capture a full-quality screenshot of the entire application window."""
        # Generate default filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"FluxDFT_screenshot_{timestamp}.png"
        
        # Show save dialog
        filepath, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Save Screenshot",
            default_name,
            "PNG Image (*.png);;JPEG Image (*.jpg *.jpeg);;BMP Image (*.bmp);;All Files (*)"
        )
        
        if not filepath:
            return  # User cancelled
        
        try:
            # Grab the entire window at full device-pixel resolution
            screen = QApplication.primaryScreen()
            if screen is None:
                QMessageBox.warning(self, "Screenshot Error", "No screen available.")
                return
            
            # Use grab() on the window for full quality including all widgets
            pixmap = screen.grabWindow(int(self.winId()))
            
            # Determine format from extension
            ext = Path(filepath).suffix.lower()
            fmt_map = {'.png': 'PNG', '.jpg': 'JPEG', '.jpeg': 'JPEG', '.bmp': 'BMP'}
            fmt = fmt_map.get(ext, 'PNG')
            
            # Save with maximum quality
            quality = 100 if fmt == 'JPEG' else -1  # -1 = default (lossless for PNG)
            success = pixmap.save(filepath, fmt, quality)
            
            if success:
                self.status_bar.showMessage(f"Screenshot saved: {filepath}", 5000)
            else:
                QMessageBox.warning(self, "Screenshot Error", f"Failed to save screenshot to:\n{filepath}")
                
        except Exception as e:
            QMessageBox.warning(self, "Screenshot Error", f"Screenshot failed:\n{e}")
    
    def _on_about(self):
        QMessageBox.about(
            self,
            "About FluxDFT",
            f"""<h3>{APP_NAME} v{APP_VERSION}</h3>
            <p>{APP_COPYRIGHT}</p>
            <p>Professional DFT Interface powered by Quantum ESPRESSO.</p>
            <p><b>Features:</b></p>
            <ul>
                <li>Visual input file generation</li>
                <li>Structure visualization with PyVista</li>
                <li>Job management and monitoring</li>
                <li>Publication-quality plotting</li>
                <li>HPC cluster integration</li>
            </ul>
            """
        )

    def _on_job_completed(self, job):
        """Handle automated result processing when a job finishes."""
        self.status_bar.showMessage(f"Processing results for job: {job.name}...")
        
        # 1. Update Visualization Panel
        try:
            # Open and focus SCF tab
            self._open_visualization(mode="scf")
            
            panel = self.pages.get("visualization")
            if panel and hasattr(panel, 'process_job_results'):
                panel.process_job_results(job.output_file)
                
        except Exception as e:
            print(f"Auto-viz error: {e}")

        # 2. Update Results Dashboard
        try:
            # Ensure panel is open
            if "results" not in self.pages:
                self._open_results_tab()
            
            res_panel = self.pages.get("results")
            if res_panel:
                # Need to parse results first using parser
                from ..core.output_parser import OutputParser
                parser = OutputParser()
                try:
                    # Basic SCF parsing
                    pw_out = parser.parse_pw_output(job.output_file)
                    # Convert PWOutput to dict for dashboard (simplified)
                    res_dict = {
                        'total_energy': pw_out.final_energy,
                        # 'fermi_energy': pw_out.fermi_energy, # if available
                    }
                    res_panel.set_results(res_dict)
                except:
                    pass
        except Exception as e:
            print(f"Auto-results error: {e}")
            
        self.status_bar.showMessage(f"Results processed for {job.name}")
