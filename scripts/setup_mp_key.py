import sys
import os
from pathlib import Path

# Add src to python path to allow imports
sys.path.append(str(Path(__file__).parent.parent / "src"))

from fluxdft.utils.config import Config
from fluxdft.materials_project.client import MaterialsProjectClient

def main():
    key = "CGv2bDNtLF2O7gLng8SpxCrLyaXc8lc5"
    print(f"Configuring Materials Project API key...")
    
    try:
        config = Config()
        current_key = config.get("mp_api_key")
        
        if current_key == key:
            print("Key is already set correctly.")
        else:
            config.set("mp_api_key", key)
            print("API key saved to config.")
            
        print("Testing connection...")
        client = MaterialsProjectClient(api_key=key)
        
        if client.test_connection():
            print("SUCCESS: Materials Project API key verified.")
            return 0
        else:
            print("FAILURE: Could not connect to Materials Project.")
            return 1
            
    except Exception as e:
        print(f"ERROR: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
