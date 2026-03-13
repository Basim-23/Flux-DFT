"""
Phonon Workflow for FluxDFT.

Generates and manages phonon calculation workflows:
SCF -> DFPT (ph.x) -> q2r.x -> matdyn.x
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


@dataclass
class PhononConfig:
    """Configuration for phonon calculation."""
    
    # Q-point grid for DFPT
    nq1: int = 4
    nq2: int = 4
    nq3: int = 4
    
    # Acoustic sum rule
    asr: str = 'crystal'  # 'crystal', 'simple', 'no'
    
    # Path for dispersion
    q_path: List[Tuple[str, List[float]]] = field(default_factory=list)
    n_points: int = 100  # Points along path
    
    # DOS settings
    dos_nfreq: int = 500
    dos_deltaE: float = 1.0  # cm^-1
    
    # Other
    tr2_ph: float = 1.0e-14
    alpha_mix: float = 0.7
    

def get_standard_q_path(crystal_system: str) -> List[Tuple[str, List[float]]]:
    """Get standard high-symmetry q-path for a crystal system."""
    paths = {
        'cubic': [
            ('Γ', [0.0, 0.0, 0.0]),
            ('X', [0.5, 0.0, 0.0]),
            ('M', [0.5, 0.5, 0.0]),
            ('Γ', [0.0, 0.0, 0.0]),
            ('R', [0.5, 0.5, 0.5]),
            ('X', [0.5, 0.0, 0.0]),
        ],
        'hexagonal': [
            ('Γ', [0.0, 0.0, 0.0]),
            ('M', [0.5, 0.0, 0.0]),
            ('K', [0.333, 0.333, 0.0]),
            ('Γ', [0.0, 0.0, 0.0]),
            ('A', [0.0, 0.0, 0.5]),
        ],
        'tetragonal': [
            ('Γ', [0.0, 0.0, 0.0]),
            ('X', [0.5, 0.0, 0.0]),
            ('M', [0.5, 0.5, 0.0]),
            ('Γ', [0.0, 0.0, 0.0]),
            ('Z', [0.0, 0.0, 0.5]),
        ],
    }
    return paths.get(crystal_system.lower(), paths['cubic'])


class PhononWorkflow:
    """
    Generates and manages a complete phonon workflow.
    
    Usage:
        workflow = PhononWorkflow(
            base_scf_input="si.scf.in",
            work_dir="./phonon",
            prefix="si"
        )
        
        workflow.config.nq1 = 4
        workflow.config.nq2 = 4
        workflow.config.nq3 = 4
        
        # Generate all input files
        inputs = workflow.generate_all()
        
        # Get job list for runner
        jobs = workflow.get_job_sequence()
    """
    
    def __init__(
        self,
        base_scf_input: Path,
        work_dir: Path,
        prefix: str = "pwscf"
    ):
        self.base_scf_input = Path(base_scf_input)
        self.work_dir = Path(work_dir)
        self.prefix = prefix
        self.config = PhononConfig()
        
        self.work_dir.mkdir(parents=True, exist_ok=True)
    
    def generate_scf_input(self) -> Path:
        """Generate/copy SCF input file."""
        scf_path = self.work_dir / f"{self.prefix}.scf.in"
        
        if self.base_scf_input.exists():
            content = self.base_scf_input.read_text()
            # Ensure proper settings for phonons
            # (verbosity = 'high', tprnfor = .true., tstress = .true.)
            scf_path.write_text(content)
        
        return scf_path
    
    def generate_ph_input(self) -> Path:
        """Generate ph.x input file for DFPT."""
        c = self.config
        
        content = f"""Phonon calculation for {self.prefix}
&INPUTPH
  prefix = '{self.prefix}'
  outdir = './tmp'
  tr2_ph = {c.tr2_ph}
  alpha_mix(1) = {c.alpha_mix}
  ldisp = .true.
  nq1 = {c.nq1}
  nq2 = {c.nq2}
  nq3 = {c.nq3}
  fildyn = '{self.prefix}.dyn'
/
"""
        
        ph_path = self.work_dir / f"{self.prefix}.ph.in"
        ph_path.write_text(content)
        return ph_path
    
    def generate_q2r_input(self) -> Path:
        """Generate q2r.x input for Fourier interpolation."""
        c = self.config
        
        content = f"""&INPUT
  fildyn = '{self.prefix}.dyn'
  zasr = '{c.asr}'
  flfrc = '{self.prefix}.fc'
/
"""
        
        q2r_path = self.work_dir / f"{self.prefix}.q2r.in"
        q2r_path.write_text(content)
        return q2r_path
    
    def generate_matdyn_bands_input(self) -> Path:
        """Generate matdyn.x input for phonon dispersion."""
        c = self.config
        
        # Build q-path
        if not c.q_path:
            c.q_path = get_standard_q_path('cubic')
        
        q_lines = []
        for label, coords in c.q_path:
            q_lines.append(f"  {coords[0]:.6f} {coords[1]:.6f} {coords[2]:.6f}  ! {label}")
        
        content = f"""&INPUT
  asr = '{c.asr}'
  flfrc = '{self.prefix}.fc'
  flfrq = '{self.prefix}.freq'
  flvec = '{self.prefix}.modes'
  q_in_band_form = .true.
