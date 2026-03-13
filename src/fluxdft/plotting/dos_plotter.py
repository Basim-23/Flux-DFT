"""
Density of States Plotter for FluxDFT.

Publication-quality DOS visualization with:
- Total and projected DOS support
- Spin-polarized (mirrored) display
- Filled area visualization
- Fermi level alignment
- Horizontal and vertical orientations

Inspired by sumo's SDOSPlotter and pyprocar's DOSPlot.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path
import numpy as np
import logging

import matplotlib.pyplot as plt
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from .styles import PlotStyle, get_element_color, get_orbital_color

logger = logging.getLogger(__name__)


class DOSPlotter:
    """
    Publication-quality density of states plotter.
    
    Features:
        - Total DOS plotting
        - Projected DOS (PDOS) by element/orbital
        - Spin-polarized display (mirrored or overlaid)
        - Filled area visualization
        - Fermi level alignment (E - Ef = 0)
        - Horizontal and vertical orientations
        - Stacked PDOS display
        
    Usage:
        >>> plotter = DOSPlotter(
        ...     energies=e_grid,
        ...     total_dos=dos_total,  # Shape: (n_energies,) or (2, n_energies)
        ...     fermi_energy=efermi,
        ... )
        >>> fig = plotter.plot()
        
        # With projected DOS:
        >>> plotter = DOSPlotter(
        ...     energies=e_grid,
        ...     total_dos=dos_total,
        ...     fermi_energy=efermi,
        ...     pdos={'Si-s': si_s, 'Si-p': si_p, 'O-p': o_p},
        ... )
        >>> fig = plotter.plot_pdos()
    """
    
    def __init__(
        self,
        energies: np.ndarray,
        total_dos: np.ndarray,
        fermi_energy: float,
        pdos: Optional[Dict[str, np.ndarray]] = None,
        style: Optional[PlotStyle] = None,
    ):
        """
        Initialize DOS plotter.
        
        Args:
            energies: Energy grid in eV (n_energies,).
            total_dos: Total DOS values.
                Shape: (n_energies,) for non-spin-polarized
                Shape: (2, n_energies) for spin-polarized [up, down]
            fermi_energy: Fermi energy in eV.
            pdos: Optional dict of projected DOS.
                Keys: 'Element-orbital' (e.g., 'Si-s', 'O-p')
                Values: DOS arrays matching total_dos shape
            style: PlotStyle configuration.
        """
        self.energies_raw = np.asarray(energies)
        self.fermi_energy = float(fermi_energy)
        
        # Shift energies to Fermi level
        self.energies = self.energies_raw - self.fermi_energy
        
        # Normalize total_dos to 2D array
        total_dos = np.asarray(total_dos)
        if total_dos.ndim == 1:
            self.total_dos = total_dos[np.newaxis, :]
        else:
            self.total_dos = total_dos
        
        self.is_spin_polarized = self.total_dos.shape[0] == 2
        
        # Projected DOS
        self.pdos = pdos or {}
        
        self.style = style or PlotStyle()
    
    def plot(
        self,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-10.0, 10.0),
        orientation: str = 'vertical',
        show_fermi: bool = True,
        show_fill: bool = True,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Plot total density of states.
        
        Args:
            ax: Matplotlib axes. Creates new figure if None.
            energy_range: (min, max) energy range relative to Fermi level.
            orientation: 'vertical' (DOS on x-axis) or 'horizontal' (DOS on y-axis).
            show_fermi: Show Fermi level indicator.
            show_fill: Fill area under DOS curve.
            title: Optional plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.dos_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        self.style.apply_to_figure(fig)
        
        # Mask to energy range
        mask = (self.energies >= energy_range[0]) & (self.energies <= energy_range[1])
        e = self.energies[mask]
        
        if orientation == 'vertical':
            self._plot_vertical(ax, e, mask, show_fill)
            if show_fermi:
                ax.axhline(0, **self._fermi_style())
            ax.set_ylim(energy_range)
            ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
            ax.set_xlabel('DOS (states/eV)', fontsize=self.style.label_size)
        else:
            self._plot_horizontal(ax, e, mask, show_fill)
            if show_fermi:
                ax.axvline(0, **self._fermi_style())
            ax.set_xlim(energy_range)
            ax.set_xlabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
            ax.set_ylabel('DOS (states/eV)', fontsize=self.style.label_size)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        
        if self.is_spin_polarized:
            ax.legend(loc='best', fontsize=self.style.tick_size, framealpha=0.9)
        
        fig.tight_layout()
        return fig
    
    def _plot_vertical(
        self,
        ax: Axes,
        e: np.ndarray,
        mask: np.ndarray,
        show_fill: bool,
    ) -> None:
        """Plot DOS with energy on y-axis."""
        if self.is_spin_polarized:
            dos_up = self.total_dos[0][mask]
            dos_down = self.total_dos[1][mask]
            
            if show_fill:
                ax.fill_betweenx(
                    e, 0, dos_up,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.spin_up_color,
                )
                ax.fill_betweenx(
                    e, 0, -dos_down,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.spin_down_color,
                )
            
            ax.plot(
                dos_up, e,
                color=self.style.spin_up_color,
                linewidth=self.style.band_linewidth,
                label='Spin ↑',
            )
            ax.plot(
                -dos_down, e,
                color=self.style.spin_down_color,
                linewidth=self.style.band_linewidth,
                label='Spin ↓',
            )
            
            # Zero line for spin separation
            ax.axvline(0, color=self.style.grid_color, linewidth=0.5)
            
            # Symmetric x-axis
            max_dos = max(np.max(dos_up), np.max(dos_down)) * 1.1
            ax.set_xlim(-max_dos, max_dos)
        else:
            dos = self.total_dos[0][mask]
            
            if show_fill:
                ax.fill_betweenx(
                    e, 0, dos,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.dos_color,
                )
            
            ax.plot(
                dos, e,
                color=self.style.dos_color,
                linewidth=self.style.band_linewidth,
            )
            
            ax.set_xlim(0, np.max(dos) * 1.1)
    
    def _plot_horizontal(
        self,
        ax: Axes,
        e: np.ndarray,
        mask: np.ndarray,
        show_fill: bool,
    ) -> None:
        """Plot DOS with energy on x-axis (traditional orientation)."""
        if self.is_spin_polarized:
            dos_up = self.total_dos[0][mask]
            dos_down = self.total_dos[1][mask]
            
            if show_fill:
                ax.fill_between(
                    e, 0, dos_up,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.spin_up_color,
                )
                ax.fill_between(
                    e, 0, -dos_down,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.spin_down_color,
                )
            
            ax.plot(
                e, dos_up,
                color=self.style.spin_up_color,
                linewidth=self.style.band_linewidth,
                label='Spin ↑',
            )
            ax.plot(
                e, -dos_down,
                color=self.style.spin_down_color,
                linewidth=self.style.band_linewidth,
                label='Spin ↓',
            )
            
            ax.axhline(0, color=self.style.grid_color, linewidth=0.5)
        else:
            dos = self.total_dos[0][mask]
            
            if show_fill:
                ax.fill_between(
                    e, 0, dos,
                    alpha=self.style.dos_fill_alpha,
                    color=self.style.dos_color,
                )
            
            ax.plot(
                e, dos,
                color=self.style.dos_color,
                linewidth=self.style.band_linewidth,
            )
    
    def plot_pdos(
        self,
        ax: Optional[Axes] = None,
        energy_range: Tuple[float, float] = (-10.0, 10.0),
        orientation: str = 'vertical',
        show_total: bool = True,
        stack: bool = False,
        species_filter: Optional[List[str]] = None,
        orbital_filter: Optional[List[str]] = None,
        title: Optional[str] = None,
    ) -> Figure:
        """
        Plot projected density of states.
        
        Args:
            ax: Matplotlib axes.
            energy_range: Energy range relative to Fermi level.
            orientation: 'vertical' or 'horizontal'.
            show_total: Show total DOS as background.
            stack: Stack PDOS contributions.
            species_filter: Only show these elements (e.g., ['Si', 'O']).
            orbital_filter: Only show these orbitals (e.g., ['s', 'p']).
            title: Optional plot title.
            
        Returns:
            Matplotlib Figure object.
        """
        if not self.pdos:
            logger.warning("No PDOS data available, plotting total DOS only")
            return self.plot(ax=ax, energy_range=energy_range, orientation=orientation)
        
        if ax is None:
            fig, ax = plt.subplots(figsize=self.style.dos_figsize)
        else:
            fig = ax.get_figure()
        
        self.style.apply_to_axes(ax)
        self.style.apply_to_figure(fig)
        
        mask = (self.energies >= energy_range[0]) & (self.energies <= energy_range[1])
        e = self.energies[mask]
        
        # Filter PDOS components
        filtered_pdos = self._filter_pdos(species_filter, orbital_filter)
        
        if orientation == 'vertical':
            self._plot_pdos_vertical(ax, e, mask, filtered_pdos, show_total, stack)
            ax.axhline(0, **self._fermi_style())
            ax.set_ylim(energy_range)
            ax.set_ylabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
            ax.set_xlabel('DOS (states/eV)', fontsize=self.style.label_size)
        else:
            self._plot_pdos_horizontal(ax, e, mask, filtered_pdos, show_total, stack)
            ax.axvline(0, **self._fermi_style())
            ax.set_xlim(energy_range)
            ax.set_xlabel('E − E$_F$ (eV)', fontsize=self.style.label_size)
            ax.set_ylabel('DOS (states/eV)', fontsize=self.style.label_size)
        
        ax.legend(loc='best', fontsize=self.style.tick_size - 1, framealpha=0.9)
        
        if title:
            ax.set_title(title, fontsize=self.style.title_size)
        
        fig.tight_layout()
        return fig
    
    def _plot_pdos_vertical(
        self,
        ax: Axes,
        e: np.ndarray,
        mask: np.ndarray,
        pdos_dict: Dict[str, np.ndarray],
        show_total: bool,
        stack: bool,
    ) -> None:
        """Plot PDOS with energy on y-axis."""
        # Background: total DOS
        if show_total:
            total = self.total_dos[0][mask]
            ax.fill_betweenx(
                e, 0, total,
                alpha=0.15,
                color='gray',
                label='Total',
            )
        
        # Foreground: PDOS components
        for label, pdos in pdos_dict.items():
            pdos_masked = pdos[mask] if pdos.ndim == 1 else pdos[0][mask]
            
            # Get color based on element or orbital
            parts = label.split('-')
            if len(parts) == 2:
                element, orbital = parts
                color = get_orbital_color(orbital)
            else:
                color = get_element_color(label)
            
            ax.plot(
                pdos_masked, e,
                color=color,
                linewidth=self.style.band_linewidth,
                label=label,
            )
    
    def _plot_pdos_horizontal(
        self,
        ax: Axes,
        e: np.ndarray,
        mask: np.ndarray,
        pdos_dict: Dict[str, np.ndarray],
        show_total: bool,
        stack: bool,
    ) -> None:
        """Plot PDOS with energy on x-axis."""
        if show_total:
            total = self.total_dos[0][mask]
            ax.fill_between(
                e, 0, total,
                alpha=0.15,
                color='gray',
                label='Total',
            )
        
        for label, pdos in pdos_dict.items():
            pdos_masked = pdos[mask] if pdos.ndim == 1 else pdos[0][mask]
            
            parts = label.split('-')
            if len(parts) == 2:
                color = get_orbital_color(parts[1])
            else:
                color = get_element_color(label)
            
            ax.plot(
                e, pdos_masked,
                color=color,
                linewidth=self.style.band_linewidth,
                label=label,
            )
    
    def _filter_pdos(
        self,
        species: Optional[List[str]],
        orbitals: Optional[List[str]],
    ) -> Dict[str, np.ndarray]:
        """Filter PDOS by species and/or orbitals."""
        filtered = {}
        
        for label, pdos in self.pdos.items():
            parts = label.split('-')
            
            # Check species filter
            if species and len(parts) >= 1:
                if parts[0] not in species:
                    continue
            
            # Check orbital filter
            if orbitals and len(parts) >= 2:
                if parts[1] not in orbitals:
                    continue
            
            filtered[label] = pdos
        
        return filtered
    
    def _fermi_style(self) -> Dict:
        """Get Fermi level line style kwargs."""
        return {
            'color': self.style.fermi_color,
            'linestyle': self.style.fermi_linestyle,
            'linewidth': self.style.fermi_linewidth,
            'label': 'E$_F$',
        }
    
    def save(
        self,
        filepath: Union[str, Path],
        energy_range: Tuple[float, float] = (-10.0, 10.0),
        **kwargs,
    ) -> None:
        """Generate and save DOS plot."""
        fig = self.plot(energy_range=energy_range, **kwargs)
        fig.savefig(filepath, dpi=self.style.dpi, bbox_inches='tight')
        plt.close(fig)
        logger.info(f"Saved DOS plot to {filepath}")
    
    @classmethod
    def from_pymatgen(
        cls,
        dos,  # pymatgen.electronic_structure.dos.Dos or CompleteDos
        style: Optional[PlotStyle] = None,
    ) -> 'DOSPlotter':
        """
        Create plotter from pymatgen DOS object.
        
        Args:
            dos: pymatgen Dos or CompleteDos object.
            style: Optional PlotStyle.
            
        Returns:
            DOSPlotter instance.
        """
        from pymatgen.electronic_structure.dos import Dos, CompleteDos
        from pymatgen.electronic_structure.core import Spin
        
        energies = dos.energies
        fermi = dos.efermi
        
        # Get densities
        densities = dos.get_densities()
        
        if isinstance(densities, dict):
            # Spin-polarized
            if Spin.up in densities:
                total_dos = np.array([densities[Spin.up], densities[Spin.down]])
            elif 1 in densities:  # Sometimes uses int keys
                total_dos = np.array([densities[1], densities[-1]])
            else:
                # Non-spin case returning dict
                total_dos = np.array(list(densities.values())[0])
        else:
            total_dos = np.array(densities)
        
        # Extract PDOS if available
        pdos = {}
        if isinstance(dos, CompleteDos):
            element_dos = dos.get_element_dos()
            for el, el_dos in element_dos.items():
                el_densities = el_dos.get_densities()
                if isinstance(el_densities, dict):
                    pdos[str(el)] = np.array(list(el_densities.values())[0])
                else:
                    pdos[str(el)] = np.array(el_densities)
        
        return cls(
            energies=energies,
            total_dos=total_dos,
            fermi_energy=fermi,
            pdos=pdos if pdos else None,
            style=style,
        )
