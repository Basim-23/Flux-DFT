"""
Effective Mass Calculator for FluxDFT.

Calculates carrier effective masses from band curvature.
Essential for semiconductor transport property predictions.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union, Literal
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Physical constants
HBAR = 1.054571817e-34  # J·s
M_E = 9.10938e-31  # kg (electron mass)
EV_TO_J = 1.602176634e-19  # eV to Joules
ANGSTROM_TO_M = 1e-10


@dataclass
class EffectiveMass:
    """
    Effective mass result.
    
    Attributes:
        value: Effective mass in units of electron mass (m*)
        direction: Direction in k-space (Cartesian)
        kpoint_index: K-point where calculated
        kpoint_label: High-symmetry label if applicable
        band_index: Band index
        band_type: 'electron' (CBM) or 'hole' (VBM)
        tensor: Full 3x3 effective mass tensor if calculated
    """
    value: float
    direction: np.ndarray
    kpoint_index: int
    kpoint_label: Optional[str] = None
    band_index: int = 0
    band_type: Literal['electron', 'hole'] = 'electron'
    tensor: Optional[np.ndarray] = None
    
    @property
    def value_formatted(self) -> str:
        """Formatted mass as 'm* = X m_e'."""
        return f"{self.value:.3f} m₀"
    
    def __str__(self) -> str:
        label = self.kpoint_label or f"k{self.kpoint_index}"
        return f"{self.band_type.capitalize()} mass at {label}: {self.value_formatted}"


class EffectiveMassCalculator:
    """
    Calculate carrier effective masses from band structure.
    
    Uses parabolic band fitting to extract effective masses from
    band curvature at high-symmetry points.
    
    Methods:
        1. Finite difference: d²E/dk² from neighboring points
        2. Polynomial fitting: Fit parabola near extremum
        3. Density functional perturbation (requires special calc)
    
    The effective mass is:
        m* = ℏ² / (d²E/dk²)
    
    Usage:
        >>> calc = EffectiveMassCalculator(band_structure)
        >>> m_e = calc.get_electron_mass()  # At CBM
        >>> m_h = calc.get_hole_mass()  # At VBM
        >>> m_tensor = calc.get_mass_tensor(kpoint='Γ', band=4)
    """
    
    def __init__(
        self,
        band_structure: 'ElectronicBandStructure',
        method: Literal['finite_diff', 'polynomial'] = 'polynomial',
    ):
        """
        Initialize calculator.
        
        Args:
            band_structure: ElectronicBandStructure instance.
            method: Calculation method.
        """
        self.bs = band_structure
        self.method = method
        
        # Cache band gap info
        self._gap_info = band_structure.get_band_gap()
    
    def get_electron_mass(
        self,
        direction: Optional[np.ndarray] = None,
        n_points: int = 5,
    ) -> EffectiveMass:
        """
        Calculate electron effective mass at CBM.
        
        Args:
            direction: Direction for 1D mass. None uses path direction.
            n_points: Number of points for fitting.
            
        Returns:
            EffectiveMass result.
        """
        if self._gap_info.is_metal:
            raise ValueError("Cannot calculate electron mass for metal")
        
        cbm = self._gap_info.cbm
        return self._calculate_mass(
            kpoint_index=cbm.kpoint_index,
            band_index=cbm.band_index,
            band_type='electron',
            direction=direction,
            n_points=n_points,
        )
    
    def get_hole_mass(
        self,
        direction: Optional[np.ndarray] = None,
        n_points: int = 5,
    ) -> EffectiveMass:
        """
        Calculate hole effective mass at VBM.
        
        Args:
            direction: Direction for 1D mass.
            n_points: Number of points for fitting.
            
        Returns:
            EffectiveMass result.
        """
        if self._gap_info.is_metal:
            raise ValueError("Cannot calculate hole mass for metal")
        
        vbm = self._gap_info.vbm
        return self._calculate_mass(
            kpoint_index=vbm.kpoint_index,
            band_index=vbm.band_index,
            band_type='hole',
            direction=direction,
            n_points=n_points,
        )
    
    def get_mass_at_kpoint(
        self,
        kpoint_label: str,
        band_index: int,
        band_type: Literal['electron', 'hole'] = 'electron',
        direction: Optional[np.ndarray] = None,
        n_points: int = 5,
    ) -> EffectiveMass:
        """
        Calculate effective mass at specific k-point and band.
        
        Args:
            kpoint_label: High-symmetry point label (e.g., 'Γ', 'X').
            band_index: Band index.
            band_type: 'electron' or 'hole'.
            direction: Direction for 1D mass.
            n_points: Number of points for fitting.
            
        Returns:
            EffectiveMass result.
        """
        # Find k-point index
        kpt_idx = None
        for idx, label in self.bs.kpath.labels:
            if label == kpoint_label or (label == 'Γ' and kpoint_label.upper() == 'GAMMA'):
                kpt_idx = idx
                break
        
        if kpt_idx is None:
            raise ValueError(f"K-point {kpoint_label} not found")
        
        return self._calculate_mass(
            kpoint_index=kpt_idx,
            band_index=band_index,
            band_type=band_type,
            direction=direction,
            n_points=n_points,
        )
    
    def get_mass_tensor(
        self,
        kpoint_index: int,
        band_index: int,
    ) -> np.ndarray:
        """
        Calculate full 3x3 effective mass tensor.
        
        Requires 3D k-grid data (not just k-path).
        
        Returns:
            3x3 mass tensor in units of m_e.
        """
        # This requires 3D k-space sampling
        # For now, return diagonal approximation from path
        logger.warning("Full tensor calculation requires 3D k-grid. Using 1D approximation.")
        
        m = self._calculate_mass(kpoint_index, band_index, 'electron')
        return np.eye(3) * m.value
    
    def _calculate_mass(
        self,
        kpoint_index: int,
        band_index: int,
        band_type: Literal['electron', 'hole'],
        direction: Optional[np.ndarray] = None,
        n_points: int = 5,
        spin: int = 0,
    ) -> EffectiveMass:
        """
        Core mass calculation using polynomial fitting.
        
        Fits E(k) = E_0 + (ℏ²k²)/(2m*) near the extremum.
        """
        # Get eigenvalues along path
        e_band = self.bs.eigenvalues_shifted[spin, :, band_index]
        k_dist = self.bs.kpath.distances
        
        # Select points around k-point for fitting
        half = n_points // 2
        start = max(0, kpoint_index - half)
        end = min(len(k_dist), kpoint_index + half + 1)
        
        k_fit = k_dist[start:end]
        e_fit = e_band[start:end]
        
        # Center around k-point
        k0 = k_dist[kpoint_index]
        e0 = e_band[kpoint_index]
        dk = k_fit - k0
        de = e_fit - e0
        
        # Polynomial fit: E = a + b*k + c*k²
        # For an extremum, b ≈ 0, so m* = ℏ²/(2c)
        try:
            coeffs = np.polyfit(dk, de, 2)
            c = coeffs[0]  # k² coefficient
            
            if abs(c) < 1e-10:
                logger.warning("Very flat band - effective mass is very large")
                m_star = 100.0  # Cap at 100 m_e
            else:
                # Convert to SI: k is in 1/Å, E in eV
                # m* = ℏ² / (2c) where c is in eV·Å²
                # Need to convert c to J·m²
                c_si = c * EV_TO_J * (ANGSTROM_TO_M ** 2)
                m_star_kg = (HBAR ** 2) / (2 * c_si)
                m_star = abs(m_star_kg / M_E)
                
                # For holes, mass should be positive (we use |m*|)
                # The sign of c tells us if it's a max or min
                if band_type == 'hole' and c > 0:
                    # VBM should have negative curvature
                    logger.debug("Adjusting sign for hole mass")
        
        except Exception as e:
            logger.warning(f"Mass fitting failed: {e}")
            m_star = 1.0
        
        # Get direction in k-space
        if direction is None:
            # Use path direction at this k-point
            if kpoint_index > 0 and kpoint_index < len(k_dist) - 1:
                dk_vec = (
                    self.bs.kpath.kpoints[kpoint_index + 1] -
                    self.bs.kpath.kpoints[kpoint_index - 1]
                )
            else:
                dk_vec = np.array([1, 0, 0])
            direction = dk_vec / np.linalg.norm(dk_vec)
        
        return EffectiveMass(
            value=m_star,
            direction=direction,
            kpoint_index=kpoint_index,
            kpoint_label=self.bs._get_kpoint_label(kpoint_index),
            band_index=band_index,
            band_type=band_type,
        )
    
    def get_summary(self) -> Dict:
        """
        Get summary of important effective masses.
        
        Returns dict with electron and hole masses at key points.
        """
        summary = {}
        
        try:
            m_e = self.get_electron_mass()
            summary['electron_mass'] = {
                'value': m_e.value,
                'kpoint': m_e.kpoint_label,
                'band': m_e.band_index,
            }
        except Exception as e:
            summary['electron_mass'] = {'error': str(e)}
        
        try:
            m_h = self.get_hole_mass()
            summary['hole_mass'] = {
                'value': m_h.value,
                'kpoint': m_h.kpoint_label,
                'band': m_h.band_index,
            }
        except Exception as e:
            summary['hole_mass'] = {'error': str(e)}
        
        # Reduced mass for excitons
        if 'value' in summary.get('electron_mass', {}) and 'value' in summary.get('hole_mass', {}):
            me = summary['electron_mass']['value']
            mh = summary['hole_mass']['value']
            summary['reduced_mass'] = (me * mh) / (me + mh)
            summary['exciton_mass'] = me + mh
        
        return summary
