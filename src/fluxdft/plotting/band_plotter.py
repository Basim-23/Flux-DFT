"""
Band Structure Plotter for FluxDFT.

Publication-quality band structure visualization with:
- Proper k-path handling with automatic branch detection
- Fermi level alignment (E - Ef = 0)
- High-symmetry point labels (Γ, X, M, etc.)
- Band gap annotation
- Spin-polarized support

Inspired by sumo's SBSPlotter and pyprocar's EBSPlot.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np
import logging

import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .styles import PlotStyle, PlotTheme

logger = logging.getLogger(__name__)


class BandStructurePlotter:
    """
    Publication-quality band structure plotter.
    
    Features:
        - Proper k-path handling with branch detection
        - Fermi level alignment (E - Ef = 0)
        - High-symmetry point labels (Γ, X, M, etc.)
        - Band gap annotation with VBM/CBM markers
        - Spin-polarized plotting with distinct colors
        - Reference band structure overlay (e.g., from Materials Project)
        
    Usage:
        >>> plotter = BandStructurePlotter(
        ...     eigenvalues=eigs,  # Shape: (n_kpts, n_bands) or (n_spins, n_kpts, n_bands)
        ...     kpoints=kpath,
        ...     fermi_energy=efermi,
        ...     kpoint_labels=[(0.0, 'Γ'), (0.5, 'X'), (1.0, 'M')],
        ... )
        >>> fig = plotter.plot()
        >>> fig.savefig('band_structure.png')
    """
    
    # Greek letter replacements for k-point labels
    LABEL_MAPPING = {
        'GAMMA': 'Γ', 'G': 'Γ',
        'SIGMA': 'Σ', 'DELTA': 'Δ',
        'LAMBDA': 'Λ', 'PI': 'Π',
    }
    
    def __init__(
        self,
        eigenvalues: np.ndarray,
        kpoints: np.ndarray,
        fermi_energy: float,
        kpoint_labels: Optional[List[Tuple[float, str]]] = None,
        style: Optional[PlotStyle] = None,
    ):
        """
        Initialize band structure plotter.
        
        Args:
            eigenvalues: Band eigenvalues in eV.
                Shape: (n_kpts, n_bands) for non-spin-polarized
                Shape: (n_spins, n_kpts, n_bands) for spin-polarized
            kpoints: K-point distances along the path (n_kpts,).
                Usually cumulative distances in reciprocal space.
            fermi_energy: Fermi energy in eV.
            kpoint_labels: List of (position, label) tuples for high-symmetry points.
                Position should match values in kpoints array.
            style: PlotStyle configuration. Uses default if not provided.
        """
        # Normalize eigenvalues to 3D array (n_spins, n_kpts, n_bands)
        eigenvalues = np.asarray(eigenvalues)
        if eigenvalues.ndim == 2:
            self.eigenvalues = eigenvalues[np.newaxis, :, :]
        elif eigenvalues.ndim == 3:
            if eigenvalues.shape[0] not in (1, 2):
                # Assume it's (n_kpts, n_bands, n_spins) and transpose
                logger.warning("Transposing eigenvalues to (n_spins, n_kpts, n_bands)")
                self.eigenvalues = np.transpose(eigenvalues, (2, 0, 1))
            else:
                self.eigenvalues = eigenvalues
        else:
            raise ValueError(f"eigenvalues must be 2D or 3D, got {eigenvalues.ndim}D")
        
        self.kpoints = np.asarray(kpoints)
        self.fermi_energy = float(fermi_energy)
        self.kpoint_labels = kpoint_labels or []
        self.style = style or PlotStyle()
        
        # Derived properties
        self.n_spins = self.eigenvalues.shape[0]
        self.n_kpts = self.eigenvalues.shape[1]
        self.n_bands = self.eigenvalues.shape[2]
        self.is_spin_polarized = self.n_spins == 2
        
        # Reference data (optional, set via set_reference)
        self._reference_eigenvalues = None
        self._reference_kpoints = None
        self._reference_label = "Reference"
    
    def set_reference(
        self,
        eigenvalues: np.ndarray,
        kpoints: Optional[np.ndarray] = None,
        label: str = "Reference",
    ) -> None:
        """
        Set reference band structure for comparison.
        
        Args:
            eigenvalues: Reference eigenvalues (already Fermi-aligned, i.e., E - Ef)
            kpoints: Reference k-points. If None, uses same as main data.
            label: Legend label for reference bands.
        """
        self._reference_eigenvalues = np.asarray(eigenvalues)
        if self._reference_eigenvalues.ndim == 2:
            self._reference_eigenvalues = self._reference_eigenvalues[np.newaxis, :, :]
        
        self._reference_kpoints = kpoints if kpoints is not None else self.kpoints
        self._reference_label = label
    
    def plot(
        self,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        show_fermi: bool = True,
        show_bandgap: bool = True,
        show_vbm_cbm: bool = False,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Generate band structure plot.
        
        Args:
            ax: Matplotlib axes to plot on. Creates new figure if None.
            energy_range: (min, max) energy range relative to Fermi level.
            show_fermi: Show horizontal Fermi level line.
            show_bandgap: Annotate band gap value if semiconductor/insulator.
            show_vbm_cbm: Mark VBM and CBM positions.
            title: Optional plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.band_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        self.style.apply_to_figure(fig)
        
        # Shift eigenvalues to Fermi level
        energies = self.eigenvalues - self.fermi_energy
        
        # Plot reference bands first (background)
        if self._reference_eigenvalues is not None:
            self._plot_reference_bands(ax)
        
        # Plot main bands
        self._plot_bands(ax, energies)
        
        # Fermi level line
        if show_fermi:
            ax.axhline(
                0,
                color=self.style.fermi_color,
                linestyle=self.style.fermi_linestyle,
                linewidth=self.style.fermi_linewidth,
                label='E$_F$',
                zorder=5,
            )
        
        # High-symmetry point lines and labels
        if self.kpoint_labels:
            self._add_kpoint_labels(ax)
        
        # Band gap analysis
        gap_info = self._calculate_bandgap(energies)
        
        if show_bandgap and gap_info['gap'] > 0.01:
            ax.annotate(
                f"E$_g$ = {gap_info['gap']:.2f} eV",
                xy=(0.02, 0.98),
                xycoords='axes fraction',
                fontsize=self.style.font_size,
                va='top',
                ha='left',
                bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8),
            )
        
        if show_vbm_cbm and gap_info['gap'] > 0.01:
            self._mark_vbm_cbm(ax, gap_info, energies)
        
        # Axis configuration
        ax.set_xlim(self.kpoints[0], self.kpoints[-1])
        ax.set_ylim(energy_range)
        ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
        ax.set_xlabel('')
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        
        # Legend for spin-polarized
        if self.is_spin_polarized:
            ax.legend(
                loc='upper right',
                fontsize=self.style.tick_size,
                framealpha=0.9,
            )
        
        fig.tight_layout()
        return fig
    
    def _plot_bands(self, ax: Axes, energies: np.ndarray) -> None:
        """Plot the main band structure lines."""
        for spin in range(self.n_spins):
            if self.is_spin_polarized:
                color = self.style.spin_up_color if spin == 0 else self.style.spin_down_color
                linestyle = '-' if spin == 0 else self.style.spin_down_linestyle
                label = 'Spin ↑' if spin == 0 else 'Spin ↓'
            else:
                color = self.style.band_color
                linestyle = '-'
                label = None
            
            for band_idx in range(self.n_bands):
                ax.plot(
                    self.kpoints,
                    energies[spin, :, band_idx],
                    color=color,
                    linewidth=self.style.band_linewidth,
                    linestyle=linestyle,
                    label=label if band_idx == 0 else None,
                    zorder=10,
                )
    
    def _plot_reference_bands(self, ax: Axes) -> None:
        """Plot reference band structure in background."""
        ref_eg = self._reference_eigenvalues
        ref_kp = self._reference_kpoints
        
        n_ref_spins = ref_eg.shape[0]
        n_ref_bands = ref_eg.shape[2]
        
        for spin in range(n_ref_spins):
            for band_idx in range(n_ref_bands):
                ax.plot(
                    ref_kp,
                    ref_eg[spin, :, band_idx],
                    color=self.style.reference_color,
                    linewidth=self.style.reference_linewidth,
                    linestyle=self.style.reference_linestyle,
                    alpha=0.6,
                    label=self._reference_label if spin == 0 and band_idx == 0 else None,
                    zorder=1,
                )
    
    def _add_kpoint_labels(self, ax: Axes) -> None:
        """Add high-symmetry point labels and vertical lines."""
        positions = []
        labels = []
        
        for pos, label in self.kpoint_labels:
            positions.append(pos)
            labels.append(self._format_label(label))
            
            # Vertical line at high-symmetry point
            ax.axvline(
                pos,
                color=self.style.grid_color,
                linewidth=self.style.grid_linewidth,
                linestyle='-',
                zorder=0,
            )
        
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=self.style.tick_size)
    
    def _format_label(self, label: str) -> str:
        """Format k-point label with Greek letters."""
        upper = label.upper()
        if upper in self.LABEL_MAPPING:
            return self.LABEL_MAPPING[upper]
        return label
    
    def _calculate_bandgap(self, energies: np.ndarray) -> Dict:
        """
        Calculate band gap from eigenvalues.
        
        Returns dict with:
            - gap: Band gap in eV
            - vbm: Valence band maximum energy (relative to Ef)
            - cbm: Conduction band minimum energy (relative to Ef)
            - vbm_kindex: K-point index of VBM
            - cbm_kindex: K-point index of CBM
            - is_direct: Whether gap is direct
        """
        # Consider all spins
        all_occupied = []
        all_unoccupied = []
        
        for spin in range(self.n_spins):
            for kpt in range(self.n_kpts):
                for band in range(self.n_bands):
                    e = energies[spin, kpt, band]
                    if e <= 0:
                        all_occupied.append((e, kpt, spin, band))
                    else:
                        all_unoccupied.append((e, kpt, spin, band))
        
        if not all_occupied or not all_unoccupied:
            return {
                'gap': 0.0, 'vbm': None, 'cbm': None,
                'vbm_kindex': None, 'cbm_kindex': None,
                'is_direct': None,
            }
        
        # Find VBM (highest occupied)
        vbm_data = max(all_occupied, key=lambda x: x[0])
        vbm, vbm_k, vbm_spin, vbm_band = vbm_data
        
        # Find CBM (lowest unoccupied)
        cbm_data = min(all_unoccupied, key=lambda x: x[0])
        cbm, cbm_k, cbm_spin, cbm_band = cbm_data
        
        gap = cbm - vbm
        is_direct = (vbm_k == cbm_k)
        
        return {
            'gap': gap,
            'vbm': vbm,
            'cbm': cbm,
            'vbm_kindex': vbm_k,
            'cbm_kindex': cbm_k,
            'is_direct': is_direct,
        }
    
    def _mark_vbm_cbm(
        self,
        ax: Axes,
        gap_info: Dict,
        energies: np.ndarray,
    ) -> None:
        """Mark VBM and CBM positions on the plot."""
        if gap_info['vbm_kindex'] is None:
            return
        
        vbm_k = self.kpoints[gap_info['vbm_kindex']]
        cbm_k = self.kpoints[gap_info['cbm_kindex']]
        
        # VBM marker
        ax.plot(
            vbm_k, gap_info['vbm'],
            marker=self.style.vbm_cbm_marker,
            markersize=self.style.vbm_cbm_size,
            color='green',
            markerfacecolor='white',
            markeredgewidth=2,
            zorder=20,
            label='VBM',
        )
        
        # CBM marker
        ax.plot(
            cbm_k, gap_info['cbm'],
            marker=self.style.vbm_cbm_marker,
            markersize=self.style.vbm_cbm_size,
            color='red',
            markerfacecolor='white',
            markeredgewidth=2,
            zorder=20,
            label='CBM',
        )
        
        # Arrow connecting VBM to CBM
        if gap_info['is_direct']:
            # Vertical arrow for direct gap
            ax.annotate(
                '',
                xy=(vbm_k, gap_info['cbm']),
                xytext=(vbm_k, gap_info['vbm']),
                arrowprops=dict(
                    arrowstyle='<->',
                    color='gray',
                    lw=1.5,
                ),
            )
    
    def save(
        self,
        filepath: Union[str, Path],
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        **kwargs,
    ) -> None:
        """
        Generate and save band structure plot.
        
        Args:
            filepath: Output file path (format determined by extension).
            energy_range: Energy range for plot.
            **kwargs: Additional arguments passed to plot().
        """
        fig = self.plot(energy_range=energy_range, **kwargs)
        fig.savefig(filepath, dpi=self.style.dpi, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Saved band structure plot to {filepath}")
    
    @classmethod
    def from_pymatgen(
        cls,
        bs,  # pymatgen.electronic_structure.bandstructure.BandStructure
        style: Optional[PlotStyle] = None,
    ) -> 'BandStructurePlotter':
        """
        Create plotter from pymatgen BandStructure object.
        
        Args:
            bs: pymatgen BandStructureSymmLine object.
            style: Optional PlotStyle.
            
        Returns:
            BandStructurePlotter instance.
        """
        from pymatgen.electronic_structure.bandstructure import BandStructureSymmLine
        
        if not isinstance(bs, BandStructureSymmLine):
            raise TypeError("Expected BandStructureSymmLine object")
        
        # Extract eigenvalues
        # bs.bands is dict: {Spin.up: array(n_bands, n_kpts), ...}
        from pymatgen.electronic_structure.core import Spin
        
        spins = list(bs.bands.keys())
        n_bands = bs.bands[spins[0]].shape[0]
        n_kpts = bs.bands[spins[0]].shape[1]
        
        eigenvalues = np.zeros((len(spins), n_kpts, n_bands))
        for i, spin in enumerate(spins):
            eigenvalues[i] = bs.bands[spin].T  # Transpose to (n_kpts, n_bands)
        
        # Extract k-point distances
        kpoints = np.array([k for k in bs.distance])
        
        # Extract labels
        labels = []
        for i, kpt in enumerate(bs.kpoints):
            if kpt.label:
                labels.append((kpoints[i], kpt.label))
        
        return cls(
            eigenvalues=eigenvalues,
            kpoints=kpoints,
            fermi_energy=bs.efermi,
            kpoint_labels=labels,
            style=style,
        )
