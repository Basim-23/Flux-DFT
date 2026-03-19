"""
Phonon Analysis Module for FluxDFT.

Provides phonon band structure and DOS analysis from QE ph.x output.
Based on patterns from abipy's dfpt module.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import numpy as np
import logging

logger = logging.getLogger(__name__)

# Constants
THZ_TO_CM = 33.35641  # THz to cm^-1
THZ_TO_MEV = 4.13567  # THz to meV
CM_TO_MEV = 0.12398  # cm^-1 to meV


@dataclass
class PhononMode:
    """A single phonon mode at a q-point."""
    frequency: float  # THz
    eigenvector: np.ndarray  # (natoms, 3) complex
    q_point: np.ndarray  # Fractional coordinates
    mode_index: int
    
    @property
    def frequency_cm(self) -> float:
        """Frequency in cm^-1."""
        return self.frequency * THZ_TO_CM
    
    @property
    def frequency_meV(self) -> float:
        """Frequency in meV."""
        return self.frequency * THZ_TO_MEV
    
    @property
    def is_acoustic(self) -> bool:
        """Check if this is likely an acoustic mode (low frequency at Γ)."""
        is_gamma = np.allclose(self.q_point, [0, 0, 0])
        return is_gamma and abs(self.frequency) < 0.5  # THz threshold


@dataclass
class PhononBandStructure:
    """
    Phonon band structure container.
    
    Stores phonon frequencies along a q-point path.
    """
    # Q-point data
    qpoints: np.ndarray  # (nqpts, 3)
    q_distances: np.ndarray  # (nqpts,)
    
    # Frequencies: (nqpts, nmodes) where nmodes = 3*natoms
    frequencies: np.ndarray  # THz
    
    # Eigenvectors (optional): (nqpts, nmodes, natoms, 3)
    eigenvectors: Optional[np.ndarray] = None
    
    # High-symmetry point labels
    hs_labels: Dict[int, str] = field(default_factory=dict)
    
    # Structure info
    natoms: int = 0
    atom_masses: List[float] = field(default_factory=list)
    atom_species: List[str] = field(default_factory=list)
    
    @property
    def nmodes(self) -> int:
        """Number of phonon modes."""
        return self.frequencies.shape[1]
    
    @property
    def nqpoints(self) -> int:
        """Number of q-points."""
        return len(self.qpoints)
    
    @property
    def frequencies_cm(self) -> np.ndarray:
        """Frequencies in cm^-1."""
        return self.frequencies * THZ_TO_CM
    
    @property
    def frequencies_meV(self) -> np.ndarray:
        """Frequencies in meV."""
        return self.frequencies * THZ_TO_MEV
    
    def get_mode(self, q_idx: int, mode_idx: int) -> PhononMode:
        """Get a specific phonon mode."""
        eigvec = None
        if self.eigenvectors is not None:
            eigvec = self.eigenvectors[q_idx, mode_idx]
        
        return PhononMode(
            frequency=self.frequencies[q_idx, mode_idx],
            eigenvector=eigvec,
            q_point=self.qpoints[q_idx],
            mode_index=mode_idx,
        )
    
    @classmethod
    def from_qe_matdyn(cls, freq_file: Union[str, Path]) -> 'PhononBandStructure':
        """
        Read phonon band structure from QE matdyn.x output.
        
        Args:
            freq_file: Path to matdyn.freq or .gp file
            
        Returns:
            PhononBandStructure object
        """
        freq_file = Path(freq_file)
        
        # Parse the freq/gp file
        with open(freq_file, 'r') as f:
            lines = f.readlines()
        
        # First line has dimensions
        first_line = lines[0].strip().split()
        if len(first_line) >= 2:
            nqpts = int(first_line[0].replace(',', ''))
            nmodes = int(first_line[1].replace(',', ''))
        else:
            raise ValueError("Could not parse matdyn output header")
        
        # Parse frequency data
        qpoints = []
        frequencies = []
        
        current_q = None
        current_freqs = []
        
        for line in lines[1:]:
            parts = line.strip().split()
            
            if not parts:
                continue
            
            # Check if this is a q-point line
            if len(parts) == 3:
                try:
                    q = [float(x) for x in parts]
                    if current_q is not None and current_freqs:
                        qpoints.append(current_q)
                        frequencies.append(current_freqs)
                    current_q = q
                    current_freqs = []
                except ValueError:
                    # Not a q-point, could be frequencies
                    for val in parts:
                        try:
                            current_freqs.append(float(val))
                        except ValueError:
                            pass
            else:
                # Frequency values
                for val in parts:
                    try:
                        current_freqs.append(float(val))
                    except ValueError:
                        pass
        
        # Add last q-point
        if current_q is not None and current_freqs:
            qpoints.append(current_q)
            frequencies.append(current_freqs)
        
        qpoints = np.array(qpoints)
        
        # Ensure all frequency lists have same length
        max_modes = max(len(f) for f in frequencies)
        freq_array = np.zeros((len(frequencies), max_modes))
        for i, freqs in enumerate(frequencies):
            freq_array[i, :len(freqs)] = freqs
        
        # Convert from cm^-1 to THz (matdyn outputs cm^-1)
        freq_array = freq_array / THZ_TO_CM
        
        # Calculate q-distances
        q_distances = np.zeros(len(qpoints))
        for i in range(1, len(qpoints)):
            q_distances[i] = q_distances[i-1] + np.linalg.norm(qpoints[i] - qpoints[i-1])
        
        return cls(
            qpoints=qpoints,
            q_distances=q_distances,
            frequencies=freq_array,
            natoms=nmodes // 3,
        )


@dataclass
class PhononDOS:
    """
    Phonon density of states container.
    """
    # Energy grid (usually in THz or cm^-1)
    energies: np.ndarray
    
    # Total DOS
    total_dos: np.ndarray
    
    energy_unit: str = "THz"  # or "cm^-1", "meV"
    
    # Projected DOS per atom (optional)
    projected_dos: Optional[Dict[str, np.ndarray]] = None
    
    # Partial DOS per direction (optional)
    partial_dos: Optional[np.ndarray] = None  # (natoms, 3, npoints)
    
    @property
    def energies_cm(self) -> np.ndarray:
        """Energies in cm^-1."""
        if self.energy_unit == "THz":
            return self.energies * THZ_TO_CM
        elif self.energy_unit == "meV":
            return self.energies / CM_TO_MEV
        return self.energies
    
    @property
    def energies_meV(self) -> np.ndarray:
        """Energies in meV."""
        if self.energy_unit == "THz":
            return self.energies * THZ_TO_MEV
        elif self.energy_unit == "cm^-1":
            return self.energies * CM_TO_MEV
        return self.energies
    
    @classmethod
    def from_qe_matdyn_dos(cls, dos_file: Union[str, Path]) -> 'PhononDOS':
        """
        Read phonon DOS from QE matdyn.x output.
        
        Args:
            dos_file: Path to matdyn.dos file
            
        Returns:
            PhononDOS object
        """
        data = np.loadtxt(dos_file, comments='#')
        
        return cls(
            energies=data[:, 0],
            total_dos=data[:, 1],
            energy_unit="cm^-1",
        )
    
    def get_thermodynamic_properties(
        self,
        temperatures: np.ndarray,
    ) -> Dict[str, np.ndarray]:
        """
        Calculate thermodynamic properties from phonon DOS.
        
        Args:
            temperatures: Temperature array in K
            
        Returns:
            Dictionary with F, E, S, Cv as functions of T
        """
        from scipy import constants
        
        kB = constants.k / constants.eV  # eV/K
        hbar = constants.hbar / constants.eV  # eV⋅s
        
        # Convert energies to eV
        if self.energy_unit == "THz":
            omega = self.energies * 2 * np.pi * 1e12 * hbar
        elif self.energy_unit == "cm^-1":
            omega = self.energies * CM_TO_MEV / 1000
        else:
            omega = self.energies / 1000  # meV to eV
        
        dE = omega[1] - omega[0] if len(omega) > 1 else 1
        dos = self.total_dos
        
        F = np.zeros_like(temperatures)  # Helmholtz free energy
        E = np.zeros_like(temperatures)  # Internal energy
        S = np.zeros_like(temperatures)  # Entropy
        Cv = np.zeros_like(temperatures)  # Heat capacity
        
        for i, T in enumerate(temperatures):
            if T < 1e-6:
                continue
            
            beta = 1.0 / (kB * T)
            
            for j, w in enumerate(omega):
                if w < 1e-10:
                    continue
                
                x = beta * w
                n = 1.0 / (np.exp(x) - 1) if x < 50 else 0
                
                # Free energy contribution
                F[i] += dos[j] * (w/2 + kB * T * np.log(1 - np.exp(-x))) * dE
                
                # Internal energy
                E[i] += dos[j] * w * (0.5 + n) * dE
                
                # Entropy
                if n > 1e-10:
                    S[i] += dos[j] * kB * ((1 + n) * np.log(1 + n) - n * np.log(n)) * dE
                
                # Heat capacity
                if x < 50:
                    Cv[i] += dos[j] * kB * x**2 * np.exp(x) / (np.exp(x) - 1)**2 * dE
        
        return {
            'temperature': temperatures,
            'free_energy': F,
            'internal_energy': E,
            'entropy': S,
            'heat_capacity': Cv,
        }


class PhononPlotter:
    """
    Publication-quality phonon band structure and DOS plotter.
    """
    
    def __init__(
        self,
        phonon_bands: Optional[PhononBandStructure] = None,
        phonon_dos: Optional[PhononDOS] = None,
    ):
        """
        Initialize plotter.
        
        Args:
            phonon_bands: Phonon band structure
            phonon_dos: Phonon DOS
        """
        self.bands = phonon_bands
        self.dos = phonon_dos
    
    def plot_bands(
        self,
        ax=None,
        units: str = "THz",
        color: str = "#2563eb",
        linewidth: float = 1.0,
        **kwargs,
    ):
        """
        Plot phonon band structure.
        
        Args:
            ax: matplotlib axes
            units: Frequency units ('THz', 'cm^-1', 'meV')
            color: Line color
            linewidth: Line width
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if self.bands is None:
            raise ValueError("No phonon band structure data")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(8, 6))
        
        # Get frequencies in requested units
        if units == "THz":
            freqs = self.bands.frequencies
            ylabel = "Frequency (THz)"
        elif units == "cm^-1":
            freqs = self.bands.frequencies_cm
            ylabel = "Frequency (cm⁻¹)"
        else:
            freqs = self.bands.frequencies_meV
            ylabel = "Frequency (meV)"
        
        x = self.bands.q_distances
        
        # Plot each mode
        for mode in range(self.bands.nmodes):
            ax.plot(x, freqs[:, mode], color=color, linewidth=linewidth)
        
        # Add high-symmetry point markers
        for idx, label in self.bands.hs_labels.items():
            ax.axvline(x[idx], color='gray', linestyle='--', alpha=0.5)
        
        # Add zero line
        ax.axhline(0, color='black', linestyle='-', linewidth=0.5)
        
        ax.set_xlim(x.min(), x.max())
        ax.set_ylabel(ylabel)
        ax.set_xlabel('')
        
        # Set x-tick labels
        if self.bands.hs_labels:
            tick_positions = [x[idx] for idx in sorted(self.bands.hs_labels.keys())]
            tick_labels = [self.bands.hs_labels[idx] for idx in sorted(self.bands.hs_labels.keys())]
            ax.set_xticks(tick_positions)
            ax.set_xticklabels(tick_labels)
        
        return ax
    
    def plot_dos(
        self,
        ax=None,
        units: str = "THz",
        color: str = "#2563eb",
        fill: bool = True,
        orientation: str = "vertical",
        **kwargs,
    ):
        """
        Plot phonon DOS.
        
        Args:
            ax: matplotlib axes
            units: Frequency units
            color: Line/fill color
            fill: Fill under curve
            orientation: 'vertical' or 'horizontal'
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        if self.dos is None:
            raise ValueError("No phonon DOS data")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=(3, 6) if orientation == 'vertical' else (8, 3))
        
        # Get energies in requested units
        if units == "THz":
            if self.dos.energy_unit == "cm^-1":
                energies = self.dos.energies / THZ_TO_CM
            else:
                energies = self.dos.energies
        else:
            energies = self.dos.energies_cm if units == "cm^-1" else self.dos.energies_meV
        
        dos = self.dos.total_dos
        
        if orientation == 'vertical':
            ax.plot(dos, energies, color=color)
            if fill:
                ax.fill_betweenx(energies, 0, dos, color=color, alpha=0.3)
            ax.set_xlabel('DOS')
            ax.set_ylim(energies.min(), energies.max())
        else:
            ax.plot(energies, dos, color=color)
            if fill:
                ax.fill_between(energies, 0, dos, color=color, alpha=0.3)
            ax.set_ylabel('DOS')
        
        return ax
    
    def plot_combined(
        self,
        units: str = "THz",
        figsize: Tuple[float, float] = (10, 6),
        dos_ratio: float = 0.25,
        **kwargs,
    ):
        """
        Plot combined band structure and DOS.
        
        Args:
            units: Frequency units
            figsize: Figure size
            dos_ratio: DOS panel width ratio
            
        Returns:
            matplotlib Figure
        """
        try:
            import matplotlib.pyplot as plt
            from matplotlib.gridspec import GridSpec
        except ImportError:
            logger.error("matplotlib required for plotting")
            return
        
        fig = plt.figure(figsize=figsize)
        gs = GridSpec(1, 2, width_ratios=[1 - dos_ratio, dos_ratio], wspace=0.05)
        
        ax_bands = fig.add_subplot(gs[0])
        ax_dos = fig.add_subplot(gs[1], sharey=ax_bands)
        
        # Plot bands
        if self.bands:
            self.plot_bands(ax=ax_bands, units=units, **kwargs)
        
        # Plot DOS
        if self.dos:
            self.plot_dos(ax=ax_dos, units=units, orientation='vertical', **kwargs)
            ax_dos.set_ylabel('')
            ax_dos.tick_params(labelleft=False)
        
        return fig


class PhononAnalyzer:
    """
    High-level phonon analysis.
    
    Provides:
        - Soft mode detection
        - Thermal properties calculation
        - Mode symmetry analysis
    """
    
    def __init__(self, phonon_bands: PhononBandStructure):
        """
        Initialize analyzer.
        
        Args:
            phonon_bands: Phonon band structure data
        """
        self.bands = phonon_bands
    
    def check_dynamical_stability(self) -> Tuple[bool, List[Dict]]:
        """
        Check for imaginary/soft modes indicating dynamical instability.
        
        Returns:
            Tuple of (is_stable, list of soft modes)
        """
        soft_modes = []
        threshold = -0.1  # THz threshold for soft modes
        
        for q_idx in range(self.bands.nqpoints):
            for mode_idx in range(self.bands.nmodes):
                freq = self.bands.frequencies[q_idx, mode_idx]
                
                if freq < threshold:
                    soft_modes.append({
                        'q_index': q_idx,
                        'q_point': self.bands.qpoints[q_idx].tolist(),
                        'mode': mode_idx,
                        'frequency_THz': freq,
                        'frequency_cm': freq * THZ_TO_CM,
                    })
        
        is_stable = len(soft_modes) == 0
        
        return is_stable, soft_modes
    
    def get_acoustic_modes(self) -> List[int]:
        """
        Identify acoustic mode indices.
        
        Returns:
            List of acoustic mode indices (0, 1, 2 for 3 acoustic modes)
        """
        # Find gamma point
        gamma_idx = None
        for i, q in enumerate(self.bands.qpoints):
            if np.allclose(q, [0, 0, 0]):
                gamma_idx = i
                break
        
        if gamma_idx is None:
            logger.warning("Gamma point not found")
            return [0, 1, 2]  # Default
        
        # Get frequencies at gamma
        gamma_freqs = self.bands.frequencies[gamma_idx]
        
        # Acoustic modes have near-zero frequency at gamma
        acoustic = np.where(np.abs(gamma_freqs) < 0.5)[0]
        
        return acoustic.tolist()[:3]
    
    def get_max_frequency(self) -> float:
        """Get maximum phonon frequency in THz."""
        return np.max(self.bands.frequencies)
    
    def get_band_gap(self) -> Optional[float]:
        """
        Get phonon band gap if present.
        
        Returns:
            Gap in THz, or None if no gap
        """
        all_freqs = self.bands.frequencies.flatten()
        all_freqs = all_freqs[all_freqs > 0]  # Only positive frequencies
        all_freqs = np.sort(all_freqs)
        
        # Look for gaps
        gaps = np.diff(all_freqs)
        max_gap_idx = np.argmax(gaps)
        
        if gaps[max_gap_idx] > 0.5:  # THz threshold for meaningful gap
            return gaps[max_gap_idx]
        
        return None
