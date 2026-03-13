"""
Base classes for plot recipes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from datetime import datetime


@dataclass
class PlotMetadata:
    """Metadata for a generated plot."""
    recipe_id: str
    title: str
    filename: str
    path: Path
    format: str  # "png", "pdf", "svg"
    timestamp: datetime = field(default_factory=datetime.now)
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "recipe_id": self.recipe_id,
            "title": self.title,
            "filename": self.filename,
            "path": str(self.path),
            "format": self.format,
            "timestamp": self.timestamp.isoformat(),
            "parameters": self.parameters,
        }


@dataclass
class PlotStyle:
    """
    Consistent styling for publication-quality plots.
    
    Uses FluxDFT's dark theme colors.
    """
    
    # Colors
    bg_color: str = "#1e1e2e"
    fg_color: str = "#cdd6f4"
    grid_color: str = "#45475a"
    accent_color: str = "#89b4fa"
    
    # Spin colors
    spin_up_color: str = "#89b4fa"
    spin_down_color: str = "#f38ba8"
    
    # Reference colors
    fermi_color: str = "#a6adc8"
    ref_color: str = "#a6e3a1"
    
    # Sizes
    line_width: float = 1.2
    font_size: int = 11
    title_size: int = 13
    dpi: int = 300
    
    def apply(self, fig, ax):
        """Apply style to matplotlib figure and axes."""
        import matplotlib.pyplot as plt
        
        fig.set_facecolor(self.bg_color)
        ax.set_facecolor(self.bg_color)
        
        # Spines
        for spine in ax.spines.values():
            spine.set_color(self.grid_color)
        
        # Ticks and labels
        ax.tick_params(colors=self.fg_color, labelsize=self.font_size)
        ax.xaxis.label.set_color(self.fg_color)
        ax.yaxis.label.set_color(self.fg_color)
        ax.title.set_color(self.fg_color)
        
        # Grid
        ax.grid(True, alpha=0.2, color=self.grid_color)


class PlotRecipe(ABC):
    """
    Base class for deterministic plot recipes.
    
    Each recipe defines:
    - What data it needs
    - How to check applicability
    - How to generate the plot
    """
    
    recipe_id: str = "PLOT_000"
    name: str = "Unknown Plot"
    description: str = ""
    required_data: List[str] = []
    
    def __init__(self):
        self.style = PlotStyle()
    
    @abstractmethod
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        """Check if this recipe can be applied."""
        pass
    
    @abstractmethod
    def generate(
        self,
        data: Dict,
        output_dir: Path,
        style: Optional[PlotStyle] = None,
    ) -> PlotMetadata:
        """Generate the plot and return metadata."""
        pass
    
    def _check_required_data(self, data: Dict) -> bool:
        """Check if all required data is present."""
        return all(key in data and data[key] is not None for key in self.required_data)
    
    def _save_figure(
        self,
        fig,
        output_dir: Path,
        filename: str,
        style: PlotStyle,
    ) -> Path:
        """Save figure with consistent settings."""
        path = output_dir / filename
        fig.savefig(
            path,
            dpi=style.dpi,
            bbox_inches="tight",
            facecolor=style.bg_color,
            edgecolor="none",
        )
        return path
