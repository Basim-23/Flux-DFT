"""
Composite Bands + DOS plot recipe.
"""

from typing import Dict, Optional
from pathlib import Path
import numpy as np

from .base import PlotRecipe, PlotMetadata, PlotStyle


class CompositeBandsDOSRecipe(PlotRecipe):
    """
    Publication-standard Bands + DOS side-by-side layout.
    
    Common in papers: band structure on left (3:1 ratio),
    DOS on right, sharing y-axis (energy relative to Fermi).
    """
    
    recipe_id = "COMPOSITE_001"
    name = "Bands + DOS"
    description = "Combined band structure and DOS (publication format)"
    required_data = ["eigenvalues", "kpath", "dos_energy", "dos_total", "fermi_energy"]
    
    E_RANGE_BELOW = 8.0
    E_RANGE_ABOVE = 6.0
    
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        # Only applicable when we have both bands AND dos data
        return self._check_required_data(available_data)
    
    def generate(
        self,
        data: Dict,
        output_dir: Path,
        style: Optional[PlotStyle] = None,
    ) -> PlotMetadata:
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
        
        style = style or self.style
        
        fig = plt.figure(figsize=(12, 8))
        fig.set_facecolor(style.bg_color)
        
        # Create grid: bands (3 parts) + DOS (1 part)
        gs = GridSpec(1, 2, width_ratios=[3, 1], wspace=0.02)
        
        ax_bands = fig.add_subplot(gs[0])
        ax_dos = fig.add_subplot(gs[1], sharey=ax_bands)
        
        style.apply(fig, ax_bands)
        style.apply(fig, ax_dos)
        
        ef = data["fermi_energy"]
        
        # --- Bands (left panel) ---
        eigenvalues = np.array(data["eigenvalues"])
        kpath = np.array(data["kpath"])
        labels = data.get("kpoint_labels", [])
        
        is_spin = len(eigenvalues.shape) == 3
        
        if is_spin:
            nbnd = eigenvalues.shape[2]
            for band in range(nbnd):
                ax_bands.plot(
                    kpath, eigenvalues[0, :, band] - ef,
                    color=style.spin_up_color,
                    lw=style.line_width * 0.8,
                )
                ax_bands.plot(
                    kpath, eigenvalues[1, :, band] - ef,
                    color=style.spin_down_color,
                    lw=style.line_width * 0.8,
                )
        else:
            nbnd = eigenvalues.shape[1]
            for band in range(nbnd):
                ax_bands.plot(
                    kpath, eigenvalues[:, band] - ef,
                    color=style.accent_color,
                    lw=style.line_width * 0.8,
                )
        
        # Fermi level
        ax_bands.axhline(0, color=style.fermi_color, ls="--", lw=0.8)
        
        # High-symmetry points
        if labels:
            for pos, label in labels:
                ax_bands.axvline(pos, color=style.grid_color, ls="-", lw=0.5)
            ax_bands.set_xticks([pos for pos, _ in labels])
            ax_bands.set_xticklabels([self._format_label(lbl) for _, lbl in labels])
        
        ax_bands.set_xlim(kpath[0], kpath[-1])
        ax_bands.set_ylim(-self.E_RANGE_BELOW, self.E_RANGE_ABOVE)
        ax_bands.set_ylabel("E − E$_F$ (eV)", fontsize=style.font_size)
        ax_bands.set_title("Band Structure", fontsize=style.title_size, loc="left")
        
        # --- DOS (right panel) ---
        dos_energy = np.array(data["dos_energy"]) - ef
        dos = np.array(data["dos_total"])
        
        dos_is_spin = len(dos.shape) == 2 and dos.shape[0] == 2
        
        if dos_is_spin:
            ax_dos.fill_betweenx(
                dos_energy, 0, dos[0],
                alpha=0.3,
                color=style.spin_up_color,
            )
            ax_dos.plot(dos[0], dos_energy, color=style.spin_up_color, lw=1)
        else:
            ax_dos.fill_betweenx(
                dos_energy, 0, dos,
                alpha=0.3,
                color=style.accent_color,
            )
            ax_dos.plot(dos, dos_energy, color=style.accent_color, lw=1)
        
        ax_dos.axhline(0, color=style.fermi_color, ls="--", lw=0.8)
        
        ax_dos.set_xlabel("DOS", fontsize=style.font_size)
        ax_dos.set_title("DOS", fontsize=style.title_size, loc="left")
        ax_dos.yaxis.set_visible(False)
        ax_dos.set_xlim(0, None)
        
        # Save
        plt.tight_layout()
        filename = "bands_dos_composite.png"
        path = self._save_figure(fig, output_dir, filename, style)
        plt.close(fig)
        
        return PlotMetadata(
            recipe_id=self.recipe_id,
            title="Band Structure + DOS",
            filename=filename,
            path=path,
            format="png",
            parameters={
                "spin_polarized": is_spin or dos_is_spin,
            },
        )
    
    def _format_label(self, label: str) -> str:
        """Format k-point label with proper symbols."""
        replacements = {
            "G": "Γ",
            "GAMMA": "Γ",
            "Gamma": "Γ",
        }
        return replacements.get(label.upper(), label)
