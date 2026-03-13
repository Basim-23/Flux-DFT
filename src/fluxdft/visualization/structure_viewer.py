"""
Crystal Structure Viewer for FluxDFT.

3D visualization of crystal structures with PyVista.
Inspired by Crystal Toolkit's scene graph approach.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class AtomStyle(Enum):
    """Atom rendering styles."""
    SPHERE = "sphere"
    BALL_AND_STICK = "ball_and_stick"
    STICK = "stick"
    VDW = "vdw"  # Van der Waals radii


class ColorScheme(Enum):
    """Color schemes for atoms."""
    JMOL = "jmol"
    VESTA = "vesta"
    CPK = "cpk"
    CUSTOM = "custom"


# JMOL color scheme
JMOL_COLORS = {
    'H': (1.000, 1.000, 1.000),
    'He': (0.851, 1.000, 1.000),
    'Li': (0.800, 0.502, 1.000),
    'Be': (0.761, 1.000, 0.000),
    'B': (1.000, 0.710, 0.710),
    'C': (0.565, 0.565, 0.565),
    'N': (0.188, 0.314, 0.973),
    'O': (1.000, 0.051, 0.051),
    'F': (0.565, 0.878, 0.314),
    'Ne': (0.702, 0.890, 0.961),
    'Na': (0.671, 0.361, 0.949),
    'Mg': (0.541, 1.000, 0.000),
    'Al': (0.749, 0.651, 0.651),
    'Si': (0.941, 0.784, 0.627),
    'P': (1.000, 0.502, 0.000),
    'S': (1.000, 1.000, 0.188),
    'Cl': (0.122, 0.941, 0.122),
    'Ar': (0.502, 0.820, 0.890),
    'K': (0.561, 0.251, 0.831),
    'Ca': (0.239, 1.000, 0.000),
    'Sc': (0.902, 0.902, 0.902),
    'Ti': (0.749, 0.761, 0.780),
    'V': (0.651, 0.651, 0.671),
    'Cr': (0.541, 0.600, 0.780),
    'Mn': (0.612, 0.478, 0.780),
    'Fe': (0.878, 0.400, 0.200),
    'Co': (0.941, 0.565, 0.627),
    'Ni': (0.314, 0.816, 0.314),
    'Cu': (0.784, 0.502, 0.200),
    'Zn': (0.490, 0.502, 0.690),
    'Ga': (0.761, 0.561, 0.561),
    'Ge': (0.400, 0.561, 0.561),
    'As': (0.741, 0.502, 0.890),
    'Se': (1.000, 0.631, 0.000),
    'Br': (0.651, 0.161, 0.161),
    'Kr': (0.361, 0.722, 0.820),
    'Rb': (0.439, 0.180, 0.690),
    'Sr': (0.000, 1.000, 0.000),
    'Y': (0.580, 1.000, 1.000),
    'Zr': (0.580, 0.878, 0.878),
    'Mo': (0.329, 0.710, 0.710),
    'Ag': (0.753, 0.753, 0.753),
    'I': (0.580, 0.000, 0.580),
    'Ba': (0.000, 0.788, 0.000),
    'La': (0.439, 0.831, 1.000),
    'Au': (1.000, 0.820, 0.137),
    'Pb': (0.341, 0.349, 0.380),
}

# Covalent radii (Å)
COVALENT_RADII = {
    'H': 0.31, 'He': 0.28, 'Li': 1.28, 'Be': 0.96, 'B': 0.84, 'C': 0.76,
    'N': 0.71, 'O': 0.66, 'F': 0.57, 'Ne': 0.58, 'Na': 1.66, 'Mg': 1.41,
    'Al': 1.21, 'Si': 1.11, 'P': 1.07, 'S': 1.05, 'Cl': 1.02, 'Ar': 1.06,
    'K': 2.03, 'Ca': 1.76, 'Sc': 1.70, 'Ti': 1.60, 'V': 1.53, 'Cr': 1.39,
    'Mn': 1.39, 'Fe': 1.32, 'Co': 1.26, 'Ni': 1.24, 'Cu': 1.32, 'Zn': 1.22,
    'Ga': 1.22, 'Ge': 1.20, 'As': 1.19, 'Se': 1.20, 'Br': 1.20, 'Kr': 1.16,
    'Mo': 1.54, 'Ag': 1.45, 'Au': 1.36, 'Pb': 1.46,
}


@dataclass
class AtomRenderInfo:
    """Rendering information for an atom."""
    position: np.ndarray
    species: str
    radius: float
    color: Tuple[float, float, float]
    label: Optional[str] = None
    is_visible: bool = True


@dataclass
class BondRenderInfo:
    """Rendering information for a bond."""
    start: np.ndarray
    end: np.ndarray
    start_species: str
    end_species: str
    radius: float = 0.1
    is_visible: bool = True


@dataclass
class StructureScene:
    """
    Scene graph for structure visualization.
    
    Contains all rendering primitives for the structure.
    """
    atoms: List[AtomRenderInfo] = field(default_factory=list)
    bonds: List[BondRenderInfo] = field(default_factory=list)
    unit_cell_lines: List[Tuple[np.ndarray, np.ndarray]] = field(default_factory=list)
    
    # View settings
    show_unit_cell: bool = True
    show_bonds: bool = True
    show_labels: bool = False
    background_color: str = "#1a1a2e"
    
    @classmethod
    def from_structure(
        cls,
        structure: 'Structure',
        style: AtomStyle = AtomStyle.BALL_AND_STICK,
        color_scheme: ColorScheme = ColorScheme.JMOL,
        supercell: Tuple[int, int, int] = (1, 1, 1),
        bond_cutoff: float = 2.5,
    ) -> 'StructureScene':
        """
        Create scene from pymatgen Structure.
        
        Args:
            structure: pymatgen Structure
            style: Rendering style
            color_scheme: Color scheme
            supercell: Supercell dimensions
            bond_cutoff: Bond length cutoff (Å)
            
        Returns:
            StructureScene
        """
        scene = cls()
        
        # Apply supercell if requested
        if supercell != (1, 1, 1):
            structure = structure * supercell
        
        # Generate atoms
        for i, site in enumerate(structure):
            species = str(site.specie)
            
            # Get radius
            if style == AtomStyle.VDW:
                radius = COVALENT_RADII.get(species, 1.0) * 1.5
            elif style == AtomStyle.BALL_AND_STICK:
                radius = COVALENT_RADII.get(species, 1.0) * 0.4
            elif style == AtomStyle.STICK:
                radius = 0.1
            else:
                radius = COVALENT_RADII.get(species, 1.0) * 0.8
            
            # Get color
            color = JMOL_COLORS.get(species, (0.5, 0.5, 0.5))
            
            atom = AtomRenderInfo(
                position=site.coords.copy(),
                species=species,
                radius=radius,
                color=color,
                label=f"{species}{i+1}",
            )
            scene.atoms.append(atom)
        
        # Generate bonds
        if style in [AtomStyle.BALL_AND_STICK, AtomStyle.STICK]:
            scene._generate_bonds(structure, bond_cutoff)
        
        # Generate unit cell
        scene._generate_unit_cell(structure.lattice.matrix)
        
        return scene
    
    def _generate_bonds(self, structure: 'Structure', cutoff: float):
        """Generate bonds between atoms."""
        for i, site1 in enumerate(structure):
            for j, site2 in enumerate(structure):
                if i >= j:
                    continue
                
                dist = site1.distance(site2)
                
                # Check if within bonding distance
                r1 = COVALENT_RADII.get(str(site1.specie), 1.0)
                r2 = COVALENT_RADII.get(str(site2.specie), 1.0)
                
                if dist < (r1 + r2) * 1.3 and dist < cutoff:
                    bond = BondRenderInfo(
                        start=site1.coords.copy(),
                        end=site2.coords.copy(),
                        start_species=str(site1.specie),
                        end_species=str(site2.specie),
                    )
                    self.bonds.append(bond)
    
    def _generate_unit_cell(self, lattice_matrix: np.ndarray):
        """Generate unit cell box lines."""
        a, b, c = lattice_matrix
        origin = np.zeros(3)
        
        # Define the 12 edges of the unit cell
        edges = [
            (origin, a),
            (origin, b),
            (origin, c),
            (a, a + b),
            (a, a + c),
            (b, a + b),
            (b, b + c),
            (c, a + c),
            (c, b + c),
            (a + b, a + b + c),
            (a + c, a + b + c),
            (b + c, a + b + c),
        ]
        
        self.unit_cell_lines = edges


class StructureViewer:
    """
    3D Crystal Structure Viewer using PyVista.
    
    Features:
        - Multiple rendering styles (ball-stick, VDW, etc.)
        - Color schemes (JMOL, VESTA, CPK)
        - Unit cell visualization
        - Bond estimation
        - Supercell generation
        - Interactive rotation/zoom
        - Export to image/video
    
    Usage:
        >>> viewer = StructureViewer(structure)
        >>> viewer.show()
        >>> viewer.save("structure.png")
    """
    
    def __init__(
        self,
        structure: Optional['Structure'] = None,
        style: AtomStyle = AtomStyle.BALL_AND_STICK,
        color_scheme: ColorScheme = ColorScheme.JMOL,
        background_color: str = "#1a1a2e",
    ):
        """
        Initialize viewer.
        
        Args:
            structure: pymatgen Structure (optional, can set later)
            style: Rendering style
            color_scheme: Color scheme
            background_color: Background color
        """
        self.structure = structure
        self.style = style
        self.color_scheme = color_scheme
        self.background_color = background_color
        
        self.scene: Optional[StructureScene] = None
        self.plotter = None
        
        if structure is not None:
            self.set_structure(structure)
    
    def set_structure(
        self,
        structure: 'Structure',
        supercell: Tuple[int, int, int] = (1, 1, 1),
    ):
        """
        Set structure to visualize.
        
        Args:
            structure: pymatgen Structure
            supercell: Supercell dimensions
        """
        self.structure = structure
        self.scene = StructureScene.from_structure(
            structure,
            style=self.style,
            color_scheme=self.color_scheme,
            supercell=supercell,
        )
    
    def _create_plotter(self):
        """Create PyVista plotter."""
        try:
            import pyvista as pv
            
            self.plotter = pv.Plotter()
            self.plotter.set_background(self.background_color)
            
        except ImportError:
            raise ImportError("pyvista required for 3D visualization")
    
    def _add_atoms(self):
        """Add atoms to plotter."""
        import pyvista as pv
        
        for atom in self.scene.atoms:
            if not atom.is_visible:
                continue
            
            sphere = pv.Sphere(radius=atom.radius, center=atom.position)
            self.plotter.add_mesh(
                sphere,
                color=atom.color,
                smooth_shading=True,
                pbr=True,
                metallic=0.2,
                roughness=0.3,
            )
    
    def _add_bonds(self):
        """Add bonds to plotter."""
        import pyvista as pv
        
        for bond in self.scene.bonds:
            if not bond.is_visible:
                continue
            
            # Mid-point for two-color bond
            mid = (bond.start + bond.end) / 2
            
            # First half
            cyl1 = pv.Cylinder(
                center=(bond.start + mid) / 2,
                direction=mid - bond.start,
                radius=bond.radius,
                height=np.linalg.norm(mid - bond.start),
            )
            color1 = JMOL_COLORS.get(bond.start_species, (0.5, 0.5, 0.5))
            self.plotter.add_mesh(cyl1, color=color1, smooth_shading=True)
            
            # Second half
            cyl2 = pv.Cylinder(
                center=(mid + bond.end) / 2,
                direction=bond.end - mid,
                radius=bond.radius,
                height=np.linalg.norm(bond.end - mid),
            )
            color2 = JMOL_COLORS.get(bond.end_species, (0.5, 0.5, 0.5))
            self.plotter.add_mesh(cyl2, color=color2, smooth_shading=True)
    
    def _add_unit_cell(self):
        """Add unit cell lines to plotter."""
        import pyvista as pv
        
        if not self.scene.show_unit_cell:
            return
        
        for start, end in self.scene.unit_cell_lines:
            line = pv.Line(start, end)
            self.plotter.add_mesh(line, color="white", line_width=2)
    
    def _add_labels(self):
        """Add atom labels."""
        if not self.scene.show_labels:
            return
        
        for atom in self.scene.atoms:
            if atom.label:
                self.plotter.add_point_labels(
                    [atom.position],
                    [atom.label],
                    font_size=12,
                    text_color="white",
                )
    
    def show(self, interactive: bool = True):
        """
        Display the structure.
        
        Args:
            interactive: Enable interactive mode
        """
        if self.scene is None:
            raise ValueError("No structure set. Call set_structure() first.")
        
        self._create_plotter()
        self._add_atoms()
        
        if self.scene.show_bonds:
            self._add_bonds()
        
        self._add_unit_cell()
        self._add_labels()
        
        self.plotter.show(interactive=interactive)
    
    def save(
        self,
        filename: str,
        resolution: Tuple[int, int] = (1920, 1080),
    ):
        """
        Save structure to image.
        
        Args:
            filename: Output filename (PNG, JPG, etc.)
            resolution: Image resolution
        """
        if self.scene is None:
            raise ValueError("No structure set.")
        
        self._create_plotter()
        self._add_atoms()
        
        if self.scene.show_bonds:
            self._add_bonds()
        
        self._add_unit_cell()
        
        self.plotter.window_size = resolution
        self.plotter.screenshot(filename)
        self.plotter.close()
        
        logger.info(f"Saved structure image to {filename}")
    
    def export_gltf(self, filename: str):
        """
        Export structure to GLTF format for web viewing.
        
        Args:
            filename: Output GLTF file
        """
        if self.scene is None:
            raise ValueError("No structure set.")
        
        self._create_plotter()
        self._add_atoms()
        if self.scene.show_bonds:
            self._add_bonds()
        
        self.plotter.export_gltf(filename)
        self.plotter.close()
        
        logger.info(f"Exported structure to {filename}")


def view_structure(
    structure: 'Structure',
    style: str = "ball_and_stick",
    supercell: Tuple[int, int, int] = (1, 1, 1),
    save_to: Optional[str] = None,
):
    """
    Quick structure visualization.
    
    Args:
        structure: pymatgen Structure
        style: Rendering style
        supercell: Supercell dimensions
        save_to: Optional output file
    """
    style_map = {
        "ball_and_stick": AtomStyle.BALL_AND_STICK,
        "sphere": AtomStyle.SPHERE,
        "stick": AtomStyle.STICK,
        "vdw": AtomStyle.VDW,
    }
    
    viewer = StructureViewer(
        structure,
        style=style_map.get(style, AtomStyle.BALL_AND_STICK),
    )
    viewer.set_structure(structure, supercell=supercell)
    
    if save_to:
        viewer.save(save_to)
    else:
        viewer.show()
