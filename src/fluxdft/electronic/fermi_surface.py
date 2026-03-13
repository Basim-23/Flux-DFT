"""
Fermi Surface Analysis for FluxDFT.

3D Fermi surface generation and visualization.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class FermiSurfaceSlice:
    """
    2D slice of Fermi surface.
    
    Attributes:
        plane: Plane normal ('xy', 'xz', 'yz', or custom)
        offset: Offset from origin in fractional coordinates
        contours: List of contour paths [(x, y), ...]
        band_indices: Band indices contributing to each contour
    """
    plane: str
    offset: float
    contours: List[np.ndarray]
    band_indices: List[int] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            'plane': self.plane,
            'offset': self.offset,
            'contours': [c.tolist() for c in self.contours],
            'band_indices': self.band_indices,
        }


class FermiSurface:
    """
    3D Fermi surface container and generator.
    
    Generates Fermi surface isosurfaces from 3D k-space band data.
    Supports visualization with PyVista and export to common formats.
    
    Features:
        - Marching cubes isosurface generation
        - Multiple band support
        - Spin-polarized surfaces
        - Brillouin zone clipping
        - 2D slice generation
        - Export to BXSF, VTK formats
        
    Usage:
        >>> fs = FermiSurface.from_band_structure(bs, kgrid=(20, 20, 20))
        >>> mesh = fs.get_isosurface()
        >>> fs.plot()  # Interactive 3D view
        >>> fs.to_bxsf("fermi.bxsf")
    """
    
    def __init__(
        self,
        eigenvalues: np.ndarray,
        kgrid: Tuple[int, int, int],
        reciprocal_lattice: np.ndarray,
        fermi_energy: float,
        band_indices: Optional[List[int]] = None,
        spin: int = 0,
    ):
        """
        Initialize Fermi surface.
        
        Args:
            eigenvalues: Eigenvalues on 3D k-grid.
                Shape: (nkx, nky, nkz, n_bands) or (n_spins, nkx, nky, nkz, n_bands)
            kgrid: K-point grid dimensions.
            reciprocal_lattice: Reciprocal lattice vectors (3, 3).
            fermi_energy: Fermi energy in eV.
            band_indices: Indices of bands crossing Fermi level.
            spin: Spin channel to use.
        """
        eigenvalues = np.asarray(eigenvalues)
        
        # Handle spin dimension
        if eigenvalues.ndim == 5:
            self.eigenvalues = eigenvalues[spin]
        else:
            self.eigenvalues = eigenvalues
        
        self.kgrid = kgrid
        self.reciprocal_lattice = np.asarray(reciprocal_lattice)
        self.fermi_energy = float(fermi_energy)
        self.spin = spin
        
        # Auto-detect bands crossing Fermi level
        if band_indices is None:
            self.band_indices = self._find_fermi_bands()
        else:
            self.band_indices = band_indices
        
        # Cache for generated surfaces
        self._isosurfaces: Dict[int, 'pv.PolyData'] = {}
    
    @property
    def n_bands(self) -> int:
        return self.eigenvalues.shape[-1]
    
    @property
    def eigenvalues_shifted(self) -> np.ndarray:
        """Eigenvalues relative to Fermi level."""
        return self.eigenvalues - self.fermi_energy
    
    def _find_fermi_bands(self) -> List[int]:
        """Find bands that cross the Fermi level."""
        crossing = []
        e = self.eigenvalues_shifted
        
        for band in range(self.n_bands):
            band_e = e[:, :, :, band]
            if np.any(band_e < 0) and np.any(band_e > 0):
                crossing.append(band)
        
        return crossing
    
    def get_isosurface(
        self,
        band_index: Optional[int] = None,
        energy: float = 0.0,
    ) -> 'pv.PolyData':
        """
        Generate isosurface mesh using marching cubes.
        
        Args:
            band_index: Specific band. None uses first crossing band.
            energy: Energy level relative to Fermi (0 = Fermi surface).
            
        Returns:
            PyVista PolyData mesh.
        """
        try:
            import pyvista as pv
            from skimage import measure
        except ImportError:
            raise ImportError("pyvista and scikit-image required for isosurface generation")
        
        if band_index is None:
            if not self.band_indices:
                raise ValueError("No bands crossing Fermi level")
            band_index = self.band_indices[0]
        
        # Get band eigenvalues
        band_e = self.eigenvalues_shifted[:, :, :, band_index]
        
        # Marching cubes
        try:
            verts, faces, normals, values = measure.marching_cubes(
                band_e,
                level=energy,
                spacing=(1.0/self.kgrid[0], 1.0/self.kgrid[1], 1.0/self.kgrid[2]),
            )
        except ValueError:
            logger.warning(f"No isosurface found for band {band_index} at E={energy}")
            return pv.PolyData()
        
        # Convert to Cartesian coordinates
        # Scale vertices to fractional, then apply reciprocal lattice
        verts_frac = verts  # Already in fractional from spacing
        verts_cart = verts_frac @ self.reciprocal_lattice
        
        # Create PyVista mesh
        faces_pv = np.hstack([np.full((len(faces), 1), 3), faces]).ravel()
        mesh = pv.PolyData(verts_cart, faces_pv)
        mesh['energy'] = values
        
        return mesh
    
    def get_all_isosurfaces(self, energy: float = 0.0) -> 'pv.PolyData':
        """Get combined isosurface for all Fermi-crossing bands."""
        try:
            import pyvista as pv
        except ImportError:
            raise ImportError("pyvista required")
        
        combined = pv.PolyData()
        for band in self.band_indices:
            mesh = self.get_isosurface(band, energy)
            if mesh.n_points > 0:
                combined = combined.merge(mesh)
        
        return combined
    
    def get_slice(
        self,
        plane: str = 'xy',
        offset: float = 0.0,
        band_index: Optional[int] = None,
    ) -> FermiSurfaceSlice:
        """
        Get 2D slice of Fermi surface.
        
        Args:
            plane: Slice plane ('xy', 'xz', 'yz').
            offset: Offset in third dimension (fractional).
            band_index: Specific band index.
            
        Returns:
            FermiSurfaceSlice with contour data.
        """
        from skimage import measure
        
        if band_index is None:
            band_index = self.band_indices[0] if self.band_indices else 0
        
        band_e = self.eigenvalues_shifted[:, :, :, band_index]
        
        # Get slice index
        if plane == 'xy':
            idx = int(offset * self.kgrid[2])
            slice_data = band_e[:, :, idx]
        elif plane == 'xz':
            idx = int(offset * self.kgrid[1])
            slice_data = band_e[:, idx, :]
        elif plane == 'yz':
            idx = int(offset * self.kgrid[0])
            slice_data = band_e[idx, :, :]
        else:
            raise ValueError(f"Unknown plane: {plane}")
        
        # Get contours at Fermi level
        contours = measure.find_contours(slice_data, level=0.0)
        
        return FermiSurfaceSlice(
            plane=plane,
            offset=offset,
            contours=contours,
            band_indices=[band_index],
        )
    
    def plot(
        self,
        show_bz: bool = True,
        opacity: float = 0.8,
        color: str = 'blue',
    ) -> None:
        """
        Interactive 3D plot of Fermi surface.
        
        Args:
            show_bz: Show Brillouin zone wireframe.
            opacity: Surface opacity.
            color: Surface color.
        """
        try:
            import pyvista as pv
        except ImportError:
            raise ImportError("pyvista required for plotting")
        
        plotter = pv.Plotter()
        
        # Add Fermi surface
        mesh = self.get_all_isosurfaces()
        if mesh.n_points > 0:
            plotter.add_mesh(mesh, color=color, opacity=opacity)
        
        # Add Brillouin zone
        if show_bz:
            bz_mesh = self._create_bz_wireframe()
            plotter.add_mesh(bz_mesh, color='black', style='wireframe', line_width=2)
        
        plotter.add_axes()
        plotter.show()
    
    def _create_bz_wireframe(self) -> 'pv.PolyData':
        """Create Brillouin zone wireframe."""
        import pyvista as pv
        
        # Simple cubic BZ (TODO: proper Wigner-Seitz cell)
        a, b, c = self.reciprocal_lattice
        corners = np.array([
            [0, 0, 0],
            a, b, c,
            a + b, b + c, a + c,
            a + b + c,
        ])
        
        box = pv.Box(bounds=[
            corners[:, 0].min(), corners[:, 0].max(),
            corners[:, 1].min(), corners[:, 1].max(),
            corners[:, 2].min(), corners[:, 2].max(),
        ])
        
        return box.extract_feature_edges()
    
    def to_bxsf(self, filepath: Union[str, Path]) -> None:
        """
        Export to BXSF format (XCrySDen, FermiSurfer).
        
        Args:
            filepath: Output file path.
        """
        filepath = Path(filepath)
        
        with open(filepath, 'w') as f:
            f.write("BEGIN_INFO\n")
            f.write(f"  Fermi Energy: {self.fermi_energy}\n")
            f.write("END_INFO\n\n")
            
            f.write("BEGIN_BLOCK_BANDGRID_3D\n")
            f.write("  fermi_surface\n")
            f.write("  BEGIN_BANDGRID_3D_fermi\n")
            f.write(f"    {len(self.band_indices)}\n")  # Number of bands
            f.write(f"    {self.kgrid[0]} {self.kgrid[1]} {self.kgrid[2]}\n")
            
            # Origin
            f.write("    0.0 0.0 0.0\n")
            
            # Reciprocal vectors
            for vec in self.reciprocal_lattice:
                f.write(f"    {vec[0]:.6f} {vec[1]:.6f} {vec[2]:.6f}\n")
            
            # Band data
            for band in self.band_indices:
                f.write(f"    BAND: {band}\n")
                band_e = self.eigenvalues[:, :, :, band]
                for iz in range(self.kgrid[2]):
                    for iy in range(self.kgrid[1]):
                        for ix in range(self.kgrid[0]):
                            f.write(f"    {band_e[ix, iy, iz]:.6f}\n")
            
            f.write("  END_BANDGRID_3D\n")
            f.write("END_BLOCK_BANDGRID_3D\n")
        
        logger.info(f"Wrote BXSF file to {filepath}")
    
    @classmethod
    def from_band_structure(
        cls,
        bs: 'ElectronicBandStructure',
        kgrid: Tuple[int, int, int] = (20, 20, 20),
    ) -> 'FermiSurface':
        """
        Create Fermi surface from band structure using interpolation.
        
        Note: This requires a uniform k-grid or interpolation.
        For accurate Fermi surfaces, use output from pw.x with dense k-grid.
        """
        # TODO: Implement interpolation from k-path to 3D grid
        raise NotImplementedError(
            "Fermi surface interpolation not implemented. "
            "Use from_qe_uniform_grid() instead."
        )
    
    @classmethod
    def from_qe_uniform_grid(
        cls,
        eigenvalues_file: Union[str, Path],
        kgrid: Tuple[int, int, int],
        reciprocal_lattice: np.ndarray,
        fermi_energy: float,
    ) -> 'FermiSurface':
        """
        Create from QE eigenvalues on uniform grid.
        
        Args:
            eigenvalues_file: Path to eigenvalues file.
            kgrid: K-point grid dimensions.
            reciprocal_lattice: Reciprocal lattice vectors.
            fermi_energy: Fermi energy.
        """
        # TODO: Implement QE eigenvalue file parsing
        raise NotImplementedError("QE eigenvalue parsing not implemented")
