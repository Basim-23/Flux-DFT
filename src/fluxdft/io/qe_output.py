"""
Quantum ESPRESSO Output Parsing Module.

Provides parsers for:
- pw.x standard output (energy, forces, stress, convergence)
- bands.x output (bands.dat)
- dos.x output (pwscf.dos)

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

import re
import numpy as np
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Union, Tuple
import logging

logger = logging.getLogger(__name__)


@dataclass
class QEOutputData:
    """Parsed data from pw.x output."""
    total_energy_ev: Optional[float] = None
    fermi_energy_ev: Optional[float] = None
    forces: Optional[np.ndarray] = None  # (nat, 3) in Ry/au
    stress: Optional[np.ndarray] = None  # (3, 3) in kbar
    cell_parameters: Optional[np.ndarray] = None  # (3, 3) in Angstrom
    atomic_positions: Optional[List[Dict]] = None
    scf_iterations: List[Dict] = field(default_factory=list)
    job_done: bool = False
    converged: bool = False
    wall_time: Optional[float] = None
    version: Optional[str] = None
    
    # Metadata
    nat: int = 0
    ntyp: int = 0
    ecutwfc: float = 0.0
    
    @property
    def final_energy(self) -> Optional[float]:
        """Get final energy (alias)."""
        return self.total_energy_ev


@dataclass
class QEBandsData:
    """Parsed data from bands.x output (bands.dat)."""
    kpoints: np.ndarray  # (nks, 3)
    eigenvalues: np.ndarray  # (nks, nbnd) in eV
    nbnd: int
    nks: int
    fermi_energy: Optional[float] = None


@dataclass
class QEDosData:
    """Parsed data from dos.x output."""
    energies: np.ndarray
    dos_up: np.ndarray
    dos_down: Optional[np.ndarray] = None
    integrated_dos: np.ndarray
    fermi_energy: Optional[float] = None


class QEOutputParser:
    """
    Parser for Quantum ESPRESSO output files.
    
    Usage:
        >>> parser = QEOutputParser()
        >>> data = parser.parse("scf.out")
        >>> print(data.total_energy_ev)
    """
    
    def parse(self, filepath: Union[str, Path]) -> QEOutputData:
        """
        Parse pw.x standard output.
        
        Args:
            filepath: Path to output file
            
        Returns:
            QEOutputData object
        """
        filepath = Path(filepath)
        if not filepath.exists():
            raise FileNotFoundError(f"File not found: {filepath}")
        
        content = filepath.read_text(encoding='utf-8', errors='replace')
        return self.parse_string(content)
    
    def parse_string(self, content: str) -> QEOutputData:
        """Parse output from string."""
        data = QEOutputData()
        
        # Parse version
        m = re.search(r'Program PWSCF v\.(\S+)', content)
        if m:
            data.version = m.group(1)
            
        # Parse system info
        m = re.search(r'number of atoms/cell\s*=\s*(\d+)', content)
        if m:
            data.nat = int(m.group(1))
            
        m = re.search(r'number of atomic types\s*=\s*(\d+)', content)
        if m:
            data.ntyp = int(m.group(1))
            
        m = re.search(r'kinetic-energy cutoff\s*=\s*([\d\.]+)\s*Ry', content)
        if m:
            data.ecutwfc = float(m.group(1))
            
        # Check if job done
        if 'JOB DONE' in content:
            data.job_done = True
            
        # Parse SCF iterations
        self._parse_scf_iterations(content, data)
        
        # Parse final energy (usually the last one marked with !)
        energies = re.findall(r'!\s+total energy\s*=\s*([-\d\.]+)\s*Ry', content)
        if energies:
            data.total_energy_ev = float(energies[-1]) * 13.6056980659  # Ry to eV
            
        # Parse Fermi energy
        # "the Fermi energy is    12.3456 eV"
        m = re.findall(r'the Fermi energy is\s*([-\d\.]+)\s*eV', content)
        if m:
            data.fermi_energy_ev = float(m[-1])
            
        # Parse forces
        # "Forces acting on atoms (cartesian axes, Ry/au):"
        if "Forces acting on atoms" in content:
            self._parse_forces(content, data)
            
        # Parse stress
        # "total   stress  (Ry/bohr**3)                   (kbar)     P=  -1.23"
        if "total   stress" in content:
            self._parse_stress(content, data)
            
        # Parse wall time
        # "PWSCF        :     1m23.45s CPU     1m24.00s WALL"
        m = re.search(r'PWSCF\s*:\s*.*CPU\s*([^\s]+)\s*WALL', content)
        if m:
            time_str = m.group(1)
            data.wall_time = self._parse_time(time_str)
            
        # Check convergence
        if 'convergence has been achieved' in content:
            data.converged = True
        elif 'convergence NOT achieved' in content:
            data.converged = False
            
        return data
    
    def _parse_scf_iterations(self, content: str, data: QEOutputData):
        """Parse SCF iteration history."""
        # Pattern: iteration #  1     ecut=    60.00 Ry     beta=0.70
        #          Davidson diagonalization with overlap
        #          ethr =  1.00E-02,  avg # of iterations =  2.0
        #          total cpu time spent up to now is        0.5 secs
        #          total energy              =     -15.79045612 Ry
        #          Harris-Foulkes estimate   =     -15.89045612 Ry
        #          estimated scf accuracy    <       0.12345678 Ry
        
        pattern = r'iteration #\s*(\d+).*?total energy\s*=\s*([-\d\.]+)\s*Ry.*?estimated scf accuracy\s*<\s*([-\d\.E]+)\s*Ry'
        matches = re.findall(pattern, content, re.DOTALL)
        
        for m in matches:
            iteration = int(m[0])
            energy = float(m[1])
            accuracy = float(m[2])
            
            data.scf_iterations.append({
                'iteration': iteration,
                'energy_ry': energy,
                'accuracy_ry': accuracy,
                'energy_ev': energy * 13.6056980659
            })
            
    def _parse_forces(self, content: str, data: QEOutputData):
        """Parse forces block."""
        # Find last occurrence
        parts = content.split("Forces acting on atoms (cartesian axes, Ry/au):")
        if len(parts) < 2:
            return
            
        block = parts[-1]
        lines = block.split('\n')
        
        forces = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if "atom" not in line or "type" not in line:
                # End of block usually followed by blank line or stress
                if len(forces) > 0:
                    break
                continue
                
            # atom    1 type  1   force =     0.00000000    0.00000000    0.00000000
            m = re.search(r'force\s*=\s*([-\d\.]+)\s*([-\d\.]+)\s*([-\d\.]+)', line)
            if m:
                forces.append([float(m.group(1)), float(m.group(2)), float(m.group(3))])
                
        if forces:
            data.forces = np.array(forces)
            
    def _parse_stress(self, content: str, data: QEOutputData):
        """Parse stress block."""
        # Find last occurrence
        parts = content.split("total   stress")
        if len(parts) < 2:
            return
            
        block = parts[-1]
        lines = block.split('\n')
        
        stress = []
        for line in lines:
            # (Ry/bohr**3)                   (kbar)     P=  -1.23
            if "P=" in line:
                continue
                
            #      -0.00000500   0.00000000   0.00000000        -0.74      0.00      0.00
            parts = line.split()
            if len(parts) == 6:
                # Last 3 columns are kbar
                stress.append([float(parts[3]), float(parts[4]), float(parts[5])])
                
            if len(stress) == 3:
                break
                
        if stress:
            data.stress = np.array(stress)

    def _parse_time(self, time_str: str) -> float:
        """Parse time string (e.g. 1h23m45s) to seconds."""
        total_seconds = 0.0
        
        m = re.search(r'(\d+)h', time_str)
        if m:
            total_seconds += int(m.group(1)) * 3600
            
        m = re.search(r'(\d+)m', time_str)
        if m:
            total_seconds += int(m.group(1)) * 60
            
        m = re.search(r'([\d\.]+)s', time_str)
        if m:
            total_seconds += float(m.group(1))
            
        return total_seconds


class QEBandsParser:
    """Parser for bands.x output (bands.dat or .gnu)."""
    
    @staticmethod
    def parse(filepath: Union[str, Path]) -> QEBandsData:
        """Parse bands.dat."""
        filepath = Path(filepath)
        
        with open(filepath, 'r') as f:
            lines = f.readlines()
            
        # Parse header if XMGR format
        #  &plot nbnd=   8, nks=    20 /
        nbnd = 0
        nks = 0
        
        if '&plot' in lines[0]:
            m = re.search(r'nbnd\s*=\s*(\d+)', lines[0])
            if m: nbnd = int(m.group(1))
            m = re.search(r'nks\s*=\s*(\d+)', lines[0])
            if m: nks = int(m.group(1))
            
            start_idx = 1
        else:
            # Try to infer or assume standard format
            # Might be flat list of kpoints + eigenvalues
            start_idx = 0
            
        if nbnd == 0 or nks == 0:
            # Fallback deduction not implemented for brevity
            raise ValueError("Could not determine nbnd/nks from header")
            
        kpoints = []
        eigenvalues = []
        
        current_k = None
        current_eigs = []
        
        # Format usually:
        #   kpoint_x kpoint_y kpoint_z
        #   eig1 eig2 eig3 ...
        #   eigN ...
        
        # Iterate through file
        # This is a bit tricky as formatting varies.
        # Let's assume standard 'bands.x' output
        
        # Often:
        #   -0.500000  0.500000  0.500000
        #   -5.834  -2.345 ...
        
        # Simpler approach: Read all numbers, reshape
        all_numbers = []
        for line in lines[start_idx:]:
            # Clean up
            line = line.strip()
            if not line or line.startswith('/'): continue
            all_numbers.extend([float(x) for x in line.split()])
            
        # Structure: for each kpoint: 3 coords + nbnd eigenvalues
        # Total numbers = nks * (3 + nbnd)
        
        numbers = np.array(all_numbers)
        records = numbers.reshape((nks, 3 + nbnd))
        
        kpoints = records[:, :3]
        eigenvalues = records[:, 3:]
        
        return QEBandsData(
            kpoints=kpoints,
            eigenvalues=eigenvalues,
            nbnd=nbnd,
            nks=nks
        )


class QEDosParser:
    """Parser for dos.x output."""
    
    @staticmethod
    def parse(filepath: Union[str, Path]) -> QEDosData:
        """Parse dos.dat."""
        filepath = Path(filepath)
        
        # Standard format: E (eV)  DOS(E)  Int DOS(E)
        # Or if spin: E (eV)  DOS(up)  DOS(down)  Int DOS(up)  Int DOS(down)
        
        # Skip header lines usually with #
        data = np.loadtxt(filepath, comments='#')
        
        if data.shape[1] == 3:
            # Non-spin polarized
            energies = data[:, 0]
            dos_up = data[:, 1]
            integrated = data[:, 2]
            return QEDosData(energies, dos_up, None, integrated)
            
        elif data.shape[1] == 5:
            # Spin polarized
            energies = data[:, 0]
            dos_up = data[:, 1]
            dos_down = data[:, 2]
            integrated = data[:, 3] + data[:, 4] # Approx
            return QEDosData(energies, dos_up, dos_down, integrated)
            
        else:
            raise ValueError(f"Unknown DOS format with {data.shape[1]} columns")
