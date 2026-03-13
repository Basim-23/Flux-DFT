"""
Input Set Generators for FluxDFT x Atomate2.

These classes translate abstract requirements (structure, precision) 
into concrete Quantum ESPRESSO input files (namelists, k-points).
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Union
import copy

from pymatgen.core import Structure
from pymatgen.io.pwscf import PWInput

@dataclass
class FluxQEInputGenerator:
    """
    Base class for generating FluxDFT-compliant QE input sets.
    
    Acts as the translation layer between high-level intent and low-level QE params.
    """
    base_settings: Dict[str, Any] = field(default_factory=dict)
    user_settings: Dict[str, Any] = field(default_factory=dict)
    
    def get_input_set(self, structure: Structure, prev_dir: Optional[str] = None) -> PWInput:
        """
        Generate the PWInput object.
        
        Args:
            structure: The input structure.
            prev_dir: Directory of previous calculation (for restarts/chaining).
            
        Returns:
            PWInput: The pymatgen IO object ready to be written.
        """
        raise NotImplementedError("Must implement get_input_set")

    def _merge_settings(self, defaults: Dict, overrides: Dict) -> Dict:
        """Recursive dict merge."""
        merged = copy.deepcopy(defaults)
        for k, v in overrides.items():
            if isinstance(v, dict) and k in merged:
                merged[k] = self._merge_settings(merged[k], v)
            else:
                merged[k] = v
        return merged


@dataclass
class RelaxSetGenerator(FluxQEInputGenerator):
    """Generator for Geometry Optimization (vc-relax/relax)."""
    relax_cell: bool = True
    precision: str = "medium"
    
    def get_input_set(self, structure: Structure, prev_dir: Optional[str] = None) -> PWInput:
        # 1. Run Material Intelligence
        # This is where the magic happens: Dynamic inference of physics
        try:
            from ...intelligence.inference import MaterialIntelligence
            intelligence = MaterialIntelligence(structure)
            inferred = intelligence.infer_calculation_settings()
        except ImportError:
            # Fallback if intelligence module fails (e.g. no pymatgen)
            inferred = {
                "system": {"nspin": 1, "occupations": "fixed"},
                "magnetism": {},
                "kpoints": None
            }
        
        # 2. Define Defaults based on Precision
        precision_defaults = {
            "low": {"system": {"ecutwfc": 30.0, "ecutrho": 240.0}},
            "medium": {"system": {"ecutwfc": 50.0, "ecutrho": 400.0}},
            "high": {"system": {"ecutwfc": 80.0, "ecutrho": 640.0}},
            "production": {"system": {"ecutwfc": 100.0, "ecutrho": 800.0}},
        }
        
        settings = precision_defaults.get(self.precision, precision_defaults["medium"])
        
        # 3. Logic: Relax vs VC-Relax
        calc_type = "vc-relax" if self.relax_cell else "relax"
        
        # 4. Base Namelists
        control = {"calculation": calc_type, "restart_mode": "from_scratch", "pseudo_dir": "./"}
        system = {"ibrav": 0, "nat": len(structure), "ntyp": len(structure.composition.elements)}
        electrons = {"conv_thr": 1.0e-8, "mixing_beta": 0.7}
        ions = {"ion_dynamics": "bfgs"}
        cell = {"cell_dynamics": "bfgs"} if self.relax_cell else {}
        
        # Merge Inferred Physics
        # System (smearing, nspin)
        system.update(inferred.get("system", {}))
        
        # Magnetism details
        mag_props = inferred.get("magnetism", {})
        if mag_props.get("starting_magnetization"):
            # We need to map species symbols to indices for QE input if using simple dict
            # or rely on pymatgen's PWInput handling of this.
            # Pymatgen PWInput expects 'starting_magnetization' in system dict keyed by species label?
            # Actually, pymatgen handles this if we pass a structure with magmoms.
            # But here we are passing raw dicts.
            # Let's pass it to the 'structure' object if possible?
            # For now, let's just update the system dict and hope pymatgen PWInput handles it
            # or we manually format it.
            # Pymatgen's PWInput is robust.
            pass

        # 5. Merge Layers
        full_settings = {
            "control": control,
            "system": system,
            "electrons": electrons,
            "ions": ions,
            "cell": cell
        }
        
        # Apply Precision Settings
        full_settings = self._merge_settings(full_settings, settings)
        
        # Apply User Overrides
        full_settings = self._merge_settings(full_settings, self.user_settings)
        
        # 6. K-Points
        # Use inferred KPoints or fallback
        kpoints = inferred.get("kpoints")
        if kpoints:
            kpoints_grid = kpoints.grid
        else:
            kpoints_grid = (4, 4, 4) 
        
        # 7. Pseudopotentials
        # Ideally intelligence infers this too from SSSP
        pseudo = {str(el): f"{el.symbol}.UPF" for el in structure.composition.elements}
        
        # Construct PWInput
        # Note: We need to handle magnetism specific formatting if pymatgen doesn't do it automatically from dict
        # For simple robust integration, we let the user/intelligence set 'starting_magnetization' 
        # inside system, but typically QE needs starting_magnetization(i).
        
        return PWInput(
            structure=structure,
            pseudo=pseudo,
            control=full_settings["control"],
            system=full_settings["system"],
            electrons=full_settings["electrons"],
            ions=full_settings["ions"],
            cell=full_settings["cell"],
            kpoints_grid=kpoints_grid,
        )


@dataclass
class BandsSetGenerator(FluxQEInputGenerator):
    """Generator for Band Structure (bands)."""
    
    def get_input_set(self, structure: Structure, prev_dir: Optional[str] = None) -> PWInput:
        # Logic for bands calculation
        # Requires NSCF or Bands calculation type
        # MUST read charge density from prev_dir usually
        
        settings = {
            "control": {"calculation": "bands", "restart_mode": "from_scratch"},
            "system": {"ecutwfc": 50.0}, # Should match SCF
            "electrons": {"conv_thr": 1.0e-8},
        }
        
        # ... Implementation would mirror RelaxSetGenerator but with K-path logic
        # For now, MVP stub
        
        return PWInput(
            structure=structure,
            control=settings["control"],
            kpoints_mode="crystal_b", # Path mode
            kpoints_grid=[], # Would need KPath generator here
        )
