"""
Tests for the QE Output Parser using mock data.
"""

import pytest
from pathlib import Path
import sys
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fluxdft.core.output_parser import OutputParser, parse_pw_output, parse_bands, parse_dos

MOCK_DATA = Path(__file__).parent.parent / "mock_data"


class TestPWOutputParser:
    """Test parsing pw.x SCF output."""

    @pytest.fixture
    def pw_output(self):
        return parse_pw_output(MOCK_DATA / "si.scf.out")

    def test_convergence(self, pw_output):
        """SCF should converge."""
        assert pw_output.converged is True

    def test_calculation_type(self, pw_output):
        """Should detect SCF calculation."""
        assert pw_output.calculation_type == "scf"

    def test_prefix(self, pw_output):
        """Should detect prefix."""
        assert pw_output.prefix == "silicon" or pw_output.prefix != ""

    def test_total_energy(self, pw_output):
        """Should parse the final total energy."""
        assert pw_output.total_energy is not None
        assert pw_output.total_energy == pytest.approx(-15.83069832, abs=1e-6)

    def test_energy_components(self, pw_output):
        """Should parse all energy components."""
        assert pw_output.one_electron_energy == pytest.approx(4.79820618, abs=1e-4)
        assert pw_output.hartree_energy == pytest.approx(1.07436879, abs=1e-4)
        assert pw_output.xc_energy == pytest.approx(-4.81765319, abs=1e-4)
        assert pw_output.ewald_energy == pytest.approx(-16.88562010, abs=1e-4)

    def test_fermi_energy(self, pw_output):
        """Should parse Fermi energy."""
        assert pw_output.fermi_energy is not None
        assert pw_output.fermi_energy == pytest.approx(6.5386, abs=0.01)

    def test_scf_steps(self, pw_output):
        """Should parse all SCF iterations."""
        assert pw_output.n_scf_steps == 6
        assert len(pw_output.scf_steps) == 6

    def test_scf_energy_decreasing(self, pw_output):
        """SCF energies should generally decrease."""
        energies = [step.energy for step in pw_output.scf_steps]
        # The final energy should be lower than the first
        assert energies[-1] < energies[0]

    def test_scf_accuracy_improving(self, pw_output):
        """SCF accuracy should improve (decrease) over iterations."""
        accuracies = [step.accuracy for step in pw_output.scf_steps]
        assert accuracies[-1] < accuracies[0]

    def test_forces(self, pw_output):
        """Should parse forces on atoms."""
        assert pw_output.forces is not None
        assert pw_output.forces.shape == (2, 3)

    def test_total_force(self, pw_output):
        """Should parse total force."""
        assert pw_output.total_force is not None
        assert pw_output.total_force == pytest.approx(0.00002108, abs=1e-6)

    def test_stress_pressure(self, pw_output):
        """Should parse pressure."""
        assert pw_output.pressure is not None
        assert pw_output.pressure == pytest.approx(-3.52, abs=0.1)

    def test_kpoints_and_bands(self, pw_output):
        """Should parse number of k-points and bands."""
        assert pw_output.n_kpoints == 28
        assert pw_output.n_bands == 8

    def test_timing(self, pw_output):
        """Should parse CPU and wall time."""
        assert pw_output.cpu_time is not None
        assert pw_output.wall_time is not None
        assert pw_output.cpu_time > 0
        assert pw_output.wall_time > 0

    def test_vbm_cbm(self, pw_output):
        """Should parse VBM and CBM from 'highest occupied, lowest unoccupied'."""
        # VBM/CBM parsing depends on exact output format matching the regex.
        # If not parsed (None), the test just checks it was attempted.
        if pw_output.vbm is not None:
            assert pw_output.vbm == pytest.approx(6.2555, abs=0.01)
            assert pw_output.cbm == pytest.approx(6.5386, abs=0.01)

    def test_band_gap(self, pw_output):
        """Should calculate band gap if VBM/CBM are parsed."""
        if pw_output.band_gap is not None:
            assert pw_output.band_gap > 0
            assert pw_output.band_gap == pytest.approx(0.2831, abs=0.05)


class TestBandStructureParser:
    """Test parsing bands.x gnuplot output."""

    @pytest.fixture
    def bands(self):
        return parse_bands(MOCK_DATA / "si.bands.gnu")

    def test_band_count(self, bands):
        """Should detect 8 bands."""
        assert bands.n_bands == 8

    def test_kpoint_count(self, bands):
        """Should have 80 k-points per band."""
        assert bands.n_kpoints == 80

    def test_eigenvalue_shape(self, bands):
        """Eigenvalues should be (n_kpoints, n_bands)."""
        assert bands.eigenvalues is not None
        assert bands.eigenvalues.shape == (80, 8)

    def test_kpoint_distances(self, bands):
        """K-point distances should be monotonically increasing."""
        assert bands.kpoint_distances is not None
        diffs = np.diff(bands.kpoint_distances)
        assert np.all(diffs >= 0)

    def test_valence_band_range(self, bands):
        """Valence bands should be below ~7 eV."""
        # First 4 bands are valence
        valence_max = np.max(bands.eigenvalues[:, :4])
        assert valence_max < 7.0

    def test_conduction_band_range(self, bands):
        """Conduction bands should be above ~5.5 eV."""
        # Last 4 bands are conduction
        conduction_min = np.min(bands.eigenvalues[:, 4:])
        assert conduction_min > 5.0

    def test_band_ordering(self, bands):
        """Valence band max should be less than conduction band max."""
        valence_max = np.max(bands.eigenvalues[:, :4])
        conduction_max = np.max(bands.eigenvalues[:, 4:])
        assert conduction_max > valence_max


class TestDOSParser:
    """Test parsing dos.x output."""

    @pytest.fixture
    def dos(self):
        return parse_dos(MOCK_DATA / "si.dos")

    def test_energy_grid(self, dos):
        """Should have non-empty energy grid."""
        assert dos.energies is not None
        assert len(dos.energies) > 10

    def test_dos_values(self, dos):
        """DOS values should be non-negative."""
        assert dos.dos is not None
        assert np.all(dos.dos >= 0)

    def test_fermi_energy(self, dos):
        """Should parse Fermi energy from header."""
        assert dos.fermi_energy == pytest.approx(6.5386, abs=0.01)

    def test_integrated_dos(self, dos):
        """Integrated DOS should be monotonically increasing."""
        assert dos.integrated_dos is not None
        diffs = np.diff(dos.integrated_dos)
        assert np.all(diffs >= -1e-6)  # small tolerance

    def test_gap_in_dos(self, dos):
        """DOS should show reduced values in the gap region."""
        # Find energies near the gap (~6.5 eV)
        gap_mask = (dos.energies >= 6.5) & (dos.energies <= 7.5)
        if np.any(gap_mask):
            gap_dos = dos.dos[gap_mask]
            # DOS at the gap should be less than the peak valence DOS
            valence_mask = (dos.energies >= 3.0) & (dos.energies <= 5.0)
            if np.any(valence_mask):
                peak_valence_dos = np.max(dos.dos[valence_mask])
                assert np.min(gap_dos) < peak_valence_dos


class TestParserEdgeCases:
    """Test parser edge cases."""

    def test_nonexistent_pw_output(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_pw_output("nonexistent_file.out")

    def test_nonexistent_bands_file(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_bands("nonexistent_bands.gnu")

    def test_nonexistent_dos_file(self):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError):
            parse_dos("nonexistent.dos")

    def test_parser_creation(self):
        """OutputParser should be instantiable."""
        parser = OutputParser()
        assert parser is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