/
{len(c.q_path)}
""" + "\n".join(q_lines) + "\n"
        
        path = self.work_dir / f"{self.prefix}.matdyn_bands.in"
        path.write_text(content)
        return path
    
    def generate_matdyn_dos_input(self) -> Path:
        """Generate matdyn.x input for phonon DOS."""
        c = self.config
        
        content = f"""&INPUT
  asr = '{c.asr}'
  flfrc = '{self.prefix}.fc'
  flfrq = '{self.prefix}.dos.freq'
  dos = .true.
  fldos = '{self.prefix}.phdos'
  nk1 = {c.nq1 * 4}
  nk2 = {c.nq2 * 4}
  nk3 = {c.nq3 * 4}
  deltaE = {c.dos_deltaE}
/
"""
        
        path = self.work_dir / f"{self.prefix}.matdyn_dos.in"
        path.write_text(content)
        return path
    
    def generate_all(self) -> Dict[str, Path]:
        """Generate all input files for the workflow."""
        return {
            'scf': self.generate_scf_input(),
            'ph': self.generate_ph_input(),
            'q2r': self.generate_q2r_input(),
            'matdyn_bands': self.generate_matdyn_bands_input(),
            'matdyn_dos': self.generate_matdyn_dos_input(),
        }
    
    def get_job_sequence(self) -> List[Dict[str, Any]]:
        """
        Get the sequence of jobs to run.
        
        Returns list of job specs for JobRunner.
        """
        inputs = self.generate_all()
        
        return [
            {
                'name': f'{self.prefix} - SCF',
                'executable': 'pw.x',
                'input_file': inputs['scf'],
                'output_file': self.work_dir / f"{self.prefix}.scf.out",
            },
            {
                'name': f'{self.prefix} - Phonon (DFPT)',
                'executable': 'ph.x',
                'input_file': inputs['ph'],
                'output_file': self.work_dir / f"{self.prefix}.ph.out",
            },
            {
                'name': f'{self.prefix} - q2r',
                'executable': 'q2r.x',
                'input_file': inputs['q2r'],
                'output_file': self.work_dir / f"{self.prefix}.q2r.out",
            },
            {
                'name': f'{self.prefix} - Phonon Bands',
                'executable': 'matdyn.x',
                'input_file': inputs['matdyn_bands'],
                'output_file': self.work_dir / f"{self.prefix}.matdyn_bands.out",
            },
            {
                'name': f'{self.prefix} - Phonon DOS',
                'executable': 'matdyn.x',
                'input_file': inputs['matdyn_dos'],
                'output_file': self.work_dir / f"{self.prefix}.matdyn_dos.out",
            },
        ]
    
    def parse_phonon_dispersion(self) -> Optional[Dict[str, Any]]:
        """Parse phonon dispersion from matdyn output."""
        freq_file = self.work_dir / f"{self.prefix}.freq"
        
        if not freq_file.exists():
            return None
        
        try:
            content = freq_file.read_text()
            
            # Parse frequencies (simplified)
            q_points = []
            frequencies = []
            
            current_q = None
            current_freqs = []
            
            for line in content.split('\n'):
                line = line.strip()
                if not line:
                    continue
                
                if 'q =' in line.lower():
                    if current_q is not None:
                        q_points.append(current_q)
                        frequencies.append(current_freqs)
                    
                    parts = line.split('=')[1].strip().replace('(', '').replace(')', '')
                    coords = [float(x) for x in parts.split()]
                    current_q = coords
                    current_freqs = []
                else:
                    try:
                        freqs = [float(x) for x in line.split()]
                        current_freqs.extend(freqs)
                    except ValueError:
                        pass
            
            # Add last point
            if current_q is not None:
                q_points.append(current_q)
                frequencies.append(current_freqs)
            
            return {
                'q_points': q_points,
                'frequencies': frequencies,
                'n_modes': len(frequencies[0]) if frequencies else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to parse phonon dispersion: {e}")
            return None
    
    def parse_phonon_dos(self) -> Optional[Dict[str, Any]]:
        """Parse phonon DOS from matdyn output."""
        dos_file = self.work_dir / f"{self.prefix}.phdos"
        
        if not dos_file.exists():
            return None
        
        try:
            content = dos_file.read_text()
            
            energies = []
            dos_values = []
            
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                parts = line.split()
                if len(parts) >= 2:
                    energies.append(float(parts[0]))
                    dos_values.append(float(parts[1]))
            
            return {
                'energies': energies,  # cm^-1
                'dos': dos_values,
            }
            
        except Exception as e:
            logger.error(f"Failed to parse phonon DOS: {e}")
            return None
    
    def check_imaginary_frequencies(self) -> List[Tuple[int, float]]:
        """
        Check for imaginary (negative) frequencies indicating instability.
        
        Returns list of (q_point_index, frequency) for imaginary modes.
        """
        dispersion = self.parse_phonon_dispersion()
        if not dispersion:
            return []
        
        imaginary = []
        for i, freqs in enumerate(dispersion['frequencies']):
            for freq in freqs:
                if freq < -0.5:  # Small threshold for numerical noise
                    imaginary.append((i, freq))
        
        return imaginary
