"""
Extended tests for the Input Builder.
Covers bands, DOS, phonon, relaxation, and various k-point modes.
"""

import pytest
from pathlib import Path
import sys
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fluxdft.core.input_builder import (
    InputBuilder, PWInput, AtomicSpecies, Atom,
    CellParameters, KPoints, create_silicon_scf_example
)


class TestBandsInput:
    """Test bands.x input generation."""

    def test_default_bands_input(self):
        builder = InputBuilder()
        content = builder.build_bands_input(prefix="silicon")

        assert "&BANDS" in content
        assert "prefix = 'silicon'" in content
        assert "filband = 'bands.out'" in content
        assert "lsym = .true." in content

    def test_custom_bands_input(self):
        builder = InputBuilder()
        content = builder.build_bands_input(
            prefix="gaas",
            outdir="./tmp",
            filband="gaas_bands.dat",
            lsym=False,
            spin_component=1,
        )

        assert "prefix = 'gaas'" in content
        assert "filband = 'gaas_bands.dat'" in content
        assert "lsym = .false." in content
        assert "spin_component = 1" in content


class TestDOSInput:
    """Test dos.x input generation."""

    def test_default_dos_input(self):
        builder = InputBuilder()
        content = builder.build_dos_input(prefix="silicon")

        assert "&DOS" in content
        assert "prefix = 'silicon'" in content
        assert "fildos = 'silicon.dos'" in content

    def test_dos_with_energy_range(self):
        builder = InputBuilder()
        content = builder.build_dos_input(
            prefix="silicon",
            Emin=-10.0,
            Emax=10.0,
            DeltaE=0.01,
        )

        assert "Emin = -10.0" in content
        assert "Emax = 10.0" in content
        assert "DeltaE = 0.01" in content


class TestPhononInput:
    """Test ph.x input generation."""

    def test_phonon_dispersion_input(self):
        builder = InputBuilder()
        content = builder.build_ph_input(
            prefix="silicon",
            nq1=4, nq2=4, nq3=4,
        )

        assert "&INPUTPH" in content
        assert "prefix = 'silicon'" in content
        assert "ldisp = .true." in content
        assert "nq1 = 4" in content
        assert "nq2 = 4" in content
        assert "nq3 = 4" in content

    def test_phonon_with_dielectric(self):
        builder = InputBuilder()
        content = builder.build_ph_input(
            prefix="silicon",
            nq1=1, nq2=1, nq3=1,
            epsil=True,
        )

        assert "epsil = .true." in content


class TestProjwfcInput:
    """Test projwfc.x input generation."""

    def test_default_projwfc(self):
        builder = InputBuilder()
        content = builder.build_projwfc_input(prefix="silicon")

        assert "&PROJWFC" in content
        assert "prefix = 'silicon'" in content

    def test_projwfc_with_range(self):
        builder = InputBuilder()
        content = builder.build_projwfc_input(
            prefix="silicon",
            Emin=-10.0,
            Emax=10.0,
            DeltaE=0.02,
        )

        assert "Emin = -10.0" in content
        assert "Emax = 10.0" in content
        assert "DeltaE = 0.02" in content


class TestRelaxationInput:
    """Test relaxation calculation input."""

    def test_relax_includes_ions(self):
        builder = InputBuilder()

        pw_input = PWInput(
            calculation="relax",
            prefix="test",
            ecutwfc=40.0,
            ion_dynamics="bfgs",
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[
                Atom("Si", (0.0, 0.0, 0.0)),
                Atom("Si", (0.25, 0.25, 0.25)),
            ],
            kpoints=KPoints(mode="automatic", grid=(4, 4, 4)),
        )

        content = builder.build_pw_input(pw_input)

        assert "calculation = 'relax'" in content
        assert "&IONS" in content
        assert "ion_dynamics = 'bfgs'" in content

    def test_vc_relax_includes_cell(self):
        builder = InputBuilder()

        pw_input = PWInput(
            calculation="vc-relax",
            prefix="test",
            ecutwfc=40.0,
            ion_dynamics="bfgs",
            cell_dynamics="bfgs",
            press=0.0,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[
                Atom("Si", (0.0, 0.0, 0.0)),
                Atom("Si", (0.25, 0.25, 0.25)),
            ],
            kpoints=KPoints(mode="automatic", grid=(4, 4, 4)),
        )

        content = builder.build_pw_input(pw_input)

        assert "calculation = 'vc-relax'" in content
        assert "&IONS" in content
        assert "&CELL" in content
        assert "cell_dynamics = 'bfgs'" in content


