import sys
from pathlib import Path

# Add src to python path to allow imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from fluxdft.utils.config import Config
from fluxdft.materials_project.client import MaterialsProjectClient

def main():
    print("Initializing MP Client...")
    config = Config()
    key = config.get("mp_api_key")
    if not key:
        print("ERROR: API key not set.")
        return 1
        
    client = MaterialsProjectClient(api_key=key)
    
    # Test Silicon (mp-149)
    mp_id = "mp-149" 
    print(f"\nFetching data for {mp_id} (Silicon)...")
    
    # 1. Band Structure
    print("  - Fetching Band Structure...")
    bs = client.get_band_structure(mp_id)
    if bs:
        print(f"    SUCCESS: Got BandStructure object.")
        print(f"    Gap: {bs.get_band_gap()['energy']:.4f} eV")
        print(f"    Direct: {bs.get_band_gap()['direct']}")
    else:
        print("    FAILURE: Could not fetch Band Structure.")
        
    # 2. DOS
    print("  - Fetching DOS...")
    dos = client.get_dos(mp_id)
    if dos:
        print(f"    SUCCESS: Got CompleteDos object.")
        print(f"    E_fermi: {dos.efermi:.4f} eV")
    else:
        print("    FAILURE: Could not fetch DOS.")

if __name__ == "__main__":
    sys.exit(main())
