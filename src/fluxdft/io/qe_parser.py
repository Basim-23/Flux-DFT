"""
Quantum ESPRESSO Output Parser for FluxDFT.

Comprehensive parser for pw.x, bands.x, dos.x, and other QE outputs.
Extracts all relevant data for analysis and visualization.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from dataclasses import dataclass, field
from pathlib import Path
import re
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class SCFIteration:
    """Data from a single SCF iteration."""
    iteration: int
    total_energy: float  # Ry
    accuracy: float  # Ry
    cpu_time: Optional[float] = None
    magnetization: Optional[float] = None
    absolute_magnetization: Optional[float] = None


@dataclass
class AtomicForce:
    """Force on an atom."""
    atom_index: int
    species: str
    force: np.ndarray  # shape (3,), in Ry/Bohr
    
    @property
    def magnitude(self) -> float:
        return np.linalg.norm(self.force)
    
    @property
    def force_ev_ang(self) -> np.ndarray:
        """Force in eV/Angstrom."""
        return self.force * 25.7112  # Ry/Bohr to eV/Å


@dataclass
class ParsedQEOutput:
    """
    Complete parsed Quantum ESPRESSO output.
    
    Contains all extracted data from a pw.x calculation.
    """
    # Job info
    job_done: bool = False
    wall_time: Optional[float] = None  # seconds
    cpu_time: Optional[float] = None
    
    # System info
    calculation_type: str = ""
    prefix: str = ""
    pseudo_dir: str = ""
    outdir: str = ""
    nat: int = 0
    ntyp: int = 0
    nbnd: int = 0
    nelec: float = 0.0
    
    # Lattice
    alat: float = 0.0  # Bohr
    cell_parameters: Optional[np.ndarray] = None  # 3x3 in Bohr
    volume: float = 0.0  # Bohr^3
    
    # K-points
    nkpts: int = 0
    kpoints: List[np.ndarray] = field(default_factory=list)
    kweights: List[float] = field(default_factory=list)
    
    # SCF data
    scf_iterations: List[SCFIteration] = field(default_factory=list)
    scf_converged: bool = False
    final_energy: float = 0.0  # Ry
    fermi_energy: float = 0.0  # eV
    
    # Magnetization
    is_spin_polarized: bool = False
    total_magnetization: float = 0.0
    absolute_magnetization: float = 0.0
    
    # Forces and stress
    forces: List[AtomicForce] = field(default_factory=list)
    total_force: float = 0.0  # Ry/Bohr
    stress_tensor: Optional[np.ndarray] = None  # 3x3 in kbar
    pressure: float = 0.0  # kbar
    
    # Eigenvalues (if present)
    eigenvalues: Optional[np.ndarray] = None  # shape (nspins, nkpts, nbands)
    occupations: Optional[np.ndarray] = None
    
    # Band structure specific
    is_band_calculation: bool = False
    high_symmetry_points: Dict[str, int] = field(default_factory=dict)
    
    # Structural relaxation
    is_relaxation: bool = False
    relaxation_steps: int = 0
    final_positions: Optional[np.ndarray] = None  # fractional
    final_cell: Optional[np.ndarray] = None
    relaxation_converged: bool = False
    
    # Errors and warnings
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_energy_ev(self) -> float:
        """Total energy in eV."""
        return self.final_energy * 13.6057  # Ry to eV
    
    @property
    def max_force(self) -> float:
        """Maximum force on any atom (Ry/Bohr)."""
        if not self.forces:
            return 0.0
        return max(f.magnitude for f in self.forces)
    
    @property
    def volume_ang3(self) -> float:
        """Volume in Angstrom^3."""
        return self.volume * (0.529177 ** 3)


class QEOutputParser:
    """
    Parser for Quantum ESPRESSO output files.
    
    Handles:
        - pw.x output (SCF, relaxation, bands, nscf)
        - bands.x output
        - dos.x output
        - Error detection
    
    Usage:
        >>> parser = QEOutputParser()
        >>> result = parser.parse("pw.out")
        >>> print(result.final_energy)
    """
    
    # Regular expressions for parsing
    PATTERNS = {
        'calculation': re.compile(r"calculation\s*=\s*'(\w+)'"),
        'prefix': re.compile(r"prefix\s*=\s*'(\w+)'"),
        'nat': re.compile(r"number of atoms/cell\s*=\s*(\d+)"),
        'ntyp': re.compile(r"number of atomic types\s*=\s*(\d+)"),
        'nelec': re.compile(r"number of electrons\s*=\s*([\d.]+)"),
        'nbnd': re.compile(r"number of Kohn-Sham states\s*=\s*(\d+)"),
        'ecutwfc': re.compile(r"kinetic-energy cutoff\s*=\s*([\d.]+)\s*Ry"),
        'ecutrho': re.compile(r"charge density cutoff\s*=\s*([\d.]+)\s*Ry"),
        
        'alat': re.compile(r"lattice parameter \(alat\)\s*=\s*([\d.]+)\s*a\.u\."),
        'cell_volume': re.compile(r"unit-cell volume\s*=\s*([\d.]+)\s*\(a\.u\.\)"),
        'nkpts': re.compile(r"number of k points\s*=\s*(\d+)"),
        
        'scf_iteration': re.compile(
            r"iteration\s*#\s*(\d+)\s*ecut=.*\n.*total energy\s*=\s*([-\d.]+)\s*Ry"
        ),
        'total_energy': re.compile(r"!\s*total energy\s*=\s*([-\d.]+)\s*Ry"),
        'fermi_energy': re.compile(r"(?:the Fermi energy is|Fermi energy is)\s*([-\d.]+)\s*ev", re.I),
        'homo_lumo': re.compile(r"highest occupied.*:\s*([-\d.]+)\s*ev", re.I),
        
        'scf_accuracy': re.compile(r"estimated scf accuracy\s*<\s*([\d.Ee+-]+)\s*Ry"),
        'convergence': re.compile(r"convergence has been achieved"),
        
        'total_mag': re.compile(r"total magnetization\s*=\s*([-\d.]+)\s*Bohr mag"),
        'abs_mag': re.compile(r"absolute magnetization\s*=\s*([-\d.]+)\s*Bohr mag"),
        
        'force_line': re.compile(
            r"atom\s+(\d+)\s+type\s+\d+\s+force\s*=\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)"
        ),
        'total_force': re.compile(r"Total force\s*=\s*([\d.]+)"),
        
        'stress_tensor': re.compile(
            r"^\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*$",
            re.MULTILINE
        ),
        'pressure': re.compile(r"P=\s*([-\d.]+)"),
        
        'bfgs_converged': re.compile(r"bfgs converged in\s*(\d+)\s*scf cycles"),
        'final_enthalpy': re.compile(r"Final enthalpy\s*=\s*([-\d.]+)\s*Ry"),
        
        'job_done': re.compile(r"JOB DONE"),
        'wall_time': re.compile(r"PWSCF\s*:\s*(.+)\s*WALL"),
        
        'error': re.compile(r"Error|ERROR|%%%"),
        'warning': re.compile(r"Warning|WARNING"),
    }
    
    def parse(self, filepath: Union[str, Path]) -> ParsedQEOutput:
        """
        Parse a Quantum ESPRESSO output file.
        
        Args:
            filepath: Path to output file
            
        Returns:
            ParsedQEOutput object with all extracted data
        """
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"Output file not found: {filepath}")
        
        with open(filepath, 'r', errors='replace') as f:
            content = f.read()
        
        result = ParsedQEOutput()
        
        # Basic job info
        result.job_done = bool(self.PATTERNS['job_done'].search(content))
        
        # Parse wall time
        wall_match = self.PATTERNS['wall_time'].search(content)
        if wall_match:
            result.wall_time = self._parse_time(wall_match.group(1))
        
        # System info
        self._parse_system_info(content, result)
        
        # SCF iterations
        self._parse_scf_iterations(content, result)
        
        # Final energy and Fermi level
        self._parse_energies(content, result)
        
        # Magnetization
        self._parse_magnetization(content, result)
        
        # Forces
        self._parse_forces(content, result)
        
        # Stress
        self._parse_stress(content, result)
        
        # Relaxation data
        self._parse_relaxation(content, result)
        
        # Eigenvalues (if bands calculation)
        self._parse_eigenvalues(content, result)
        
        # Errors and warnings
        self._parse_errors_warnings(content, result)
        
        return result
    
    def _parse_system_info(self, content: str, result: ParsedQEOutput):
        """Parse system information."""
        # Calculation type
        calc_match = self.PATTERNS['calculation'].search(content)
        if calc_match:
            result.calculation_type = calc_match.group(1)
            result.is_band_calculation = result.calculation_type == 'bands'
            result.is_relaxation = result.calculation_type in ['relax', 'vc-relax']
        
        # Other parameters
        for key, pattern in [
            ('prefix', 'prefix'),
            ('nat', 'nat'),
            ('ntyp', 'ntyp'),
            ('nelec', 'nelec'),
            ('nbnd', 'nbnd'),
            ('alat', 'alat'),
            ('volume', 'cell_volume'),
            ('nkpts', 'nkpts'),
        ]:
            match = self.PATTERNS[pattern].search(content)
            if match:
                value = match.group(1)
                if key in ['nat', 'ntyp', 'nbnd', 'nkpts']:
                    setattr(result, key, int(value))
                else:
                    setattr(result, key, float(value))
        
        # Cell parameters
        self._parse_cell_parameters(content, result)
    
    def _parse_cell_parameters(self, content: str, result: ParsedQEOutput):
        """Parse crystal axes / cell parameters."""
        # Look for crystal axes in units of alat
        axes_pattern = re.compile(
            r"crystal axes:.*?\n"
            r"\s*a\(1\)\s*=\s*\(([-\d.\s]+)\)\s*\n"
            r"\s*a\(2\)\s*=\s*\(([-\d.\s]+)\)\s*\n"
            r"\s*a\(3\)\s*=\s*\(([-\d.\s]+)\)",
            re.DOTALL
        )
        match = axes_pattern.search(content)
        if match:
            cell = np.zeros((3, 3))
            for i, group in enumerate([match.group(1), match.group(2), match.group(3)]):
                values = [float(x) for x in group.split()]
                cell[i] = values
            result.cell_parameters = cell * result.alat
    
    def _parse_scf_iterations(self, content: str, result: ParsedQEOutput):
        """Parse SCF iteration data."""
        # Find all iteration blocks
        iter_pattern = re.compile(
            r"iteration\s*#\s*(\d+).*?total energy\s*=\s*([-\d.]+)\s*Ry",
            re.DOTALL
        )
        
        for match in iter_pattern.finditer(content):
            iteration = int(match.group(1))
            energy = float(match.group(2))
            
            # Try to get accuracy for this iteration
            # Look in nearby text
            start = match.start()
            end = min(match.end() + 200, len(content))
            nearby = content[start:end]
            
            acc_match = self.PATTERNS['scf_accuracy'].search(nearby)
            accuracy = float(acc_match.group(1)) if acc_match else 0.0
            
            scf_iter = SCFIteration(
                iteration=iteration,
                total_energy=energy,
                accuracy=accuracy,
            )
            result.scf_iterations.append(scf_iter)
        
        result.scf_converged = bool(self.PATTERNS['convergence'].search(content))
    
    def _parse_energies(self, content: str, result: ParsedQEOutput):
        """Parse final energies."""
        # Total energy (final converged value with !)
        energy_match = self.PATTERNS['total_energy'].search(content)
        if energy_match:
            result.final_energy = float(energy_match.group(1))
        elif result.scf_iterations:
            # Use last SCF iteration
            result.final_energy = result.scf_iterations[-1].total_energy
        
        # Fermi energy
        fermi_match = self.PATTERNS['fermi_energy'].search(content)
        if fermi_match:
            result.fermi_energy = float(fermi_match.group(1))
        else:
            # Try HOMO/LUMO format
            homo_match = self.PATTERNS['homo_lumo'].search(content)
            if homo_match:
                result.fermi_energy = float(homo_match.group(1))
    
    def _parse_magnetization(self, content: str, result: ParsedQEOutput):
        """Parse magnetization data."""
        total_match = self.PATTERNS['total_mag'].search(content)
        if total_match:
            result.is_spin_polarized = True
            result.total_magnetization = float(total_match.group(1))
        
        abs_match = self.PATTERNS['abs_mag'].search(content)
        if abs_match:
            result.absolute_magnetization = float(abs_match.group(1))
    
    def _parse_forces(self, content: str, result: ParsedQEOutput):
        """Parse atomic forces."""
        # Find all force lines
        for match in self.PATTERNS['force_line'].finditer(content):
            atom_idx = int(match.group(1))
            fx = float(match.group(2))
            fy = float(match.group(3))
            fz = float(match.group(4))
            
            force = AtomicForce(
                atom_index=atom_idx,
                species="",  # TODO: get from atomic positions
                force=np.array([fx, fy, fz]),
            )
            result.forces.append(force)
        
        # Total force
        total_match = self.PATTERNS['total_force'].search(content)
        if total_match:
            result.total_force = float(total_match.group(1))
    
    def _parse_stress(self, content: str, result: ParsedQEOutput):
        """Parse stress tensor."""
        # Look for stress tensor block
        stress_section = re.search(
            r"entering subroutine stress.*?"
            r"total\s+stress.*?\n"
            r"(.*?)\n\s*\n",
            content, re.DOTALL
        )
        
        if stress_section:
            lines = stress_section.group(1).strip().split('\n')
            stress = np.zeros((3, 3))
            for i, line in enumerate(lines[:3]):
                values = [float(x) for x in line.split()[:3]]
                if len(values) == 3:
                    stress[i] = values
            
            if np.any(stress != 0):
                result.stress_tensor = stress
        
        # Pressure
        pressure_match = self.PATTERNS['pressure'].search(content)
        if pressure_match:
            result.pressure = float(pressure_match.group(1))
    
    def _parse_relaxation(self, content: str, result: ParsedQEOutput):
        """Parse structural relaxation data."""
        bfgs_match = self.PATTERNS['bfgs_converged'].search(content)
        if bfgs_match:
            result.relaxation_converged = True
            result.relaxation_steps = int(bfgs_match.group(1))
        
        # Final coordinates
        # Look for "Begin final coordinates" block
        final_coords = re.search(
            r"Begin final coordinates.*?"
            r"ATOMIC_POSITIONS.*?\n(.*?)\n(?:End final|CELL_PARAMETERS)",
            content, re.DOTALL
        )
        
        if final_coords:
            lines = final_coords.group(1).strip().split('\n')
            positions = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        pos = [float(parts[1]), float(parts[2]), float(parts[3])]
                        positions.append(pos)
                    except ValueError:
                        continue
            
            if positions:
                result.final_positions = np.array(positions)
    
    def _parse_eigenvalues(self, content: str, result: ParsedQEOutput):
        """Parse eigenvalues from bands calculation."""
        if not result.is_band_calculation and 'bands' not in content.lower():
            return
        
        # Look for eigenvalue blocks
        eig_pattern = re.compile(
            r"k =.*?\n((?:\s*[-\d.]+)+)",
            re.MULTILINE
        )
        
        all_eigenvalues = []
        for match in eig_pattern.finditer(content):
            eig_text = match.group(1)
            values = [float(x) for x in eig_text.split()]
            if values:
                all_eigenvalues.append(values)
        
        if all_eigenvalues:
            # Determine shape
            nkpts = len(all_eigenvalues)
            nbands = len(all_eigenvalues[0]) if all_eigenvalues else 0
            
            if nbands > 0:
                result.eigenvalues = np.zeros((1, nkpts, nbands))
                for i, eigs in enumerate(all_eigenvalues):
                    result.eigenvalues[0, i, :len(eigs)] = eigs
    
    def _parse_errors_warnings(self, content: str, result: ParsedQEOutput):
        """Parse errors and warnings."""
        for match in self.PATTERNS['error'].finditer(content):
            start = max(0, match.start() - 100)
            end = min(len(content), match.end() + 200)
            context = content[start:end].strip()
            result.errors.append(context)
        
        for match in self.PATTERNS['warning'].finditer(content):
            start = max(0, match.start() - 50)
            end = min(len(content), match.end() + 100)
            context = content[start:end].strip()
            result.warnings.append(context)
    
    def _parse_time(self, time_str: str) -> float:
        """Parse time string to seconds."""
        time_str = time_str.strip()
        
        # Handle "Xh Ym Zs" format
        hours = minutes = seconds = 0
        
        h_match = re.search(r'(\d+)h', time_str)
        if h_match:
            hours = int(h_match.group(1))
        
        m_match = re.search(r'(\d+)m', time_str)
        if m_match:
            minutes = int(m_match.group(1))
        
        s_match = re.search(r'([\d.]+)s', time_str)
        if s_match:
            seconds = float(s_match.group(1))
        
        return hours * 3600 + minutes * 60 + seconds
    
    def parse_bands_dat(self, filepath: Union[str, Path]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Parse bands.x output file (*.dat or *.gnu format).
        
        Args:
            filepath: Path to bands.dat file
            
        Returns:
            Tuple of (k_distances, eigenvalues) arrays
        """
        filepath = Path(filepath)
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
        
        bands_data = []
        current_band = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_band:
                    bands_data.append(current_band)
                    current_band = []
            else:
                values = [float(x) for x in line.split()]
                if len(values) >= 2:
                    current_band.append(values)
        
        if current_band:
            bands_data.append(current_band)
        
        # Convert to arrays
        nbands = len(bands_data)
        nkpts = len(bands_data[0]) if bands_data else 0
        
        k_distances = np.zeros(nkpts)
        eigenvalues = np.zeros((nbands, nkpts))
        
        for i, band in enumerate(bands_data):
            for j, (k, e) in enumerate(band):
                k_distances[j] = k
                eigenvalues[i, j] = e
        
        return k_distances, eigenvalues
    
    def parse_dos(self, filepath: Union[str, Path]) -> Tuple[np.ndarray, np.ndarray]:
        """
        Parse dos.x output file.
        
        Args:
            filepath: Path to DOS file (e.g., prefix.dos)
            
        Returns:
            Tuple of (energies, dos) arrays
        """
        filepath = Path(filepath)
        
        data = np.loadtxt(filepath, comments='#')
        
        energies = data[:, 0]
        dos = data[:, 1]
        
        return energies, dos
