"""
Project Explorer for FluxDFT.

BURAI-style file tree panel showing project structure.
"""

from pathlib import Path
from typing import Optional, List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QTreeWidget, QTreeWidgetItem, QFileDialog,
    QMenu, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QAction

# Try to import qtawesome for icons
try:
    import qtawesome as qta
    HAS_ICONS = True
except ImportError:
    HAS_ICONS = False


class ProjectExplorer(QWidget):
    """File tree explorer for DFT projects."""
    
    file_selected = pyqtSignal(str)  # Emitted when file is double-clicked
    structure_loaded = pyqtSignal(str)  # Emitted when structure file is selected
    
    # File type labels (text-based, no emojis)
    FILE_LABELS = {
        '.in': '[IN]',
        '.inp': '[IN]', 
        '.pwi': '[IN]',
        '.out': '[OUT]',
        '.log': '[LOG]',
        '.cif': '[CIF]',
        '.xyz': '[XYZ]',
        '.vasp': '[VASP]',
        '.pdb': '[PDB]',
        '.png': '[IMG]',
        '.pdf': '[PDF]',
        '.dat': '[DAT]',
    }
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.project_dir: Optional[Path] = None
        
        self._create_ui()
    
    def _create_ui(self):
        """Create the explorer UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)
        
        # Header
        header = QLabel("EXPLORER")
        header.setStyleSheet("color: #45475a; font-size: 10px; font-weight: 600; letter-spacing: 2px;")
        layout.addWidget(header)
        
        # Tabs (BURAI-style)
        from PyQt6.QtWidgets import QTabWidget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #313244;
                background: #11111b;
            }
            QTabBar::tab {
                background: #1e1e2e;
                color: #6c7086;
                padding: 8px 12px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
                font-size: 11px;
            }
            QTabBar::tab:selected {
                background: #181825;
                color: #cdd6f4;
                border-bottom: 2px solid #89b4fa;
            }
        """)
        
        # 1. Computer Tab
        self.computer_tab = QWidget()
        self._setup_computer_tab()
        self.tabs.addTab(self.computer_tab, "Files")
        
        # 2. Projects Tab
        self.projects_tab = QWidget()
        self._setup_projects_tab()
        self.tabs.addTab(self.projects_tab, "Projects")
        
        # 3. Recent Tab
        self.recent_tab = QWidget()
        layout_recent = QVBoxLayout(self.recent_tab)
        recent_label = QLabel("Recent files will appear here")
        recent_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout_recent.addWidget(recent_label)
        layout_recent.addStretch()
        self.tabs.addTab(self.recent_tab, "Recent")
        
        # 4. Calculating Tab
        self.calc_tab = QWidget()
        layout_calc = QVBoxLayout(self.calc_tab)
        calc_label = QLabel("Active jobs will appear here")
        calc_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout_calc.addWidget(calc_label)
        layout_calc.addStretch()
        self.tabs.addTab(self.calc_tab, "Jobs")
        
        layout.addWidget(self.tabs)
        
        # Info label
        self.info_label = QLabel("No folder opened")
        self.info_label.setStyleSheet("color: #45475a; font-size: 10px;")
        layout.addWidget(self.info_label)

    def _setup_computer_tab(self):
        """Setup the Computer tab (System File Browser)."""
        layout = QVBoxLayout(self.computer_tab)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Toolbar
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)
        
        open_btn = QPushButton("Open")
        open_btn.clicked.connect(self._open_folder)
        open_btn.setStyleSheet("""
            QPushButton {
                background: #313244;
                border: none;
                border-radius: 4px;
                padding: 6px 12px;
                color: #a6adc8;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #45475a;
                color: #cdd6f4;
            }
        """)
        toolbar.addWidget(open_btn)
        
        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh)
        refresh_btn.setStyleSheet(open_btn.styleSheet())
        toolbar.addWidget(refresh_btn)
        
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        
        # Tree widget
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setStyleSheet("""
            QTreeWidget {
                background: #11111b;
                border: none;
                color: #a6adc8;
            }
            QTreeWidget::item {
                padding: 4px 2px;
            }
            QTreeWidget::item:selected {
                background: rgba(137, 180, 250, 0.2);
                color: #cdd6f4;
            }
            QTreeWidget::item:hover {
                background: rgba(137, 180, 250, 0.1);
            }
            QTreeWidget::branch {
                background: transparent;
            }
        """)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

    def _setup_projects_tab(self):
        """Setup Projects tab."""
        layout = QVBoxLayout(self.projects_tab)
        label = QLabel("Saved projects will appear here")
        label.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(label)
        layout.addStretch()

    def _open_folder(self):
        """Open a project folder."""
        folder = QFileDialog.getExistingDirectory(self, "Open Project Folder")
        if folder:
            self.set_project_dir(folder)
    
    def set_project_dir(self, path: str):
        """Set the project directory and populate tree."""
        self.project_dir = Path(path)
        self._populate_tree()
        self.info_label.setText(f"{self.project_dir.name}")
        self.info_label.setStyleSheet("color: #89b4fa; font-size: 10px;")
    
    def _populate_tree(self):
        """Populate the tree with project files."""
        self.tree.clear()
        
        if not self.project_dir or not self.project_dir.exists():
            return
        
        # Add root item
        root = QTreeWidgetItem(self.tree, [self.project_dir.name])
        root.setData(0, Qt.ItemDataRole.UserRole, str(self.project_dir))
        root.setExpanded(True)
        
        # Categorize files
        categories = {
            "Input Files": ['.in', '.inp', '.pwi'],
            "Output Files": ['.out', '.log'],
            "Structures": ['.cif', '.xyz', '.vasp', '.pdb', '.POSCAR'],
            "Data": ['.dat', '.xml'],
            "Images": ['.png', '.pdf', '.ps'],
        }
        
        # Scan directory
        all_files = list(self.project_dir.iterdir())
        
        for cat_name, extensions in categories.items():
            cat_files = [f for f in all_files if f.is_file() and f.suffix.lower() in extensions]
            
            if cat_files:
                cat_item = QTreeWidgetItem(root, [cat_name])
                cat_item.setExpanded(True)
                
                for file in sorted(cat_files):
                    label = self.FILE_LABELS.get(file.suffix.lower(), '[FILE]')
                    item = QTreeWidgetItem(cat_item, [f"{label} {file.name}"])
                    item.setData(0, Qt.ItemDataRole.UserRole, str(file))
        
        # Add subdirectories
        subdirs = [d for d in all_files if d.is_dir() and not d.name.startswith('.')]
        for subdir in sorted(subdirs):
            self._add_directory(root, subdir)
    
    def _add_directory(self, parent: QTreeWidgetItem, path: Path, depth: int = 0):
        """Recursively add directory to tree."""
        if depth > 3:  # Limit recursion
            return
        
        dir_item = QTreeWidgetItem(parent, [path.name])
        dir_item.setData(0, Qt.ItemDataRole.UserRole, str(path))
        
        try:
            for child in sorted(path.iterdir()):
                if child.is_file():
                    label = self.FILE_LABELS.get(child.suffix.lower(), '[FILE]')
                    item = QTreeWidgetItem(dir_item, [f"{label} {child.name}"])
                    item.setData(0, Qt.ItemDataRole.UserRole, str(child))
                elif child.is_dir() and not child.name.startswith('.'):
                    self._add_directory(dir_item, child, depth + 1)
        except PermissionError:
            pass
    
    def _refresh(self):
        """Refresh the tree."""
        if self.project_dir:
            self._populate_tree()
    
    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double-click on item."""
        filepath = item.data(0, Qt.ItemDataRole.UserRole)
        if filepath:
            path = Path(filepath)
            if path.is_file():
                self.file_selected.emit(filepath)
                
                # Check if it's a structure file
                if path.suffix.lower() in ['.cif', '.xyz', '.vasp', '.pdb']:
                    self.structure_loaded.emit(filepath)
    
    def _show_context_menu(self, position):
        """Show context menu for tree items."""
        item = self.tree.itemAt(position)
        if not item:
            return
        
        filepath = item.data(0, Qt.ItemDataRole.UserRole)
        if not filepath:
            return
        
        path = Path(filepath)
        
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background: #1e1e2e;
                border: 1px solid #313244;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item {
                padding: 8px 20px;
                color: #a6adc8;
            }
            QMenu::item:selected {
                background: rgba(137, 180, 250, 0.2);
                color: #cdd6f4;
            }
        """)
        
        if path.is_file():
            open_action = menu.addAction("Open")
            open_action.triggered.connect(lambda: self.file_selected.emit(filepath))
            
            if path.suffix.lower() in ['.cif', '.xyz', '.vasp', '.pdb']:
                load_action = menu.addAction("Load in Viewer")
                load_action.triggered.connect(lambda: self.structure_loaded.emit(filepath))
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete")
            delete_action.triggered.connect(lambda: self._delete_file(path))
        
        elif path.is_dir():
            refresh_action = menu.addAction("Refresh")
            refresh_action.triggered.connect(self._refresh)
        
        menu.exec(self.tree.viewport().mapToGlobal(position))
    
    def _delete_file(self, path: Path):
        """Delete a file with confirmation."""
        result = QMessageBox.question(
            self,
            "Delete File",
            f"Are you sure you want to delete:\n{path.name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if result == QMessageBox.StandardButton.Yes:
            try:
                path.unlink()
                self._refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete:\n{e}")
