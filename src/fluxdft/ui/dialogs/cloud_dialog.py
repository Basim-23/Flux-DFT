"""
Cloud Integration Dialogs.
Login, Signup, and Configuration.
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QMessageBox, QTabWidget,
    QWidget, QFormLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...utils.config import Config
from ...cloud.client import SupabaseManager
from ..theme import theme_manager

class CloudDialog(QDialog):
    """
    Main Cloud Interaction Dialog.
    Tabs: Login, Sign Up, Settings (Connection).
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("FluxDFT Cloud")
        self.setFixedWidth(400)
        
        self.config = Config()
        self.client = SupabaseManager(
            self.config.supabase_url,
            self.config.supabase_key
        )
        
        self._create_ui()
        
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Header
        title = QLabel("FluxDFT Cloud")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        layout.addWidget(title)
        
        # Tabs
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        
        # Tab 1: Login
        self.login_tab = QWidget()
        self._setup_login_tab(self.login_tab)
        # Only show login/signup if configured
        if self.config.supabase_url:
            self.tabs.addTab(self.login_tab, "Login")
        
        # Tab 2: Settings
        self.settings_tab = QWidget()
        self._setup_settings_tab(self.settings_tab)
        self.tabs.addTab(self.settings_tab, "Connection")
        
        # Set default tab
        if not self.config.supabase_url:
            self.tabs.setCurrentIndex(0) # Settings
        
    def _setup_login_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        
        form = QFormLayout()
        
        self.email_input = QLineEdit()
        self.email_input.setPlaceholderText("user@example.com")
        form.addRow("Email:", self.email_input)
        
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self.pass_input)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        login_btn = QPushButton("Log In")
        login_btn.setObjectName("primary")
        login_btn.clicked.connect(self._on_login)
        btn_layout.addWidget(login_btn)
        
        signup_btn = QPushButton("Sign Up")
        signup_btn.clicked.connect(self._on_signup)
        btn_layout.addWidget(signup_btn)
        
        layout.addLayout(btn_layout)
        layout.addStretch()
        
    def _setup_settings_tab(self, parent):
        layout = QVBoxLayout(parent)
        layout.setContentsMargins(16, 16, 16, 16)
        
        info = QLabel("Configure your Supabase Project.")
        layout.addWidget(info)
        
        form = QFormLayout()
        
        self.url_input = QLineEdit(self.config.supabase_url)
        self.url_input.setPlaceholderText("https://xyz.supabase.co")
        form.addRow("Project URL:", self.url_input)
        
        self.key_input = QLineEdit(self.config.supabase_key)
        self.key_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Anon Key:", self.key_input)
        
        layout.addLayout(form)
        
        save_btn = QPushButton("Save Connection")
        save_btn.clicked.connect(self._on_save_config)
        layout.addWidget(save_btn)
        layout.addStretch()
        
    def _on_save_config(self):
        """Save Supabase credentials."""
        url = self.url_input.text().strip()
        key = self.key_input.text().strip()
        
        self.config.supabase_url = url
        self.config.supabase_key = key
        self.config.save()
        
        # Refresh client
        self.client = SupabaseManager(url, key)
        
        QMessageBox.information(self, "Saved", "Cloud configuration saved.\nPlease restart to apply changes fully.")
        self.accept()
        
    def _on_login(self):
        """Handle Login."""
        email = self.email_input.text()
        password = self.pass_input.text()
        
        if not email or not password:
            QMessageBox.warning(self, "Input Error", "Please enter email and password.")
            return
            
        try:
            user = self.client.login(email, password)
            QMessageBox.information(self, "Success", f"Logged in as: {user.email}")
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Login Failed", str(e))

    def _on_signup(self):
        """Handle Sign Up."""
        email = self.email_input.text()
        password = self.pass_input.text()
        
        try:
            user = self.client.sign_up(email, password)
            QMessageBox.information(
                self, "Success", 
                "Account created!\nPlease check your email to verify your account."
            )
        except Exception as e:
            QMessageBox.critical(self, "Sign Up Failed", str(e))
