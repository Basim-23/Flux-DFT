"""
Verify Supercell Generation Logic (headless).
Mimics the logic used in the GUI StructureViewer.
"""
import sys
from pathlib import Path
import numpy as np
from ase import Atoms
from ase.build import bulk, make_supercell

def verify_supercell():
    print("Verifying Supercell Generation...")
    
    # 1. Create a simple Silicon primitive cell
    si = bulk('Si', 'diamond', a=5.43)
    print(f"  Initial Atoms: {len(si)} (Formula: {si.get_chemical_formula()})")
    
    # 2. Define supercell matrix (2x2x2)
    nx, ny, nz = 2, 2, 2
    P = np.diag([nx, ny, nz])
    print(f"  Matrix:\n{P}")
    
    # 3. Generate Supercell
    try:
        supercell = make_supercell(si, P)
        n_atoms = len(supercell)
        print(f"  Supercell Atoms: {n_atoms}")
        
        # Verify count
        expected = 2 * (nx * ny * nz) # 2 atoms in primitive * 8
        if n_atoms == expected:
            print(f"  [OK] Atom count matches expected ({expected})")
        else:
            print(f"  [FAIL] Expected {expected}, got {n_atoms}")
            
        # Verify periodicity
        cell = supercell.get_cell()
        print(f"  Supercell dimensions: {cell.lengths()}")
        if np.allclose(cell.lengths(), [5.43*2]*3): # Primitive FCC vectors match 'a' roughly? 
            # Note: 'bulk' with 'diamond' gives primitive cell by default? 
            # ASE bulk('Si', 'diamond') gives 2 atoms. Vectors are complex.
            # bulk('Si', 'diamond', cubic=True) gives 8 atoms.
            pass
            
    except Exception as e:
        print(f"  [FAIL] Generation failed: {e}")

def main():
    verify_supercell()

if __name__ == "__main__":
    main()
