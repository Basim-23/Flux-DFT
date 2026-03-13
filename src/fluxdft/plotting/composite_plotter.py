"""
Composite Plotter for FluxDFT.

Combined band structure + DOS plots with shared energy axis.
The standard publication format for electronic structure visualization.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, Tuple, Union
from pathlib import Path
import logging

import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.gridspec import GridSpec

from .band_plotter import BandStructurePlotter
from .dos_plotter import DOSPlotter
from .styles import PlotStyle

logger = logging.getLogger(__name__)


class BandDOSPlotter:
    """
    Combined band structure + DOS plotter.
    
    Creates side-by-side plots with:
    - Band structure on the left (wider)
    - DOS on the right (narrower, vertical orientation)
    - Shared energy (y) axis
    
    This is the standard format for publication-quality electronic
    structure figures.
    
    Usage:
        >>> bs_plotter = BandStructurePlotter(...)
        >>> dos_plotter = DOSPlotter(...)
        >>> combined = BandDOSPlotter(bs_plotter, dos_plotter)
        >>> fig = combined.plot()
        >>> fig.savefig('electronic_structure.png')
    """
    
    def __init__(
        self,
        band_plotter: BandStructurePlotter,
        dos_plotter: DOSPlotter,
        style: Optional[PlotStyle] = None,
    ):
        """
        Initialize combined plotter.
        
        Args:
            band_plotter: Configured BandStructurePlotter instance.
            dos_plotter: Configured DOSPlotter instance.
            style: Optional PlotStyle (overrides individual plotter styles).
        """
        self.band_plotter = band_plotter
        self.dos_plotter = dos_plotter
        self.style = style or band_plotter.style
    
    def plot(
        self,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        width_ratio: float = 3.0,
        show_bandgap: bool = True,
        show_fermi: bool = True,
        band_title: Optional[str] = None,
        dos_title: Optional[str] = None,
        suptitle: Optional[str] = None,
    ) -> Figure:
        """
        Generate combined band structure + DOS plot.
        
        Args:
            energy_range: Shared energy range relative to Fermi level.
            width_ratio: Ratio of band plot width to DOS plot width.
            show_bandgap: Show band gap annotation on band structure.
            show_fermi: Show Fermi level line.
            band_title: Optional title for band structure subplot.
            dos_title: Optional title for DOS subplot.
            suptitle: Optional super-title for entire figure.
            
        Returns:
            Matplotlib Figure object.
        """
        fig = plt.figure(figsize=self.style.combined_figsize)
        
        # Create gridspec with specified width ratio
        gs = GridSpec(1, 2, width_ratios=[width_ratio, 1], wspace=0.05)
        
        ax_bands = fig.add_subplot(gs[0])
        ax_dos = fig.add_subplot(gs[1], sharey=ax_bands)
        
        # Plot band structure
        self.band_plotter.style = self.style
        self.band_plotter.plot(
            ax=ax_bands,
            energy_range=energy_range,
            show_fermi=show_fermi,
            show_bandgap=show_bandgap,
            title=band_title,
        )
        
        # Plot DOS (vertical orientation to share y-axis with bands)
        self.dos_plotter.style = self.style
        self.dos_plotter.plot(
            ax=ax_dos,
            energy_range=energy_range,
            orientation='vertical',
            show_fermi=False,  # Already shown in band plot
            title=dos_title,
        )
        
        # Fix axes
        ax_dos.set_ylabel('')  # Remove duplicate y-label
        ax_dos.tick_params(axis='y', labelleft=False)
        
        # Fermi line continues across both plots
        if show_fermi:
            ax_dos.axhline(
                0,
                color=self.style.fermi_color,
                linestyle=self.style.fermi_linestyle,
                linewidth=self.style.fermi_linewidth,
            )
        
        if suptitle:
            fig.suptitle(suptitle, fontsize=self.style.title_size + 2)
        
        fig.tight_layout()
        
        return fig
    
    def plot_with_pdos(
        self,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        width_ratio: float = 3.0,
        show_total_dos: bool = True,
        species_filter: Optional[list] = None,
        orbital_filter: Optional[list] = None,
        suptitle: Optional[str] = None,
    ) -> Figure:
        """
        Generate combined band structure + PDOS plot.
        
        Args:
            energy_range: Shared energy range.
            width_ratio: Band:DOS width ratio.
            show_total_dos: Show total DOS as background.
            species_filter: Only show these elements.
            orbital_filter: Only show these orbitals.
            suptitle: Optional super-title.
            
        Returns:
            Matplotlib Figure object.
        """
        fig = plt.figure(figsize=self.style.combined_figsize)
        gs = GridSpec(1, 2, width_ratios=[width_ratio, 1], wspace=0.05)
        
        ax_bands = fig.add_subplot(gs[0])
        ax_dos = fig.add_subplot(gs[1], sharey=ax_bands)
        
        # Band structure
        self.band_plotter.style = self.style
        self.band_plotter.plot(
            ax=ax_bands,
            energy_range=energy_range,
            show_fermi=True,
            show_bandgap=True,
        )
        
        # PDOS
        self.dos_plotter.style = self.style
        self.dos_plotter.plot_pdos(
            ax=ax_dos,
            energy_range=energy_range,
            orientation='vertical',
            show_total=show_total_dos,
            species_filter=species_filter,
            orbital_filter=orbital_filter,
        )
        
        ax_dos.set_ylabel('')
        ax_dos.tick_params(axis='y', labelleft=False)
        
        ax_dos.axhline(
            0,
            color=self.style.fermi_color,
            linestyle=self.style.fermi_linestyle,
            linewidth=self.style.fermi_linewidth,
        )
        
        if suptitle:
            fig.suptitle(suptitle, fontsize=self.style.title_size + 2)
        
        fig.tight_layout()
        return fig
    
    def save(
        self,
        filepath: Union[str, Path],
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        **kwargs,
    ) -> None:
        """Generate and save combined plot."""
        fig = self.plot(energy_range=energy_range, **kwargs)
        fig.savefig(filepath, dpi=self.style.dpi, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Saved combined band+DOS plot to {filepath}")


class MultiBandPlotter:
    """
    Plot multiple band structures for comparison.
    
    Useful for:
    - Comparing different calculations (LDA vs GGA)
    - Showing spin-up/down separately
    - Comparing materials
    """
    
    def __init__(
        self,
        plotters: list,
        labels: Optional[list] = None,
        style: Optional[PlotStyle] = None,
    ):
        """
        Initialize multi-band plotter.
        
        Args:
            plotters: List of BandStructurePlotter instances.
            labels: Labels for each band structure.
            style: Shared PlotStyle.
        """
        self.plotters = plotters
        self.labels = labels or [f'Calc {i+1}' for i in range(len(plotters))]
        self.style = style or PlotStyle()
    
    def plot_overlay(
        self,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        colors: Optional[list] = None,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Overlay all band structures on single axes.
        
        Args:
            energy_range: Energy range.
            colors: List of colors for each band structure.
            title: Plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if colors is None:
            # Use a colormap
            cmap = plt.get_cmap('tab10')
            colors = [cmap(i) for i in range(len(self.plotters))]
        
        fig, ax = plt.subplots(figsize=self.style.band_figsize)
        self.style.apply_to_axes(ax)
        
        for i, (plotter, label, color) in enumerate(zip(self.plotters, self.labels, colors)):
            energies = plotter.eigenvalues - plotter.fermi_energy
            
            for spin in range(plotter.n_spins):
                for band in range(plotter.n_bands):
                    ax.plot(
                        plotter.kpoints,
                        energies[spin, :, band],
                        color=color,
                        linewidth=self.style.band_linewidth,
                        alpha=0.8,
                        label=label if spin == 0 and band == 0 else None,
                    )
            
            # Add k-point labels from first plotter
            if i == 0 and plotter.kpoint_labels:
                for pos, lbl in plotter.kpoint_labels:
                    ax.axvline(pos, color='gray', linewidth=0.3)
                positions = [p for p, _ in plotter.kpoint_labels]
                labels_fmt = [l if l.upper() not in ('GAMMA', 'G') else 'Γ' 
                              for _, l in plotter.kpoint_labels]
                ax.set_xticks(positions)
                ax.set_xticklabels(labels_fmt)
        
        ax.axhline(0, color=self.style.fermi_color, 
                   linestyle='--', linewidth=self.style.fermi_linewidth)
        
        ax.set_xlim(self.plotters[0].kpoints[0], self.plotters[0].kpoints[-1])
        ax.set_ylim(energy_range)
        ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
        
        ax.legend(loc='upper right', framealpha=0.9)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        
        fig.tight_layout()
        return fig
    
    def plot_grid(
        self,
        energy_range: Tuple[float, float] = (-6.0, 6.0),
        ncols: int = 2,
        titles: Optional[list] = None,
    ) -> Figure:
        """
        Plot band structures in a grid layout.
        
        Args:
            energy_range: Shared energy range.
            ncols: Number of columns.
            titles: Titles for each subplot.
            
        Returns:
            Matplotlib Figure object.
        """
        n = len(self.plotters)
        nrows = (n + ncols - 1) // ncols
        
        fig, axes = plt.subplots(
            nrows, ncols,
            figsize=(self.style.band_figsize[0] * ncols * 0.6,
                     self.style.band_figsize[1] * nrows * 0.8),
            sharey=True,
        )
        axes = axes.flatten() if n > 1 else [axes]
        
        titles = titles or self.labels
        
        for i, (plotter, ax, title) in enumerate(zip(self.plotters, axes, titles)):
            plotter.style = self.style
            plotter.plot(
                ax=ax,
                energy_range=energy_range,
                title=title,
            )
            
            if i % ncols != 0:
                ax.set_ylabel('')
        
        # Hide unused axes
        for j in range(n, len(axes)):
            axes[j].set_visible(False)
        
        fig.tight_layout()
        return fig
