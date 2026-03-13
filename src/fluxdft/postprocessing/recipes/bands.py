"""
Band structure plot recipe.
"""

from typing import Dict, Optional, List, Tuple
from pathlib import Path
import numpy as np

from .base import PlotRecipe, PlotMetadata, PlotStyle


class BandStructureRecipe(PlotRecipe):
    """
    Publication-quality band structure plot.
    
    Features:
    - Fermi level alignment (E - Ef = 0)
    - High-symmetry point labels with vertical lines
    - Spin-polarized support (overlaid colors)
    - Automatic y-axis range based on data
    - Band gap annotation for insulators
    """
    
    recipe_id = "BANDS_001"
    name = "Band Structure"
    description = "Electronic band structure along high-symmetry path"
    required_data = ["eigenvalues", "kpath", "fermi_energy"]
    
    # Energy range (eV relative to Fermi)
    E_RANGE_BELOW = 8.0
    E_RANGE_ABOVE = 6.0
    
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        return (
            job_type in ("bands", "nscf") and
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
        
        eigenvalues = np.array(data["eigenvalues"])
        kpath = np.array(data["kpath"])
        ef = data["fermi_energy"]
        labels = data.get("kpoint_labels", [])
        
        # Detect MP reference data
        mp_bands = data.get("mp_bands")
        
        fig, ax = plt.subplots(figsize=(8, 6))
        style.apply(fig, ax)
        
        # Plot MP Bands (Reference) - Plot FIRST to be in background
        if mp_bands:
            # Check if using pymatgen object
            try:
                from pymatgen.electronic_structure.plotter import BSPlotter
                plotter = BSPlotter(mp_bands)
                bs_data = plotter.bs_plot_data()
                
                # BSPlotter aligns to efermi=0 by default
                for path in bs_data['energy']:
                    # path["1"] is Spin.up, path["-1"] is Spin.down
                    # distances are in bs_data['distances']
                    
                    # Distances for this segment
                    dists = bs_data['distances'][bs_data['energy'].index(path)]
                    
                    if '1' in path:
                        for band in path['1']:
                            ax.plot(dists, band, color='#cccccc', lw=1.5, ls='--', alpha=0.6, zorder=1)
                            
                    if '-1' in path:
                         for band in path['-1']:
                            ax.plot(dists, band, color='#cccccc', lw=1.5, ls='--', alpha=0.6, zorder=1)
                            
                # Add proxy artist for legend
                ax.plot([], [], color='#cccccc', ls='--', label='MP Ref')
                
            except Exception as e:
                print(f"Could not plot MP bands: {e}")

        # Detect spin polarization
        is_spin = len(eigenvalues.shape) == 3 and eigenvalues.shape[0] == 2
        
        # Handle singleton dimension (1, k, b)
        if len(eigenvalues.shape) == 3 and eigenvalues.shape[0] == 1:
            eigenvalues = eigenvalues[0]
        
        if is_spin:
            nbnd = eigenvalues.shape[2]
            # Spin up
            for band in range(nbnd):
                ax.plot(
                    kpath, eigenvalues[0, :, band] - ef,
                    color=style.spin_up_color,
                    lw=style.line_width,
                    label="Spin ↑" if band == 0 else None,
                    zorder=2
                )
            # Spin down
            for band in range(nbnd):
                ax.plot(
                    kpath, eigenvalues[1, :, band] - ef,
                    color=style.spin_down_color,
                    lw=style.line_width,
                    label="Spin ↓" if band == 0 else None,
                    zorder=2
                )
            ax.legend(loc="upper right", framealpha=0.9)
        else:
            nbnd = eigenvalues.shape[1]
            for band in range(nbnd):
                ax.plot(
                    kpath, eigenvalues[:, band] - ef,
                    color=style.accent_color,
                    lw=style.line_width,
                    zorder=2
                )
        
        # Fermi level line
        ax.axhline(0, color=style.fermi_color, ls="--", lw=0.8, label="E$_F$")
        
        # High-symmetry points
        if labels:
            for pos, label in labels:
                ax.axvline(pos, color=style.grid_color, ls="-", lw=0.5)
            ax.set_xticks([pos for pos, _ in labels])
            ax.set_xticklabels([self._format_label(lbl) for _, lbl in labels])
        
        # Calculate and annotate band gap
        gap_info = self._calculate_band_gap(eigenvalues, ef)
        if gap_info and gap_info["gap"] > 0.01:
            ax.annotate(
                f"Eg = {gap_info['gap']:.2f} eV",
                xy=(0.02, 0.98),
                xycoords="axes fraction",
                fontsize=10,
                color=style.ref_color,
                verticalalignment="top",
            )
        
        # Axis configuration
        ax.set_xlim(kpath[0], kpath[-1])
        ax.set_ylim(-self.E_RANGE_BELOW, self.E_RANGE_ABOVE)
        ax.set_ylabel("E − E$_F$ (eV)", fontsize=style.font_size)
        ax.set_xlabel("")
        ax.set_title("Band Structure", fontsize=style.title_size)
        
        # Save
        plt.tight_layout()
        filename = "band_structure.png"
        path = self._save_figure(fig, output_dir, filename, style)
        plt.close(fig)
        
        return PlotMetadata(
            recipe_id=self.recipe_id,
            title="Band Structure",
            filename=filename,
            path=path,
            format="png",
            parameters={
                "fermi_energy": ef,
                "spin_polarized": is_spin,
                "n_bands": nbnd,
                "band_gap": gap_info["gap"] if gap_info else None,
                "ref_data": "Materials Project" if mp_bands else "None",
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
    
    def _calculate_band_gap(
        self,
        eigenvalues: np.ndarray,
        ef: float,
    ) -> Optional[Dict]:
        """Calculate band gap from eigenvalues."""
        # Flatten to handle spin
        if len(eigenvalues.shape) == 3:
            eigs = np.concatenate([eigenvalues[0], eigenvalues[1]], axis=0)
        else:
            eigs = eigenvalues
        
        # Find VBM and CBM
        occupied = eigs[eigs <= ef]
        unoccupied = eigs[eigs > ef]
        
        if len(occupied) == 0 or len(unoccupied) == 0:
            return None
        
        vbm = np.max(occupied)
        cbm = np.min(unoccupied)
        gap = cbm - vbm
        
        return {
            "gap": gap,
            "vbm": vbm,
            "cbm": cbm,
        }
