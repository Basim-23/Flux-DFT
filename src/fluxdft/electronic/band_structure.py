"""
Electronic Band Structure Analysis for FluxDFT.

Comprehensive band structure container with analysis methods inspired by
abipy's ElectronBands class. Provides band gap detection, k-path handling,
orbital projections, and export capabilities.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, Literal
from pathlib import Path
from enum import Enum
import numpy as np
import logging

logger = logging.getLogger(__name__)


class BandGapType(Enum):
    """Type of band gap."""
    DIRECT = "direct"
    INDIRECT = "indirect"
    METAL = "metal"


@dataclass
class BandEdge:
    """
    Information about a band edge (VBM or CBM).
    
    Attributes:
        energy: Energy in eV (relative to Fermi level)
        kpoint_index: Index of k-point
        kpoint_frac: Fractional coordinates
        kpoint_cart: Cartesian coordinates (1/Å)
        band_index: Band index
        spin: Spin channel (0 or 1)
        kpoint_label: High-symmetry label if applicable
    """
    energy: float
    kpoint_index: int
    kpoint_frac: np.ndarray
    kpoint_cart: np.ndarray
    band_index: int
    spin: int = 0
    kpoint_label: Optional[str] = None
    
    def __str__(self) -> str:
        label = self.kpoint_label or f"k={self.kpoint_frac}"
        return f"E={self.energy:.3f} eV at {label} (band {self.band_index})"


@dataclass
class BandGapInfo:
    """
    Complete band gap information.
    
    Attributes:
        gap_type: Direct, indirect, or metallic
        energy: Band gap in eV (0 for metals)
        vbm: Valence band maximum info
        cbm: Conduction band minimum info
        direct_gap: Direct gap value (may differ from indirect)
        direct_gap_kpoint: K-point of direct gap
    """
    gap_type: BandGapType
    energy: float
    vbm: Optional[BandEdge] = None
    cbm: Optional[BandEdge] = None
    direct_gap: Optional[float] = None
    direct_gap_kpoint: Optional[str] = None
    
    @property
    def is_metal(self) -> bool:
        return self.gap_type == BandGapType.METAL
    
    @property
    def is_direct(self) -> bool:
        return self.gap_type == BandGapType.DIRECT
    
    def __str__(self) -> str:
        if self.is_metal:
            return "Metallic (no band gap)"
        gap_str = f"{self.gap_type.value.capitalize()} gap: {self.energy:.3f} eV"
        if self.vbm:
            gap_str += f"\n  VBM: {self.vbm}"
        if self.cbm:
            gap_str += f"\n  CBM: {self.cbm}"
        if self.direct_gap and not self.is_direct:
            gap_str += f"\n  Direct gap: {self.direct_gap:.3f} eV at {self.direct_gap_kpoint}"
        return gap_str


@dataclass
class KPath:
    """
    K-point path information.
    
    Attributes:
        kpoints: K-point fractional coordinates (n_kpts, 3)
        distances: Cumulative distance along path (n_kpts,)
        labels: List of (index, label) for high-symmetry points
        segments: List of (start_idx, end_idx) for each segment
    """
    kpoints: np.ndarray
    distances: np.ndarray
    labels: List[Tuple[int, str]] = field(default_factory=list)
    segments: List[Tuple[int, int]] = field(default_factory=list)
    
    @property
    def n_kpts(self) -> int:
        return len(self.kpoints)
    
    def get_label_positions(self) -> Tuple[List[float], List[str]]:
        """Get positions and labels for plot ticks."""
        positions = [self.distances[idx] for idx, _ in self.labels]
        labels = [lbl for _, lbl in self.labels]
        return positions, labels


class ElectronicBandStructure:
    """
    Comprehensive electronic band structure container.
    
    Inspired by abipy's ElectronBands class. Provides complete analysis
    and visualization capabilities for DFT band structures.
    
    Features:
        - Band gap detection (direct/indirect)
        - VBM/CBM identification
        - Spin-polarized support
        - Orbital projections (fat bands)
        - Fermi level alignment
        - K-path handling with high-symmetry labels
        - Export to various formats
        
    Usage:
        >>> bs = ElectronicBandStructure.from_qe_output("pw.out", "bands.out")
        >>> gap = bs.get_band_gap()
        >>> print(gap)
        Direct gap: 1.123 eV
          VBM: E=0.000 eV at Γ (band 3)
          CBM: E=1.123 eV at Γ (band 4)
          
        >>> fig = bs.plot()
        >>> bs.to_bxsf("fermi_surface.bxsf")
    """
    
    def __init__(
        self,
        eigenvalues: np.ndarray,
        kpath: KPath,
        fermi_energy: float,
        structure: Optional['Structure'] = None,
        projections: Optional[np.ndarray] = None,
        projection_labels: Optional[List[str]] = None,
        occupations: Optional[np.ndarray] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Initialize electronic band structure.
        
        Args:
            eigenvalues: Band eigenvalues in eV.
                Shape: (n_kpts, n_bands) or (n_spins, n_kpts, n_bands)
            kpath: K-path information.
            fermi_energy: Fermi energy in eV.
            structure: Optional pymatgen Structure.
            projections: Optional orbital projections.
                Shape: (n_spins, n_kpts, n_bands, n_orbitals)
            projection_labels: Labels for each orbital.
            occupations: Band occupations (0-2 or 0-1 for spin-polarized).
            metadata: Additional calculation metadata.
        """
        # Normalize eigenvalues to 3D
        eigenvalues = np.asarray(eigenvalues)
        if eigenvalues.ndim == 2:
            self.eigenvalues = eigenvalues[np.newaxis, :, :]
        else:
            self.eigenvalues = eigenvalues
        
        self.kpath = kpath
        self.fermi_energy = float(fermi_energy)
        self.structure = structure
        self.projections = projections
        self.projection_labels = projection_labels or []
        self.occupations = occupations
        self.metadata = metadata or {}
        
        # Derived properties
        self.n_spins = self.eigenvalues.shape[0]
        self.n_kpts = self.eigenvalues.shape[1]
        self.n_bands = self.eigenvalues.shape[2]
        
        # Cache for expensive calculations
        self._band_gap_cache: Optional[BandGapInfo] = None
    
    @property
    def is_spin_polarized(self) -> bool:
        """Check if calculation is spin-polarized."""
        return self.n_spins == 2
    
    @property
    def eigenvalues_shifted(self) -> np.ndarray:
        """Eigenvalues relative to Fermi level."""
        return self.eigenvalues - self.fermi_energy
    
    def get_band_gap(self, tol: float = 1e-4) -> BandGapInfo:
        """
        Calculate band gap with VBM/CBM information.
        
        Args:
            tol: Tolerance for identifying degenerate states (eV).
            
        Returns:
            BandGapInfo with complete gap analysis.
        """
        if self._band_gap_cache is not None:
            return self._band_gap_cache
        
        e_shifted = self.eigenvalues_shifted
        
        # Find occupied and unoccupied states
        # VBM: highest occupied, CBM: lowest unoccupied
        vbm_energy = -np.inf
        cbm_energy = np.inf
        vbm_info = None
        cbm_info = None
        
        for spin in range(self.n_spins):
            for kpt in range(self.n_kpts):
                for band in range(self.n_bands):
                    e = e_shifted[spin, kpt, band]
                    
                    # Check if occupied (below Fermi level)
                    if e <= tol:
                        if e > vbm_energy:
                            vbm_energy = e
                            vbm_info = BandEdge(
                                energy=e,
                                kpoint_index=kpt,
                                kpoint_frac=self.kpath.kpoints[kpt],
                                kpoint_cart=self.kpath.kpoints[kpt],  # TODO: proper conversion
                                band_index=band,
                                spin=spin,
                                kpoint_label=self._get_kpoint_label(kpt),
                            )
                    else:
                        if e < cbm_energy:
                            cbm_energy = e
                            cbm_info = BandEdge(
                                energy=e,
                                kpoint_index=kpt,
                                kpoint_frac=self.kpath.kpoints[kpt],
                                kpoint_cart=self.kpath.kpoints[kpt],
                                band_index=band,
                                spin=spin,
                                kpoint_label=self._get_kpoint_label(kpt),
                            )
        
        # Determine gap type
        if vbm_info is None or cbm_info is None:
            # Metal
            gap_info = BandGapInfo(
                gap_type=BandGapType.METAL,
                energy=0.0,
            )
        else:
            gap = cbm_energy - vbm_energy
            
            # Check if direct or indirect
            same_kpoint = vbm_info.kpoint_index == cbm_info.kpoint_index
            
            if same_kpoint:
                gap_type = BandGapType.DIRECT
                direct_gap = gap
                direct_kpt = vbm_info.kpoint_label
            else:
                gap_type = BandGapType.INDIRECT
                # Find direct gap
                direct_gap, direct_kpt = self._find_direct_gap(e_shifted, tol)
            
            gap_info = BandGapInfo(
                gap_type=gap_type,
                energy=gap,
                vbm=vbm_info,
                cbm=cbm_info,
                direct_gap=direct_gap if gap_type == BandGapType.INDIRECT else None,
                direct_gap_kpoint=direct_kpt if gap_type == BandGapType.INDIRECT else None,
            )
        
        self._band_gap_cache = gap_info
        return gap_info
    
    def _find_direct_gap(
        self,
        e_shifted: np.ndarray,
        tol: float,
    ) -> Tuple[float, str]:
        """Find the smallest direct gap."""
        min_direct_gap = np.inf
        min_kpt_label = ""
        
        for kpt in range(self.n_kpts):
            # Get VBM and CBM at this k-point
            occupied = e_shifted[:, kpt, :][e_shifted[:, kpt, :] <= tol]
            unoccupied = e_shifted[:, kpt, :][e_shifted[:, kpt, :] > tol]
            
            if len(occupied) > 0 and len(unoccupied) > 0:
                local_gap = np.min(unoccupied) - np.max(occupied)
                if local_gap < min_direct_gap:
                    min_direct_gap = local_gap
                    min_kpt_label = self._get_kpoint_label(kpt) or f"k{kpt}"
        
        return min_direct_gap, min_kpt_label
    
    def _get_kpoint_label(self, kpt_idx: int) -> Optional[str]:
        """Get label for k-point if it's a high-symmetry point."""
        for idx, label in self.kpath.labels:
            if idx == kpt_idx:
                return label
        return None
    
    def get_band_energies_at_kpoint(
        self,
        kpoint_label: str,
        spin: int = 0,
    ) -> np.ndarray:
        """Get all band energies at a specific high-symmetry point."""
        for idx, label in self.kpath.labels:
            if label.upper() == kpoint_label.upper() or label == 'Γ' and kpoint_label.upper() == 'GAMMA':
                return self.eigenvalues_shifted[spin, idx, :]
        raise ValueError(f"K-point {kpoint_label} not found")
    
    def get_bands_in_range(
        self,
        emin: float,
        emax: float,
        spin: int = 0,
    ) -> List[int]:
        """Get indices of bands that fall within energy range."""
        bands = []
        for band in range(self.n_bands):
            e_band = self.eigenvalues_shifted[spin, :, band]
            if np.any((e_band >= emin) & (e_band <= emax)):
                bands.append(band)
        return bands
    
    def get_projection(
        self,
        orbital: str,
        spin: int = 0,
    ) -> Optional[np.ndarray]:
        """
        Get projection weights for a specific orbital.
        
        Args:
            orbital: Orbital label (e.g., 's', 'p', 'd', 'Si-s', 'O-p')
            spin: Spin channel.
            
        Returns:
            Projection weights (n_kpts, n_bands) or None if not available.
        """
        if self.projections is None:
            return None
        
        for i, label in enumerate(self.projection_labels):
            if orbital.lower() in label.lower():
                return self.projections[spin, :, :, i]
        
        return None
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'eigenvalues': self.eigenvalues.tolist(),
            'fermi_energy': self.fermi_energy,
            'kpoints': self.kpath.kpoints.tolist(),
            'kpoint_labels': self.kpath.labels,
            'n_spins': self.n_spins,
            'n_bands': self.n_bands,
            'metadata': self.metadata,
        }
    
    def to_bxsf(self, filepath: Union[str, Path]) -> None:
        """
        Export to BXSF format for Fermi surface visualization.
        
        The BXSF format is used by XCrySDen and FermiSurfer.
        """
        # TODO: Implement BXSF export
        raise NotImplementedError("BXSF export not yet implemented")
    
    @classmethod
    def from_pymatgen(
        cls,
        bs: 'BandStructureSymmLine',
    ) -> 'ElectronicBandStructure':
        """
        Create from pymatgen BandStructureSymmLine.
        
        Args:
            bs: pymatgen band structure object.
            
        Returns:
            ElectronicBandStructure instance.
        """
        from pymatgen.electronic_structure.core import Spin
        
        # Extract eigenvalues
        if bs.is_spin_polarized:
            eigs_up = np.array([bs.bands[Spin.up][:, k] for k in range(len(bs.kpoints))]).T
            eigs_down = np.array([bs.bands[Spin.down][:, k] for k in range(len(bs.kpoints))]).T
            eigenvalues = np.array([eigs_up.T, eigs_down.T])
        else:
            spin_key = Spin.up if Spin.up in bs.bands else list(bs.bands.keys())[0]
            eigenvalues = np.array([bs.bands[spin_key][:, k] for k in range(len(bs.kpoints))]).T
            eigenvalues = eigenvalues[np.newaxis, :, :]
        
        # Transpose to (n_spins, n_kpts, n_bands)
        eigenvalues = np.transpose(eigenvalues, (0, 2, 1))
        
        # Build k-path
        kpoints = np.array([k.frac_coords for k in bs.kpoints])
        distances = bs.distance
        
        # Get labels
        labels = []
        for i, k in enumerate(bs.kpoints):
            if k.label:
                labels.append((i, k.label))
        
        kpath = KPath(
            kpoints=kpoints,
            distances=np.array(distances),
            labels=labels,
        )
        
        return cls(
            eigenvalues=eigenvalues,
            kpath=kpath,
            fermi_energy=bs.efermi,
            structure=bs.structure,
        )
    
    @classmethod
    def from_qe_output(
        cls,
        bands_file: Union[str, Path],
        fermi_energy: Optional[float] = None,
    ) -> 'ElectronicBandStructure':
        """
        Create from Quantum ESPRESSO bands.x output (bands.dat).
        
        Args:
            bands_file: Path to bands.dat.
            fermi_energy: Fermi energy in eV.
            
        Returns:
            ElectronicBandStructure instance.
        """
        from ..io.qe_output import QEBandsParser
        
        try:
            data = QEBandsParser.parse(bands_file)
        except Exception as e:
            logger.error(f"Failed to parse bands file: {e}")
            raise
            
        # Calculate distances along path (Euclidean approx without lattice)
        # Ideally we'd use the lattice, but bands.dat often lacks it.
        # We assume the user creates the KPath correctly elsewhere if needed.
        kpoints = data.kpoints
        if len(kpoints) > 0:
            # Simple distance calculation (assuming cartesian or consistent scaling)
            diffs = np.diff(kpoints, axis=0)
            dists = np.linalg.norm(diffs, axis=1)
            distances = np.concatenate(([0], np.cumsum(dists)))
        else:
            distances = np.zeros(data.nks)
            
        kpath = KPath(
            kpoints=kpoints,
            distances=distances,
            labels=[], # Labels not present in bands.dat
        )
        
        # Reshape eigenvalues to (n_spins, n_kpts, n_bands)
        # QEBandsParser returns (nks, nbnd) for non-spin polarized
        # TODO: Handle spin-polarized bands.dat (often separate files or columns)
        eigenvalues = data.eigenvalues
        if eigenvalues.ndim == 2:
            eigenvalues = eigenvalues[np.newaxis, :, :] # Add spin dimension
            # Ensure shape is (1, nks, nbnd) which it is after newaxis at 0?
            # data.eigenvalues is (nks, nbnd).
            # newaxis at 0 -> (1, nks, nbnd). Correct.
            
        # If fermi energy not provided, try to find it in 3rd line of bands.dat?
        # Typically not there. Default to 0.0.
        ef = fermi_energy if fermi_energy is not None else (data.fermi_energy or 0.0)
        
        return cls(
            eigenvalues=eigenvalues,
            kpath=kpath,
            fermi_energy=ef,
        )
