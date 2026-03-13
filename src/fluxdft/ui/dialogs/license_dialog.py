"""
License activation dialog for FluxDFT.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QFrame, QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...utils.constants import APP_NAME
from ...utils.config import Config


class LicenseDialog(QDialog):
    """License activation dialog."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config = Config()
        
        self.setWindowTitle(f"{APP_NAME} - License Activation")
        self.setFixedSize(500, 350)
        self.setModal(True)
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # Header
        header = QLabel("Activate Your License")
        header.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        header.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(header)
        
        # Instructions
        instructions = QLabel(
            "Enter your license key to activate FluxDFT.\n"
            "If you don't have a license, visit fluxdft.com to purchase one."
        )
        instructions.setFont(QFont("Segoe UI", 11))
        instructions.setStyleSheet("color: #a6adc8;")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)
        
        # Email input
        email_label = QLabel("Email Address:")
        email_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(email_label)
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("your.email@university.edu")
        self.email_input.setText(self.config.get("license_email", ""))
        layout.addWidget(self.email_input)
        
        # License key input
        key_label = QLabel("License Key:")
        key_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(key_label)
        
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXX-XXXX-XXXX-XXXX")
        self.key_input.setText(self.config.get("license_key", ""))
        layout.addWidget(self.key_input)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        buy_btn = QPushButton("🛒 Purchase License")
        buy_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #89b4fa;
                border: 1px solid #89b4fa;
                border-radius: 6px;
                padding: 10px 20px;
            }
            QPushButton:hover {
                background-color: #89b4fa;
                color: #1e1e2e;
            }
        """)
        btn_layout.addWidget(buy_btn)
        
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        activate_btn = QPushButton("Activate")
        activate_btn.setObjectName("primary")
        activate_btn.clicked.connect(self._activate)
        btn_layout.addWidget(activate_btn)
        
        layout.addLayout(btn_layout)
    
    def _activate(self):
        """Validate and save the license."""
        email = self.email_input.text().strip()
        key = self.key_input.text().strip()
        
        if not email:
            QMessageBox.warning(self, "Error", "Please enter your email address.")
            return
        
        if not key:
            QMessageBox.warning(self, "Error", "Please enter your license key.")
            return
        
        # TODO: Implement actual license validation
        # For now, accept any non-empty key
        if len(key) >= 10:
            self.config.set("license_email", email)
            self.config.set("license_key", key)
            
            QMessageBox.information(
                self, 
                "Success", 
                "License activated successfully!\n\n"
                "Thank you for purchasing FluxDFT."
            )
            self.accept()
        else:
            QMessageBox.warning(
                self, 
                "Invalid License", 
                "The license key you entered is invalid.\n\n"
                "Please check your key and try again."
            )
