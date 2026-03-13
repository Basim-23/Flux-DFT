"""
Density of States Analysis for FluxDFT.

Comprehensive DOS container with total, partial, and projected DOS
analysis capabilities.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class OrbitalProjection:
    """
    Orbital projection information.
    
    Attributes:
        element: Element symbol
        orbital: Orbital type (s, p, d, f)
        angular_momentum: l quantum number
        densities: DOS values (n_energies,) or (2, n_energies) for spin
    """
    element: str
    orbital: str
    angular_momentum: int
    densities: np.ndarray
    site_index: Optional[int] = None
    
    @property
    def label(self) -> str:
        if self.site_index is not None:
            return f"{self.element}{self.site_index}-{self.orbital}"
        return f"{self.element}-{self.orbital}"
    
    @property
    def is_spin_polarized(self) -> bool:
        return self.densities.ndim == 2 and self.densities.shape[0] == 2


class ProjectedDOS:
    """
    Container for projected density of states (PDOS).
    
    Stores DOS projections onto atomic orbitals.
    """
    
    def __init__(
        self,
        energies: np.ndarray,
        projections: List[OrbitalProjection],
        fermi_energy: float,
    ):
        """
        Initialize projected DOS.
        
        Args:
            energies: Energy grid in eV.
            projections: List of orbital projections.
            fermi_energy: Fermi energy in eV.
        """
        self.energies = np.asarray(energies)
        self.projections = projections
        self.fermi_energy = float(fermi_energy)
    
    @property
    def energies_shifted(self) -> np.ndarray:
        """Energies relative to Fermi level."""
        return self.energies - self.fermi_energy
    
    def get_element_dos(self, element: str) -> np.ndarray:
        """Sum all orbital projections for an element."""
        total = None
        for proj in self.projections:
            if proj.element == element:
                if total is None:
                    total = proj.densities.copy()
                else:
                    total += proj.densities
        return total if total is not None else np.zeros_like(self.energies)
    
    def get_orbital_dos(self, orbital: str) -> np.ndarray:
        """Sum all element projections for an orbital type."""
        total = None
        for proj in self.projections:
            if proj.orbital == orbital:
                if total is None:
                    total = proj.densities.copy()
                else:
                    total += proj.densities
        return total if total is not None else np.zeros_like(self.energies)
    
    def get_site_dos(self, site_index: int) -> np.ndarray:
        """Sum all orbital projections for a specific site."""
        total = None
        for proj in self.projections:
            if proj.site_index == site_index:
                if total is None:
                    total = proj.densities.copy()
                else:
                    total += proj.densities
        return total if total is not None else np.zeros_like(self.energies)
    
    def get_projection(self, label: str) -> Optional[np.ndarray]:
        """Get specific projection by label (e.g., 'Si-p', 'O-s')."""
        for proj in self.projections:
            if proj.label == label:
                return proj.densities
        return None
    
    @property
    def elements(self) -> List[str]:
        """List of unique elements."""
        return list(set(p.element for p in self.projections))
    
    @property
    def orbitals(self) -> List[str]:
        """List of unique orbital types."""
        return list(set(p.orbital for p in self.projections))


class ElectronicDOS:
    """
    Comprehensive electronic density of states container.
    
    Provides total and projected DOS with analysis methods.
    
    Features:
        - Total DOS (spin-resolved)
        - Projected DOS (element, orbital, site)
        - Fermi level alignment
        - Integration (electron count)
        - Band center calculation
        - Export capabilities
        
    Usage:
        >>> dos = ElectronicDOS.from_qe_output("dos.dat", "pdos.dat")
        >>> total = dos.get_total()
        >>> si_p = dos.get_pdos("Si", "p")
        >>> fig = dos.plot()
    """
    
    def __init__(
        self,
        energies: np.ndarray,
        total_dos: np.ndarray,
        fermi_energy: float,
        pdos: Optional[ProjectedDOS] = None,
        integrated_dos: Optional[np.ndarray] = None,
        metadata: Optional[Dict] = None,
    ):
        """
        Initialize electronic DOS.
        
        Args:
            energies: Energy grid in eV (n_energies,).
            total_dos: Total DOS values.
                Shape: (n_energies,) or (2, n_energies) for spin-polarized
            fermi_energy: Fermi energy in eV.
            pdos: Optional projected DOS.
            integrated_dos: Optional integrated DOS (electron count).
            metadata: Additional metadata.
        """
        self.energies = np.asarray(energies)
        
        total_dos = np.asarray(total_dos)
        if total_dos.ndim == 1:
            self._total_dos = total_dos[np.newaxis, :]
        else:
            self._total_dos = total_dos
        
        self.fermi_energy = float(fermi_energy)
        self.pdos = pdos
        self.integrated_dos = integrated_dos
        self.metadata = metadata or {}
    
    @property
    def n_energies(self) -> int:
        return len(self.energies)
    
    @property
    def is_spin_polarized(self) -> bool:
        return self._total_dos.shape[0] == 2
    
    @property
    def energies_shifted(self) -> np.ndarray:
        """Energies relative to Fermi level."""
        return self.energies - self.fermi_energy
    
    def get_total(self, spin: Optional[int] = None) -> np.ndarray:
        """
        Get total DOS.
        
        Args:
            spin: Spin channel (0 or 1). None returns sum.
            
        Returns:
            DOS values.
        """
        if spin is not None:
            return self._total_dos[spin]
        return np.sum(self._total_dos, axis=0)
    
    def get_in_range(
        self,
        emin: float,
        emax: float,
        relative_to_fermi: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Get DOS in energy range.
        
        Returns:
            (energies, dos) in the specified range.
        """
        if relative_to_fermi:
            e = self.energies_shifted
        else:
            e = self.energies
        
        mask = (e >= emin) & (e <= emax)
        return e[mask], self.get_total()[mask]
    
    def integrate(
        self,
        emin: float,
        emax: float,
        relative_to_fermi: bool = True,
    ) -> float:
        """
        Integrate DOS in energy range (electron count).
        
        Args:
            emin: Lower energy bound.
            emax: Upper energy bound.
            relative_to_fermi: If True, bounds are relative to Ef.
            
        Returns:
            Number of electrons in range.
        """
        e, dos = self.get_in_range(emin, emax, relative_to_fermi)
        if len(e) < 2:
            return 0.0
        return np.trapz(dos, e)
    
    def get_band_center(
        self,
        orbital: Optional[str] = None,
        element: Optional[str] = None,
        emin: float = -10.0,
        emax: float = 0.0,
    ) -> float:
        """
        Calculate band center (first moment of DOS).
        
        The d-band center model is important for catalysis predictions.
        
        Args:
            orbital: Specific orbital (e.g., 'd').
            element: Specific element.
            emin: Lower energy bound (relative to Ef).
            emax: Upper energy bound (relative to Ef).
            
        Returns:
            Band center in eV relative to Fermi level.
        """
        e = self.energies_shifted
        mask = (e >= emin) & (e <= emax)
        e_range = e[mask]
        
        # Get appropriate DOS
        if orbital and element and self.pdos:
            dos = self.pdos.get_projection(f"{element}-{orbital}")
            if dos is None:
                dos = self.get_total()[mask]
            else:
                dos = dos[mask] if dos.ndim == 1 else dos[0][mask]
        elif element and self.pdos:
            dos = self.pdos.get_element_dos(element)[mask]
        elif orbital and self.pdos:
            dos = self.pdos.get_orbital_dos(orbital)[mask]
        else:
            dos = self.get_total()[mask]
        
        # First moment
        if np.sum(dos) == 0:
            return 0.0
        return np.sum(e_range * dos) / np.sum(dos)
    
    def get_d_band_center(self, element: Optional[str] = None) -> float:
        """
        Calculate d-band center for catalysis analysis.
        
        Args:
            element: Specific transition metal element.
            
        Returns:
            d-band center in eV relative to Fermi level.
        """
        return self.get_band_center(orbital='d', element=element)
    
    def get_fermi_level_dos(self) -> float:
        """Get DOS value at Fermi level (N(Ef))."""
        # Find closest energy point to Ef
        idx = np.argmin(np.abs(self.energies_shifted))
        return self.get_total()[idx]
    
    def to_dict(self) -> Dict:
        """Serialize to dictionary."""
        return {
            'energies': self.energies.tolist(),
            'total_dos': self._total_dos.tolist(),
            'fermi_energy': self.fermi_energy,
            'is_spin_polarized': self.is_spin_polarized,
            'metadata': self.metadata,
        }
    
    @classmethod
    def from_pymatgen(
        cls,
        dos: 'CompleteDos',
    ) -> 'ElectronicDOS':
        """
        Create from pymatgen CompleteDos.
        
        Args:
            dos: pymatgen CompleteDos object.
            
        Returns:
            ElectronicDOS instance.
        """
        from pymatgen.electronic_structure.core import Spin, OrbitalType
        
        energies = dos.energies
        fermi = dos.efermi
        
        # Get total DOS
        densities = dos.get_densities()
        if isinstance(densities, dict):
            if Spin.up in densities:
                total_dos = np.array([densities[Spin.up], densities[Spin.down]])
            else:
                total_dos = np.array(list(densities.values())[0])
        else:
            total_dos = np.array(densities)
        
        # Get PDOS
        projections = []
        if hasattr(dos, 'pdos'):
            for site, site_pdos in dos.pdos.items():
                element = site.specie.symbol
                site_idx = site.index if hasattr(site, 'index') else None
                
                for orbital, orbital_dos in site_pdos.items():
                    orb_densities = orbital_dos.get_densities()
                    if isinstance(orb_densities, dict):
                        orb_densities = np.array([orb_densities[Spin.up], orb_densities[Spin.down]])
                    else:
                        orb_densities = np.array(orb_densities)
                    
                    # Map orbital to l quantum number
                    l_map = {'s': 0, 'p': 1, 'd': 2, 'f': 3}
                    orb_name = str(orbital).lower()[0]
                    l = l_map.get(orb_name, 0)
                    
                    projections.append(OrbitalProjection(
                        element=element,
                        orbital=orb_name,
                        angular_momentum=l,
                        densities=orb_densities,
                        site_index=site_idx,
                    ))
        
        pdos = ProjectedDOS(energies, projections, fermi) if projections else None
        
        return cls(
            energies=energies,
            total_dos=total_dos,
            fermi_energy=fermi,
            pdos=pdos,
        )
    
    @classmethod
    def from_qe_output(
        cls,
        dos_file: Union[str, Path],
        pdos_files: Optional[List[Union[str, Path]]] = None,
        fermi_energy: Optional[float] = None,
    ) -> 'ElectronicDOS':
        """
        Create from Quantum ESPRESSO dos.x output (formatted dos).
        
        Args:
            dos_file: Path to dos_file (e.g. pwscf.dos).
            pdos_files: Optional list of pdos files (not fully supported yet).
            fermi_energy: Fermi energy in eV.
            
        Returns:
            ElectronicDOS instance.
        """
        from ..io.qe_output import QEDosParser
        
        try:
            data = QEDosParser.parse(dos_file)
        except Exception as e:
            logger.error(f"Failed to parse DOS file: {e}")
            raise
            
        # Determine total DOS shape (1 or 2 rows for spin)
        if data.dos_down is not None:
             total_dos = np.vstack([data.dos_up, data.dos_down])
        else:
             total_dos = data.dos_up
             
        # Use provided Ef or fallback (dos.dat header parsing is fragile)
        ef = fermi_energy if fermi_energy is not None else (data.fermi_energy or 0.0)
        
        return cls(
            energies=data.energies,
            total_dos=total_dos,
            fermi_energy=ef,
            integrated_dos=data.integrated_dos,
            # PDOS parsing from separate *pdos* files requires filename parsing logic 
            # (e.g. prefix.pdos_atm#1(Si)_wfc#1(s)) which is best handled by a dedicated PDOS aggregator.
            pdos=None 
        )
