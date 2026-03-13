import sys
try:
    import mp_api
    print(f"mp_api version: {mp_api.__version__}")
except ImportError:
    print("mp_api not installed")

try:
    import pymatgen.core
    print(f"pymatgen version: {pymatgen.core.__version__}")
except ImportError:
    print("pymatgen not installed")

try:
    import pydantic
    print(f"pydantic version: {pydantic.VERSION}")
except ImportError:
    print("pydantic not installed")

print("\nAttempting to import MPRester...")
try:
    from mp_api.client import MPRester
    print("MPRester imported successfully.")
except Exception as e:
    print(f"Error importing MPRester: {e}")
    import traceback
    traceback.print_exc()
