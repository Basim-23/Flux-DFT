"""
Verify Professional Physics Features (Phonons & HSE).
"""
import sys
import os
from pathlib import Path

# Add src to path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from fluxdft.core.input_builder import InputBuilder, PWInput, create_silicon_scf_example

def verify_phonons(builder, output_dir):
    print("Verifying Phonon Input...")
    content = builder.build_ph_input(
        prefix="silicon",
        outdir="./tmp",
        ldisp=True,
        nq1=2, nq2=2, nq3=2,
        epsil=True
    )
    
    filepath = output_dir / "silicon.ph.in"
    builder.write_file(filepath, content)
    print(f"  Generated: {filepath}")
    
    # Check for critical keys
    if "ldisp = .true." in content and "epsil = .true." in content:
        print("  [OK] Phonon keys found")
    else:
        print("  [FAIL] Phonon keys missing")

def verify_hse(builder, output_dir):
    print("\nVerifying HSE Input...")
    
    # Get base silicon input
    inp = create_silicon_scf_example()
    
    # Modify for HSE
    inp.input_dft = "hse"
    inp.nqx1 = 2
    inp.nqx2 = 2
    inp.nqx3 = 2
    
    content = builder.build_pw_input(inp)
    
    filepath = output_dir / "silicon.hse.in"
    builder.write_file(filepath, content)
    print(f"  Generated: {filepath}")
    
    # Check for keys
    if "input_dft = 'hse'" in content and "nqx1 = 2" in content:
        print("  [OK] HSE keys found")
    else:
        print("  [FAIL] HSE keys missing")

def main():
    output_dir = Path("scripts/verification_physics")
    output_dir.mkdir(exist_ok=True, parents=True)
    
    builder = InputBuilder()
    
    try:
        verify_phonons(builder, output_dir)
        verify_hse(builder, output_dir)
        print("\nVerification Complete!")
    except Exception as e:
        print(f"\n[ERROR] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
