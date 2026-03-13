"""
Projected Density of States (PDOS) plot recipe.
"""

from typing import Dict, Optional, List
from pathlib import Path
import numpy as np

from .base import PlotRecipe, PlotMetadata, PlotStyle


class PDOSRecipe(PlotRecipe):
    """
    Projected Density of States plot.
    
    Features:
    - Orbital-resolved DOS (s, p, d, f)
    - Element-resolved DOS
    - Stacked or overlaid presentation
    - Spin polarization support
    """
    
    recipe_id = "PDOS_001"
    name = "Projected DOS"
    description = "Orbital and element-resolved density of states"
    required_data = ["dos_energy", "pdos_data", "fermi_energy"]
    
    # Orbital colors
    ORBITAL_COLORS = {
        "s": "#89b4fa",
        "p": "#a6e3a1",
        "d": "#f9e2af",
        "f": "#f38ba8",
        "tot": "#cdd6f4",
    }
    
    E_RANGE = 10.0
    
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        return (
            job_type in ("pdos", "projwfc") and
            self._check_required_data(available_data)
        )
    
    def generate(
        self,
        data: Dict,
        output_dir: Path,
        style: Optional[PlotStyle] = None,
    ) -> PlotMetadata:
        import matplotlib.pyplot as plt
        
        style = style or self.style
        
        energy = np.array(data["dos_energy"]) - data["fermi_energy"]
        pdos_data = data["pdos_data"]  # Dict: {element: {orbital: dos_array}}
        
        fig, ax = plt.subplots(figsize=(8, 6))
        style.apply(fig, ax)
        
        # Plot each element's orbital contributions
        for element, orbitals in pdos_data.items():
            for orbital, dos in orbitals.items():
                color = self.ORBITAL_COLORS.get(orbital, "#cdd6f4")
                label = f"{element}-{orbital}"
                
                ax.fill_between(
                    energy, 0, dos,
                    alpha=0.2,
                    color=color,
                )
                ax.plot(
                    energy, dos,
                    color=color,
                    lw=style.line_width,
                    label=label,
                )
        
        # Fermi level
        ax.axvline(0, color=style.fermi_color, ls="--", lw=0.8, label="E$_F$")
        
        # Axis configuration
        ax.set_xlim(-self.E_RANGE, self.E_RANGE)
        ax.set_ylim(0, None)
        ax.set_xlabel("E − E$_F$ (eV)", fontsize=style.font_size)
        ax.set_ylabel("PDOS (states/eV)", fontsize=style.font_size)
        ax.set_title("Projected Density of States", fontsize=style.title_size)
        ax.legend(loc="upper right", framealpha=0.9, fontsize=9)
        
        # Save
        plt.tight_layout()
        filename = "pdos.png"
        path = self._save_figure(fig, output_dir, filename, style)
        plt.close(fig)
        
        return PlotMetadata(
            recipe_id=self.recipe_id,
            title="Projected DOS",
            filename=filename,
            path=path,
            format="png",
            parameters={
                "elements": list(pdos_data.keys()),
            },
        )
