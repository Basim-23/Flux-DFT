"""
Workflow Makers for FluxDFT.

Pre-built workflow factories for common DFT calculation patterns.
Inspired by atomate2's Maker classes.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Union
from pathlib import Path
from abc import ABC, abstractmethod
import logging

from .base import TaskStatus
from .task import QETask, QEInput, ScfTask, NscfTask, BandsTask, DosTask, RelaxTask, VCRelaxTask
from .workflow import QEWorkflow

logger = logging.getLogger(__name__)


class WorkflowMaker(ABC):
    """
    Base class for workflow factories.
    
    Makers create pre-configured workflows from minimal input.
    Each maker encapsulates best practices for a specific calculation type.
    
    Usage:
        >>> maker = BandStructureMaker(
        ...     kpath=[('Γ', [0,0,0]), ('X', [0.5,0,0])],
        ...     npoints=100,
        ... )
        >>> workflow = maker.make(structure, workdir=Path("./bands"))
        >>> result = workflow.run()
    """
    
    name: str = "base"
    
    @abstractmethod
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        **kwargs,
    ) -> QEWorkflow:
        """
        Create workflow.
        
        Args:
            structure: pymatgen Structure.
            workdir: Working directory.
            **kwargs: Additional parameters.
            
        Returns:
            Configured QEWorkflow.
        """
        pass
    
    def _create_base_input(
        self,
        structure: 'Structure',
        calculation: str = 'scf',
        **kwargs,
    ) -> QEInput:
        """Create base QE input from structure."""
        qe_input = QEInput(calculation=calculation)
        
        # System parameters from structure
        qe_input.system.update({
            'nat': len(structure),
            'ntyp': len(set(s.specie.symbol for s in structure)),
            'ibrav': 0,
        })
        
        # Default electrons settings
        qe_input.electrons.update({
            'conv_thr': 1.0e-8,
            'mixing_beta': 0.7,
        })
        
        # Apply user overrides
        for key, val in kwargs.items():
            if key in ('ecutwfc', 'ecutrho', 'occupations', 'smearing', 'degauss'):
                qe_input.system[key] = val
            elif key in ('conv_thr', 'mixing_beta', 'electron_maxstep'):
                qe_input.electrons[key] = val
        
        # Structure cards
        qe_input.additional_cards = self._structure_to_cards(structure)
        
        return qe_input
    
    def _structure_to_cards(self, structure: 'Structure') -> Dict[str, str]:
        """Convert structure to QE cards."""
        cards = {}
        
        # CELL_PARAMETERS
        lines = ["CELL_PARAMETERS angstrom"]
        for vec in structure.lattice.matrix:
            lines.append(f"  {vec[0]:15.10f} {vec[1]:15.10f} {vec[2]:15.10f}")
        cards['cell_parameters'] = "\n".join(lines)
        
        # ATOMIC_SPECIES (requires pseudopotential info)
        species = sorted(set(s.specie.symbol for s in structure))
        lines = ["ATOMIC_SPECIES"]
        for sp in species:
            # Default PP naming convention
            lines.append(f"  {sp}  {0.0}  {sp}.UPF")
        cards['atomic_species'] = "\n".join(lines)
        
        # ATOMIC_POSITIONS
        lines = ["ATOMIC_POSITIONS crystal"]
        for site in structure:
            pos = site.frac_coords
            lines.append(f"  {site.specie.symbol}  {pos[0]:15.10f} {pos[1]:15.10f} {pos[2]:15.10f}")
        cards['atomic_positions'] = "\n".join(lines)
        
        return cards


@dataclass
class BandStructureMaker(WorkflowMaker):
    """
    Create band structure calculation workflow.
    
    Workflow: SCF → NSCF (bands) → bands.x post-processing
    
    Attributes:
        kpath: K-point path as [(label, coords), ...]
        npoints: Points per segment
        ecutwfc: Plane-wave cutoff
        ecutrho: Charge density cutoff
        kgrid: SCF k-point grid
    """
    
    name: str = "band_structure"
    kpath: List[tuple] = field(default_factory=list)
    npoints: int = 50
    ecutwfc: float = 60.0
    ecutrho: Optional[float] = None
    kgrid: tuple = (8, 8, 8)
    
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        **kwargs,
    ) -> QEWorkflow:
        """Create band structure workflow."""
        workflow = QEWorkflow(
            name=f"bands_{structure.formula}",
            workdir=workdir,
            description=f"Band structure calculation for {structure.formula}",
        )
        
        # SCF task
        scf_input = self._create_base_input(
            structure,
            calculation='scf',
            ecutwfc=self.ecutwfc,
            ecutrho=self.ecutrho or self.ecutwfc * 8,
        )
        scf_input.kpoints = {
            'type': 'automatic',
            'grid': self.kgrid,
            'shift': (0, 0, 0),
        }
        scf_input.additional_cards['k_points'] = (
            f"K_POINTS automatic\n  {self.kgrid[0]} {self.kgrid[1]} {self.kgrid[2]} 0 0 0"
        )
        
        scf_task = ScfTask(name="scf", input_data=scf_input)
        workflow.add_task(scf_task)
        
        # Bands task
        bands_input = self._create_base_input(
            structure,
            calculation='bands',
            ecutwfc=self.ecutwfc,
            ecutrho=self.ecutrho or self.ecutwfc * 8,
        )
        
        # Generate k-path
        if self.kpath:
            kpoints_str = self._generate_kpath_string(self.kpath, self.npoints)
            bands_input.additional_cards['k_points'] = kpoints_str
        
        bands_task = BandsTask(name="bands", input_data=bands_input)
        workflow.add_task(bands_task, depends_on=['scf'])
        
        return workflow
    
    def _generate_kpath_string(
        self,
        kpath: List[tuple],
        npoints: int,
    ) -> str:
        """Generate K_POINTS card for band structure."""
        n_segments = len(kpath) - 1
        lines = [f"K_POINTS crystal_b", f"  {len(kpath)}"]
        
        for i, (label, coords) in enumerate(kpath):
            npts = npoints if i < len(kpath) - 1 else 0
            lines.append(f"  {coords[0]:10.6f} {coords[1]:10.6f} {coords[2]:10.6f}  {npts}")
        
        return "\n".join(lines)


@dataclass
class DOSMaker(WorkflowMaker):
    """
    Create DOS calculation workflow.
    
    Workflow: SCF → NSCF (dense k-grid) → dos.x
    """
    
    name: str = "dos"
    ecutwfc: float = 60.0
    ecutrho: Optional[float] = None
    scf_kgrid: tuple = (8, 8, 8)
    nscf_kgrid: tuple = (16, 16, 16)
    degauss: float = 0.02
    
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        **kwargs,
    ) -> QEWorkflow:
        """Create DOS workflow."""
        workflow = QEWorkflow(
            name=f"dos_{structure.formula}",
            workdir=workdir,
            description=f"DOS calculation for {structure.formula}",
        )
        
        # SCF task
        scf_input = self._create_base_input(
            structure,
            calculation='scf',
            ecutwfc=self.ecutwfc,
            ecutrho=self.ecutrho or self.ecutwfc * 8,
            degauss=self.degauss,
            occupations='smearing',
            smearing='gaussian',
        )
        scf_input.additional_cards['k_points'] = (
            f"K_POINTS automatic\n  {self.scf_kgrid[0]} {self.scf_kgrid[1]} {self.scf_kgrid[2]} 0 0 0"
        )
        
        scf_task = ScfTask(name="scf", input_data=scf_input)
        workflow.add_task(scf_task)
        
        # NSCF task (dense k-grid)
        nscf_input = self._create_base_input(
            structure,
            calculation='nscf',
            ecutwfc=self.ecutwfc,
            ecutrho=self.ecutrho or self.ecutwfc * 8,
            degauss=self.degauss,
            occupations='tetrahedra',
        )
        nscf_input.additional_cards['k_points'] = (
            f"K_POINTS automatic\n  {self.nscf_kgrid[0]} {self.nscf_kgrid[1]} {self.nscf_kgrid[2]} 0 0 0"
        )
        
        nscf_task = NscfTask(name="nscf", input_data=nscf_input)
        workflow.add_task(nscf_task, depends_on=['scf'])
        
        # DOS task
        dos_task = DosTask(name="dos")
        workflow.add_task(dos_task, depends_on=['nscf'])
        
        return workflow


@dataclass
class RelaxationMaker(WorkflowMaker):
    """
    Create relaxation workflow.
    
    Can do atomic-only or variable-cell relaxation.
    """
    
    name: str = "relaxation"
    variable_cell: bool = False
    ecutwfc: float = 60.0
    ecutrho: Optional[float] = None
    kgrid: tuple = (8, 8, 8)
    force_thr: float = 1.0e-4
    press_thr: float = 0.5  # kbar
    
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        **kwargs,
    ) -> QEWorkflow:
        """Create relaxation workflow."""
        calc_type = 'vc-relax' if self.variable_cell else 'relax'
        
        workflow = QEWorkflow(
            name=f"{calc_type}_{structure.formula}",
            workdir=workdir,
            description=f"Relaxation for {structure.formula}",
        )
        
        # Relax task
        relax_input = self._create_base_input(
            structure,
            calculation=calc_type,
            ecutwfc=self.ecutwfc,
            ecutrho=self.ecutrho or self.ecutwfc * 8,
        )
        
        relax_input.control['forc_conv_thr'] = self.force_thr
        relax_input.ions['ion_dynamics'] = 'bfgs'
        
        if self.variable_cell:
            relax_input.control['press_conv_thr'] = self.press_thr
            relax_input.cell['cell_dynamics'] = 'bfgs'
        
        relax_input.additional_cards['k_points'] = (
            f"K_POINTS automatic\n  {self.kgrid[0]} {self.kgrid[1]} {self.kgrid[2]} 0 0 0"
        )
        
        TaskClass = VCRelaxTask if self.variable_cell else RelaxTask
        relax_task = TaskClass(name="relax", input_data=relax_input)
        workflow.add_task(relax_task)
        
        return workflow


@dataclass
class ConvergenceTestMaker(WorkflowMaker):
    """
    Create convergence test workflow.
    
    Tests energy convergence with respect to ecutwfc and k-grid.
    """
    
    name: str = "convergence_test"
    ecutwfc_range: List[float] = field(default_factory=lambda: [40, 50, 60, 70, 80])
    kgrid_range: List[tuple] = field(default_factory=lambda: [(4,4,4), (6,6,6), (8,8,8), (10,10,10)])
    
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        test_type: str = 'ecutwfc',
        **kwargs,
    ) -> QEWorkflow:
        """Create convergence test workflow."""
        workflow = QEWorkflow(
            name=f"conv_test_{structure.formula}",
            workdir=workdir,
            description=f"Convergence test for {structure.formula}",
            max_parallel=4,  # Run tests in parallel
        )
        
        if test_type == 'ecutwfc':
            for ecut in self.ecutwfc_range:
                input_data = self._create_base_input(
                    structure,
                    calculation='scf',
                    ecutwfc=ecut,
                    ecutrho=ecut * 8,
                )
                input_data.additional_cards['k_points'] = "K_POINTS automatic\n  8 8 8 0 0 0"
                
                task = ScfTask(name=f"scf_ecut{int(ecut)}", input_data=input_data)
                workflow.add_task(task)
        
        elif test_type == 'kgrid':
            for kg in self.kgrid_range:
                input_data = self._create_base_input(
                    structure,
                    calculation='scf',
                    ecutwfc=60.0,
                    ecutrho=480.0,
                )
                input_data.additional_cards['k_points'] = f"K_POINTS automatic\n  {kg[0]} {kg[1]} {kg[2]} 0 0 0"
                
                task = ScfTask(name=f"scf_k{'x'.join(map(str, kg))}", input_data=input_data)
                workflow.add_task(task)
        
        return workflow


@dataclass
class FullAnalysisMaker(WorkflowMaker):
    """
    Create comprehensive analysis workflow.
    
    Workflow: Relax → SCF → Bands → DOS → (optional) phonons
    """
    
    name: str = "full_analysis"
    relax: bool = True
    variable_cell: bool = True
    kpath: List[tuple] = field(default_factory=list)
    npoints: int = 50
    ecutwfc: float = 60.0
    kgrid: tuple = (8, 8, 8)
    
    def make(
        self,
        structure: 'Structure',
        workdir: Optional[Path] = None,
        **kwargs,
    ) -> QEWorkflow:
        """Create full analysis workflow."""
        workflow = QEWorkflow(
            name=f"full_{structure.formula}",
            workdir=workdir,
            description=f"Full electronic structure analysis for {structure.formula}",
        )
        
        prev_task = None
        
        # Optional relaxation
        if self.relax:
            relax_maker = RelaxationMaker(
                variable_cell=self.variable_cell,
                ecutwfc=self.ecutwfc,
                kgrid=self.kgrid,
            )
            # Create relax task manually for integration
            calc_type = 'vc-relax' if self.variable_cell else 'relax'
            relax_input = relax_maker._create_base_input(
                structure, calculation=calc_type, ecutwfc=self.ecutwfc
            )
            relax_input.additional_cards['k_points'] = (
                f"K_POINTS automatic\n  {self.kgrid[0]} {self.kgrid[1]} {self.kgrid[2]} 0 0 0"
            )
            
            TaskClass = VCRelaxTask if self.variable_cell else RelaxTask
            relax_task = TaskClass(name="relax", input_data=relax_input)
            workflow.add_task(relax_task)
            prev_task = "relax"
        
        # SCF
        scf_input = self._create_base_input(
            structure, calculation='scf', ecutwfc=self.ecutwfc
        )
        scf_input.additional_cards['k_points'] = (
            f"K_POINTS automatic\n  {self.kgrid[0]} {self.kgrid[1]} {self.kgrid[2]} 0 0 0"
        )
        scf_task = ScfTask(name="scf", input_data=scf_input)
        workflow.add_task(scf_task, depends_on=[prev_task] if prev_task else None)
        
        # Bands
        bands_input = self._create_base_input(
            structure, calculation='bands', ecutwfc=self.ecutwfc
        )
        if self.kpath:
            bands_input.additional_cards['k_points'] = self._generate_kpath_string(self.kpath)
        
        bands_task = BandsTask(name="bands", input_data=bands_input)
        workflow.add_task(bands_task, depends_on=['scf'])
        
        # DOS
        nscf_input = self._create_base_input(
            structure, calculation='nscf', ecutwfc=self.ecutwfc
        )
        nscf_input.additional_cards['k_points'] = "K_POINTS automatic\n  16 16 16 0 0 0"
        nscf_task = NscfTask(name="nscf", input_data=nscf_input)
        workflow.add_task(nscf_task, depends_on=['scf'])
        
        dos_task = DosTask(name="dos")
        workflow.add_task(dos_task, depends_on=['nscf'])
        
        return workflow
    
    def _generate_kpath_string(self, kpath: List[tuple]) -> str:
        """Generate K_POINTS card."""
        lines = [f"K_POINTS crystal_b", f"  {len(kpath)}"]
        for i, (label, coords) in enumerate(kpath):
            npts = self.npoints if i < len(kpath) - 1 else 0
            lines.append(f"  {coords[0]:10.6f} {coords[1]:10.6f} {coords[2]:10.6f}  {npts}")
        return "\n".join(lines)
