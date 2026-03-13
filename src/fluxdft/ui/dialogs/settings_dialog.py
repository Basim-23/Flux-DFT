"""
Settings dialog for FluxDFT.
"""

from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QTabWidget, QWidget,
    QFormLayout, QSpinBox, QCheckBox, QComboBox,
    QFileDialog, QGroupBox, QListWidget, QListWidgetItem,
    QMessageBox,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ...utils.constants import APP_NAME
from ...utils.config import Config, RemoteServer


class SettingsDialog(QDialog):
    """Application settings dialog."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.config = Config()
        
        self.setWindowTitle(f"{APP_NAME} - Settings")
        self.setMinimumSize(600, 500)
        self.setModal(True)
        
        self._create_ui()
        self._load_settings()
    
    def _create_ui(self):
        """Create the dialog UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Tabs
        tabs = QTabWidget()
        
        # General tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        # Paths tab
        paths_tab = self._create_paths_tab()
        tabs.addTab(paths_tab, "Paths")
        
        # Remote Servers tab
        servers_tab = self._create_servers_tab()
        tabs.addTab(servers_tab, "Remote Servers")
        
        # Defaults tab
        defaults_tab = self._create_defaults_tab()
        tabs.addTab(defaults_tab, "Calculation Defaults")
        
        # Materials Project tab
        mp_tab = self._create_mp_tab()
        tabs.addTab(mp_tab, "Materials Project")
        
        # Auto-Graphing tab
        graphing_tab = self._create_graphing_tab()
        tabs.addTab(graphing_tab, "Auto-Graphing")
        
        # AI Assistant tab
        ai_tab = self._create_ai_tab()
        tabs.addTab(ai_tab, "Assistant (AI)")
        
        layout.addWidget(tabs)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)
        
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(apply_btn)
        
        ok_btn = QPushButton("OK")
        ok_btn.setObjectName("primary")
        ok_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(ok_btn)
        
        layout.addLayout(btn_layout)
    
    def _create_general_tab(self) -> QWidget:
        """Create the general settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        # Theme
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        layout.addRow("Theme:", self.theme_combo)
        
        # Font size
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 24)
        layout.addRow("Font Size:", self.font_spin)
        
        # Tooltips
        self.tooltips_check = QCheckBox("Show tooltips")
        layout.addRow("", self.tooltips_check)
        
        # Welcome screen
        self.welcome_check = QCheckBox("Show welcome screen on startup")
        layout.addRow("", self.welcome_check)
        
        return widget
    
    def _create_paths_tab(self) -> QWidget:
        """Create the paths settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # QE path
        qe_group = QGroupBox("Quantum ESPRESSO")
        qe_layout = QHBoxLayout(qe_group)
        
        self.qe_path_edit = QLineEdit()
        qe_layout.addWidget(self.qe_path_edit)
        
        qe_browse = QPushButton("Browse...")
        qe_browse.clicked.connect(self._browse_qe_path)
        qe_layout.addWidget(qe_browse)
        
        layout.addWidget(qe_group)
        
        # Pseudo path
        pseudo_group = QGroupBox("Pseudopotentials")
        pseudo_layout = QHBoxLayout(pseudo_group)
        
        self.pseudo_path_edit = QLineEdit()
        pseudo_layout.addWidget(self.pseudo_path_edit)
        
        pseudo_browse = QPushButton("Browse...")
        pseudo_browse.clicked.connect(self._browse_pseudo_path)
        pseudo_layout.addWidget(pseudo_browse)
        
        layout.addWidget(pseudo_group)
        
        # Work directory
        work_group = QGroupBox("Projects Directory")
        work_layout = QHBoxLayout(work_group)
        
        self.work_path_edit = QLineEdit()
        work_layout.addWidget(self.work_path_edit)
        
        work_browse = QPushButton("Browse...")
        work_browse.clicked.connect(self._browse_work_path)
        work_layout.addWidget(work_browse)
        
        layout.addWidget(work_group)
        
        layout.addStretch()
        
        return widget
    
    def _create_servers_tab(self) -> QWidget:
        """Create the remote servers tab."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # Server list
        list_layout = QVBoxLayout()
        
        self.server_list = QListWidget()
        list_layout.addWidget(self.server_list)
        
        btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add")
        add_btn.clicked.connect(self._add_server)
        btn_layout.addWidget(add_btn)
        
        remove_btn = QPushButton("Remove")
        remove_btn.clicked.connect(self._remove_server)
        btn_layout.addWidget(remove_btn)
        
        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout)
        
        # Server details (placeholder)
        details = QLabel("Select a server to edit its settings")
        details.setAlignment(Qt.AlignmentFlag.AlignCenter)
        details.setStyleSheet("color: #6c7086;")
        layout.addWidget(details)
        
        return widget
    
    def _create_defaults_tab(self) -> QWidget:
        """Create the calculation defaults tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        # ecutwfc
        self.ecutwfc_spin = QSpinBox()
        self.ecutwfc_spin.setRange(10, 200)
        self.ecutwfc_spin.setSuffix(" Ry")
        layout.addRow("Wavefunction Cutoff:", self.ecutwfc_spin)
        
        # ecutrho
        self.ecutrho_spin = QSpinBox()
        self.ecutrho_spin.setRange(40, 1600)
        self.ecutrho_spin.setSuffix(" Ry")
        layout.addRow("Density Cutoff:", self.ecutrho_spin)
        
        # K-points
        kpt_layout = QHBoxLayout()
        self.kpt1_spin = QSpinBox()
        self.kpt1_spin.setRange(1, 24)
        kpt_layout.addWidget(self.kpt1_spin)
        
        self.kpt2_spin = QSpinBox()
        self.kpt2_spin.setRange(1, 24)
        kpt_layout.addWidget(self.kpt2_spin)
        
        self.kpt3_spin = QSpinBox()
        self.kpt3_spin.setRange(1, 24)
        kpt_layout.addWidget(self.kpt3_spin)
        
        kpt_widget = QWidget()
        kpt_widget.setLayout(kpt_layout)
        layout.addRow("Default K-points:", kpt_widget)
        
        return widget
    
    def _create_mp_tab(self) -> QWidget:
        """Create the Materials Project settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        # Info label
        info = QLabel(
            "Materials Project provides reference data for validation.\n"
            "Get your API key at: materialsproject.org"
        )
        info.setStyleSheet("color: #6c7086; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # API Key group
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout(api_group)
        
        self.mp_api_key_edit = QLineEdit()
        self.mp_api_key_edit.setPlaceholderText("Enter your Materials Project API key")
        self.mp_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        api_layout.addRow("API Key:", self.mp_api_key_edit)
        
        # Show/hide key button
        show_key_btn = QPushButton("Show Key")
        show_key_btn.setCheckable(True)
        show_key_btn.toggled.connect(
            lambda checked: self.mp_api_key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )
        api_layout.addRow("", show_key_btn)
        
        self.mp_enabled_check = QCheckBox("Enable Materials Project integration")
        api_layout.addRow("", self.mp_enabled_check)
        
        layout.addWidget(api_group)
        
        # Test connection button
        test_btn = QPushButton("Test Connection")
        test_btn.clicked.connect(self._test_mp_connection)
        layout.addWidget(test_btn)
        
        layout.addStretch()
        
        return widget
    
    def _create_graphing_tab(self) -> QWidget:
        """Create the auto-graphing settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)
        layout.setSpacing(15)
        
        self.auto_plot_check = QCheckBox("Automatically generate plots after job completion")
        layout.addRow("", self.auto_plot_check)
        
        self.auto_navigate_check = QCheckBox("Navigate to plots when ready")
        layout.addRow("", self.auto_navigate_check)
        
        self.plot_format_combo = QComboBox()
        self.plot_format_combo.addItems(["png", "pdf", "svg"])
        layout.addRow("Plot Format:", self.plot_format_combo)
        
        self.plot_dpi_spin = QSpinBox()
        self.plot_dpi_spin.setRange(72, 600)
        self.plot_dpi_spin.setSuffix(" dpi")
        layout.addRow("Resolution:", self.plot_dpi_spin)
        
        return widget
    
    def _create_ai_tab(self) -> QWidget:
        """Create the AI Assistant settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        
        info = QLabel(
            "FluxDFT AI Assistant uses OpenAI compatible APIs.\n"
            "The assistant can explain physics, analyze errors, and draft reports."
        )
        info.setStyleSheet("color: #6c7086; margin-bottom: 10px;")
        layout.addWidget(info)
        
        # Config Group
        group = QGroupBox("Configuration")
        form = QFormLayout(group)
        
        self.ai_enabled_check = QCheckBox("Enable AI Assistant")
        form.addRow("", self.ai_enabled_check)
        
        self.ai_key_edit = QLineEdit()
        self.ai_key_edit.setPlaceholderText("sk-...")
        self.ai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("API Key:", self.ai_key_edit)
        
        self.ai_model_combo = QComboBox()
        self.ai_model_combo.addItems(["gpt-4o", "gpt-4-turbo", "gpt-3.5-turbo"])
        form.addRow("Model:", self.ai_model_combo)
        
        layout.addWidget(group)
        
        # Validation
        self.ai_test_label = QLabel("")
        
        test_btn = QPushButton("Test AI Connection")
        test_btn.clicked.connect(self._test_ai_connection)
        
        layout.addWidget(test_btn)
        layout.addWidget(self.ai_test_label)
        
        layout.addStretch()
        return widget
    
    def _test_ai_connection(self):
        """Test AI Assistant connection."""
        api_key = self.ai_key_edit.text()
        model = self.ai_model_combo.currentText()
        
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please enter your OpenAI API key first.")
            return
            
        try:
            from ...ai.core import FluxAIClient
            # Create temp client
            client = FluxAIClient(api_key=api_key, model=model)
            
            self.ai_test_label.setText("Testing connection...")
            self.ai_test_label.repaint()
            
            # Simple ping
            response = client.query("You are a connection tester.", "Reply with 'OK'.")
            
            if "OK" in response or "ok" in response.lower():
                self.ai_test_label.setText("[OK] Connection Successful!")
                self.ai_test_label.setStyleSheet("color: #10b981")
                QMessageBox.information(self, "Success", f"Connected to OpenAI ({model})")
            else:
                 self.ai_test_label.setText(f"[WARN] Response: {response}")
                 self.ai_test_label.setStyleSheet("color: #f59e0b")
        except Exception as e:
            self.ai_test_label.setText("[ERROR] Connection Failed")
            self.ai_test_label.setStyleSheet("color: #ef4444")
            QMessageBox.critical(self, "Error", f"AI Connection error: {e}")

    def _load_settings(self):
        """Load current settings into the UI."""
        cfg = self.config.config
        
        # General
        self.theme_combo.setCurrentText(cfg.theme.capitalize())
        self.font_spin.setValue(cfg.font_size)
        self.tooltips_check.setChecked(cfg.show_tooltips)
        self.welcome_check.setChecked(cfg.show_welcome)
        
        # Paths
        self.qe_path_edit.setText(cfg.qe_path)
        self.pseudo_path_edit.setText(cfg.pseudo_dir)
        self.work_path_edit.setText(cfg.work_dir)
        
        # Defaults
        self.ecutwfc_spin.setValue(int(cfg.default_ecutwfc))
        self.ecutrho_spin.setValue(int(cfg.default_ecutrho))
        
        kpts = cfg.default_kpoints
        if len(kpts) >= 3:
            self.kpt1_spin.setValue(kpts[0])
            self.kpt2_spin.setValue(kpts[1])
            self.kpt3_spin.setValue(kpts[2])
        
        # Materials Project
        self.mp_api_key_edit.setText(cfg.mp_api_key)
        self.mp_enabled_check.setChecked(cfg.mp_enabled)
        
        # Auto-graphing
        self.auto_plot_check.setChecked(cfg.auto_generate_plots)
        self.auto_navigate_check.setChecked(cfg.auto_navigate_to_plots)
        self.plot_format_combo.setCurrentText(cfg.plot_format)
        self.plot_dpi_spin.setValue(cfg.plot_dpi)
        
        # Servers
        for server in self.config.get_remote_servers():
            self.server_list.addItem(server.name)

        # AI Assistant
        self.ai_enabled_check.setChecked(cfg.ai_enabled)
        self.ai_key_edit.setText(cfg.openai_api_key)
        self.ai_model_combo.setCurrentText(cfg.ai_model)
    
    def _apply_settings(self):
        """Apply settings without closing."""
        cfg = self.config.config
        
        # General
        cfg.theme = self.theme_combo.currentText().lower()
        cfg.font_size = self.font_spin.value()
        cfg.show_tooltips = self.tooltips_check.isChecked()
        cfg.show_welcome = self.welcome_check.isChecked()
        
        # Paths
        cfg.qe_path = self.qe_path_edit.text()
        cfg.pseudo_dir = self.pseudo_path_edit.text()
        cfg.work_dir = self.work_path_edit.text()
        
        # Defaults
        cfg.default_ecutwfc = float(self.ecutwfc_spin.value())
        cfg.default_ecutrho = float(self.ecutrho_spin.value())
        cfg.default_kpoints = [
            self.kpt1_spin.value(),
            self.kpt2_spin.value(),
            self.kpt3_spin.value(),
        ]
        
        # Materials Project
        cfg.mp_api_key = self.mp_api_key_edit.text()
        cfg.mp_enabled = self.mp_enabled_check.isChecked()
        
        # Auto-graphing
        cfg.auto_generate_plots = self.auto_plot_check.isChecked()
        cfg.auto_navigate_to_plots = self.auto_navigate_check.isChecked()
        cfg.plot_format = self.plot_format_combo.currentText()
        cfg.plot_dpi = self.plot_dpi_spin.value()
        
        # AI Assistant
        cfg.ai_enabled = self.ai_enabled_check.isChecked()
        cfg.openai_api_key = self.ai_key_edit.text()
        cfg.ai_model = self.ai_model_combo.currentText()
        
        self.config.save()
        
        # Apply theme and font to running app
        self._apply_ui_settings()
        
    def _apply_ui_settings(self):
        """Apply theme and font immediately to the running application."""
        from PyQt6.QtWidgets import QApplication
        
        app = QApplication.instance()
        if not app:
            return
            
        cfg = self.config.config
        
        # Apply font size
        font = app.font()
        font.setPointSize(cfg.font_size)
        app.setFont(font)
        
        # Reload the scientific theme stylesheet
        try:
            from pathlib import Path as _Path
            theme_path = _Path(__file__).resolve().parent.parent / "styles" / "scientific.qss"
            if theme_path.exists():
                with open(theme_path, "r") as f:
                    app.setStyleSheet(f.read())
        except Exception:
            pass  # Keep current stylesheet if reload fails
    
    def _save_and_close(self):
        """Save settings and close dialog."""
        self._apply_settings()
        self.accept()
    
    def _browse_qe_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select QE Directory")
        if path:
            self.qe_path_edit.setText(path)
    
    def _browse_pseudo_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Pseudopotential Directory")
        if path:
            self.pseudo_path_edit.setText(path)
    
    def _browse_work_path(self):
        path = QFileDialog.getExistingDirectory(self, "Select Projects Directory")
        if path:
            self.work_path_edit.setText(path)
    
    def _add_server(self):
        # TODO: Implement server add dialog
        QMessageBox.information(self, "Info", "Server configuration coming soon")
    
    def _remove_server(self):
        item = self.server_list.currentItem()
        if item:
            self.config.remove_remote_server(item.text())
            self.server_list.takeItem(self.server_list.row(item))
    
    def _test_mp_connection(self):
        """Test Materials Project API connection."""
        api_key = self.mp_api_key_edit.text()
        if not api_key:
            QMessageBox.warning(self, "No API Key", "Please enter your API key first.")
            return
        
        try:
            from ...materials_project import MaterialsProjectClient
            client = MaterialsProjectClient(api_key)
            
            if client.test_connection():
                # Quick test query
                results = client.find_by_formula("Si")
                if results:
                    QMessageBox.information(
                        self,
                        "Connection Successful",
                        f"[OK] Connected to Materials Project\n"
                        f"[OK] Found {len(results)} materials for Si\n"
                        f"[OK] Ground state: {results[0].mp_id}"
                    )
                else:
                    QMessageBox.information(self, "Connected", "Connected but no results")
            else:
                QMessageBox.warning(self, "Connection Failed", "Could not connect to MP API")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Connection error: {e}")
