"""
Convergence plot recipe.
"""

from typing import Dict, Optional, List
from pathlib import Path
import numpy as np

from .base import PlotRecipe, PlotMetadata, PlotStyle


class ConvergenceRecipe(PlotRecipe):
    """
    SCF and relaxation convergence plots.
    
    Features:
    - SCF energy convergence per iteration
    - Forces convergence for relaxation
    - Threshold lines showing convergence criteria
    """
    
    recipe_id = "CONV_001"
    name = "Convergence"
    description = "SCF and relaxation convergence history"
    required_data = ["scf_energies"]
    
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        return "scf_energies" in available_data or "forces_history" in available_data
    
    def generate(
        self,
        data: Dict,
        output_dir: Path,
        style: Optional[PlotStyle] = None,
    ) -> PlotMetadata:
        import matplotlib.pyplot as plt
        
        style = style or self.style
        
        has_scf = "scf_energies" in data
        has_forces = "forces_history" in data
        
        if has_scf and has_forces:
            fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
            style.apply(fig, ax1)
            style.apply(fig, ax2)
            self._plot_scf(ax1, data["scf_energies"], style)
            self._plot_forces(ax2, data["forces_history"], data.get("forc_conv_thr"), style)
        elif has_scf:
            fig, ax1 = plt.subplots(figsize=(8, 5))
            style.apply(fig, ax1)
            self._plot_scf(ax1, data["scf_energies"], style)
        elif has_forces:
            fig, ax2 = plt.subplots(figsize=(8, 5))
            style.apply(fig, ax2)
            self._plot_forces(ax2, data["forces_history"], data.get("forc_conv_thr"), style)
        else:
            return None
        
        plt.tight_layout()
        filename = "convergence.png"
        path = self._save_figure(fig, output_dir, filename, style)
        plt.close(fig)
        
        return PlotMetadata(
            recipe_id=self.recipe_id,
            title="Convergence",
            filename=filename,
            path=path,
            format="png",
            parameters={
                "has_scf": has_scf,
                "has_forces": has_forces,
            },
        )
    
    def _plot_scf(self, ax, scf_energies: List[float], style: PlotStyle):
        """Plot SCF energy convergence."""
        energies = np.array(scf_energies)
        iterations = np.arange(1, len(energies) + 1)
        
        # Energy per iteration
        ax.plot(
            iterations, energies,
            'o-',
            color=style.accent_color,
            lw=style.line_width,
            markersize=4,
        )
        
        ax.set_xlabel("SCF Iteration", fontsize=style.font_size)
        ax.set_ylabel("Total Energy (Ry)", fontsize=style.font_size)
        ax.set_title("SCF Convergence", fontsize=style.title_size)
        
        # Add energy change inset if enough points
        if len(energies) > 2:
            dE = np.abs(np.diff(energies))
            ax2 = ax.twinx()
            ax2.semilogy(
                iterations[1:], dE,
                's--',
                color=style.ref_color,
                lw=1,
                markersize=3,
                alpha=0.7,
            )
            ax2.set_ylabel("ΔE (Ry)", color=style.ref_color, fontsize=style.font_size - 1)
            ax2.tick_params(axis='y', colors=style.ref_color)
    
    def _plot_forces(
        self,
        ax,
        forces_history: List[float],
        threshold: Optional[float],
        style: PlotStyle,
    ):
        """Plot maximum force convergence."""
        forces = np.array(forces_history)
        steps = np.arange(1, len(forces) + 1)
        
        ax.semilogy(
            steps, forces,
            'o-',
            color=style.accent_color,
            lw=style.line_width,
            markersize=5,
        )
        
        # Threshold line
        if threshold:
            ax.axhline(
                threshold,
                color=style.ref_color,
                ls="--",
                lw=1,
                label=f"Threshold: {threshold:.0e}",
            )
            ax.legend(loc="upper right", framealpha=0.9)
        
        ax.set_xlabel("Relaxation Step", fontsize=style.font_size)
        ax.set_ylabel("Max Force (Ry/Bohr)", fontsize=style.font_size)
        ax.set_title("Force Convergence", fontsize=style.title_size)
