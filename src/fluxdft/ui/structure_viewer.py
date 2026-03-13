"""
Professional Structure Viewer for FluxDFT.
High-fidelity 3D visualization with supercell creation and export.
Copyright (c) 2024 FluxDFT. All rights reserved.
"""

import logging
from typing import Optional, Tuple
import numpy as np
from dataclasses import dataclass
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QFileDialog, QComboBox, QCheckBox, 
    QSpinBox, QDoubleSpinBox, QGroupBox, QFormLayout, 
    QMessageBox, QFrame, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor
    pv.set_plot_theme("document")
    HAS_PYVISTA = True
except ImportError:
    HAS_PYVISTA = False

try:
    from pymatgen.core import Structure, Element
    from pymatgen.analysis.local_env import CrystalNN
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False

from ..core.structure_model import StructureModel
from .theme import theme_manager

logger = logging.getLogger(__name__)

# Jmol Colors for elements
JMOL_COLORS = {
    1: (1.0, 1.0, 1.0),      # H
    6: (0.565, 0.565, 0.565), # C
    7: (0.188, 0.314, 0.973), # N
    8: (1.0, 0.051, 0.051),   # O
    9: (0.565, 0.878, 0.314), # F
    11: (0.671, 0.361, 0.949), # Na
    12: (0.541, 1.0, 0.0),    # Mg
    13: (0.749, 0.651, 0.651), # Al
    14: (0.941, 0.784, 0.627), # Si
    15: (1.0, 0.502, 0.0),    # P
    16: (1.0, 1.0, 0.188),    # S
    17: (0.122, 0.941, 0.122), # Cl
    20: (0.239, 1.0, 0.0),    # Ca
    22: (0.749, 0.761, 0.78),  # Ti
    26: (0.878, 0.4, 0.2),    # Fe
    27: (0.941, 0.565, 0.627), # Co
    28: (0.314, 0.816, 0.314), # Ni
    29: (0.784, 0.502, 0.2),  # Cu
    30: (0.49, 0.502, 0.69),  # Zn
    64: (0.1, 0.9, 0.9),    # Gd - MP Cyan
}

def get_element_color(z: int) -> Tuple[float, float, float]:
    """Get RGB color for atomic number z."""
    if z in JMOL_COLORS:
        return JMOL_COLORS[z]
    
    import colorsys
    import random
    random.seed(z)
    hue = random.random()
    return colorsys.hls_to_rgb(hue, 0.6, 0.8)


@dataclass
class ViewSettings:
    """Visualization settings."""
    atom_scale: float = 0.35
    bond_radius: float = 0.06
    show_bonds: bool = True
    show_cell: bool = True
    show_axes: bool = True
    background: str = "#0d0d12"
    use_pbr: bool = False


