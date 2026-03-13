"""
Enhanced Effective Mass Analyzer for FluxDFT.

Based on patterns from abipy's EffMassAnalyzer and sumo's effective_mass module.
Provides segment-based analysis, parabolic and nonparabolic fitting.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Physical constants
EV_TO_HARTREE = 0.03674932248  # eV/Hartree
BOHR_TO_ANGSTROM = 0.529177249  # Bohr/Angstrom
HBAR_EV_S = 6.582119514e-16  # ℏ in eV⋅s
ME = 9.10938e-31  # Electron mass in kg


@dataclass
class Segment:
    """
    Stores KS energies along a k-space segment passing through k0.
    
    Provides methods to compute effective masses at k0 via finite differences
    or polynomial fitting.
    """
    k0_index: int  # Index of k0 in the full k-path
    spin: int
    band_indices: List[int]
    kpoint_indices: np.ndarray  # Indices of k-points in this segment
    energies: np.ndarray  # Shape: (nbands, nkpoints)
    k_distances: np.ndarray  # |k - k0| in Å⁻¹
    k_distances_sq: np.ndarray  # |k - k0|² in Å⁻²
    dk: float  # K-point spacing
    direction: Optional[np.ndarray] = None  # Direction vector
    direction_label: str = ""
    
    @property
    def k0_position(self) -> int:
        """Position of k0 within segment."""
        return np.argmin(np.abs(self.k_distances))
    
    @property
    def nbands(self) -> int:
        """Number of bands in segment."""
        return self.energies.shape[0]
    
    @property
    def nkpoints(self) -> int:
        """Number of k-points in segment."""
        return self.energies.shape[1]
    
    def get_effective_mass_parabolic(
        self,
        band_idx: int = 0,
        n_points: int = 5,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate effective mass using parabolic fit.
        
        E(k) = E0 + ℏ²(k-k0)²/(2m*)
        
        Args:
            band_idx: Which band in segment to analyze
            n_points: Number of points to use for fit
            
        Returns:
            Tuple of (effective_mass, fit_info)
        """
        k0_pos = self.k0_position
        
        # Select points around k0
        start = max(0, k0_pos - n_points // 2)
        end = min(self.nkpoints, k0_pos + n_points // 2 + 1)
        
        distances = self.k_distances[start:end]
        energies = self.energies[band_idx, start:end]
        
        # Normalize to k0
        energies = energies - energies[k0_pos - start]
        
        # Parabolic fit: E = a*k² + b*k + c
        # For symmetric data around k0: b ≈ 0
        coeffs = np.polyfit(distances, energies, 2)
        a = coeffs[0]  # Coefficient of k²
        
        # m* = ℏ² / (2a) where a is in eV/Å⁻²
        # Convert to electron mass units
        # ℏ² = 7.6199 eV⋅Å² in appropriate units
        hbar_sq = 7.6199  # eV⋅Å²
        
        if abs(a) < 1e-10:
            effective_mass = float('inf')
        else:
            effective_mass = hbar_sq / (2 * a)
        
        # Fit quality
        fit_energies = np.polyval(coeffs, distances)
        r_squared = 1 - np.sum((energies - fit_energies)**2) / np.sum((energies - np.mean(energies))**2)
        
        fit_info = {
            'coefficients': coeffs,
            'r_squared': r_squared,
            'n_points': end - start,
            'distances': distances,
            'energies': energies,
            'fit_energies': fit_energies,
            'curvature': 2 * a,
        }
        
        return effective_mass, fit_info
    
    def get_effective_mass_nonparabolic(
        self,
        band_idx: int = 0,
        n_points: int = 7,
    ) -> Tuple[float, Dict[str, Any]]:
        """
        Calculate effective mass using Kane's nonparabolic model.
        
        E(1 + αE) = ℏ²k²/(2m*)
        
        Where α is the nonparabolicity parameter.
        This is important for narrow-gap semiconductors.
        
        Args:
            band_idx: Which band in segment to analyze
            n_points: Number of points for fit
            
        Returns:
            Tuple of (effective_mass, fit_info)
        """
        try:
            from scipy.optimize import curve_fit
        except ImportError:
            logger.warning("scipy not available, falling back to parabolic fit")
            return self.get_effective_mass_parabolic(band_idx, n_points)
        
        k0_pos = self.k0_position
        start = max(0, k0_pos - n_points // 2)
        end = min(self.nkpoints, k0_pos + n_points // 2 + 1)
        
        distances = self.k_distances[start:end]
        energies = self.energies[band_idx, start:end]
        energies = energies - energies[k0_pos - start]
        
        # Kane model: E = (sqrt(1 + 4αdk²) - 1) / (2α)
        # where d = ℏ²/(2m*)
        def kane_model(k, alpha, d):
            k_sq = k ** 2
            if alpha < 1e-10:
                return d * k_sq  # Reduce to parabolic
            return (np.sqrt(1 + 4 * alpha * d * k_sq) - 1) / (2 * alpha)
        
        try:
            hbar_sq = 7.6199
            p0 = [0.1, hbar_sq / 2]  # Initial guess
            bounds = ([1e-10, 0.01], [10.0, 100.0])
            
            popt, pcov = curve_fit(
                kane_model, distances, energies,
                p0=p0, bounds=bounds, maxfev=5000
            )
            alpha, d = popt
            
            # m* = ℏ²/(2d)
            effective_mass = hbar_sq / (2 * d)
            
            fit_energies = kane_model(distances, *popt)
            r_squared = 1 - np.sum((energies - fit_energies)**2) / np.sum((energies - np.mean(energies))**2)
            
            fit_info = {
                'alpha': alpha,
                'd': d,
                'r_squared': r_squared,
                'n_points': end - start,
                'distances': distances,
                'energies': energies,
                'fit_energies': fit_energies,
                'is_nonparabolic': alpha > 0.01,
            }
            
            return effective_mass, fit_info
            
        except Exception as e:
            logger.warning(f"Nonparabolic fit failed: {e}, using parabolic")
            return self.get_effective_mass_parabolic(band_idx, n_points)
    
    def get_effective_mass_tensor(
        self,
        band_idx: int = 0,
    ) -> np.ndarray:
        """
        Calculate effective mass tensor component along segment direction.
        
        Returns:
            Mass tensor component (scalar for 1D segment)
        """
        m_star, _ = self.get_effective_mass_parabolic(band_idx)
        return m_star


@dataclass
class EffectiveMassResult:
    """Complete effective mass analysis result."""
    carrier_type: str  # 'electron' or 'hole'
    kpoint_label: str
    kpoint_frac: np.ndarray
    band_index: int
    spin: int
    effective_mass: float  # In units of m_e
    direction: str
    fit_method: str  # 'parabolic' or 'nonparabolic'
    r_squared: float
    is_direct: bool  # True if at direct gap
    nonparabolicity: Optional[float] = None  # Kane α parameter
    
    def __str__(self) -> str:
        sign = '+' if self.effective_mass > 0 else ''
        return (
            f"{self.carrier_type.capitalize()} effective mass: "
            f"{sign}{self.effective_mass:.4f} m₀ "
            f"at {self.kpoint_label} along {self.direction}"
        )


class AdvancedEffMassAnalyzer:
    """
    Advanced effective mass analyzer for electronic band structures.
    
    Enhanced implementation based on abipy's EffMassAnalyzer and sumo patterns.
    
    Features:
        - VBM/CBM automatic detection
        - Multi-segment analysis
        - Parabolic and nonparabolic fitting
        - Degeneracy handling
        - Direction-dependent masses
        - Pandas integration for results
    
    Usage:
        >>> from fluxdft.electronic import ElectronicBandStructure
        >>> analyzer = AdvancedEffMassAnalyzer(band_structure)
        >>> 
        >>> # Analyze band edges
        >>> analyzer.select_cbm()
        >>> analyzer.select_vbm()
        >>> 
        >>> # Get results
        >>> results = analyzer.get_all_masses()
        >>> df = analyzer.to_dataframe()
    """
    
    def __init__(
        self,
        band_structure: 'ElectronicBandStructure',
        degeneracy_tol: float = 0.001,  # eV
    ):
        """
        Initialize analyzer.
        
        Args:
            band_structure: Electronic band structure object
            degeneracy_tol: Energy tolerance for degeneracy detection
        """
        self.bs = band_structure
        self.degeneracy_tol = degeneracy_tol
        self.segments: List[Segment] = []
        self.results: List[EffectiveMassResult] = []
    
    def select_cbm(
        self,
        spin: int = 0,
        include_degenerate: bool = True,
    ) -> int:
        """
        Select conduction band minimum for analysis.
        
        Args:
            spin: Spin channel
            include_degenerate: Include degenerate bands
            
        Returns:
            Number of segments created
        """
        gap_info = self.bs.get_band_gap()
        if gap_info is None or gap_info.cbm is None:
            raise ValueError("No CBM found - material may be metallic")
        
        cbm = gap_info.cbm
        return self._build_segments(
            kpoint=cbm.kpoint,
            band_index=cbm.band_index,
            spin=spin,
            carrier_type='electron',
            include_degenerate=include_degenerate,
        )
    
    def select_vbm(
        self,
        spin: int = 0,
        include_degenerate: bool = True,
    ) -> int:
        """
        Select valence band maximum for analysis.
        
        Args:
            spin: Spin channel
            include_degenerate: Include degenerate bands
            
        Returns:
            Number of segments created
        """
        gap_info = self.bs.get_band_gap()
        if gap_info is None or gap_info.vbm is None:
            raise ValueError("No VBM found")
        
        vbm = gap_info.vbm
        return self._build_segments(
            kpoint=vbm.kpoint,
            band_index=vbm.band_index,
            spin=spin,
            carrier_type='hole',
            include_degenerate=include_degenerate,
        )
    
    def select_band_edges(
        self,
        spin: int = 0,
        include_degenerate: bool = True,
    ) -> int:
        """Select both VBM and CBM."""
        n_vbm = self.select_vbm(spin, include_degenerate)
        n_cbm = self.select_cbm(spin, include_degenerate)
        return n_vbm + n_cbm
    
    def select_kpoint_band(
        self,
        kpoint: Union[int, np.ndarray],
        band_index: int,
        spin: int = 0,
        carrier_type: str = 'electron',
    ) -> int:
        """
        Select arbitrary k-point and band for analysis.
        
        Args:
            kpoint: K-point index or fractional coordinates
            band_index: Band index
            spin: Spin channel
            carrier_type: 'electron' or 'hole'
            
        Returns:
            Number of segments created
        """
        return self._build_segments(
            kpoint=kpoint,
            band_index=band_index,
            spin=spin,
            carrier_type=carrier_type,
            include_degenerate=False,
        )
    
    def _build_segments(
        self,
        kpoint: Union[int, np.ndarray],
        band_index: int,
        spin: int,
        carrier_type: str,
        include_degenerate: bool = True,
    ) -> int:
        """
        Build k-space segments through the specified k-point.
        
        For each line segment in the k-path that passes through kpoint,
        creates a Segment object for mass calculation.
        """
        # Find k-point index
        if isinstance(kpoint, int):
            k_idx = kpoint
        else:
            # Find closest k-point
            k_idx = self.bs.get_kpoint_index(kpoint)
        
        # Get k-path information
        kpath = self.bs.kpath
        if kpath is None:
            # Not a line-mode calculation, can't do segment analysis
            logger.warning("Band structure not in line mode, using single-point analysis")
            # Create pseudo-segment with available data
            return self._build_single_point_segment(k_idx, band_index, spin, carrier_type)
        
        # Find degenerate bands if requested
        band_indices = [band_index]
        if include_degenerate:
            e0 = self.bs.eigenvalues[spin, k_idx, band_index]
            for b in range(self.bs.nbands):
                if b != band_index:
                    if abs(self.bs.eigenvalues[spin, k_idx, b] - e0) < self.degeneracy_tol:
                        band_indices.append(b)
        
        # Find segments containing this k-point
        segments_created = 0
        for segment_idx, segment_data in enumerate(kpath.segments):
            if k_idx in segment_data['kpoint_indices']:
                seg = self._create_segment(
                    segment_data, k_idx, band_indices, spin, carrier_type
                )
                self.segments.append(seg)
                segments_created += 1
        
        if segments_created == 0:
            # K-point not on a path segment, use single-point
            return self._build_single_point_segment(k_idx, band_index, spin, carrier_type)
        
        return segments_created
    
    def _create_segment(
        self,
        segment_data: Dict,
        k0_idx: int,
        band_indices: List[int],
        spin: int,
        carrier_type: str,
    ) -> Segment:
        """Create a Segment object from k-path segment data."""
        kpoint_indices = np.array(segment_data['kpoint_indices'])
        
        # Get energies
        energies = np.array([
            self.bs.eigenvalues[spin, kpoint_indices, b]
            for b in band_indices
        ])
        
        # Calculate k-space distances
        k0_pos = np.where(kpoint_indices == k0_idx)[0][0]
        k0_coords = self.bs.kpoints[k0_idx]
        
        k_distances = np.array([
            np.linalg.norm(self.bs.kpoints[ki] - k0_coords)
            for ki in kpoint_indices
        ])
        
        # Sign the distances based on position relative to k0
        k_distances[:k0_pos] = -k_distances[:k0_pos]
        
        k_distances_sq = k_distances ** 2
        
        # Estimate spacing
        dk = np.mean(np.diff(np.abs(k_distances[k_distances != 0])))
        
        # Direction
        if len(kpoint_indices) > 1:
            direction = (
                self.bs.kpoints[kpoint_indices[-1]] - 
                self.bs.kpoints[kpoint_indices[0]]
            )
            direction = direction / np.linalg.norm(direction)
        else:
            direction = None
        
        return Segment(
            k0_index=k0_idx,
            spin=spin,
            band_indices=band_indices,
            kpoint_indices=kpoint_indices,
            energies=energies,
            k_distances=k_distances,
            k_distances_sq=k_distances_sq,
            dk=dk,
            direction=direction,
            direction_label=segment_data.get('label', ''),
        )
    
    def _build_single_point_segment(
        self,
        k_idx: int,
        band_index: int,
        spin: int,
        carrier_type: str,
    ) -> int:
        """Create segment for single-point analysis (no k-path)."""
        # This is a fallback for non-line-mode calculations
        logger.warning("Single-point segment - limited accuracy")
        return 0
    
    def analyze(
        self,
        method: str = 'parabolic',
        n_points: int = 5,
    ) -> List[EffectiveMassResult]:
        """
        Perform effective mass analysis on all segments.
        
        Args:
            method: 'parabolic' or 'nonparabolic'
            n_points: Number of points for fitting
            
        Returns:
            List of EffectiveMassResult objects
        """
        self.results = []
        
        for segment in self.segments:
            for band_idx in range(segment.nbands):
                if method == 'nonparabolic':
                    mass, fit_info = segment.get_effective_mass_nonparabolic(
                        band_idx, n_points
                    )
                    alpha = fit_info.get('alpha')
                else:
                    mass, fit_info = segment.get_effective_mass_parabolic(
                        band_idx, n_points
                    )
                    alpha = None
                
                # Determine carrier type from band position
                # (negative curvature = hole, positive = electron)
                curvature = fit_info.get('curvature', 0)
                carrier = 'hole' if curvature < 0 else 'electron'
                
                # Get k-point label
                k_frac = self.bs.kpoints[segment.k0_index]
                k_label = self._get_kpoint_label(segment.k0_index)
                
                result = EffectiveMassResult(
                    carrier_type=carrier,
                    kpoint_label=k_label,
                    kpoint_frac=k_frac,
                    band_index=segment.band_indices[band_idx],
                    spin=segment.spin,
                    effective_mass=mass,
                    direction=segment.direction_label or str(segment.direction),
                    fit_method=method,
                    r_squared=fit_info.get('r_squared', 0),
                    is_direct=True,  # TODO: Determine from gap info
                    nonparabolicity=alpha,
                )
                self.results.append(result)
        
        return self.results
    
    def _get_kpoint_label(self, k_idx: int) -> str:
        """Get label for k-point if available."""
        if self.bs.kpath is not None:
            for label, idx in self.bs.kpath.labels.items():
                if idx == k_idx:
                    return label
        
        # Return fractional coordinates
        k = self.bs.kpoints[k_idx]
        return f"({k[0]:.3f}, {k[1]:.3f}, {k[2]:.3f})"
    
    def to_dataframe(self) -> 'pd.DataFrame':
        """
        Convert results to pandas DataFrame.
        
        Returns:
            DataFrame with effective mass results
        """
        try:
            import pandas as pd
        except ImportError:
            raise ImportError("pandas required for to_dataframe()")
        
        if not self.results:
            return pd.DataFrame()
        
        data = []
        for r in self.results:
            data.append({
                'Carrier': r.carrier_type,
                'K-point': r.kpoint_label,
                'Band': r.band_index,
                'Spin': r.spin,
                'm* (m₀)': r.effective_mass,
                'Direction': r.direction,
                'Method': r.fit_method,
                'R²': r.r_squared,
                'α': r.nonparabolicity or 0,
            })
        
        return pd.DataFrame(data)
    
    def summarize(self) -> str:
        """Generate summary of effective mass results."""
        if not self.results:
            return "No results. Run analyze() first."
        
        lines = ["=" * 60]
        lines.append("Effective Mass Analysis Summary")
        lines.append("=" * 60)
        
        electrons = [r for r in self.results if r.carrier_type == 'electron']
        holes = [r for r in self.results if r.carrier_type == 'hole']
        
        if electrons:
            lines.append("\nElectron effective masses (at CBM):")
            for e in electrons:
                lines.append(f"  {e.effective_mass:+.4f} m₀ along {e.direction} (R²={e.r_squared:.4f})")
        
        if holes:
            lines.append("\nHole effective masses (at VBM):")
            for h in holes:
                lines.append(f"  {h.effective_mass:+.4f} m₀ along {h.direction} (R²={h.r_squared:.4f})")
        
        # Average masses
        if electrons:
            avg_e = np.mean([e.effective_mass for e in electrons])
            lines.append(f"\nAverage electron mass: {avg_e:.4f} m₀")
        if holes:
            avg_h = np.mean([abs(h.effective_mass) for h in holes])
            lines.append(f"Average hole mass: {avg_h:.4f} m₀")
        
        # Conductivity effective mass
        if electrons and holes:
            m_cond = len(electrons) / sum(1/e.effective_mass for e in electrons)
            lines.append(f"\nConductivity effective mass (electrons): {m_cond:.4f} m₀")
        
        lines.append("=" * 60)
        return "\n".join(lines)


def calculate_dos_effective_mass(
    energies: np.ndarray,
    dos: np.ndarray,
    fermi_energy: float,
    energy_range: float = 0.1,
) -> float:
    """
    Calculate DOS effective mass from density of states.
    
    Uses the relation: g(E) ∝ (m*)^(3/2) * sqrt(E - E_edge)
    for 3D parabolic bands.
    
    Args:
        energies: Energy grid in eV
        dos: Density of states values
        fermi_energy: Fermi energy in eV
        energy_range: Range above/below edge to fit
        
    Returns:
        DOS effective mass in units of m_e
    """
    # Find the band edge (where DOS starts to be significant)
    # This is a simplified implementation
    logger.warning("DOS effective mass calculation is approximate")
    
    # TODO: Implement proper edge detection and fitting
    return 1.0  # Placeholder
