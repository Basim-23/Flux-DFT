import sys
import numpy as np
from pathlib import Path
import matplotlib.pyplot as plt

sys.path.append(str(Path(__file__).parent.parent / "src"))

from fluxdft.materials_project.client import MaterialsProjectClient
from fluxdft.utils.config import Config
from fluxdft.postprocessing.recipes.bands import BandStructureRecipe
from fluxdft.postprocessing.recipes.dos import DOSRecipe
from fluxdft.postprocessing.recipes.base import PlotStyle

def main():
    print("Setting up verification...")
    config = Config()
    key = config.get("mp_api_key")
    if not key:
        print("No API key.")
        return 1
        
    client = MaterialsProjectClient(api_key=key)
    mp_id = "mp-149" # Silicon
    
    print(f"Fetching MP data for {mp_id}...")
    mp_bands = client.get_band_structure(mp_id)
    mp_dos = client.get_dos(mp_id)
    
    output_dir = Path("scripts/plots_verification")
    output_dir.mkdir(exist_ok=True)
    
    # 1. Test Band Structure
    print("\nTesting Band Structure Plot...")
    # Create mock user bands (just some cosine waves)
    kpath = np.linspace(0, 5, 100)
    eigenvalues = np.zeros((1, 100, 4)) # 1 spin, 100 kpoints, 4 bands
    for b in range(4):
        eigenvalues[0, :, b] = np.cos(kpath + b) * 2 + (b * 2) - 5
        
    bs_data = {
        "eigenvalues": eigenvalues,
        "kpath": kpath,
        "fermi_energy": 2.5, # Some arbitrary Fermi energy
        "kpoint_labels": [(0, "G"), (2.5, "X"), (5, "L")],
        "mp_bands": mp_bands
    }
    
    
    try:
        recipe = BandStructureRecipe()
        metadata = recipe.generate(bs_data, output_dir)
        print(f"  Generated: {metadata.path}")
    except Exception as e:
        print(f"  Error generating bands plot: {e}")
        import traceback
        traceback.print_exc()

    # 2. Test DOS
    print("\nTesting DOS Plot...")
    # Mock DOS (Gaussian)
    energy = np.linspace(-10, 10, 200)
    dos_total = np.exp(-(energy)**2 / 2) * 5
    
    dos_data = {
        "dos_energy": energy + 3.0, # Shifted by Fermi
        "dos_total": dos_total,
        "fermi_energy": 3.0,
        "mp_dos": mp_dos
    }
    
    try:
        recipe = DOSRecipe()
        metadata = recipe.generate(dos_data, output_dir)
        print(f"  Generated: {metadata.path}")
    except Exception as e:
        print(f"  Error generating DOS plot: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    sys.exit(main())
