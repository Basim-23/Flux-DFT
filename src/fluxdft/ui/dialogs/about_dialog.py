"""
Professional About Dialog for FluxDFT.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap, QPainter, QColor, QLinearGradient

from ...utils.constants import APP_NAME, APP_VERSION, APP_COPYRIGHT, APP_WEBSITE


class AboutDialog(QDialog):
    """Professional about dialog for FluxDFT."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(500, 400)
        self.setModal(True)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header with gradient
        header = QFrame()
        header.setFixedHeight(150)
        header.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #1e1e2e, stop:0.5 #181825, stop:1 #11111b);
            }
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Product name
        name_label = QLabel(APP_NAME)
        name_label.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        name_label.setStyleSheet("color: #cdd6f4;")
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(name_label)
        
        # Tagline
        tagline = QLabel("Professional GUI for Quantum ESPRESSO")
        tagline.setFont(QFont("Segoe UI", 12))
        tagline.setStyleSheet("color: #a6adc8;")
        tagline.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header_layout.addWidget(tagline)
        
        layout.addWidget(header)
        
        # Content area
        content = QFrame()
        content.setStyleSheet("background-color: #1e1e2e;")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(30, 20, 30, 20)
        content_layout.setSpacing(12)
        
        # Version
        version = QLabel(f"Version {APP_VERSION}")
        version.setFont(QFont("Segoe UI", 11))
        version.setStyleSheet("color: #89b4fa;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(version)
        
        # Description
        description = QLabel(
            "FluxDFT provides an intuitive interface for performing\n"
            "density functional theory calculations with Quantum ESPRESSO.\n\n"
            "Designed for researchers, professors, and students in\n"
            "computational materials science and physics."
        )
        description.setFont(QFont("Segoe UI", 10))
        description.setStyleSheet("color: #cdd6f4;")
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(description)
        
        content_layout.addStretch()
        
        # Links
        links_layout = QHBoxLayout()
        
        website_btn = QPushButton("Website")
        website_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #89b4fa;
                border: none;
                padding: 8px;
            }
            QPushButton:hover {
                color: #b4befe;
            }
        """)
        links_layout.addWidget(website_btn)
        
        docs_btn = QPushButton("Documentation")
        docs_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #89b4fa;
                border: none;
                padding: 8px;
            }
            QPushButton:hover {
                color: #b4befe;
            }
        """)
        links_layout.addWidget(docs_btn)
        
        support_btn = QPushButton("Support")
        support_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #89b4fa;
                border: none;
                padding: 8px;
            }
            QPushButton:hover {
                color: #b4befe;
            }
        """)
        links_layout.addWidget(support_btn)
        
        content_layout.addLayout(links_layout)
        
        # Copyright
        copyright_label = QLabel(APP_COPYRIGHT)
        copyright_label.setFont(QFont("Segoe UI", 9))
        copyright_label.setStyleSheet("color: #6c7086;")
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        content_layout.addWidget(copyright_label)
        
        layout.addWidget(content)
        
        # Close button
        btn_layout = QHBoxLayout()
        btn_layout.setContentsMargins(20, 10, 20, 20)
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.setMinimumWidth(100)
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        content_layout.addLayout(btn_layout)
