"""
Plot Styles and Themes for FluxDFT.

Provides unified styling for all electronic structure plots.
Inspired by sumo's clean publication-quality aesthetics.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import matplotlib.pyplot as plt
import matplotlib as mpl


@dataclass
class PlotStyle:
    """
    Unified styling configuration for electronic structure plots.
    
    Provides consistent colors, fonts, and line styles across
    all FluxDFT plotting functions.
    """
    
    # === Colors ===
    # Primary band/line color
    band_color: str = "#3366cc"
    
    # DOS fill color
    dos_color: str = "#3366cc"
    
    # Spin-polarized colors
    spin_up_color: str = "#3366cc"
    spin_down_color: str = "#cc3366"
    
    # Fermi level indicator
    fermi_color: str = "#ff6600"
    
    # Reference/comparison data
    reference_color: str = "#999999"
    
    # Grid and axes
    grid_color: str = "#e0e0e0"
    axis_color: str = "#333333"
    
    # Colormap for projections
    projection_cmap: str = "coolwarm"
    
    # === Typography ===
    font_family: str = "sans-serif"
    font_size: int = 12
    label_size: int = 14
    title_size: int = 16
    tick_size: int = 11
    
    # Use LaTeX for labels (requires LaTeX installation)
    use_latex: bool = False
    
    # === Lines ===
    band_linewidth: float = 1.5
    fermi_linewidth: float = 1.0
    grid_linewidth: float = 0.5
    reference_linewidth: float = 1.2
    
    # Line styles
    fermi_linestyle: str = "--"
    reference_linestyle: str = "--"
    spin_down_linestyle: str = "--"
    
    # === Fill ===
    dos_fill_alpha: float = 0.3
    reference_fill_alpha: float = 0.2
    
    # === Figure ===
    dpi: int = 300
    figure_padding: float = 0.1
    
    # Default figure sizes (width, height in inches)
    band_figsize: Tuple[float, float] = (8.0, 6.0)
    dos_figsize: Tuple[float, float] = (4.0, 6.0)
    combined_figsize: Tuple[float, float] = (10.0, 6.0)
    
    # === Markers ===
    vbm_cbm_marker: str = "o"
    vbm_cbm_size: float = 8.0
    
    def apply_to_axes(self, ax: plt.Axes) -> None:
        """Apply style settings to a matplotlib axes."""
        ax.tick_params(
            axis='both',
            which='major',
            labelsize=self.tick_size,
            direction='in',
            top=True,
            right=True,
        )
        ax.tick_params(
            axis='both',
            which='minor',
            direction='in',
            top=True,
            right=True,
        )
        
        # Spine colors
        for spine in ax.spines.values():
            spine.set_color(self.axis_color)
            spine.set_linewidth(0.8)
    
    def apply_to_figure(self, fig: plt.Figure) -> None:
        """Apply style settings to a matplotlib figure."""
        fig.set_dpi(self.dpi)
    
    def get_matplotlib_rcparams(self) -> Dict:
        """Get matplotlib rcParams dict for this style."""
        params = {
            'font.family': self.font_family,
            'font.size': self.font_size,
            'axes.labelsize': self.label_size,
            'axes.titlesize': self.title_size,
            'xtick.labelsize': self.tick_size,
            'ytick.labelsize': self.tick_size,
            'figure.dpi': self.dpi,
            'savefig.dpi': self.dpi,
            'axes.linewidth': 0.8,
            'lines.linewidth': self.band_linewidth,
        }
        
        if self.use_latex:
            params.update({
                'text.usetex': True,
                'font.family': 'serif',
            })
        
        return params
    
    @classmethod
    def publication(cls) -> 'PlotStyle':
        """
        Style optimized for journal publication.
        
        Features:
        - High DPI (600)
        - Thinner lines
        - Smaller fonts for typical journal column widths
        """
        return cls(
            band_linewidth=1.2,
            fermi_linewidth=0.8,
            font_size=10,
            label_size=11,
            title_size=12,
            tick_size=9,
            dpi=600,
            band_figsize=(3.5, 2.8),  # Single column width
            dos_figsize=(1.8, 2.8),
            combined_figsize=(5.0, 2.8),
        )
    
    @classmethod
    def presentation(cls) -> 'PlotStyle':
        """
        Style optimized for presentations/posters.
        
        Features:
        - Larger fonts
        - Thicker lines
        - Vibrant colors
        """
        return cls(
            band_linewidth=2.5,
            fermi_linewidth=1.5,
            font_size=16,
            label_size=18,
            title_size=22,
            tick_size=14,
            dpi=150,
            band_color="#2255bb",
            spin_up_color="#2255bb",
            spin_down_color="#dd2266",
            fermi_color="#ff8800",
        )
    
    @classmethod
    def dark_mode(cls) -> 'PlotStyle':
        """
        Dark mode style for screen viewing.
        """
        return cls(
            band_color="#6699ff",
            dos_color="#6699ff",
            spin_up_color="#6699ff",
            spin_down_color="#ff6699",
            fermi_color="#ffaa33",
            reference_color="#666666",
            grid_color="#404040",
            axis_color="#cccccc",
        )


class PlotTheme:
    """
    Context manager for applying plot styles.
    
    Usage:
        style = PlotStyle.publication()
        with PlotTheme(style):
            fig, ax = plt.subplots()
            # ... plotting code ...
    """
    
    def __init__(self, style: PlotStyle):
        self.style = style
        self._original_rcparams = {}
    
    def __enter__(self):
        # Save current rcParams
        self._original_rcparams = dict(plt.rcParams)
        
        # Apply style
        params = self.style.get_matplotlib_rcparams()
        plt.rcParams.update(params)
        
        return self.style
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Restore original rcParams
        plt.rcParams.update(self._original_rcparams)
        return False


# Predefined color palettes for multi-series plots
ORBITAL_COLORS = {
    's': '#ff4444',
    'p': '#44ff44', 
    'd': '#4444ff',
    'f': '#ff44ff',
}

ELEMENT_COLORS = {
    # Alkali metals
    'Li': '#cc80ff', 'Na': '#ab5cf2', 'K': '#8f40d4',
    # Alkaline earth
    'Be': '#c2ff00', 'Mg': '#8aff00', 'Ca': '#3dff00',
    # Transition metals
    'Fe': '#e06633', 'Co': '#f090a0', 'Ni': '#50d050',
    'Cu': '#c88033', 'Zn': '#7d80b0',
    # Main group
    'B': '#ffb5b5', 'C': '#909090', 'N': '#3050f8', 'O': '#ff0d0d',
    'Si': '#f0c8a0', 'P': '#ff8000', 'S': '#ffff30',
    # Default
    'default': '#888888',
}


def get_element_color(symbol: str) -> str:
    """Get color for an element symbol."""
    return ELEMENT_COLORS.get(symbol, ELEMENT_COLORS['default'])


def get_orbital_color(orbital: str) -> str:
    """Get color for an orbital type."""
    # Handle combined names like 'dx2-y2' -> 'd'
    base = orbital[0].lower() if orbital else 's'
    return ORBITAL_COLORS.get(base, '#888888')