class TestKPointModes:
    """Test various k-point specifications."""

    def test_gamma_kpoints(self):
        builder = InputBuilder()
        pw_input = PWInput(
            ecutwfc=30.0,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[Atom("Si", (0.0, 0.0, 0.0))],
            kpoints=KPoints(mode="gamma"),
        )
        content = builder.build_pw_input(pw_input)
        assert "K_POINTS {gamma}" in content

    def test_automatic_kpoints(self):
        builder = InputBuilder()
        pw_input = PWInput(
            ecutwfc=30.0,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[Atom("Si", (0.0, 0.0, 0.0))],
            kpoints=KPoints(mode="automatic", grid=(8, 8, 8), shift=(1, 1, 1)),
        )
        content = builder.build_pw_input(pw_input)
        assert "K_POINTS {automatic}" in content
        assert "8 8 8" in content
        assert "1 1 1" in content

    def test_crystal_b_kpoints(self):
        builder = InputBuilder()
        pw_input = PWInput(
            ecutwfc=30.0,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[Atom("Si", (0.0, 0.0, 0.0))],
            kpoints=KPoints(
                mode="crystal_b",
                points=[
                    (0.0, 0.0, 0.0, 20),
                    (0.5, 0.0, 0.5, 20),
                    (0.5, 0.25, 0.75, 20),
                ],
                labels=["Gamma", "X", "W"],
            ),
        )
        content = builder.build_pw_input(pw_input)
        assert "K_POINTS {crystal_b}" in content
        assert "3" in content
        assert "! Gamma" in content
        assert "! X" in content
        assert "! W" in content


class TestCellParameters:
    """Test cell parameter handling."""

    def test_ibrav_0_with_cell(self):
        builder = InputBuilder()
        cell = CellParameters(
            vectors=np.array([
                [0.0, 2.715, 2.715],
                [2.715, 0.0, 2.715],
                [2.715, 2.715, 0.0],
            ]),
            units="angstrom",
        )

        pw_input = PWInput(
            ecutwfc=30.0,
            ibrav=0,
            cell=cell,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[Atom("Si", (0.0, 0.0, 0.0))],
            kpoints=KPoints(mode="gamma"),
        )

        content = builder.build_pw_input(pw_input)
        assert "CELL_PARAMETERS {angstrom}" in content
        assert "2.7150000000" in content


class TestHubbardU:
    """Test DFT+U input generation."""

    def test_hubbard_u_card(self):
        builder = InputBuilder()
        pw_input = PWInput(
            ecutwfc=40.0,
            lda_plus_u=True,
            hubbard_u={"Fe": 4.0, "Mn": 3.5},
            species=[
                AtomicSpecies("Fe", 55.845, "Fe.upf"),
                AtomicSpecies("Mn", 54.938, "Mn.upf"),
            ],
            atoms=[
                Atom("Fe", (0.0, 0.0, 0.0)),
                Atom("Mn", (0.5, 0.5, 0.5)),
            ],
            kpoints=KPoints(mode="gamma"),
        )

        content = builder.build_pw_input(pw_input)
        assert "lda_plus_u = .true." in content
        assert "HUBBARD" in content
        assert "U Fe-3d 4.0" in content


class TestSiliconExample:
    """Test the built-in Silicon example."""

    def test_example_creation(self):
        si = create_silicon_scf_example()
        assert si is not None
        assert si.calculation == "scf"
        assert si.prefix == "silicon"
        assert si.ecutwfc == 40.0
        assert len(si.species) == 1
        assert si.species[0].symbol == "Si"
        assert len(si.atoms) == 2

    def test_example_build(self):
        si = create_silicon_scf_example()
        builder = InputBuilder()
        content = builder.build_pw_input(si)

        assert "&CONTROL" in content
        assert "&SYSTEM" in content
        assert "&ELECTRONS" in content
        assert "ATOMIC_SPECIES" in content
        assert "ATOMIC_POSITIONS" in content
        assert "K_POINTS" in content
        assert "CELL_PARAMETERS" in content
        assert "ecutwfc = 40.0" in content


class TestAtomConstraints:
    """Test atomic position constraints."""

    def test_constrained_atom(self):
        builder = InputBuilder()
        pw_input = PWInput(
            calculation="relax",
            ecutwfc=30.0,
            ion_dynamics="bfgs",
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[
                Atom("Si", (0.0, 0.0, 0.0), if_pos=(0, 0, 0)),  # Fixed
                Atom("Si", (0.25, 0.25, 0.25)),  # Free
            ],
            kpoints=KPoints(mode="gamma"),
        )

        content = builder.build_pw_input(pw_input)
        assert "0 0 0" in content  # Constraint flags


class TestFileWriter:
    """Test file writing capability."""

    def test_write_file(self, tmp_path):
        builder = InputBuilder()
        content = "Test content"
        filepath = tmp_path / "test_input.in"

        builder.write_file(filepath, content)

        assert filepath.exists()
        assert filepath.read_text() == content

    def test_write_creates_directory(self, tmp_path):
        builder = InputBuilder()
        content = "Test content"
        filepath = tmp_path / "subdir" / "test_input.in"

        builder.write_file(filepath, content)

        assert filepath.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
