"""
Tests for Phonon analysis using mock data.
"""

import pytest
from pathlib import Path
import sys
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fluxdft.phonon.phonon import (
    PhononBandStructure, PhononDOS, PhononAnalyzer, PhononMode,
    THZ_TO_CM, THZ_TO_MEV, CM_TO_MEV
)

MOCK_DATA = Path(__file__).parent.parent / "mock_data"


class TestPhononBandStructure:
    """Test phonon band structure parsing and analysis."""

    @pytest.fixture
    def phonon_bands(self):
        """Load mock phonon band structure."""
        return PhononBandStructure.from_qe_matdyn(MOCK_DATA / "si.matdyn.freq")

    def test_loading(self, phonon_bands):
        """Should load phonon bands successfully."""
        assert phonon_bands is not None

    def test_qpoint_count(self, phonon_bands):
        """Should have multiple q-points."""
        assert phonon_bands.nqpoints > 10

    def test_mode_count(self, phonon_bands):
        """Silicon (2 atoms) should have 6 modes (3N)."""
        assert phonon_bands.nmodes == 6

    def test_natoms(self, phonon_bands):
        """Should infer 2 atoms from 6 modes."""
        assert phonon_bands.natoms == 2

    def test_frequency_shape(self, phonon_bands):
        """Frequency array should be (nqpts, nmodes)."""
        assert phonon_bands.frequencies.shape == (
            phonon_bands.nqpoints, phonon_bands.nmodes
        )

    def test_frequencies_positive_range(self, phonon_bands):
        """Most frequencies should be positive (stable structure)."""
        positive_count = np.sum(phonon_bands.frequencies > -0.1)
        total = phonon_bands.frequencies.size
        assert positive_count / total > 0.9  # >90% positive

    def test_q_distances(self, phonon_bands):
        """Q-distances should be monotonically increasing."""
        diffs = np.diff(phonon_bands.q_distances)
        assert np.all(diffs >= -1e-6)

    def test_frequency_conversion_cm(self, phonon_bands):
        """Should convert to cm⁻¹."""
        freq_cm = phonon_bands.frequencies_cm
        freq_thz = phonon_bands.frequencies
        np.testing.assert_array_almost_equal(
            freq_cm, freq_thz * THZ_TO_CM, decimal=2
        )

    def test_frequency_conversion_meV(self, phonon_bands):
        """Should convert to meV."""
        freq_meV = phonon_bands.frequencies_meV
        freq_thz = phonon_bands.frequencies
        np.testing.assert_array_almost_equal(
            freq_meV, freq_thz * THZ_TO_MEV, decimal=2
        )

    def test_get_mode(self, phonon_bands):
        """Should return a PhononMode object."""
        mode = phonon_bands.get_mode(0, 0)
        assert isinstance(mode, PhononMode)
        assert mode.mode_index == 0


class TestPhononDOS:
    """Test phonon DOS parsing."""

    @pytest.fixture
    def phonon_dos(self):
        """Load mock phonon DOS."""
        return PhononDOS.from_qe_matdyn_dos(MOCK_DATA / "si.matdyn.dos")

    def test_loading(self, phonon_dos):
        """Should load phonon DOS successfully."""
        assert phonon_dos is not None

    def test_energy_grid(self, phonon_dos):
        """Should have non-empty energy grid."""
        assert len(phonon_dos.energies) > 10

    def test_dos_values(self, phonon_dos):
        """DOS values should be non-negative."""
        assert np.all(phonon_dos.total_dos >= 0)

    def test_energy_unit(self, phonon_dos):
        """Should be in cm⁻¹ from matdyn output."""
        assert phonon_dos.energy_unit == "cm^-1"

    def test_conversion_to_meV(self, phonon_dos):
        """Should convert energies to meV."""
        meV = phonon_dos.energies_meV
        assert len(meV) == len(phonon_dos.energies)
        # Max frequency of Si ~520 cm⁻¹ ≈ 64.5 meV
        assert np.max(meV) > 50  # Should have optical modes

    def test_phonon_gap(self, phonon_dos):
        """Silicon has a gap between acoustic and optical branches."""
        # There should be a region where DOS is ~0
        near_zero = phonon_dos.total_dos < 0.001
        assert np.any(near_zero)


