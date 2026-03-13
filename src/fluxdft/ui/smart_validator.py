"""
Smart Validator for Quantum ESPRESSO Input.

Parses input text (best-effort) and validates against physical principles
derived from FluxDFT's Intelligence Engine.
"""

import re
import logging
from typing import List, Dict, Any, Optional

try:
    from pymatgen.io.pwscf import PWInput
    from pymatgen.core import Structure
    HAS_PYMATGEN = True
except ImportError:
    HAS_PYMATGEN = False

from ..intelligence.inference import MaterialIntelligence

logger = logging.getLogger(__name__)

class SmartValidator:
    """
    Context-aware validator for QE input.
    """
    
    @staticmethod
    def validate(text: str) -> List[Dict[str, Any]]:
        """
        Run all validation checks.
        
        Returns:
            List of error dicts {'message': str, 'severity': 'error'|'warning', 'line': int}
        """
        errors = []
        
        # 1. Basic Syntax (Regex-based, robust)
        errors.extend(SmartValidator._check_syntax(text))
        
        # 2. Physics Validation (Structure-based)
        # 2. Physics Validation (Robust Fallback)
        structure = None
        parameters = {}
        
        if HAS_PYMATGEN:
            try:
                # Attempt to parse structure from text
                pw_input = PWInput.from_string(text)
                structure = pw_input.structure
                parameters = pw_input.as_dict()
            except Exception:
                # Parsing failed - likely incomplete input
                pass
        
        # Run Intelligence (works with or without structure)
        errors.extend(SmartValidator._check_physics(structure, parameters, text))
                
        return errors

    @staticmethod
    def _check_syntax(text: str) -> List[Dict[str, Any]]:
        """Comprehensive syntax and consistency checks."""
        errors = []
        lower_text = text.lower()
        upper_text = text.upper()
        
        # === MANDATORY NAMELISTS ===
        if '&control' not in lower_text:
             errors.append({
                 'message': "Missing &CONTROL namelist",
                 'severity': 'error',
                 'fix': {
                     'type': 'insert',
                     'text': "&CONTROL\n  calculation = 'scf'\n  prefix = 'pwscf'\n  pseudo_dir = './pseudo'\n  outdir = './tmp'\n/\n\n",
                     'position': 'top'
                 }
             })
        if '&system' not in lower_text:
             errors.append({
                 'message': "Missing &SYSTEM namelist", 
                 'severity': 'error',
                 'fix': {
                     'type': 'insert',
                     'text': "&SYSTEM\n  ibrav = 0\n  nat = 1\n  ntyp = 1\n  ecutwfc = 50.0\n/\n\n",
                     'position': 'after_control'
                 }
             })
        if '&electrons' not in lower_text:
             errors.append({
                 'message': "Missing &ELECTRONS namelist", 
                 'severity': 'error',
                 'fix': {
                     'type': 'insert',
                     'text': "&ELECTRONS\n  conv_thr = 1.0d-8\n  mixing_beta = 0.7\n/\n\n",
                     'position': 'after_system'
                 }
             })
             
        # === CALCULATION-SPECIFIC NAMELIST CHECKS ===
        calc_match = re.search(r"calculation\s*=\s*['\"](\S+)['\"]", lower_text)
        calc_type = calc_match.group(1) if calc_match else 'scf'
        
        if calc_type in ['relax', 'md', 'vc-md']:
            if '&ions' not in lower_text:
                errors.append({
                    'message': f"Missing &IONS namelist (required for {calc_type})",
                    'severity': 'error',
                    'fix': {
                        'type': 'insert',
                        'text': "&IONS\n  ion_dynamics = 'bfgs'\n/\n\n",
                        'position': 'after_system'
                    }
                })
        
        if calc_type in ['vc-relax', 'vc-md']:
            if '&cell' not in lower_text:
                errors.append({
                    'message': f"Missing &CELL namelist (required for {calc_type})",
                    'severity': 'error',
                    'fix': {
                        'type': 'insert',
                        'text': "&CELL\n  cell_dynamics = 'bfgs'\n/\n\n",
                        'position': 'after_system'
                    }
                })
             
        # === KEY PARAMETERS ===
        if 'ecutwfc' not in lower_text:
             errors.append({
                 'message': "Missing ecutwfc (wavefunction cutoff)", 
                 'severity': 'warning',
                 'fix': {
                     'type': 'inject_var',
                     'namelist': 'SYSTEM',
                     'text': '  ecutwfc = 50.0'
                 }
             })
        if 'pseudo_dir' not in lower_text and '&control' in lower_text:
             errors.append({
                 'message': "Missing pseudo_dir", 
                 'severity': 'warning',
                 'fix': {
                     'type': 'inject_var',
                     'namelist': 'CONTROL',
                     'text': "  pseudo_dir = './pseudo'"
                 }
             })
             
        # === NAT/NTYP CONSISTENCY ===
        nat_match = re.search(r"nat\s*=\s*(\d+)", lower_text)
        ntyp_match = re.search(r"ntyp\s*=\s*(\d+)", lower_text)
        
        # Count atoms in ATOMIC_POSITIONS
        atom_pos_match = re.search(r"ATOMIC_POSITIONS.*?\n(.*?)(?=\n[A-Z_]|\n\s*$|\Z)", text, re.DOTALL | re.IGNORECASE)
        if atom_pos_match:
            atom_lines = [l.strip() for l in atom_pos_match.group(1).strip().split('\n') if l.strip() and not l.strip().startswith('!')]
            actual_nat = len(atom_lines)
            if nat_match:
                declared_nat = int(nat_match.group(1))
                if declared_nat != actual_nat:
                    errors.append({
                        'message': f"nat={declared_nat} but ATOMIC_POSITIONS has {actual_nat} atoms",
                        'severity': 'error',
                        'fix': {
                            'type': 'replace_var',
                            'namelist': 'SYSTEM',
                            'var': 'nat',
                            'value': str(actual_nat)
                        }
                    })
        
        # Count species in ATOMIC_SPECIES
        atom_spec_match = re.search(r"ATOMIC_SPECIES\s*\n(.*?)(?=\n[A-Z_]|\n\s*$|\Z)", text, re.DOTALL | re.IGNORECASE)
        if atom_spec_match:
            spec_lines = [l.strip() for l in atom_spec_match.group(1).strip().split('\n') if l.strip() and not l.strip().startswith('!')]
            actual_ntyp = len(spec_lines)
            if ntyp_match:
                declared_ntyp = int(ntyp_match.group(1))
                if declared_ntyp != actual_ntyp:
                    errors.append({
                        'message': f"ntyp={declared_ntyp} but ATOMIC_SPECIES has {actual_ntyp} species",
                        'severity': 'error',
                        'fix': {
                            'type': 'replace_var',
                            'namelist': 'SYSTEM',
                            'var': 'ntyp',
                            'value': str(actual_ntyp)
                        }
                    })
             
        # === MANDATORY CARDS ===
        if 'ATOMIC_SPECIES' not in upper_text:
             errors.append({'message': "Missing ATOMIC_SPECIES card", 'severity': 'error'})
        if 'ATOMIC_POSITIONS' not in upper_text:
             errors.append({'message': "Missing ATOMIC_POSITIONS card", 'severity': 'error'})
        
        # K_POINTS check
        if calc_type in ['scf', 'nscf', 'bands', 'relax', 'vc-relax']:
            if 'K_POINTS' not in upper_text:
                 errors.append({
                     'message': f"Missing K_POINTS card for {calc_type}", 
                     'severity': 'error',
                     'fix': {
                        'type': 'replace_card',
                        'card': 'K_POINTS',
                        'val_type': 'automatic',
                        'text': "K_POINTS automatic\n  4 4 4 0 0 0" 
                     }
                 })
        
        # === CONVERGENCE THRESHOLDS ===
        conv_thr_match = re.search(r"conv_thr\s*=\s*([0-9.eEdD\-+]+)", lower_text)
        if conv_thr_match:
            try:
                conv_val = float(conv_thr_match.group(1).replace('d', 'e').replace('D', 'e'))
                if conv_val > 1e-6:
                    errors.append({
                        'message': f"conv_thr={conv_val:.0e} is too loose. Recommended: 1.0d-8 or tighter.",
                        'severity': 'warning',
                        'fix': {
                            'type': 'replace_var',
                            'namelist': 'ELECTRONS',
                            'var': 'conv_thr',
                            'value': '1.0d-8'
                        }
                    })
            except:
                pass
        
        # === MIXING BETA ===
        mixing_match = re.search(r"mixing_beta\s*=\s*([0-9.]+)", lower_text)
        if mixing_match:
            try:
                beta = float(mixing_match.group(1))
                if beta > 0.9:
                    errors.append({
                        'message': f"mixing_beta={beta} is too high. May cause SCF instability.",
                        'severity': 'warning',
                        'fix': {
                            'type': 'replace_var',
                            'namelist': 'ELECTRONS',
                            'var': 'mixing_beta',
                            'value': '0.7'
                        }
                    })
            except:
                pass
        
        # === ELECTRON_MAXSTEP ===
        maxstep_match = re.search(r"electron_maxstep\s*=\s*(\d+)", lower_text)
        if maxstep_match:
            maxstep = int(maxstep_match.group(1))
            if maxstep < 50:
                errors.append({
                    'message': f"electron_maxstep={maxstep} is low. May not converge.",
                    'severity': 'warning',
                    'fix': {
                        'type': 'replace_var',
                        'namelist': 'ELECTRONS',
                        'var': 'electron_maxstep',
                        'value': '100'
                    }
                })

        return errors

    @staticmethod
    @staticmethod
    def _check_physics(structure: Optional['Structure'], parameters: Dict[str, Any], text_content: str = "") -> List[Dict[str, Any]]:
        """
        Deep physics validation using MaterialIntelligence (if available) or text heuristics.
        Includes magnetism detection, metal/insulator inference, DFT+U, and parameter optimization.
        """
        errors = []
        
        system = parameters.get('system', {})
        electrons = parameters.get('electrons', {})
        
        # === ELEMENT DETECTION (Robust Fallback & Indexing) ===
        # We need ordered elements for species-specific tags like starting_magnetization(i) and Hubbard_U(i)
        ordered_elements = [] # List of symbol strings in order of ATOMIC_SPECIES
        
        # Fallback: Parse ATOMIC_SPECIES from text
        # Matches: Sym  Mass  Pseudo (multiline content of card)
        spec_match = re.search(r"ATOMIC_SPECIES\s*\n(.*?)(?=\n[A-Z_]|\n\s*$|\Z)", text_content, re.DOTALL | re.IGNORECASE)
        if spec_match:
            lines = spec_match.group(1).strip().split('\n')
            for line in lines:
                parts = line.split()
                if parts and not parts[0].strip().startswith('!'):
                    sym = ''.join([c for c in parts[0] if c.isalpha()])
                    if sym: ordered_elements.append(sym.title())
        
        # Use structure if available and fallback failed or for consistency (but structure species order might differ from input)
        # To be safe for fixing INPUT TEXT variables, we blindly trust the text order if available.
        # If text parsing failed but structure exists (from file load), we use structure species.
        if not ordered_elements and structure:
             ordered_elements = [str(sp) for sp in structure.types_of_specie] 

        elements = list(set(ordered_elements))
        if not elements:
            return [] 

        # === PHYSICS DATABASES ===
        MAGNETIC_ELEMENTS = {
            'Fe': 2.5, 'Co': 1.7, 'Ni': 0.6, 'Mn': 3.0, 'Cr': 2.0, 
            'V': 1.0, 'Gd': 7.0, 'Eu': 6.0, 'Nd': 3.0, 'Sm': 1.5,
            'Tb': 3.0, 'Dy': 5.0, 'Ho': 4.0, 'Er': 3.0, 'Tm': 2.0
        }
        HUBBARD_U_VALUES = {
            'Ti': 4.0, 'V': 3.25, 'Cr': 3.7, 'Mn': 3.9, 'Fe': 5.3, 
            'Co': 3.32, 'Ni': 6.2, 'Cu': 4.0, 
            'Mo': 4.38, 'W': 3.0,
            'Ce': 4.5, 'Pr': 4.5, 'Eu': 4.5, 'Gd': 4.5, 'Tb': 4.5, 
            'Dy': 4.5, 'Ho': 4.5, 'U': 4.0
        }
        TYPICAL_CUTOFFS = {
            'H': 35, 'C': 45, 'N': 50, 'O': 50, 'F': 55,
            'Si': 30, 'Al': 30, 'P': 40, 'S': 40, 'Cl': 45,
            'Fe': 60, 'Co': 60, 'Ni': 60, 'Cu': 60, 'Zn': 50,
            'Ti': 55, 'V': 55, 'Cr': 60, 'Mn': 60,
            'Mo': 60, 'Tc': 60, 'Ru': 60, 'Rh': 60, 'Pd': 60, 'Ag': 55,
            'default': 50
        }
        METALLIC_ELEMENTS = {'Li', 'Na', 'K', 'Rb', 'Cs', 'Fr',
                             'Be', 'Mg', 'Ca', 'Sr', 'Ba', 'Ra',
                             'Al', 'Ga', 'In', 'Tl', 'Sn', 'Pb', 'Bi',
                             'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
                             'Zr', 'Nb', 'Mo', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
                             'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
                             'Sc', 'Y', 'La'}

        metals_in_struct = [el for el in elements if el in METALLIC_ELEMENTS]
        nonmetals_in_struct = [el for el in elements if el not in METALLIC_ELEMENTS and el not in {'O', 'S', 'Se', 'Te', 'N', 'P', 'As', 'F', 'Cl', 'Br', 'I'}]
        is_oxide_nitride = any(el in {'O', 'N', 'F', 'S'} for el in elements)
        
        # --- A. MAGNETISM CHECK ---
        current_nspin = system.get('nspin', 1)
        if 'nspin' not in system and re.search(r"nspin\s*=\s*2", text_content, re.IGNORECASE):
             current_nspin = 2

        magnetic_present = [el for el in elements if el in MAGNETIC_ELEMENTS]
        
        if magnetic_present and current_nspin == 1:
            mag_names = magnetic_present
            mag_text = "  nspin = 2"
            # Use ordered_elements to find index 'i'
            for i, el in enumerate(ordered_elements, 1):
                if el in MAGNETIC_ELEMENTS:
                    starting_mag = min(0.6, MAGNETIC_ELEMENTS[el] / 5.0) 
                    mag_text += f"\n  starting_magnetization({i}) = {starting_mag:.2f}  ! {el}"
            
            errors.append({
                'message': f"Magnetic elements detect ({', '.join(mag_names)}). Enable spin polarization.",
                'severity': 'warning',
                'fix': {
                    'type': 'inject_var',
                    'namelist': 'SYSTEM',
                    'text': mag_text
                }
            })
        
        # --- B. METAL/INSULATOR CHECK ---
        current_occs = system.get('occupations', '')
        if not current_occs and 'occupations' in text_content.lower():
             m = re.search(r"occupations\s*=\s*['\"](\w+)['\"]", text_content, re.IGNORECASE)
             if m: current_occs = m.group(1)
        
        has_smearing = 'smearing' in text_content.lower() or 'degauss' in text_content.lower()
        likely_metal = len(metals_in_struct) > 0 and (not is_oxide_nitride or len(nonmetals_in_struct) == 0)
        
        # Expert Rule: Use robust default (smearing) without assuming metal/insulator
        # Only skip if user explicitly chose 'fixed' (tetrahedra is also valid but rarer)
        if current_occs != 'fixed' and not has_smearing and current_occs != 'smearing':
             errors.append({
                'message': f"Robust convergence strategy: Use smearing (valid for metals & insulators).",
                'severity': 'warning', # Warning because fixed might be intentional
                'fix': {
                    'type': 'inject_var',
                    'namelist': 'SYSTEM',
                    'text': "  occupations = 'smearing'\n  smearing = 'mv'\n  degauss = 0.01" # 0.01Ry ~ 0.13eV safe
                }
            })
            
        # --- C. DFT+U for CORRELATED SYSTEMS ---
        lda_plus_u = system.get('lda_plus_u', False)
        if not lda_plus_u and 'lda_plus_u' in text_content.lower() and '.true.' in text_content.lower():
            lda_plus_u = True
            
        correlated_present = [el for el in elements if el in HUBBARD_U_VALUES]
        if correlated_present and not lda_plus_u:
            u_text = "  lda_plus_u = .true.\n  lda_plus_u_kind = 0"
            suggestion_str = ", ".join([f"{el}" for el in correlated_present])
            
            # Explicitly generate Hubbard_U lines
            for i, el in enumerate(ordered_elements, 1):
                if el in HUBBARD_U_VALUES:
                    u_val = HUBBARD_U_VALUES[el]
                    u_text += f"\n  Hubbard_U({i}) = {u_val} ! {el}"

            errors.append({
                'message': f"Correlated elements ({suggestion_str}). Suggesting DFT+U.",
                'severity': 'warning',
                 'fix': {
                    'type': 'inject_var',
                    'namelist': 'SYSTEM',
                    'text': u_text
                }
            })

        # --- D. CUTOFF CONSISTENCY (ecutwfc, ecutrho) ---
        ecutwfc = system.get('ecutwfc', 0)
        if ecutwfc == 0:
             m = re.search(r"ecutwfc\s*=\s*([0-9.]+)", text_content, re.IGNORECASE)
             if m: ecutwfc = float(m.group(1))
             
        ecutrho = system.get('ecutrho', 0)
        if ecutrho == 0:
             m = re.search(r"ecutrho\s*=\s*([0-9.]+)", text_content, re.IGNORECASE)
             if m: ecutrho = float(m.group(1))

        # Check sufficiency
        rec_cutoff = max([TYPICAL_CUTOFFS.get(el, TYPICAL_CUTOFFS['default']) for el in elements])
        if ecutwfc > 0 and ecutwfc < rec_cutoff:
             errors.append({
                'message': f"Low ecutwfc ({ecutwfc} Ry). Recommended: >{rec_cutoff} Ry.",
                'severity': 'warning',
                'fix': {'type': 'replace_var', 'namelist': 'SYSTEM', 'var': 'ecutwfc', 'value': f"{rec_cutoff}.0"}
            })
            
        # Check density consistency (ecutrho)
        # Expert Standard: ecutrho >= 8 * ecutwfc (PAW/USPP/NCPP safe)
        if ecutwfc > 0:
            target_rho = ecutwfc * 8.0 
            if ecutrho < target_rho:
                 errors.append({
                    'message': f"ecutrho ({ecutrho}) low (< 8*ecutwfc). Setting to {target_rho} (publication standard).",
                    'severity': 'warning',
                    'fix': {'type': 'inject_var', 'namelist': 'SYSTEM', 'text': f"  ecutrho = {target_rho}"}
                })

        # --- E. STABILITY (mixing_beta) ---    
        mixing_beta = electrons.get('mixing_beta', 0.7)
        if likely_metal and mixing_beta > 0.4:
             errors.append({
                'message': f"High mixing_beta ({mixing_beta}) for metal.",
                'severity': 'warning',
                'fix': {'type': 'replace_var', 'namelist': 'ELECTRONS', 'var': 'mixing_beta', 'value': "0.3"}
            })

        # --- F. K-POINT DENSITY ---
        kpoints = parameters.get('kpoints_grid')
        if not kpoints and 'K_POINTS' in text_content and 'automatic' in text_content.lower():
             # Basic parse 
             m = re.search(r"K_POINTS\s+automatic\s*\n\s*(\d+)\s+(\d+)\s+(\d+)", text_content, re.DOTALL | re.IGNORECASE)
             if m: kpoints = [int(m.group(1)), int(m.group(2)), int(m.group(3))]

        if kpoints and structure and structure.lattice:
            try:
                recip_cell = structure.lattice.reciprocal_lattice
                abc_recip = recip_cell.abc
                spacings = [abc_recip[i] / max(1, kpoints[i]) for i in range(3)]
                max_spacing = max(spacings)
                
                if max_spacing > 0.35: 
                    target_spacing = 0.25 
                    suggested_k = [max(1, int(round(abc_recip[i] / target_spacing))) for i in range(3)]
                    k_text = f"{suggested_k[0]} {suggested_k[1]} {suggested_k[2]} 0 0 0"
                    errors.append({
                        'message': f"Coarse K-grid (~{max_spacing:.2f} Å⁻¹). Suggest densifying.",
                        'severity': 'warning',
                        'fix': {
                            'type': 'replace_card', 
                            'card': 'K_POINTS',
                            'val_type': 'automatic',
                            'text': f"K_POINTS automatic\n  {k_text}"
                        }
                    })
            except: pass

        return errors

