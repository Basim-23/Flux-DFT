"""
Output Parser for Quantum ESPRESSO.

Parses output files from QE calculations to extract:
- Total energies and convergence
- Band structures
- Density of states
- Forces and stresses
- Fermi energy
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import numpy as np


@dataclass
class SCFStep:
    """Single SCF iteration data."""
    iteration: int
    energy: float  # Ry
    accuracy: float  # Ry
    time: Optional[float] = None


@dataclass
class PWOutput:
    """Parsed pw.x output data."""
    # Calculation info
    calculation_type: str = ""
    prefix: str = ""
    converged: bool = False
    
    # Energies (Ry)
    total_energy: Optional[float] = None
    harris_foulkes_energy: Optional[float] = None
    one_electron_energy: Optional[float] = None
    hartree_energy: Optional[float] = None
    xc_energy: Optional[float] = None
    ewald_energy: Optional[float] = None
    
    # Fermi energy (eV)
    fermi_energy: Optional[float] = None
    
    # Band gap (eV)
    band_gap: Optional[float] = None
    vbm: Optional[float] = None  # Valence band maximum
    cbm: Optional[float] = None  # Conduction band minimum
    is_direct_gap: Optional[bool] = None
    
    # SCF convergence
    scf_steps: List[SCFStep] = field(default_factory=list)
    n_scf_steps: int = 0
    
    # Forces (Ry/Bohr)
    forces: Optional[np.ndarray] = None  # Shape: (nat, 3)
    total_force: Optional[float] = None
    
    # Stress (kbar)
    stress: Optional[np.ndarray] = None  # Shape: (3, 3)
    pressure: Optional[float] = None
    
    # Timing
    cpu_time: Optional[float] = None  # seconds
    wall_time: Optional[float] = None  # seconds
    
    # K-points and bands
    n_kpoints: int = 0
    n_bands: int = 0
    kpoints: Optional[np.ndarray] = None
    eigenvalues: Optional[np.ndarray] = None  # Shape: (nkpt, nbnd)


@dataclass
class BandStructure:
    """Band structure data."""
    n_bands: int = 0
    n_kpoints: int = 0
    kpoints: Optional[np.ndarray] = None  # Shape: (nkpt, 3)
    kpoint_distances: Optional[np.ndarray] = None  # Shape: (nkpt,)
    eigenvalues: Optional[np.ndarray] = None  # Shape: (nkpt, nbnd) in eV
    fermi_energy: float = 0.0
    high_symmetry_points: Optional[List[Tuple[float, str]]] = None  # (distance, label)


@dataclass 
class DOS:
    """Density of states data."""
    energies: Optional[np.ndarray] = None  # eV
    dos: Optional[np.ndarray] = None  # states/eV
    dos_up: Optional[np.ndarray] = None  # Spin up
    dos_down: Optional[np.ndarray] = None  # Spin down
    integrated_dos: Optional[np.ndarray] = None
    fermi_energy: float = 0.0


class OutputParser:
    """
    Parser for Quantum ESPRESSO output files.
    
    Usage:
        parser = OutputParser()
        
        # Parse pw.x output
        result = parser.parse_pw_output("si.scf.out")
        print(f"Total energy: {result.total_energy} Ry")
        
        # Parse band structure
        bands = parser.parse_bands("bands.dat.gnu")
        
        # Parse DOS
        dos = parser.parse_dos("prefix.dos")
    """
    
    # Unit conversions
    RY_TO_EV = 13.605693122994
    
    def __init__(self):
        pass
    
    def parse_pw_output(self, filepath: str | Path) -> PWOutput:
        """Parse a pw.x output file."""
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Output file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        
        result = PWOutput()
        
        # Calculation type
        match = re.search(r"calculation\s*=\s*['\"](\w+)['\"]", content)
        if match:
            result.calculation_type = match.group(1)
        
        # Prefix
        match = re.search(r"prefix\s*=\s*['\"](\w+)['\"]", content)
        if match:
            result.prefix = match.group(1)
        
        # Convergence check
        result.converged = "convergence has been achieved" in content.lower()
        
        # Parse SCF iterations
        scf_pattern = re.compile(
            r"iteration\s*#\s*(\d+)\s+ecut.*\n.*total energy\s*=\s*([-\d.]+)\s*Ry\n.*estimated scf accuracy\s*<\s*([-\d.E+]+)"
        )
        for match in scf_pattern.finditer(content):
            step = SCFStep(
                iteration=int(match.group(1)),
                energy=float(match.group(2)),
                accuracy=float(match.group(3))
            )
            result.scf_steps.append(step)
        result.n_scf_steps = len(result.scf_steps)
        
        # Final total energy
        match = re.search(r"!\s+total energy\s*=\s*([-\d.]+)\s*Ry", content)
        if match:
            result.total_energy = float(match.group(1))
        
        # Energy components
        patterns = {
            "one_electron_energy": r"one-electron contribution\s*=\s*([-\d.]+)\s*Ry",
            "hartree_energy": r"hartree contribution\s*=\s*([-\d.]+)\s*Ry",
            "xc_energy": r"xc contribution\s*=\s*([-\d.]+)\s*Ry",
            "ewald_energy": r"ewald contribution\s*=\s*([-\d.]+)\s*Ry",
        }
        for attr, pattern in patterns.items():
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                setattr(result, attr, float(match.group(1)))
        
        # Fermi energy
        match = re.search(r"the Fermi energy is\s+([-\d.]+)\s*ev", content, re.IGNORECASE)
        if match:
            result.fermi_energy = float(match.group(1))
        
        # Highest occupied / lowest unoccupied
        match = re.search(
            r"highest occupied.*?:\s+([-\d.]+)\s*ev\s+lowest unoccupied.*?:\s+([-\d.]+)\s*ev",
            content, re.IGNORECASE | re.DOTALL
        )
        if match:
            result.vbm = float(match.group(1))
            result.cbm = float(match.group(2))
            result.band_gap = result.cbm - result.vbm
        
        # Forces
        force_section = re.search(r"Forces acting on atoms.*?\n(.*?)Total force", content, re.DOTALL)
        if force_section:
            force_lines = re.findall(
                r"atom\s+\d+\s+type\s+\d+\s+force\s*=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)",
                force_section.group(1)
            )
            if force_lines:
                result.forces = np.array([[float(x), float(y), float(z)] for x, y, z in force_lines])
        
        # Total force
        match = re.search(r"Total force\s*=\s*([-\d.]+)", content)
        if match:
            result.total_force = float(match.group(1))
        
        # Stress tensor
        stress_section = re.search(r"total\s+stress.*?\n(.*?\n.*?\n.*?)\n", content, re.DOTALL)
        if stress_section:
            stress_lines = stress_section.group(1).strip().split("\n")
            stress = []
            for line in stress_lines:
                nums = re.findall(r"([-\d.]+)", line)
                if len(nums) >= 3:
                    stress.append([float(nums[0]), float(nums[1]), float(nums[2])])
            if len(stress) == 3:
                result.stress = np.array(stress)
        
        # Pressure
        match = re.search(r"P=\s*([-\d.]+)", content)
        if match:
            result.pressure = float(match.group(1))
        
        # Timing
        match = re.search(r"PWSCF\s*:\s*([\d.hms ]+)\s+CPU\s+([\d.hms ]+)\s+WALL", content)
        if match:
            result.cpu_time = self._parse_time(match.group(1))
            result.wall_time = self._parse_time(match.group(2))
        
        # Number of k-points and bands
        match = re.search(r"number of k points=\s*(\d+)", content)
        if match:
            result.n_kpoints = int(match.group(1))
        
        match = re.search(r"number of Kohn-Sham states=\s*(\d+)", content)
        if match:
            result.n_bands = int(match.group(1))
        
        return result
    
    def _parse_time(self, time_str: str) -> float:
        """Parse QE time format (e.g., '5m23.45s', '1h 2m 3s') to seconds."""
        total = 0.0
        
        # Hours
        match = re.search(r"(\d+)h", time_str)
        if match:
            total += int(match.group(1)) * 3600
        
        # Minutes
        match = re.search(r"(\d+)m", time_str)
        if match:
            total += int(match.group(1)) * 60
        
        # Seconds
        match = re.search(r"([\d.]+)s", time_str)
        if match:
            total += float(match.group(1))
        
        # If just a number, assume seconds
        if total == 0:
            try:
                total = float(time_str.strip())
            except ValueError:
                pass
        
        return total
    
    def parse_bands_gnu(self, filepath: str | Path) -> BandStructure:
        """
        Parse a bands.x output file in gnuplot format.
        
        The .gnu file has format:
            k_distance  energy_eV
            k_distance  energy_eV
            ...
            (blank line between bands)
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Band file not found: {filepath}")
        
        with open(filepath, "r") as f:
            content = f.read()
        
        # Split into bands (separated by blank lines)
        bands_data = []
        current_band = []
        
        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                if current_band:
                    bands_data.append(current_band)
                    current_band = []
            else:
                parts = line.split()
                if len(parts) >= 2:
                    k_dist = float(parts[0])
                    energy = float(parts[1])
                    current_band.append((k_dist, energy))
        
        if current_band:
            bands_data.append(current_band)
        
        if not bands_data:
            return BandStructure()
        
        n_bands = len(bands_data)
        n_kpoints = len(bands_data[0]) if bands_data else 0
        
        # Build arrays
        kpoint_distances = np.array([pt[0] for pt in bands_data[0]])
        eigenvalues = np.zeros((n_kpoints, n_bands))
        
        for band_idx, band in enumerate(bands_data):
            for kpt_idx, (k, e) in enumerate(band):
                if kpt_idx < n_kpoints:
                    eigenvalues[kpt_idx, band_idx] = e
        
        return BandStructure(
            n_bands=n_bands,
            n_kpoints=n_kpoints,
            kpoint_distances=kpoint_distances,
            eigenvalues=eigenvalues,
        )
    
    def parse_dos(self, filepath: str | Path) -> DOS:
        """
        Parse a dos.x output file.
        
        Format: E(eV)  dos(E)  int_dos(E)
        For spin-polarized: E(eV)  dos_up  dos_down  int_dos
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"DOS file not found: {filepath}")
        
        data = []
        fermi = 0.0
        
        with open(filepath, "r") as f:
            for line in f:
                line = line.strip()
                
                # Check for Fermi energy in header
                if "Fermi" in line or "EFermi" in line:
                    match = re.search(r"([-\d.]+)\s*eV", line, re.IGNORECASE)
                    if match:
                        fermi = float(match.group(1))
                    continue
                
                if line.startswith("#"):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        data.append([float(x) for x in parts])
                    except ValueError:
                        continue
        
        if not data:
            return DOS()
        
        data = np.array(data)
        
        result = DOS(
            energies=data[:, 0],
            fermi_energy=fermi,
        )
        
        if data.shape[1] == 3:
            # Non-spin-polarized
            result.dos = data[:, 1]
            result.integrated_dos = data[:, 2]
        elif data.shape[1] >= 4:
            # Spin-polarized
            result.dos_up = data[:, 1]
            result.dos_down = data[:, 2]
            result.dos = result.dos_up + result.dos_down
            result.integrated_dos = data[:, 3]
        
        return result
    
    def parse_pdos(self, filepath: str | Path) -> Dict[str, DOS]:
        """
        Parse projected DOS files from projwfc.x.
        
        Returns a dictionary mapping orbital labels to DOS objects.
        """
        filepath = Path(filepath)
        parent = filepath.parent
        prefix = filepath.stem
        
        pdos_files = list(parent.glob(f"{prefix}*.pdos_atm*"))
        
        results = {}
        for pdos_file in pdos_files:
            # Extract atom and orbital info from filename
            match = re.search(r"pdos_atm#(\d+)\((\w+)\)_wfc#(\d+)\((\w+)\)", pdos_file.name)
            if match:
                atom_idx = int(match.group(1))
                atom_symbol = match.group(2)
                wfc_idx = int(match.group(3))
                orbital = match.group(4)
                label = f"{atom_symbol}#{atom_idx}({orbital})"
            else:
                label = pdos_file.stem
            
            results[label] = self.parse_dos(pdos_file)
        
        return results


# Convenience functions
def parse_pw_output(filepath: str | Path) -> PWOutput:
    """Parse a pw.x output file."""
    return OutputParser().parse_pw_output(filepath)


def parse_bands(filepath: str | Path) -> BandStructure:
    """Parse a bands.x gnuplot output file."""
    return OutputParser().parse_bands_gnu(filepath)


def parse_dos(filepath: str | Path) -> DOS:
    """Parse a dos.x output file."""
    return OutputParser().parse_dos(filepath)