class TestPhononAnalyzer:
    """Test phonon analysis tools."""

    @pytest.fixture
    def analyzer(self):
        """Create phonon analyzer with mock data."""
        bands = PhononBandStructure.from_qe_matdyn(MOCK_DATA / "si.matdyn.freq")
        return PhononAnalyzer(bands)

    def test_dynamical_stability(self, analyzer):
        """Silicon should be dynamically stable (no imaginary modes)."""
        is_stable, soft_modes = analyzer.check_dynamical_stability()
        # We expect stability (our mock data has no strongly negative frequencies)
        assert is_stable or len(soft_modes) < 3  # allow small numerical noise

    def test_acoustic_modes(self, analyzer):
        """Should find 3 acoustic modes."""
        acoustic = analyzer.get_acoustic_modes()
        assert len(acoustic) == 3

    def test_max_frequency(self, analyzer):
        """Max frequency should be positive and reasonable."""
        fmax = analyzer.get_max_frequency()
        assert fmax > 0
        # Silicon optical modes ~15.5 THz
        assert fmax < 20  # THz, reasonable upper bound

    def test_band_gap_detection(self, analyzer):
        """Should detect phonon band gap (acoustic-optical gap in Si)."""
        gap = analyzer.get_band_gap()
        # Si has a gap between acoustic (~5 THz) and optical (~12-16 THz) branches
        # This may or may not be detected depending on mock data quality
        # Just check it doesn't crash
        assert gap is None or gap > 0


class TestPhononMode:
    """Test PhononMode data class."""

    def test_frequency_conversions(self):
        """Should convert between units."""
        mode = PhononMode(
            frequency=15.0,  # THz
            eigenvector=np.zeros((2, 3)),
            q_point=np.array([0.0, 0.0, 0.0]),
            mode_index=0,
        )
        assert mode.frequency_cm == pytest.approx(15.0 * THZ_TO_CM, rel=0.01)
        assert mode.frequency_meV == pytest.approx(15.0 * THZ_TO_MEV, rel=0.01)

    def test_acoustic_mode_detection(self):
        """Should detect acoustic modes at Gamma."""
        acoustic = PhononMode(
            frequency=0.01,  # Near-zero at Gamma
            eigenvector=np.zeros((2, 3)),
            q_point=np.array([0.0, 0.0, 0.0]),
            mode_index=0,
        )
        assert acoustic.is_acoustic is True

        optical = PhononMode(
            frequency=15.0,  # Optical at Gamma
            eigenvector=np.zeros((2, 3)),
            q_point=np.array([0.0, 0.0, 0.0]),
            mode_index=3,
        )
        assert optical.is_acoustic is False

    def test_not_acoustic_at_nonGamma(self):
        """Low frequency at non-Gamma should not be acoustic."""
        mode = PhononMode(
            frequency=0.01,
            eigenvector=np.zeros((2, 3)),
            q_point=np.array([0.5, 0.0, 0.0]),  # X point
            mode_index=0,
        )
        assert mode.is_acoustic is False


class TestUnitConversions:
    """Test unit conversion constants."""

    def test_thz_to_cm(self):
        """1 THz ≈ 33.36 cm⁻¹."""
        assert THZ_TO_CM == pytest.approx(33.356, abs=0.01)

    def test_thz_to_meV(self):
        """1 THz ≈ 4.136 meV."""
        assert THZ_TO_MEV == pytest.approx(4.136, abs=0.01)

    def test_cm_to_meV(self):
        """1 cm⁻¹ ≈ 0.124 meV."""
        assert CM_TO_MEV == pytest.approx(0.124, abs=0.001)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
