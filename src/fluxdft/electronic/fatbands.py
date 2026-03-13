"""
Fat Band Analysis for FluxDFT.

Orbital-projected band structure (fat bands) analysis and plotting.
Based on patterns from abipy's fatbands.py and pyprocar.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


# Orbital names for different l values
ORBITAL_NAMES = {
    0: ['s'],
    1: ['px', 'py', 'pz'],
    2: ['dxy', 'dyz', 'dz2', 'dxz', 'dx2-y2'],
    3: ['f-3', 'f-2', 'f-1', 'f0', 'f1', 'f2', 'f3'],
}

# Orbital abbreviations
ORBITAL_L = {'s': 0, 'p': 1, 'd': 2, 'f': 3}


@dataclass
class OrbitalWeight:
    """Orbital projection weight at a k-point/band."""
    atom_index: int
    species: str
    l: int  # Angular momentum quantum number
    m: int  # Magnetic quantum number
    weight: float  # Projection weight (0-1)
    
    @property
    def orbital_name(self) -> str:
        """Get orbital name (e.g., 'dxy')."""
        if self.l in ORBITAL_NAMES:
            orbitals = ORBITAL_NAMES[self.l]
            if 0 <= self.m < len(orbitals):
                return orbitals[self.m]
        return f"l={self.l},m={self.m}"


@dataclass
class FatBandData:
    """
    Complete fat band data container.
    
    Stores orbital projections for all bands at all k-points.
    """
    # Basic dimensions
    nkpoints: int
    nbands: int
    nspins: int
    natoms: int
    
    # K-point data
    kpoints: np.ndarray  # (nkpts, 3)
    k_distances: np.ndarray  # (nkpts,)
    
    # Eigenvalues
    eigenvalues: np.ndarray  # (nspins, nkpts, nbands)
    
    # Projections: (nspins, nkpts, nbands, natoms, norbitals)
    projections: np.ndarray
    
    # Orbital mapping
    orbital_names: List[str]
    atom_species: List[str]
    
    # High-symmetry point labels
    hs_labels: Dict[int, str] = field(default_factory=dict)
    
    # Fermi energy
    fermi_energy: float = 0.0
    
    def get_atom_projection(
        self,
        atom_indices: Union[int, List[int]],
        spin: int = 0,
    ) -> np.ndarray:
        """
        Get total projection for specific atoms.
        
        Args:
            atom_indices: Atom index or list of indices
            spin: Spin channel
            
        Returns:
            Projection weights (nkpts, nbands)
        """
        if isinstance(atom_indices, int):
            atom_indices = [atom_indices]
        
        # Sum over atoms and orbitals
        weights = np.zeros((self.nkpoints, self.nbands))
        for atom_idx in atom_indices:
            weights += np.sum(self.projections[spin, :, :, atom_idx, :], axis=-1)
        
        return weights
    
    def get_orbital_projection(
        self,
        orbital: str,
        atom_indices: Optional[List[int]] = None,
        spin: int = 0,
    ) -> np.ndarray:
        """
        Get projection for specific orbital type.
        
        Args:
            orbital: Orbital name ('s', 'p', 'd', 'px', 'dxy', etc.)
            atom_indices: Limit to specific atoms
            spin: Spin channel
            
        Returns:
            Projection weights (nkpts, nbands)
        """
        weights = np.zeros((self.nkpoints, self.nbands))
        
        # Determine which orbital indices to sum
        if orbital.lower() in ORBITAL_L:
            # Sum all orbitals of this l (e.g., 'p' = px + py + pz)
            l = ORBITAL_L[orbital.lower()]
            orb_indices = [i for i, name in enumerate(self.orbital_names)
                          if name.startswith(orbital.lower())]
        else:
            # Specific orbital (e.g., 'dxy')
            orb_indices = [i for i, name in enumerate(self.orbital_names)
                          if name == orbital.lower()]
        
        if not orb_indices:
            logger.warning(f"Orbital '{orbital}' not found")
            return weights
        
        # Sum over specified atoms and orbitals
        atom_range = atom_indices if atom_indices else range(self.natoms)
        for atom_idx in atom_range:
            for orb_idx in orb_indices:
                weights += self.projections[spin, :, :, atom_idx, orb_idx]
        
        return weights
    
    def get_species_projection(
        self,
        species: str,
        orbital: Optional[str] = None,
        spin: int = 0,
    ) -> np.ndarray:
        """
        Get projection for a specific species.
        
        Args:
            species: Element symbol (e.g., 'Fe')
            orbital: Optional orbital filter
            spin: Spin channel
            
        Returns:
            Projection weights (nkpts, nbands)
        """
        atom_indices = [i for i, sp in enumerate(self.atom_species) if sp == species]
        
        if orbital:
            return self.get_orbital_projection(orbital, atom_indices, spin)
        else:
            return self.get_atom_projection(atom_indices, spin)
    
    @classmethod
    def from_qe_projwfc(
        cls,
        projwfc_file: Union[str, Path],
        bands_file: Optional[Union[str, Path]] = None,
    ) -> 'FatBandData':
        """
        Create FatBandData from QE projwfc.x output.
        
        Args:
            projwfc_file: Path to projwfc.x output
            bands_file: Optional path to bands data
            
        Returns:
            FatBandData object
        """
        # This is a placeholder - actual implementation would parse the files
        raise NotImplementedError("Use FatBandParser.parse() instead")


class FatBandParser:
    """
    Parser for orbital projection data from various DFT codes.
    
    Supports:
        - Quantum ESPRESSO projwfc.x output
        - VASP PROCAR files
        - pymatgen ProjectedBandStructure
    """
    
    @staticmethod
    def parse_qe_projwfc(
        projwfc_file: Union[str, Path],
        atomic_proj_file: Optional[Union[str, Path]] = None,
    ) -> FatBandData:
        """
        Parse Quantum ESPRESSO projwfc.x output.
        
        Args:
            projwfc_file: Path to projwfc.x stdout
            atomic_proj_file: Path to prefix.save/atomic_proj.xml (not used yet)
            
        Returns:
            FatBandData object
        """
        projwfc_file = Path(projwfc_file)
        if not projwfc_file.exists():
            raise FileNotFoundError(f"File not found: {projwfc_file}")
            
        content = projwfc_file.read_text(encoding='utf-8', errors='ignore')
        
        import re
        
        # 1. Parse Dimensions
        nkpts_match = re.search(r'number of k points\s*=\s*(\d+)', content)
        nbands_match = re.search(r'number of Kohn-Sham states\s*=\s*(\d+)', content)
        natoms_match = re.search(r'number of atoms\s*=\s*(\d+)', content)
        
        if not all([nkpts_match, nbands_match, natoms_match]):
             # Try simpler pattern or raise error
             pass

        nkpts = int(nkpts_match.group(1)) if nkpts_match else 0
        nbands = int(nbands_match.group(1)) if nbands_match else 0
        natoms = int(natoms_match.group(1)) if natoms_match else 1
        
        if nkpts == 0 or nbands == 0:
            raise ValueError("Could not parse nkpts or nbands from projwfc output")
            
        # 2. Orbital Setup
        # Map QE (l, m) to our orbital names
        # QE typically: l=0 m=1(s); l=1 m=1(pz) m=2(px) m=3(py); 
        # l=2 m=1(dz2) m=2(dxz) m=3(dyz) m=4(dx2-y2) m=5(dxy)
        # We use standard list: s, px, py, pz, dxy, dyz, dz2, dxz, dx2-y2
        orbital_names = ['s', 'px', 'py', 'pz', 'dxy', 'dyz', 'dz2', 'dxz', 'dx2-y2']
        orb_map = {
            (0, 1): 0, # s
            (1, 1): 3, # pz -> index 3
            (1, 2): 1, # px -> index 1
            (1, 3): 2, # py -> index 2
            (2, 1): 6, # dz2 -> index 6
            (2, 2): 7, # dxz -> index 7
            (2, 3): 5, # dyz -> index 5
            (2, 4): 8, # dx2-y2 -> index 8
            (2, 5): 4, # dxy -> index 4
        }
        norbitals = len(orbital_names)
        
        # 3. Initialize Arrays
        kpoints = np.zeros((nkpts, 3))
        eigenvalues = np.zeros((1, nkpts, nbands))
        projections = np.zeros((1, nkpts, nbands, natoms, norbitals))
        
        # 4. Parse K-points and Bands
        # Split content by 'k =' identifiers
        k_blocks = re.split(r'(?m)^ \s*k\s*=\s*', content)
        
        # First block is preamble
        current_k = 0
        
        for i, block in enumerate(k_blocks[1:]):
            if current_k >= nkpts: 
                break
                
            # Parse k-coords
            # Line format: "0.0000 0.0000 0.0000 ..."
            header_line = block.strip().split('\n', 1)[0]
            try:
                parts = header_line.split()
                kpoints[current_k] = [float(x) for x in parts[:3]]
            except (ValueError, IndexError):
                logger.warning(f"Failed to parse k-point coords at block {i}")
                
            # Parse Bands and Projections within this k-block
            # Look for "==== e( N) = E eV ===="
            band_blocks = re.split(r'==== e\(', block)
            
            # band_blocks[0] is typically "bands (ev): ..." list, we can skip or use it for check
            # We rely on the detailed blocks
            
            for j, band_content in enumerate(band_blocks[1:]):
                # Format: "   1) =  -6.24838 eV ===="
                # followed by projections
                try:
                    # Parse energy
                    header, rest = band_content.split('====', 1)
                    # header looks like "   1) =  -6.24838 eV "
                    
                    band_idx_str, energy_str = header.split(') =')
                    band_idx = int(band_idx_str.strip()) - 1
                    energy = float(energy_str.replace('eV', '').strip())
                    
                    if 0 <= band_idx < nbands:
                        eigenvalues[0, current_k, band_idx] = energy
                        
                        # Parse projections
                        # Lines: "state #   1: atom   1 (Si ), wfc  1 (l=0 m= 1) =  0.024"
                        # Regex to capture atom, l, m, weight
                        proj_matches = re.finditer(
                            r'atom\s+(\d+)\s+\(\S+\s*\),\s+wfc\s+\d+\s+\(l=(\d+)\s+m=\s*(\d+)\)\s*=\s*([0-9.]+)',
                            rest
                        )
                        
                        for match in proj_matches:
                            atom_idx = int(match.group(1)) - 1
                            l = int(match.group(2))
                            m = int(match.group(3))
                            weight = float(match.group(4))
                            
                            if (l, m) in orb_map and 0 <= atom_idx < natoms:
                                orb_idx = orb_map[(l, m)]
                                projections[0, current_k, band_idx, atom_idx, orb_idx] = weight
                                
                except Exception as e:
                    # logger.debug(f"Error parsing band block {j} at kpt {current_k}: {e}")
                    pass
            
            current_k += 1

        # 5. Post-process
        # Check if we parsed formatted dates
        if current_k == 0:
            logger.warning("No k-point blocks parsed. Check file format.")
            
        # Calc k-distances
        k_distances = np.zeros(nkpts)
        for i in range(1, nkpts):
            k_distances[i] = k_distances[i-1] + np.linalg.norm(kpoints[i] - kpoints[i-1])
            
        return FatBandData(
            nkpoints=nkpts,
            nbands=nbands,
            nspins=1, # TODO: Handle spin-polarized
            natoms=natoms,
            kpoints=kpoints,
            k_distances=k_distances,
            eigenvalues=eigenvalues,
            projections=projections,
            orbital_names=orbital_names,
            atom_species=['X'] * natoms, # Placeholder species
        )
    
    @staticmethod
    def parse_vasp_procar(procar_file: Union[str, Path]) -> FatBandData:
        """
        Parse VASP PROCAR file.
        
        Args:
            procar_file: Path to PROCAR
            
        Returns:
            FatBandData object
        """
        procar_file = Path(procar_file)
        
        with open(procar_file, 'r') as f:
            lines = f.readlines()
        
        # Parse header
        header_line = lines[1]
        import re
        header_match = re.search(
            r'# of k-points:\s*(\d+)\s*# of bands:\s*(\d+)\s*# of ions:\s*(\d+)',
            header_line
        )
        
        if not header_match:
            raise ValueError("Could not parse PROCAR header")
        
        nkpts = int(header_match.group(1))
        nbands = int(header_match.group(2))
        natoms = int(header_match.group(3))
        
        # Determine orbital set (s, p, d or s, py, pz, px, dxy, ...)
        # Parse first data block to determine
        orbital_names = ['s', 'py', 'pz', 'px', 'dxy', 'dyz', 'dz2', 'dxz', 'dx2']
        norbitals = len(orbital_names)
        
        # Initialize arrays
        kpoints = np.zeros((nkpts, 3))
        k_distances = np.zeros(nkpts)
        eigenvalues = np.zeros((1, nkpts, nbands))
        projections = np.zeros((1, nkpts, nbands, natoms, norbitals))
        
        # Parse data
        current_kpt = 0
        current_band = 0
        
        i = 2
        while i < len(lines):
            line = lines[i].strip()
            
            # K-point line
            if line.startswith('k-point'):
                parts = line.split()
                kpt_idx = int(parts[1]) - 1
                # Parse k-point coordinates - they're after the colon
                k_coords = [float(x) for x in parts[3:6]]
                kpoints[kpt_idx] = k_coords
                current_kpt = kpt_idx
                
            # Band line
            elif line.startswith('band'):
                parts = line.split()
                band_idx = int(parts[1]) - 1
                energy = float(parts[4])
                eigenvalues[0, current_kpt, band_idx] = energy
                current_band = band_idx
                
            # Ion projection line
            elif line.startswith('ion'):
                # Skip header line
                pass
            elif line and line[0].isdigit():
                # This is a projection line
                parts = line.split()
                try:
                    atom_idx = int(parts[0]) - 1
                    if atom_idx < natoms:
                        for orb_idx in range(min(len(parts)-1, norbitals)):
                            projections[0, current_kpt, current_band, atom_idx, orb_idx] = float(parts[orb_idx + 1])
                except (ValueError, IndexError):
                    pass
            
            i += 1
        
        # Calculate k-distances
        for i in range(1, nkpts):
            k_distances[i] = k_distances[i-1] + np.linalg.norm(kpoints[i] - kpoints[i-1])
        
        return FatBandData(
            nkpoints=nkpts,
            nbands=nbands,
            nspins=1,
            natoms=natoms,
            kpoints=kpoints,
            k_distances=k_distances,
            eigenvalues=eigenvalues,
            projections=projections,
            orbital_names=orbital_names,
            atom_species=['X'] * natoms,
        )


class FatBandPlotter:
    """
    Publication-quality fat band plotter.
    
    Creates orbital-projected band structure plots with:
        - Line width proportional to projection weight
        - Color-coded by orbital/atom/species
        - RGB color mixing for multiple projections
        - Stacked fat band plots
    """
    
    # Default colors for orbitals
    ORBITAL_COLORS = {
        's': '#1f77b4',    # Blue
        'p': '#2ca02c',    # Green
        'd': '#d62728',    # Red
        'f': '#9467bd',    # Purple
        'px': '#2ca02c',
        'py': '#98df8a',
        'pz': '#17becf',
        'dxy': '#d62728',
        'dyz': '#ff7f0e',
        'dz2': '#e377c2',
        'dxz': '#bcbd22',
        'dx2-y2': '#8c564b',
    }
    
    def __init__(
        self,
        fatband_data: FatBandData,
        fermi_shift: bool = True,
    ):
        """
        Initialize plotter.
        
        Args:
            fatband_data: FatBandData object
            fermi_shift: Shift energies to Fermi level
        """
        self.data = fatband_data
        self.fermi_shift = fermi_shift
    
    def plot_single_orbital(
        self,
        orbital: str,
        ax=None,
        spin: int = 0,
        color: Optional[str] = None,
        max_width: float = 3.0,
        energy_range: Tuple[float, float] = (-5, 5),
        **kwargs,
    ):
        """
        Plot fat bands for a single orbital type.
        
        Args:
            orbital: Orbital to plot ('s', 'p', 'd', 'dxy', etc.)
            ax: matplotlib axes
            spin: Spin channel
            color: Line color
            max_width: Maximum line width
            energy_range: Energy range to plot
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.collections import LineCollection
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Get projection weights
        weights = self.data.get_orbital_projection(orbital, spin=spin)
        
        # Get energies
        energies = self.data.eigenvalues[spin].copy()
        if self.fermi_shift:
            energies -= self.data.fermi_energy
        
        # K-distances
        x = self.data.k_distances
        
        # Plot each band
        color = color or self.ORBITAL_COLORS.get(orbital, '#333333')
        
        for band in range(self.data.nbands):
            y = energies[:, band]
            w = weights[:, band]
            
            # Filter by energy range
            mask = (y >= energy_range[0]) & (y <= energy_range[1])
            if not np.any(mask):
                continue
            
            # Create line segments with varying width
            points = np.column_stack([x, y]).reshape(-1, 1, 2)
            segments = np.concatenate([points[:-1], points[1:]], axis=1)
            
            # Line widths based on weights
            linewidths = 0.5 + max_width * (w[:-1] + w[1:]) / 2
            
            lc = LineCollection(
                segments,
                linewidths=linewidths,
                colors=color,
                alpha=0.8,
            )
            ax.add_collection(lc)
        
        # Add high-symmetry point labels
        for idx, label in self.data.hs_labels.items():
            ax.axvline(self.data.k_distances[idx], color='gray', linestyle='--', alpha=0.5)
            ax.text(self.data.k_distances[idx], energy_range[0], label,
                   ha='center', va='top', fontsize=12)
        
        ax.set_xlim(x.min(), x.max())
        ax.set_ylim(energy_range)
        ax.set_ylabel('Energy (eV)')
        ax.axhline(0, color='black', linestyle='--', linewidth=0.5)
        
        return ax
    
    def plot_rgb(
        self,
        projections: Dict[str, str],  # {orbital: color}
        ax=None,
        spin: int = 0,
        max_width: float = 3.0,
        energy_range: Tuple[float, float] = (-5, 5),
        **kwargs,
    ):
        """
        Plot fat bands with RGB color mixing.
        
        Args:
            projections: Dictionary mapping orbitals to colors
            ax: matplotlib axes
            spin: Spin channel
            max_width: Maximum line width
            energy_range: Energy range
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.colors import to_rgb
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Get all weights and colors
        all_weights = {}
        all_colors = {}
        
        for orbital, color in projections.items():
            all_weights[orbital] = self.data.get_orbital_projection(orbital, spin=spin)
            all_colors[orbital] = np.array(to_rgb(color))
        
        # Get energies
        energies = self.data.eigenvalues[spin].copy()
        if self.fermi_shift:
            energies -= self.data.fermi_energy
        
        x = self.data.k_distances
        
        # Plot each band with mixed colors
        for band in range(self.data.nbands):
            y = energies[:, band]
            
            # Calculate mixed colors
            colors = np.zeros((len(x), 3))
            total_weight = np.zeros(len(x))
            
            for orbital in projections:
                w = all_weights[orbital][:, band]
                c = all_colors[orbital]
                
                for i in range(len(x)):
                    colors[i] += w[i] * c
                total_weight += all_weights[orbital][:, band]
            
            # Normalize colors
            for i in range(len(x)):
                if total_weight[i] > 0:
                    colors[i] /= total_weight[i]
                else:
                    colors[i] = [0.5, 0.5, 0.5]  # Gray for no projection
            
            # Clip to valid range
            colors = np.clip(colors, 0, 1)
            
            # Plot as scatter for color variation
            linewidth = 0.5 + max_width * total_weight / total_weight.max() if total_weight.max() > 0 else 1
            
            # Simple line plot (for now)
            ax.plot(x, y, 'k-', linewidth=0.3, alpha=0.3)
            ax.scatter(x, y, c=colors, s=linewidth * 3, alpha=0.7)
        
        ax.set_xlim(x.min(), x.max())
        ax.set_ylim(energy_range)
        ax.set_ylabel('Energy (eV)')
        ax.axhline(0, color='black', linestyle='--', linewidth=0.5)
        
        # Legend
        for orbital, color in projections.items():
            ax.plot([], [], 'o', color=color, label=orbital)
        ax.legend()
        
        return ax
    
    def plot_stacked(
        self,
        orbitals: List[str],
        ncols: int = 1,
        figsize: Tuple[float, float] = (8, 12),
        **kwargs,
    ):
        """
        Create stacked subplots for multiple orbitals.
        
        Args:
            orbitals: List of orbitals to plot
            ncols: Number of columns
            figsize: Figure size
            **kwargs: Arguments passed to plot_single_orbital
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        nrows = (len(orbitals) + ncols - 1) // ncols
        fig, axes = plt.subplots(nrows, ncols, figsize=figsize, sharex=True, sharey=True)
        axes = np.atleast_2d(axes).flatten()
        
        for i, orbital in enumerate(orbitals):
            self.plot_single_orbital(orbital, ax=axes[i], **kwargs)
            axes[i].set_title(orbital.upper())
        
        # Hide empty axes
        for i in range(len(orbitals), len(axes)):
            axes[i].axis('off')
        
        plt.tight_layout()
        return fig, axes
