"""
Fat Band Plotter for FluxDFT.

Orbital-projected band structure visualization with:
- Color-coded projections (s, p, d, f character)
- Variable line width based on orbital weight
- Multi-projection overlay
- Spin texture (if available)

Inspired by pyprocar's parametric band plotting.

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
from matplotlib.collections import LineCollection
from matplotlib.colors import Normalize, LinearSegmentedColormap

from .styles import PlotStyle, ORBITAL_COLORS

logger = logging.getLogger(__name__)


class FatBandPlotter:
    """
    Orbital-projected (fat) band structure plotter.
    
    Features:
        - Color-coded projections by orbital character
        - Variable line width based on projection weight
        - RGB mode for multiple simultaneous projections
        - Continuous colormap mode for single projection
        - Spin texture visualization (for SOC calculations)
        
    The "fatness" of bands indicates the orbital character at each k-point.
    
    Usage:
        >>> plotter = FatBandPlotter(
        ...     eigenvalues=eigs,
        ...     kpoints=kpath,
        ...     fermi_energy=efermi,
        ...     projections=proj,  # Shape: (n_spins, n_kpts, n_bands, n_orbitals)
        ...     orbital_labels=['s', 'p', 'd'],
        ... )
        >>> fig = plotter.plot_single_projection(orbital_index=1)  # p-character
        >>> fig = plotter.plot_rgb(orbital_indices=[0, 1, 2])  # s-p-d as RGB
    """
    
    def __init__(
        self,
        eigenvalues: np.ndarray,
        kpoints: np.ndarray,
        fermi_energy: float,
        projections: np.ndarray,
        orbital_labels: Optional[List[str]] = None,
        kpoint_labels: Optional[List[Tuple[float, str]]] = None,
        style: Optional[PlotStyle] = None,
    ):
        """
        Initialize fat band plotter.
        
        Args:
            eigenvalues: Band eigenvalues in eV.
                Shape: (n_kpts, n_bands) or (n_spins, n_kpts, n_bands)
            kpoints: K-point distances along path (n_kpts,).
            fermi_energy: Fermi energy in eV.
            projections: Orbital projections.
                Shape: (n_kpts, n_bands, n_orbitals) or
                       (n_spins, n_kpts, n_bands, n_orbitals)
                Values should be normalized (0-1) or will be normalized.
            orbital_labels: Names for each orbital (e.g., ['s', 'p', 'd']).
            kpoint_labels: High-symmetry point labels.
            style: PlotStyle configuration.
        """
        # Normalize eigenvalues to 3D
        eigenvalues = np.asarray(eigenvalues)
        if eigenvalues.ndim == 2:
            self.eigenvalues = eigenvalues[np.newaxis, :, :]
        else:
            self.eigenvalues = eigenvalues
        
        self.kpoints = np.asarray(kpoints)
        self.fermi_energy = float(fermi_energy)
        
        # Normalize projections to 4D
        projections = np.asarray(projections)
        if projections.ndim == 3:
            self.projections = projections[np.newaxis, :, :, :]
        else:
            self.projections = projections
        
        self.n_spins = self.eigenvalues.shape[0]
        self.n_kpts = self.eigenvalues.shape[1]
        self.n_bands = self.eigenvalues.shape[2]
        self.n_orbitals = self.projections.shape[3]
        
        self.orbital_labels = orbital_labels or [f'Orb{i}' for i in range(self.n_orbitals)]
        self.kpoint_labels = kpoint_labels or []
        self.style = style or PlotStyle()
        
        # Normalize projections to 0-1 range
        self._normalize_projections()
    
    def _normalize_projections(self) -> None:
        """Normalize projections to 0-1 range per k-point/band."""
        # Sum over all orbitals for each state
        total = np.sum(self.projections, axis=-1, keepdims=True)
        total = np.where(total > 0, total, 1.0)  # Avoid division by zero
        self.projections = self.projections / total
    
    def plot_single_projection(
        self,
        orbital_index: int = 0,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        width_scale: float = 15.0,
        cmap: Optional[str] = None,
        colorbar: bool = True,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Plot band structure with single orbital projection.
        
        The line width at each point indicates the orbital weight.
        
        Args:
            orbital_index: Index of orbital to visualize.
            ax: Matplotlib axes.
            energy_range: Energy range relative to Fermi level.
            width_scale: Scale factor for line widths.
            cmap: Colormap for projection intensity.
            colorbar: Show colorbar.
            title: Optional plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.band_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        
        energies = self.eigenvalues - self.fermi_energy
        weights = self.projections[:, :, :, orbital_index]
        
        cmap = cmap or self.style.projection_cmap
        colormap = plt.get_cmap(cmap)
        norm = Normalize(vmin=0, vmax=1)
        
        for spin in range(self.n_spins):
            for band in range(self.n_bands):
                e = energies[spin, :, band]
                w = weights[spin, :, band]
                
                # Create line segments
                points = np.array([self.kpoints, e]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                
                # Average weight for each segment
                seg_weights = (w[:-1] + w[1:]) / 2
                
                # Line collection with variable width and color
                lc = LineCollection(
                    segments,
                    linewidths=seg_weights * width_scale + 0.5,
                    colors=colormap(norm(seg_weights)),
                    zorder=5,
                )
                ax.add_collection(lc)
        
        # Fermi level
        ax.axhline(
            0,
            color=self.style.fermi_color,
            linestyle=self.style.fermi_linestyle,
            linewidth=self.style.fermi_linewidth,
            zorder=10,
        )
        
        # High-symmetry labels
        self._add_kpoint_labels(ax)
        
        # Colorbar
        if colorbar:
            sm = plt.cm.ScalarMappable(cmap=colormap, norm=norm)
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax, fraction=0.03, pad=0.02)
            orbital_name = self.orbital_labels[orbital_index]
            cbar.set_label(f'{orbital_name} character', fontsize=self.style.font_size)
        
        ax.set_xlim(self.kpoints[0], self.kpoints[-1])
        ax.set_ylim(energy_range)
        ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        else:
            ax.set_title(
                f'{self.orbital_labels[orbital_index]}-projected bands',
                fontsize=self.style.title_size,
            )
        
        fig.tight_layout()
        return fig
    
    def plot_rgb(
        self,
        orbital_indices: List[int] = None,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        width_scale: float = 10.0,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Plot band structure with RGB color mixing.
        
        Three orbital projections are mapped to Red, Green, Blue channels.
        Mixed colors indicate mixed orbital character.
        
        Args:
            orbital_indices: List of 3 orbital indices for [R, G, B].
                Defaults to [0, 1, 2] if available.
            ax: Matplotlib axes.
            energy_range: Energy range.
            width_scale: Scale factor for line widths.
            title: Optional plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if orbital_indices is None:
            orbital_indices = list(range(min(3, self.n_orbitals)))
        
        if len(orbital_indices) != 3:
            raise ValueError("RGB mode requires exactly 3 orbital indices")
        
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.band_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        
        energies = self.eigenvalues - self.fermi_energy
        
        # Extract RGB weights
        r_weights = self.projections[:, :, :, orbital_indices[0]]
        g_weights = self.projections[:, :, :, orbital_indices[1]]
        b_weights = self.projections[:, :, :, orbital_indices[2]]
        
        for spin in range(self.n_spins):
            for band in range(self.n_bands):
                e = energies[spin, :, band]
                r = r_weights[spin, :, band]
                g = g_weights[spin, :, band]
                b = b_weights[spin, :, band]
                
                # Total weight for line width
                total = r + g + b
                
                # Create segments
                points = np.array([self.kpoints, e]).T.reshape(-1, 1, 2)
                segments = np.concatenate([points[:-1], points[1:]], axis=1)
                
                # Segment colors (average of endpoints)
                seg_r = (r[:-1] + r[1:]) / 2
                seg_g = (g[:-1] + g[1:]) / 2
                seg_b = (b[:-1] + b[1:]) / 2
                seg_total = (total[:-1] + total[1:]) / 2
                
                # Normalize to valid RGB
                max_val = np.maximum.reduce([seg_r, seg_g, seg_b])
                max_val = np.where(max_val > 0, max_val, 1.0)
                
                colors = np.zeros((len(segments), 4))
                colors[:, 0] = seg_r / max_val  # Red
                colors[:, 1] = seg_g / max_val  # Green
                colors[:, 2] = seg_b / max_val  # Blue
                colors[:, 3] = 1.0  # Alpha
                
                lc = LineCollection(
                    segments,
                    linewidths=seg_total * width_scale + 0.5,
                    colors=colors,
                    zorder=5,
                )
                ax.add_collection(lc)
        
        # Fermi level
        ax.axhline(
            0,
            color='gray',
            linestyle=self.style.fermi_linestyle,
            linewidth=self.style.fermi_linewidth,
            zorder=10,
        )
        
        self._add_kpoint_labels(ax)
        
        ax.set_xlim(self.kpoints[0], self.kpoints[-1])
        ax.set_ylim(energy_range)
        ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
        
        # Legend for RGB mapping
        labels = [self.orbital_labels[i] for i in orbital_indices]
        handles = [
            plt.Line2D([0], [0], color='red', linewidth=3, label=labels[0]),
            plt.Line2D([0], [0], color='green', linewidth=3, label=labels[1]),
            plt.Line2D([0], [0], color='blue', linewidth=3, label=labels[2]),
        ]
        ax.legend(handles=handles, loc='upper right', framealpha=0.9)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        else:
            ax.set_title('RGB Orbital-Projected Bands', fontsize=self.style.title_size)
        
        fig.tight_layout()
        return fig
    
    def plot_overlay(
        self,
        orbital_indices: Optional[List[int]] = None,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        width_scale: float = 10.0,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Plot multiple projections overlaid with different colors.
        
        Each orbital gets a distinct color from ORBITAL_COLORS.
        
        Args:
            orbital_indices: Orbitals to plot. Defaults to all.
            ax: Matplotlib axes.
            energy_range: Energy range.
            width_scale: Line width scale.
            title: Optional title.
            
        Returns:
            Matplotlib Figure object.
        """
        if orbital_indices is None:
            orbital_indices = list(range(self.n_orbitals))
        
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.band_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        
        energies = self.eigenvalues - self.fermi_energy
        
        # Get colors for each orbital
        colors = []
        for idx in orbital_indices:
            label = self.orbital_labels[idx]
            color = ORBITAL_COLORS.get(label[0].lower(), '#888888')
            colors.append(color)
        
        # Plot each orbital as scatter with variable size
        for orb_i, orb_idx in enumerate(orbital_indices):
            weights = self.projections[:, :, :, orb_idx]
            color = colors[orb_i]
            
            for spin in range(self.n_spins):
                for band in range(self.n_bands):
                    e = energies[spin, :, band]
                    w = weights[spin, :, band]
                    
                    # Only plot points with significant weight
                    mask = w > 0.05
                    if not np.any(mask):
                        continue
                    
                    ax.scatter(
                        self.kpoints[mask],
                        e[mask],
                        s=w[mask] * width_scale * 10,
                        c=color,
                        alpha=0.7,
                        label=self.orbital_labels[orb_idx] if spin == 0 and band == 0 else None,
                        zorder=5 + orb_i,
                    )
        
        # Background bands
        for spin in range(self.n_spins):
            for band in range(self.n_bands):
                ax.plot(
                    self.kpoints,
                    energies[spin, :, band],
                    color='lightgray',
                    linewidth=0.5,
                    zorder=1,
                )
        
        ax.axhline(0, **self._fermi_style())
        self._add_kpoint_labels(ax)
        
        ax.set_xlim(self.kpoints[0], self.kpoints[-1])
        ax.set_ylim(energy_range)
        ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
        
        ax.legend(loc='upper right', framealpha=0.9)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        
        fig.tight_layout()
        return fig
    
    def _add_kpoint_labels(self, ax: Axes) -> None:
        """Add high-symmetry point labels and lines."""
        if not self.kpoint_labels:
            return
        
        positions = []
        labels = []
        
        for pos, label in self.kpoint_labels:
            positions.append(pos)
            # Greek letter substitution
            if label.upper() in ('GAMMA', 'G'):
                labels.append('Γ')
            else:
                labels.append(label)
            
            ax.axvline(pos, color='gray', linewidth=0.3, zorder=0)
        
        ax.set_xticks(positions)
        ax.set_xticklabels(labels)
    
    def _fermi_style(self) -> Dict:
        """Fermi level line style."""
        return {
            'color': self.style.fermi_color,
            'linestyle': self.style.fermi_linestyle,
            'linewidth': self.style.fermi_linewidth,
            'zorder': 10,
        }
    
    def save(
        self,
        filepath: Union[str, Path],
        mode: str = 'single',
        orbital_index: int = 0,
        orbital_indices: Optional[List[int]] = None,
        **kwargs,
    ) -> None:
        """
        Save fat band plot.
        
        Args:
            filepath: Output file path.
            mode: 'single', 'rgb', or 'overlay'.
            orbital_index: For single mode.
            orbital_indices: For rgb/overlay modes.
            **kwargs: Additional arguments to plotting function.
        """
        if mode == 'single':
            fig = self.plot_single_projection(orbital_index=orbital_index, **kwargs)
        elif mode == 'rgb':
            fig = self.plot_rgb(orbital_indices=orbital_indices, **kwargs)
        elif mode == 'overlay':
            fig = self.plot_overlay(orbital_indices=orbital_indices, **kwargs)
        else:
            raise ValueError(f"Unknown mode: {mode}")
        
        fig.savefig(filepath, dpi=self.style.dpi, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Saved fat band plot to {filepath}")
