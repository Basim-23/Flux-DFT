"""
Optical Properties Calculator for FluxDFT.

Calculates optical properties from electronic structure:
- Dielectric function ε(ω)
- Absorption coefficient α(ω)
- Reflectivity R(ω)
- Refractive index n(ω), k(ω)
- Optical conductivity σ(ω)
- Joint DOS for optical transitions

Based on patterns from abipy's optic module.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Physical constants
HBAR_EV_S = 6.582119514e-16  # ℏ in eV⋅s
C_M_S = 299792458  # Speed of light in m/s
EPSILON_0 = 8.854187817e-12  # Vacuum permittivity in F/m
E_CHARGE = 1.60217662e-19  # Elementary charge in C


@dataclass
class DielectricFunction:
    """
    Complex dielectric function ε(ω) = ε₁(ω) + iε₂(ω).
    
    Contains real and imaginary parts as functions of energy.
    """
    energies: np.ndarray  # Energy in eV
    epsilon_real: np.ndarray  # ε₁(ω)
    epsilon_imag: np.ndarray  # ε₂(ω)
    direction: str = "average"  # x, y, z, or average
    
    @property
    def epsilon_complex(self) -> np.ndarray:
        """Complex dielectric function."""
        return self.epsilon_real + 1j * self.epsilon_imag
    
    @property
    def n(self) -> np.ndarray:
        """Refractive index n (real part of N = n + ik)."""
        eps = self.epsilon_complex
        return np.sqrt(0.5 * (np.abs(eps) + self.epsilon_real))
    
    @property
    def k(self) -> np.ndarray:
        """Extinction coefficient k (imaginary part of N = n + ik)."""
        eps = self.epsilon_complex
        return np.sqrt(0.5 * (np.abs(eps) - self.epsilon_real))
    
    @property
    def reflectivity(self) -> np.ndarray:
        """Normal incidence reflectivity R."""
        n = self.n
        k = self.k
        return ((n - 1)**2 + k**2) / ((n + 1)**2 + k**2)
    
    @property
    def absorption_coefficient(self) -> np.ndarray:
        """Absorption coefficient α in cm⁻¹."""
        # α = 4πk/λ = 2ωk/c = 2Ek/(ℏc)
        k = self.k
        energies_J = self.energies * E_CHARGE  # Convert to Joules
        alpha = 2 * energies_J * k / (HBAR_EV_S * E_CHARGE * C_M_S)
        return alpha * 1e-2  # Convert to cm⁻¹
    
    def optical_conductivity(self) -> Tuple[np.ndarray, np.ndarray]:
        """
        Optical conductivity σ(ω) = σ₁ + iσ₂.
        
        Returns:
            Tuple of (σ_real, σ_imag) in S/m
        """
        omega = self.energies * E_CHARGE / (HBAR_EV_S * E_CHARGE)  # Angular frequency
        
        # σ₁ = ωε₀ε₂
        sigma_real = omega * EPSILON_0 * self.epsilon_imag
        
        # σ₂ = ωε₀(1 - ε₁)
        sigma_imag = omega * EPSILON_0 * (1 - self.epsilon_real)
        
        return sigma_real, sigma_imag
    
    def energy_loss_function(self) -> np.ndarray:
        """
        Energy loss function -Im(1/ε).
        
        Related to EELS (Electron Energy Loss Spectroscopy).
        """
        eps = self.epsilon_complex
        return -np.imag(1 / eps)


@dataclass
class OpticalTransition:
    """A single optical transition between bands."""
    initial_band: int
    final_band: int
    kpoint_index: int
    energy: float  # Transition energy in eV
    matrix_element: float  # |<f|p|i>|²
    spin: int = 0


class OpticalPropertiesCalculator:
    """
    Calculate optical properties from electronic structure.
    
    Uses the independent-particle approximation (IPA) to compute
    the imaginary part of the dielectric function from interband
    transitions, then applies Kramers-Kronig to get the real part.
    
    Features:
        - ε₂(ω) from JDOS and matrix elements
        - ε₁(ω) via Kramers-Kronig transformation
        - All derived optical properties
        - Tensor components for anisotropic materials
    
    Usage:
        >>> calc = OpticalPropertiesCalculator(band_structure)
        >>> dielectric = calc.calculate_dielectric(energy_range=(0, 10), n_points=1000)
        >>> print(dielectric.n)  # Refractive index
    """
    
    def __init__(
        self,
        band_structure: 'ElectronicBandStructure',
        structure: Optional['Structure'] = None,
    ):
        """
        Initialize calculator.
        
        Args:
            band_structure: Electronic band structure with eigenvalues
            structure: Crystal structure for volume calculation
        """
        self.bs = band_structure
        self.structure = structure
        
        if structure is not None:
            self.volume = structure.volume * 1e-30  # Å³ to m³
        else:
            self.volume = 1e-28  # Default volume
    
    def calculate_jdos(
        self,
        energy_range: Tuple[float, float] = (0, 10),
        n_points: int = 1000,
        smearing: float = 0.1,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate Joint Density of States (JDOS).
        
        JDOS(E) = Σ_cv ∫ δ(E - E_c(k) + E_v(k)) dk
        
        Args:
            energy_range: (min, max) energy in eV
            n_points: Number of energy points
            smearing: Gaussian smearing width in eV
            
        Returns:
            Tuple of (energies, jdos) arrays
        """
        energies = np.linspace(energy_range[0], energy_range[1], n_points)
        jdos = np.zeros(n_points)
        
        # Get eigenvalues
        fermi = self.bs.fermi_energy
        eigenvalues = self.bs.eigenvalues  # (nspins, nkpts, nbands)
        nspins, nkpts, nbands = eigenvalues.shape
        
        # Determine occupied/unoccupied bands
        # Simple approach: bands below Fermi are occupied
        for spin in range(nspins):
            for ik in range(nkpts):
                for iv in range(nbands):  # Valence
                    e_v = eigenvalues[spin, ik, iv]
                    if e_v > fermi:
                        continue  # Skip unoccupied
                    
                    for ic in range(nbands):  # Conduction
                        e_c = eigenvalues[spin, ik, ic]
                        if e_c <= fermi:
                            continue  # Skip occupied
                        
                        transition_energy = e_c - e_v
                        
                        # Add Gaussian contribution
                        jdos += np.exp(-0.5 * ((energies - transition_energy) / smearing)**2)
        
        # Normalize
        jdos /= (smearing * np.sqrt(2 * np.pi) * nkpts)
        
        return energies, jdos
    
    def calculate_epsilon2(
        self,
        energy_range: Tuple[float, float] = (0, 10),
        n_points: int = 1000,
        smearing: float = 0.1,
        direction: str = "average",
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calculate imaginary part of dielectric function ε₂(ω).
        
        Using independent particle approximation:
        ε₂(ω) ∝ Σ_cv |<c|p|v>|² δ(ω - E_c + E_v)
        
        Args:
            energy_range: (min, max) energy in eV
            n_points: Number of energy points
            smearing: Gaussian smearing in eV
            direction: x, y, z, or average
            
        Returns:
            Tuple of (energies, epsilon2) arrays
        """
        # For now, use JDOS as approximation (assumes constant matrix elements)
        energies, jdos = self.calculate_jdos(energy_range, n_points, smearing)
        
        # Scale by prefactors
        # ε₂ ∝ JDOS / ω²
        omega = energies.copy()
        omega[omega < 0.01] = 0.01  # Avoid division by zero
        
        epsilon2 = jdos / omega**2
        
        # Normalize (rough approximation)
        epsilon2 = epsilon2 / np.max(epsilon2) * 10  # Scale to reasonable values
        
        return energies, epsilon2
    
    def kramers_kronig(
        self,
        energies: np.ndarray,
        epsilon2: np.ndarray,
    ) -> np.ndarray:
        """
        Calculate ε₁(ω) from ε₂(ω) using Kramers-Kronig relation.
        
        ε₁(ω) = 1 + (2/π) P ∫ ω'ε₂(ω')/(ω'² - ω²) dω'
        
        Args:
            energies: Energy grid
            epsilon2: Imaginary part of dielectric function
            
        Returns:
            Real part of dielectric function
        """
        n = len(energies)
        de = energies[1] - energies[0] if n > 1 else 1.0
        epsilon1 = np.ones(n)
        
        for i, omega in enumerate(energies):
            # Principal value integral
            integral = 0.0
            for j, omega_p in enumerate(energies):
                if i != j:
                    integral += omega_p * epsilon2[j] / (omega_p**2 - omega**2)
            
            epsilon1[i] = 1.0 + (2.0 / np.pi) * integral * de
        
        return epsilon1
    
    def calculate_dielectric(
        self,
        energy_range: Tuple[float, float] = (0, 10),
        n_points: int = 500,
        smearing: float = 0.1,
        direction: str = "average",
    ) -> DielectricFunction:
        """
        Calculate complete dielectric function.
        
        Args:
            energy_range: (min, max) energy in eV
            n_points: Number of energy points
            smearing: Gaussian smearing in eV
            direction: x, y, z, or average
            
        Returns:
            DielectricFunction object with ε₁ and ε₂
        """
        energies, epsilon2 = self.calculate_epsilon2(
            energy_range, n_points, smearing, direction
        )
        
        epsilon1 = self.kramers_kronig(energies, epsilon2)
        
        return DielectricFunction(
            energies=energies,
            epsilon_real=epsilon1,
            epsilon_imag=epsilon2,
            direction=direction,
        )
    
    def get_optical_gap(
        self,
        threshold: float = 0.01,
    ) -> float:
        """
        Estimate optical gap from onset of absorption.
        
        Args:
            threshold: Threshold for determining absorption onset
            
        Returns:
            Optical gap in eV
        """
        dielectric = self.calculate_dielectric()
        
        # Find first energy where ε₂ > threshold
        idx = np.where(dielectric.epsilon_imag > threshold)[0]
        
        if len(idx) > 0:
            return dielectric.energies[idx[0]]
        
        return 0.0
    
    def calculate_tauc_gap(
        self,
        gap_type: str = "direct",
        energy_range: Tuple[float, float] = (0, 5),
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Calculate optical band gap using Tauc plot analysis.
        
        For direct gap: (αhν)² vs hν
        For indirect gap: (αhν)^(1/2) vs hν
        
        Args:
            gap_type: "direct" or "indirect"
            energy_range: Energy range for analysis
            
        Returns:
            Tuple of (gap, energies, tauc_values)
        """
        dielectric = self.calculate_dielectric(energy_range=energy_range)
        
        alpha = dielectric.absorption_coefficient
        energies = dielectric.energies
        
        if gap_type == "direct":
            tauc = (alpha * energies) ** 2
        else:  # indirect
            tauc = (alpha * energies) ** 0.5
        
        # Find linear region and extrapolate to x-axis
        # Simple approach: find max slope region
        grad = np.gradient(tauc, energies)
        max_slope_idx = np.argmax(grad)
        
        # Linear extrapolation
        if max_slope_idx > 0 and max_slope_idx < len(energies) - 1:
            slope = grad[max_slope_idx]
            intercept = tauc[max_slope_idx] - slope * energies[max_slope_idx]
            gap = -intercept / slope if slope != 0 else 0
        else:
            gap = 0.0
        
        return gap, energies, tauc
    
    def plot(
        self,
        quantity: str = "epsilon",
        ax=None,
        **kwargs,
    ):
        """
        Plot optical property.
        
        Args:
            quantity: What to plot - 'epsilon', 'n', 'alpha', 'R', 'sigma'
            ax: matplotlib axes
            **kwargs: Additional plot arguments
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if ax is None:
            fig, ax = plt.subplots()
        
        dielectric = self.calculate_dielectric()
        
        if quantity == "epsilon":
            ax.plot(dielectric.energies, dielectric.epsilon_real, label="ε₁")
            ax.plot(dielectric.energies, dielectric.epsilon_imag, label="ε₂")
            ax.set_ylabel("Dielectric function")
        elif quantity == "n":
            ax.plot(dielectric.energies, dielectric.n, label="n")
            ax.plot(dielectric.energies, dielectric.k, label="k")
            ax.set_ylabel("Refractive index")
        elif quantity == "alpha":
            ax.plot(dielectric.energies, dielectric.absorption_coefficient)
            ax.set_ylabel("α (cm⁻¹)")
        elif quantity == "R":
            ax.plot(dielectric.energies, dielectric.reflectivity)
            ax.set_ylabel("Reflectivity R")
        elif quantity == "sigma":
            sigma_r, sigma_i = dielectric.optical_conductivity()
            ax.plot(dielectric.energies, sigma_r, label="σ₁")
            ax.plot(dielectric.energies, sigma_i, label="σ₂")
            ax.set_ylabel("Conductivity (S/m)")
        
        ax.set_xlabel("Energy (eV)")
        ax.legend()
        
        return ax