class SupercellDialog(QDialog):
    """Dialog for creating supercells with custom dimensions."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Supercell")
        self.setModal(True)
        self.setMinimumWidth(300)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        
        # Title
        title = QLabel("Supercell Dimensions")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #cdd6f4;")
        layout.addWidget(title)
        
        # Dimension inputs
        form = QFormLayout()
        form.setSpacing(12)
        
        self.spin_a = QSpinBox()
        self.spin_a.setRange(1, 10)
        self.spin_a.setValue(2)
        form.addRow("a (x):", self.spin_a)
        
        self.spin_b = QSpinBox()
        self.spin_b.setRange(1, 10)
        self.spin_b.setValue(2)
        form.addRow("b (y):", self.spin_b)
        
        self.spin_c = QSpinBox()
        self.spin_c.setRange(1, 10)
        self.spin_c.setValue(2)
        form.addRow("c (z):", self.spin_c)
        
        layout.addLayout(form)
        
        # Info label
        self.info_label = QLabel("Total atoms: calculating...")
        self.info_label.setStyleSheet("color: #6c7086; font-size: 11px;")
        layout.addWidget(self.info_label)
        
        # Connect changes
        self.spin_a.valueChanged.connect(self._update_info)
        self.spin_b.valueChanged.connect(self._update_info)
        self.spin_c.valueChanged.connect(self._update_info)
        
        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | 
            QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        self.base_atoms = 1
    
    def set_base_atoms(self, n: int):
        """Set number of atoms in base structure."""
        self.base_atoms = n
        self._update_info()
    
    def _update_info(self):
        """Update atom count preview."""
        mult = self.spin_a.value() * self.spin_b.value() * self.spin_c.value()
        total = self.base_atoms * mult
        self.info_label.setText(f"Total atoms: {total} ({self.base_atoms} × {mult})")
    
    def get_dimensions(self) -> Tuple[int, int, int]:
        """Get the selected supercell dimensions."""
        return (self.spin_a.value(), self.spin_b.value(), self.spin_c.value())


class StructureViewer(QWidget):
    """Professional 3D structure viewer with supercell and export support."""
    
    structure_loaded = pyqtSignal(object)  # Emits list of unique elements
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.model: Optional[StructureModel] = None
        self.settings = ViewSettings()
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        if HAS_PYVISTA:
            # 3D Viewer
            self.plotter = QtInteractor()
            self.plotter.set_background(self.settings.background)
            layout.addWidget(self.plotter.interactor, stretch=4)
            
            # Show welcome message
            self.plotter.add_text(
                "Load a structure file to begin",
                position='upper_left',
                font_size=12,
                color='white'
            )
        else:
            # Fallback
            fallback = QLabel("PyVista not installed.\nInstall with: pip install pyvista pyvistaqt")
            fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fallback.setStyleSheet("color: #f38ba8; font-size: 14px;")
            layout.addWidget(fallback, stretch=4)
            self.plotter = None
        
        # Control Panel
        panel = self._create_control_panel()
        layout.addWidget(panel, stretch=1)
    
    def _create_control_panel(self) -> QWidget:
        """Create the right-side control panel using QScrollArea for robust layout."""
        from PyQt6.QtWidgets import QScrollArea, QSlider
        
        # Create scrollable container
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(320)
        scroll.setMaximumWidth(420)
        scroll.setStyleSheet("""
            QScrollArea {
                background: #181825;
                border: none;
                border-left: 1px solid #313244;
            }
            QScrollArea > QWidget > QWidget {
                background: #181825;
            }
        """)
        
        # Content widget
        content = QWidget()
        content.setStyleSheet("background: #181825;")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)
        
        # === HEADER ===
        header = QLabel("STRUCTURE")
        header.setStyleSheet("color: #6c7086; font-size: 11px; font-weight: bold; letter-spacing: 2px;")
        header.setFixedHeight(20)
        layout.addWidget(header)
        
        # === FILE SECTION ===
        self._add_section_label(layout, "File")
        
        btn_open = QPushButton("  Open File...")
        btn_open.setIcon(theme_manager.get_icon("fa5s.folder-open", "#ffffff"))
        btn_open.setFixedHeight(44)
        btn_open.setStyleSheet(self._get_button_css("#3b82f6"))
        btn_open.clicked.connect(self._load_file)
        layout.addWidget(btn_open)
        
        btn_save = QPushButton("  Save As...")
        btn_save.setIcon(theme_manager.get_icon("fa5s.save", "#ffffff"))
        btn_save.setFixedHeight(44)
        btn_save.setStyleSheet(self._get_button_css("#10b981"))
        btn_save.clicked.connect(self._save_file)
        layout.addWidget(btn_save)
        
        # Structure info
        self.info_label = QLabel("No structure loaded")
        self.info_label.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self.info_label.setWordWrap(True)
        self.info_label.setMinimumHeight(80)
        layout.addWidget(self.info_label)
        
        # === SUPERCELL SECTION ===
        self._add_section_label(layout, "Supercell")
        
        # Row of quick supercell buttons
        sc_row = QHBoxLayout()
        sc_row.setSpacing(10)
        for n in [2, 3, 4]:
            btn = QPushButton(f"{n}×{n}×{n}")
            btn.setFixedHeight(38)
            btn.setStyleSheet(self._get_button_css("#8b5cf6"))
            btn.clicked.connect(lambda checked, x=n: self._make_supercell(x, x, x))
            sc_row.addWidget(btn)
        layout.addLayout(sc_row)
        
        btn_custom = QPushButton("Custom Supercell...")
        btn_custom.setFixedHeight(38)
        btn_custom.setStyleSheet(self._get_button_css("#a855f7"))
        btn_custom.clicked.connect(self._show_supercell_dialog)
        layout.addWidget(btn_custom)
        
        # === DISPLAY SECTION ===
        self._add_section_label(layout, "Display Options")
        
        # Create simple checkboxes with fixed heights
        self.chk_bonds = QCheckBox("  Show Bonds")
        self.chk_bonds.setChecked(True)
        self.chk_bonds.setFixedHeight(32)
        self.chk_bonds.toggled.connect(self._on_display_change)
        layout.addWidget(self.chk_bonds)
        
        self.chk_cell = QCheckBox("  Show Unit Cell")
        self.chk_cell.setChecked(True)
        self.chk_cell.setFixedHeight(32)
        self.chk_cell.toggled.connect(self._on_display_change)
        layout.addWidget(self.chk_cell)
        
        self.chk_axes = QCheckBox("  Show Axes")
        self.chk_axes.setChecked(True)
        self.chk_axes.setFixedHeight(32)
        self.chk_axes.toggled.connect(self._on_display_change)
        layout.addWidget(self.chk_axes)
        
        # Atom size with slider
        size_label = QLabel("Atom Size")
        size_label.setStyleSheet("color: #a6adc8; font-size: 12px; margin-top: 8px;")
        layout.addWidget(size_label)
        
        size_row = QHBoxLayout()
        size_row.setSpacing(16)
        
        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(10, 200)
        self.size_slider.setValue(35)
        self.size_slider.setFixedHeight(24)
        self.size_slider.valueChanged.connect(self._on_size_slider_change)
        size_row.addWidget(self.size_slider)
        
        self.size_value_label = QLabel("0.35")
        self.size_value_label.setStyleSheet("color: #cdd6f4; font-size: 12px; min-width: 40px;")
        size_row.addWidget(self.size_value_label)
        
        layout.addLayout(size_row)
        
        # === CAMERA SECTION ===
        self._add_section_label(layout, "Camera")
        
        cam_row = QHBoxLayout()
        cam_row.setSpacing(10)
        
        for name, action in [("Reset", self._reset_camera), 
                              ("XY", lambda: self._set_view("xy")),
                              ("XZ", lambda: self._set_view("xz")),
                              ("YZ", lambda: self._set_view("yz"))]:
            btn = QPushButton(name)
            btn.setFixedHeight(36)
            btn.setStyleSheet(self._get_button_css("#6c7086"))
            btn.clicked.connect(action)
            cam_row.addWidget(btn)
        
        layout.addLayout(cam_row)
        
        # Spacer at bottom
        layout.addStretch()
        
        scroll.setWidget(content)
        return scroll
    
    def _add_section_label(self, layout: QVBoxLayout, text: str):
        """Add a section header label."""
        label = QLabel(text)
        label.setStyleSheet("color: #cdd6f4; font-size: 14px; font-weight: bold; margin-top: 12px;")
        label.setFixedHeight(28)
        layout.addWidget(label)
    
    def _get_button_css(self, color: str) -> str:
        """Get simple button CSS that won't conflict with global styles."""
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 8px;
                font-size: 13px;
                font-weight: 600;
                padding: 8px 16px;
            }}
            QPushButton:hover {{
                background-color: {color}cc;
            }}
            QPushButton:pressed {{
                background-color: {color}99;
            }}
        """
    
    def _on_size_slider_change(self, value: int):
        """Handle atom size slider change."""
        size = value / 100.0
        self.size_value_label.setText(f"{size:.2f}")
        self.settings.atom_scale = size
        if self.model:
            self._render()
    
    def _load_file(self):
        """Open file dialog and load structure."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open Structure File",
            "",
            "All Structure Files (*.cif *.poscar *.vasp *.xyz *.xsf *.json);;"
            "CIF Files (*.cif);;POSCAR (*.poscar *.vasp);;XYZ (*.xyz);;All (*)"
        )
        if filepath:
            self.set_structure(filepath)
    
    def _save_file(self):
        """Save structure to file."""
        if not self.model or not self.model.structure:
            QMessageBox.warning(self, "No Structure", "Load a structure first.")
            return
        
        filepath, filter_used = QFileDialog.getSaveFileName(
            self,
            "Save Structure",
            "",
            "CIF File (*.cif);;POSCAR (*.poscar);;XYZ (*.xyz);;All (*)"
        )
        
        if not filepath:
            return
        
        try:
            structure = self.model.structure
            
            if filepath.endswith('.cif'):
                from pymatgen.io.cif import CifWriter
                writer = CifWriter(structure)
                writer.write_file(filepath)
            elif filepath.endswith('.poscar') or filepath.endswith('.vasp'):
                from pymatgen.io.vasp import Poscar
                poscar = Poscar(structure)
                poscar.write_file(filepath)
            elif filepath.endswith('.xyz'):
                from pymatgen.io.xyz import XYZ
                xyz = XYZ(structure)
                xyz.write_file(filepath)
            else:
                # Default to CIF
                from pymatgen.io.cif import CifWriter
                writer = CifWriter(structure)
                writer.write_file(filepath)
            
            QMessageBox.information(self, "Saved", f"Structure saved to:\n{filepath}")
            
        except Exception as e:
            logger.error(f"Save failed: {e}")
            QMessageBox.critical(self, "Save Error", f"Failed to save file:\n{e}")
    
    def set_structure(self, source):
        """Load and display a structure."""
        try:
            if isinstance(source, str) or isinstance(source, Path):
                self.model = StructureModel.from_file(str(source))
            elif isinstance(source, StructureModel):
                self.model = source
            else:
                self.model = StructureModel(source)
            
            self._update_info()
            self._render()
            
            # Emit unique elements for Smart Manager
            try:
                unique_elements = [str(e) for e in self.model.composition.elements]
                self.structure_loaded.emit(unique_elements)
            except Exception as e:
                logger.warning(f"Failed to emit elements: {e}")
            
        except Exception as e:
            logger.error(f"Failed to load structure: {e}")
            QMessageBox.warning(self, "Load Error", f"Failed to load structure:\n{e}")
    
    def _update_info(self):
        """Update structure info label."""
        if not self.model or not self.model.structure:
            self.info_label.setText("No structure loaded")
            return
        
        s = self.model.structure
        formula = s.composition.reduced_formula
        n_atoms = len(s)
        
        a, b, c = s.lattice.abc
        alpha, beta, gamma = s.lattice.angles
        
        self.info_label.setText(
            f"<b>{formula}</b><br>"
            f"Atoms: {n_atoms}<br>"
            f"a={a:.3f} b={b:.3f} c={c:.3f}<br>"
            f"α={alpha:.1f}° β={beta:.1f}° γ={gamma:.1f}°"
        )
    
    def _show_supercell_dialog(self):
        """Show custom supercell dialog."""
        if not self.model:
            QMessageBox.warning(self, "No Structure", "Load a structure first.")
            return
        
        dialog = SupercellDialog(self)
        dialog.set_base_atoms(len(self.model.structure))
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            a, b, c = dialog.get_dimensions()
            self._make_supercell(a, b, c)
    
    def _make_supercell(self, a: int, b: int, c: int):
        """Create supercell with given dimensions."""
        if not self.model:
            QMessageBox.warning(self, "No Structure", "Load a structure first.")
            return
        
        try:
            # Calculate expected atoms
            expected = len(self.model.structure) * a * b * c
            
            # Warn for large supercells
            if expected > 500:
                reply = QMessageBox.question(
                    self,
                    "Large Supercell",
                    f"This will create {expected} atoms.\nRendering may be slow. Continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            # Make supercell
            self.model.make_supercell([a, b, c])
            self._update_info()
            self._render()
            
        except Exception as e:
            logger.error(f"Supercell failed: {e}")
            QMessageBox.warning(self, "Error", f"Failed to create supercell:\n{e}")
    
    def _on_display_change(self):
        """Handle display setting changes."""
        self.settings.show_bonds = self.chk_bonds.isChecked()
        self.settings.show_cell = self.chk_cell.isChecked()
        self.settings.show_axes = self.chk_axes.isChecked()
        self.settings.atom_scale = self.size_slider.value() / 100.0
        
        if self.model:
            self._render()
    
    def _render(self):
        """Render the current structure."""
        if not self.plotter or not self.model or not self.model.structure:
            return
        
        try:
            self.plotter.clear()
            structure = self.model.structure
            
            # Set background
            self.plotter.set_background(self.settings.background)
            
            # Enable quality settings
            if self.settings.use_pbr:
                try:
                    self.plotter.enable_eye_dome_lighting()
                except:
                    pass
            else:
                self.plotter.disable_eye_dome_lighting()
                self.plotter.enable_lightkit()
            
            atoms_to_draw = {}
            
            # Draw boundary replicas like MP does for cells
            for site in structure:
                fcoords = site.frac_coords
                offsets_list = []
                for f in fcoords:
                    f_mod = f % 1.0
                    if abs(f_mod) < 1e-3:
                        offsets_list.append([0, 1])
                    else:
                        offsets_list.append([0])
                
                import itertools
                for shift in itertools.product(*offsets_list):
                    shifted_fcoords = fcoords + np.array(shift)
                    coords = structure.lattice.get_cartesian_coords(shifted_fcoords)
                    key = tuple(np.round(coords, 4))
                    if key not in atoms_to_draw:
                        atoms_to_draw[key] = (coords, site.specie)
            
            bonds_to_draw = []
            if self.settings.show_bonds and HAS_PYMATGEN:
                try:
                    cnn = CrystalNN()
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore")
                        graph = cnn.get_bonded_structure(structure)
                    
                    valid_bond_lengths = []
                    
                    # Pass 1: Add first-shell neighbors and collect bond lengths
                    for u, v, data in graph.graph.edges(data=True):
                        jimage = tuple(data.get("to_jimage", (0, 0, 0)))
                        pos_u = structure[u].coords
                        pos_v = structure[v].coords + np.dot(jimage, structure.lattice.matrix)
                        
                        dist = np.linalg.norm(pos_u - pos_v)
                        valid_bond_lengths.append(dist)
                        
                        if 0.5 < dist < 4.5:
                            key_v = tuple(np.round(pos_v, 4))
                            if key_v not in atoms_to_draw:
                                atoms_to_draw[key_v] = (pos_v, structure[v].specie)
                                
                    # Pass 2: Draw bonds between ANY atoms_to_draw if they match a known bond length
                    import itertools
                    for (k1, (p1, s1)), (k2, (p2, s2)) in itertools.combinations(atoms_to_draw.items(), 2):
                        dist = np.linalg.norm(p1 - p2)
                        # Check if distance matches any bond from the graph (within a small tolerance)
                        if any(abs(dist - vd) < 0.15 for vd in valid_bond_lengths):
                            bonds_to_draw.append((p1, p2, s1, s2))
                            
                except Exception as e:
                    logger.debug(f"Bond drawing failed: {e}")

            # Group atoms by atomic number for instanced rendering (super fast)
            atoms_by_z = {}
            for coords, specie in atoms_to_draw.values():
                z = specie.number
                if z not in atoms_by_z:
                    try:
                        radius = float(specie.atomic_radius or 0.8)
                    except:
                        radius = 0.8
                    radius *= self.settings.atom_scale
                    atoms_by_z[z] = {
                        'coords': [],
                        'radius': radius,
                        'metallic': 0.2 if specie.is_metal else 0.1
                    }
                atoms_by_z[z]['coords'].append(coords)
            
            # Draw atoms using glyphs (instancing) for high performance
            for z, data in atoms_by_z.items():
                points = np.array(data['coords'])
                poly = pv.PolyData(points)
                sphere = pv.Sphere(radius=data['radius'], theta_resolution=24, phi_resolution=24)
                glyphs = poly.glyph(geom=sphere, scale=False, orient=False)
                
                rgb = get_element_color(z)
                self.plotter.add_mesh(
                    glyphs,
                    color=rgb,
                    smooth_shading=True,
                    pbr=self.settings.use_pbr,
                    metallic=data['metallic'],
                    roughness=0.4,
                    specular=0.5
                )

            # Draw bonds highly optimized using line segments
            if bonds_to_draw:
                line_points = []
                # Simple color array handling for lines
                for pos_u, pos_v, spec_u, spec_v in bonds_to_draw:
                    # Draw midpoints so colors can split
                    midpoint = (pos_u + pos_v) / 2.0
                    
                    # Store lines as [2, p1_idx, p2_idx]
                    color_u = get_element_color(spec_u.number)
                    color_v = get_element_color(spec_v.number)
                    
                    # We will just draw them as separate tubes to keep coloring accurate, 
                    # but group them by color for batched rendering
                    line_points.append((pos_u, midpoint, color_u))
                    line_points.append((midpoint, pos_v, color_v))
                
                # Group bond segments by color
                bonds_by_color = {}
                for p1, p2, color in line_points:
                    ckey = tuple(np.round(color, 3))
                    if ckey not in bonds_by_color:
                        bonds_by_color[ckey] = []
                    bonds_by_color[ckey].append((p1, p2))
                
                for ckey, lines in bonds_by_color.items():
                    # Combine all line segments of the same color into a single PolyData for maximum speed
                    lines_poly = []
                    for p1, p2 in lines:
                        l = pv.Line(p1, p2).tube(radius=self.settings.bond_radius, n_sides=10)
                        lines_poly.append(l)
                        
                    # Merge all PolyData of the same color
                    if lines_poly:
                        combined = lines_poly[0].merge(lines_poly[1:]) if len(lines_poly) > 1 else lines_poly[0]
                        self.plotter.add_mesh(
                            combined, 
                            color=ckey, 
                            smooth_shading=True, 
                            pbr=self.settings.use_pbr
                        )
            
            # Draw unit cell
            if self.settings.show_cell:
                self._draw_cell(structure)
            
            # Draw axes
            if self.settings.show_axes:
                self.plotter.add_axes()
            
            self.plotter.reset_camera()
            
        except Exception as e:
            logger.error(f"Render failed: {e}")
    
    def _draw_bonds(self, structure):
        """Legacy bond draw method (logic moved to _render)."""
        pass
    
    def _draw_cell(self, structure):
        """Draw unit cell box."""
        matrix = structure.lattice.matrix
        origin = np.zeros(3)
        
        corners = [
            origin,
            matrix[0],
            matrix[1],
            matrix[2],
            matrix[0] + matrix[1],
            matrix[0] + matrix[2],
            matrix[1] + matrix[2],
            matrix[0] + matrix[1] + matrix[2]
        ]
        
        edges = [
            (0, 1), (0, 2), (0, 3),
            (1, 4), (1, 5),
            (2, 4), (2, 6),
            (3, 5), (3, 6),
            (4, 7), (5, 7), (6, 7)
        ]
        
        for i, j in edges:
            line = pv.Line(corners[i], corners[j])
            self.plotter.add_mesh(line, color="#45475a", line_width=1)
    
    def _reset_camera(self):
        """Reset camera to default view."""
        if self.plotter:
            self.plotter.reset_camera()
            self.plotter.render()
    
    def _set_view(self, plane: str):
        """Set camera to view along a plane."""
        if not self.plotter:
            return
        
        if plane == "xy":
            self.plotter.view_xy()
        elif plane == "xz":
            self.plotter.view_xz()
        elif plane == "yz":
            self.plotter.view_yz()
        
        self.plotter.render()
