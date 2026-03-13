import sys
import importlib.metadata

packages = ["mp-api", "pymatgen", "pydantic", "typing-extensions", "emmet-core"]

print("Package Versions:")
for pkg in packages:
    try:
        ver = importlib.metadata.version(pkg)
        print(f"{pkg}: {ver}")
    except importlib.metadata.PackageNotFoundError:
        print(f"{pkg}: NOT INSTALLED")

print("\nPython Version:")
print(sys.version)

print("\nAttempting MPRester import again to catch traceback:")
try:
    from mp_api.client import MPRester
    print("MPRester imported successfully.")
except Exception:
    import traceback
    traceback.print_exc()
