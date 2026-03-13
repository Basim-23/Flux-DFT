import sys
import requests
from fluxdft.utils.config import Config

def main():
    config = Config()
    key = config.get("mp_api_key")
    if not key:
        print("No API key found.")
        return 1
        
    headers = {"X-API-KEY": key, "Accept": "application/json"}
    base_url = "https://api.materialsproject.org"
    
    mp_id = "mp-149" # Silicon
    
    endpoints_to_try = [
        f"/electronic_structure/{mp_id}/band_structure",
        f"/electronic_structure/{mp_id}/dos",
        f"/materials/{mp_id}/vasp/bandstructure",
        f"/materials/{mp_id}/electronic_structure",
        f"/electronic_structure/band_structure/?material_id={mp_id}",
    ]
    
    print(f"Probing API for {mp_id}...")
    
    for endpoint in endpoints_to_try:
        url = base_url + endpoint
        print(f"Trying {url} ...")
        try:
            response = requests.get(url, headers=headers, timeout=5)
            print(f"Status: {response.status_code}")
            if response.status_code == 200:
                print("SUCCESS!")
                print(response.text[:200])
        except Exception as e:
            print(f"Error: {e}")
            
if __name__ == "__main__":
    sys.exit(main())
