"""
Density of States plot recipe.
"""

from typing import Dict, Optional
from pathlib import Path
import numpy as np

from .base import PlotRecipe, PlotMetadata, PlotStyle


class DOSRecipe(PlotRecipe):
    """
    Total Density of States plot.
    
    Features:
    - Fermi level alignment (E - Ef = 0)
    - Spin-polarized: mirrored DOS (up positive, down negative)
    - Filled area under curve for visual clarity
    - Band gap shading for insulators
    """
    
    recipe_id = "DOS_001"
    name = "Density of States"
    description = "Total electronic density of states"
    required_data = ["dos_energy", "dos_total", "fermi_energy"]
    
    FILL_ALPHA = 0.3
    E_RANGE = 10.0  # eV from Fermi level
    
    def is_applicable(self, job_type: str, available_data: Dict) -> bool:
        return (
            job_type in ("dos", "nscf", "scf") and
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
        dos = np.array(data["dos_total"])
        
        
        fig, ax = plt.subplots(figsize=(6, 8))
        style.apply(fig, ax)
        
        # Detect MP reference data
        mp_dos = data.get("mp_dos")
        
        # Plot MP DOS (Reference) - Background
        if mp_dos:
            try:
                # Align to Fermi level
                mp_energies = mp_dos.energies - mp_dos.efermi
                mp_densities = mp_dos.get_densities()
                
                # Check MP spin
                mp_is_spin = len(mp_densities) > 1
                
                if mp_is_spin:
                    # Spin Up
                    if mp_densities.get(1) is not None: # Spin.up enum usually 1
                         ax.fill_betweenx(
                            mp_energies, 0, mp_densities[1],
                            color='#e0e0e0', alpha=0.5, label='MP Ref'
                        )
                    elif mp_densities.get('1') is not None: # Handle dict string keys if converted
                         ax.fill_betweenx(
                            mp_energies, 0, mp_densities['1'],
                            color='#e0e0e0', alpha=0.5, label='MP Ref'
                        )
                    
                    # Spin Down
                    if mp_densities.get(-1) is not None: # Spin.down usually -1
                        ax.fill_betweenx(
                            mp_energies, 0, -mp_densities[-1],
                            color='#e0e0e0', alpha=0.5
                        )
                else:
                    # Non-magnetic
                    # Pymatgen sometimes returns different keys for non-spin
                     mp_dens = mp_dos.get_densities()
                     # If it returns dict with Spin.up for non-polarized
                     if isinstance(mp_dens, dict):
                         dens = list(mp_dens.values())[0]
                     else:
                         dens = mp_dens
                         
                     ax.fill_betweenx(
                        mp_energies, 0, dens,
                        color='#e0e0e0', alpha=0.5, label='MP Ref'
                    )
            except Exception as e:
                print(f"Could not plot MP DOS: {e}")

        # Detect spin polarization
        is_spin = len(dos.shape) == 2 and dos.shape[0] == 2
        
        if is_spin:
            # Spin up (positive direction)
            ax.fill_betweenx(
                energy, 0, dos[0],
                alpha=self.FILL_ALPHA,
                color=style.spin_up_color,
            )
            ax.plot(
                dos[0], energy,
                color=style.spin_up_color,
                lw=style.line_width,
                label="Spin ↑",
            )
            
            # Spin down (mirrored, negative direction)
            ax.fill_betweenx(
                energy, 0, -dos[1],
                alpha=self.FILL_ALPHA,
                color=style.spin_down_color,
            )
            ax.plot(
                -dos[1], energy,
                color=style.spin_down_color,
                lw=style.line_width,
                label="Spin ↓",
            )
            
            # Zero line for spin separation
            ax.axvline(0, color=style.grid_color, lw=0.5)
            ax.legend(loc="upper right", framealpha=0.9)
            
            # Symmetric x-axis
            max_dos = max(np.max(dos[0]), np.max(dos[1]))
            ax.set_xlim(-max_dos * 1.1, max_dos * 1.1)
        else:
            ax.fill_betweenx(
                energy, 0, dos,
                alpha=self.FILL_ALPHA,
                color=style.accent_color,
            )
            ax.plot(
                dos, energy,
                color=style.accent_color,
                lw=style.line_width,
                label="Total DOS" # Changed label for clarity
            )
            ax.set_xlim(0, np.max(dos) * 1.1)
        
        # Fermi level line
        ax.axhline(0, color=style.fermi_color, ls="--", lw=0.8, label="E$_F$")
        
        # Energy range
        mask = (energy >= -self.E_RANGE) & (energy <= self.E_RANGE)
        ax.set_ylim(-self.E_RANGE, self.E_RANGE)
        
        # Labels
        ax.set_ylabel("E − E$_F$ (eV)", fontsize=style.font_size)
        ax.set_xlabel("DOS (states/eV)", fontsize=style.font_size)
        ax.set_title("Density of States", fontsize=style.title_size)
        
        # Save
        plt.tight_layout()
        filename = "dos.png"
        path = self._save_figure(fig, output_dir, filename, style)
        plt.close(fig)
        
        return PlotMetadata(
            recipe_id=self.recipe_id,
            title="Density of States",
            filename=filename,
            path=path,
            format="png",
            parameters={
                "spin_polarized": is_spin,
                "fermi_energy": data["fermi_energy"],
            },
        )
