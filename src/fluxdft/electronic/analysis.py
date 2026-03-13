"""
Electronic Structure Analyzer for FluxDFT.

High-level analysis combining band structure, DOS, and derived properties.
Provides carrier concentration, conductivity estimation, and optical properties.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import logging

from .band_structure import ElectronicBandStructure, BandGapInfo
from .dos import ElectronicDOS
from .effective_mass import EffectiveMassCalculator, EffectiveMass

logger = logging.getLogger(__name__)

# Physical constants
KB = 8.617333262e-5  # eV/K (Boltzmann constant)
HBAR = 6.582119569e-16  # eV·s
M_E = 9.10938e-31  # kg
EV_TO_J = 1.602176634e-19


@dataclass
class CarrierConcentration:
    """
    Carrier concentration results.
    
    Attributes:
        n_electrons: Electron concentration (cm⁻³)
        n_holes: Hole concentration (cm⁻³)
        temperature: Temperature in K
        fermi_level: Fermi level position relative to VBM
        intrinsic: Whether calculation is for intrinsic semiconductor
    """
    n_electrons: float
    n_holes: float
    temperature: float
    fermi_level: float
    intrinsic: bool = True
    
    @property
    def carrier_type(self) -> str:
        """Determine dominant carrier type."""
        if abs(self.n_electrons - self.n_holes) < 1e10:
            return "intrinsic"
        return "n-type" if self.n_electrons > self.n_holes else "p-type"
    
    @property
    def net_concentration(self) -> float:
        """Net carrier concentration (|n - p|)."""
        return abs(self.n_electrons - self.n_holes)
    
    def __str__(self) -> str:
        return (
            f"Carrier Concentration at {self.temperature} K:\n"
            f"  n = {self.n_electrons:.2e} cm⁻³\n"
            f"  p = {self.n_holes:.2e} cm⁻³\n"
            f"  Type: {self.carrier_type}"
        )


@dataclass
class TransportProperties:
    """
    Estimated transport properties.
    
    All values are rough estimates based on band structure alone.
    For accurate transport, use BoltzTraP2 or similar.
    """
    electron_mobility: Optional[float] = None  # cm²/V·s
    hole_mobility: Optional[float] = None
    conductivity: Optional[float] = None  # S/cm
    seebeck_coefficient: Optional[float] = None  # µV/K
    thermal_conductivity: Optional[float] = None  # W/m·K


class ElectronicStructureAnalyzer:
    """
    Comprehensive electronic structure analysis.
    
    Combines band structure and DOS analysis to provide:
    - Band gap analysis
    - Effective masses
    - Carrier concentrations
    - Transport property estimates
    - Optical absorption onset
    - Comparison with reference data
    
    Usage:
        >>> analyzer = ElectronicStructureAnalyzer(
        ...     band_structure=bs,
        ...     dos=dos,
        ... )
        >>> print(analyzer.get_summary())
        >>> carriers = analyzer.get_carrier_concentration(T=300)
    """
    
    def __init__(
        self,
        band_structure: Optional[ElectronicBandStructure] = None,
        dos: Optional[ElectronicDOS] = None,
        structure: Optional['Structure'] = None,
    ):
        """
        Initialize analyzer.
        
        Args:
            band_structure: ElectronicBandStructure instance.
            dos: ElectronicDOS instance.
            structure: pymatgen Structure for volume calculations.
        """
        self.bs = band_structure
        self.dos = dos
        self.structure = structure
        
        # Initialize sub-analyzers
        self._mass_calc = None
        if self.bs:
            self._mass_calc = EffectiveMassCalculator(self.bs)
    
    def get_band_gap(self) -> Optional[BandGapInfo]:
        """Get band gap information."""
        if self.bs:
            return self.bs.get_band_gap()
        return None
    
    def get_effective_masses(self) -> Dict[str, EffectiveMass]:
        """
        Get electron and hole effective masses.
        
        Returns:
            Dict with 'electron' and 'hole' keys.
        """
        if not self._mass_calc:
            return {}
        
        result = {}
        try:
            result['electron'] = self._mass_calc.get_electron_mass()
        except Exception as e:
            logger.warning(f"Could not calculate electron mass: {e}")
        
        try:
            result['hole'] = self._mass_calc.get_hole_mass()
        except Exception as e:
            logger.warning(f"Could not calculate hole mass: {e}")
        
        return result
    
    def get_carrier_concentration(
        self,
        temperature: float = 300.0,
        n_doping: float = 0.0,
        p_doping: float = 0.0,
    ) -> CarrierConcentration:
        """
        Calculate carrier concentration.
        
        Uses effective mass approximation:
        n = Nc * exp(-(Ec - Ef)/kT)
        p = Nv * exp(-(Ef - Ev)/kT)
        
        Args:
            temperature: Temperature in K.
            n_doping: Donor concentration (cm⁻³).
            p_doping: Acceptor concentration (cm⁻³).
            
        Returns:
            CarrierConcentration result.
        """
        gap = self.get_band_gap()
        if gap is None or gap.is_metal:
            return CarrierConcentration(
                n_electrons=1e22,  # Metal-like
                n_holes=1e22,
                temperature=temperature,
                fermi_level=0,
                intrinsic=True,
            )
        
        masses = self.get_effective_masses()
        me_star = masses.get('electron')
        mh_star = masses.get('hole')
        
        # Use default masses if not available
        me = me_star.value if me_star else 1.0
        mh = mh_star.value if mh_star else 1.0
        
        Eg = gap.energy
        kT = KB * temperature
        
        # Effective density of states
        # Nc = 2 * (2π * me* * kT / h²)^(3/2)
        prefactor = 2.5e19  # Approximate prefactor in cm⁻³
        Nc = prefactor * (me * temperature / 300) ** 1.5
        Nv = prefactor * (mh * temperature / 300) ** 1.5
        
        if n_doping == 0 and p_doping == 0:
            # Intrinsic semiconductor
            # Ef is at midgap (approximately)
            Ef = Eg / 2 + 0.75 * kT * np.log(mh / me)
            
            n = Nc * np.exp(-Eg / (2 * kT))
            p = Nv * np.exp(-Eg / (2 * kT))
            
            intrinsic = True
        else:
            # Extrinsic - approximate Fermi level
            Net_doping = n_doping - p_doping
            if Net_doping > 0:
                # n-type
                n = Net_doping
                p = (Nc * Nv) * np.exp(-Eg / kT) / n
                Ef = Eg - kT * np.log(Nc / n)
            else:
                # p-type
                p = -Net_doping
                n = (Nc * Nv) * np.exp(-Eg / kT) / p
                Ef = kT * np.log(Nv / p)
            
            intrinsic = False
        
        return CarrierConcentration(
            n_electrons=n,
            n_holes=p,
            temperature=temperature,
            fermi_level=Ef,
            intrinsic=intrinsic,
        )
    
    def get_dos_at_fermi(self) -> float:
        """Get density of states at Fermi level (N(Ef))."""
        if self.dos:
            return self.dos.get_fermi_level_dos()
        return 0.0
    
    def get_d_band_center(self, element: Optional[str] = None) -> Optional[float]:
        """Get d-band center for catalysis analysis."""
        if self.dos:
            return self.dos.get_d_band_center(element)
        return None
    
    def estimate_optical_gap(self) -> Optional[float]:
        """
        Estimate optical (direct) gap.
        
        For indirect gap materials, returns the direct gap
        which is relevant for optical absorption onset.
        """
        gap = self.get_band_gap()
        if gap is None:
            return None
        
        if gap.is_metal:
            return 0.0
        
        if gap.direct_gap is not None:
            return gap.direct_gap
        return gap.energy
    
    def get_summary(self) -> Dict:
        """
        Get comprehensive analysis summary.
        
        Returns dict with all calculated properties.
        """
        summary = {
            'band_gap': None,
            'effective_masses': {},
            'carrier_concentration': None,
            'dos_at_fermi': None,
            'd_band_center': None,
            'optical_gap': None,
        }
        
        # Band gap
        gap = self.get_band_gap()
        if gap:
            summary['band_gap'] = {
                'type': gap.gap_type.value,
                'energy': gap.energy,
                'is_metal': gap.is_metal,
            }
            if gap.vbm:
                summary['band_gap']['vbm'] = {
                    'energy': gap.vbm.energy,
                    'kpoint': gap.vbm.kpoint_label,
                }
            if gap.cbm:
                summary['band_gap']['cbm'] = {
                    'energy': gap.cbm.energy,
                    'kpoint': gap.cbm.kpoint_label,
                }
        
        # Effective masses
        masses = self.get_effective_masses()
        for carrier, mass in masses.items():
            summary['effective_masses'][carrier] = {
                'value': mass.value,
                'kpoint': mass.kpoint_label,
            }
        
        # Carrier concentration at 300K
        try:
            carriers = self.get_carrier_concentration(300)
            summary['carrier_concentration'] = {
                'n': carriers.n_electrons,
                'p': carriers.n_holes,
                'type': carriers.carrier_type,
                'temperature': 300,
            }
        except Exception as e:
            logger.debug(f"Carrier concentration failed: {e}")
        
        # DOS properties
        summary['dos_at_fermi'] = self.get_dos_at_fermi()
        summary['d_band_center'] = self.get_d_band_center()
        summary['optical_gap'] = self.estimate_optical_gap()
        
        return summary
    
    def compare_with_reference(
        self,
        reference: 'ElectronicStructureAnalyzer',
    ) -> Dict:
        """
        Compare with reference calculation.
        
        Args:
            reference: Another analyzer for comparison.
            
        Returns:
            Dict with differences.
        """
        this = self.get_summary()
        ref = reference.get_summary()
        
        comparison = {}
        
        # Band gap difference
        if this['band_gap'] and ref['band_gap']:
            this_gap = this['band_gap']['energy']
            ref_gap = ref['band_gap']['energy']
            comparison['band_gap_diff'] = this_gap - ref_gap
            comparison['band_gap_percent_diff'] = (
                100 * (this_gap - ref_gap) / ref_gap if ref_gap > 0 else None
            )
        
        # Mass differences
        for carrier in ['electron', 'hole']:
            if carrier in this['effective_masses'] and carrier in ref['effective_masses']:
                this_m = this['effective_masses'][carrier]['value']
                ref_m = ref['effective_masses'][carrier]['value']
                comparison[f'{carrier}_mass_diff'] = this_m - ref_m
        
        return comparison
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return self.get_summary()
    
    def generate_report(self) -> str:
        """
        Generate human-readable analysis report.
        
        Returns:
            Markdown-formatted report string.
        """
        summary = self.get_summary()
        
        lines = ["# Electronic Structure Analysis Report\n"]
        
        # Band gap section
        lines.append("## Band Gap\n")
        if summary['band_gap']:
            gap = summary['band_gap']
            if gap['is_metal']:
                lines.append("**Metallic** (no band gap)\n")
            else:
                lines.append(f"**{gap['type'].capitalize()} Gap**: {gap['energy']:.3f} eV\n")
                if 'vbm' in gap:
                    lines.append(f"- VBM: {gap['vbm']['energy']:.3f} eV at {gap['vbm']['kpoint']}\n")
                if 'cbm' in gap:
                    lines.append(f"- CBM: {gap['cbm']['energy']:.3f} eV at {gap['cbm']['kpoint']}\n")
        else:
            lines.append("*No band structure data available*\n")
        
        # Effective masses
        lines.append("\n## Effective Masses\n")
        if summary['effective_masses']:
            for carrier, data in summary['effective_masses'].items():
                lines.append(f"- **{carrier.capitalize()}**: {data['value']:.3f} m₀ at {data['kpoint']}\n")
        else:
            lines.append("*Not calculated*\n")
        
        # Carrier concentration
        lines.append("\n## Carrier Concentration (300 K)\n")
        if summary['carrier_concentration']:
            cc = summary['carrier_concentration']
            lines.append(f"- n = {cc['n']:.2e} cm⁻³\n")
            lines.append(f"- p = {cc['p']:.2e} cm⁻³\n")
            lines.append(f"- Type: {cc['type']}\n")
        
        # DOS properties
        lines.append("\n## DOS Properties\n")
        if summary['dos_at_fermi'] is not None:
            lines.append(f"- N(Eₓ) = {summary['dos_at_fermi']:.3f} states/eV\n")
        if summary['d_band_center'] is not None:
            lines.append(f"- d-band center = {summary['d_band_center']:.3f} eV\n")
        
        return ''.join(lines)
