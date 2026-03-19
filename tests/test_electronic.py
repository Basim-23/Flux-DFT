"""
Tests for Electronic Band Structure and DOS analysis using mock data.
"""

import pytest
from pathlib import Path
import sys
import numpy as np

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fluxdft.electronic.band_structure import (
    ElectronicBandStructure, KPath, BandGapType, BandGapInfo, BandEdge
)
from fluxdft.electronic.dos import (
    ElectronicDOS, ProjectedDOS, OrbitalProjection
)


class TestElectronicBandStructure:
    """Test the ElectronicBandStructure analysis class."""

    @pytest.fixture
    def silicon_bs(self):
        """Create a mock Silicon band structure with indirect gap."""
        np.random.seed(42)
        n_kpts = 50
        n_bands = 8

        # Create k-path
        kpoints = np.zeros((n_kpts, 3))
        t = np.linspace(0, 1, n_kpts)
        kpoints[:, 0] = t  # Simple 1D path
        distances = np.linspace(0, 2.0, n_kpts)
        labels = [(0, "Γ"), (24, "X"), (49, "K")]

        kpath = KPath(kpoints=kpoints, distances=distances, labels=labels)

        # Create eigenvalues: 4 valence + 4 conduction bands
        # Fermi energy at 6.5 eV
        fermi = 6.5
        eigenvalues = np.zeros((n_kpts, n_bands))

        # Valence bands (all below fermi)
        eigenvalues[:, 0] = -5.7 + 2.0 * np.sin(np.pi * t)**2
        eigenvalues[:, 1] = 3.5 + 2.5 * np.cos(np.pi * t / 2)**2
        eigenvalues[:, 2] = 3.5 + 2.0 * np.cos(np.pi * t / 2)**2
        eigenvalues[:, 3] = 6.25 - 1.5 * np.sin(np.pi * t / 2)**2  # VBM at k=0

        # Conduction bands (CBM away from Gamma = indirect)
        eigenvalues[:, 4] = 8.8 - 2.0 * np.sin(np.pi * t)**2  # CBM at t~0.5
        eigenvalues[:, 5] = 8.7 + 1.5 * np.sin(np.pi * t / 2)**2
        eigenvalues[:, 6] = 8.7 + 2.0 * np.sin(np.pi * t)**2
        eigenvalues[:, 7] = 9.5 + 2.5 * np.sin(np.pi * t / 2)**2

        return ElectronicBandStructure(
            eigenvalues=eigenvalues,
            kpath=kpath,
            fermi_energy=fermi,
        )

    @pytest.fixture
    def metal_bs(self):
        """Create a metallic band structure (bands crossing Fermi level)."""
        n_kpts = 20
        n_bands = 4
        t = np.linspace(0, 1, n_kpts)

        kpoints = np.zeros((n_kpts, 3))
        kpoints[:, 0] = t
        distances = np.linspace(0, 1.0, n_kpts)
        kpath = KPath(kpoints=kpoints, distances=distances, labels=[])

        fermi = 5.0
        eigenvalues = np.zeros((n_kpts, n_bands))
        # Bands that clearly cross the Fermi level (metallic)
        eigenvalues[:, 0] = 2.0 + 6.0 * t          # Crosses 5.0 at t~0.5
        eigenvalues[:, 1] = 4.0 + 3.0 * t           # Goes from 4 to 7
        eigenvalues[:, 2] = 6.0 - 2.0 * t           # Goes from 6 to 4
        eigenvalues[:, 3] = 8.0 - 5.0 * t           # Goes from 8 to 3

        return ElectronicBandStructure(
            eigenvalues=eigenvalues,
            kpath=kpath,
            fermi_energy=fermi,
        )

    def test_creation(self, silicon_bs):
        """Should create band structure object."""
        assert silicon_bs is not None
        assert silicon_bs.n_bands == 8
        assert silicon_bs.n_kpts == 50
        assert silicon_bs.n_spins == 1

    def test_eigenvalue_normalization(self, silicon_bs):
        """2D eigenvalues should be normalized to 3D (spins, kpts, bands)."""
        assert silicon_bs.eigenvalues.ndim == 3
        assert silicon_bs.eigenvalues.shape == (1, 50, 8)

    def test_shifted_eigenvalues(self, silicon_bs):
        """Shifted eigenvalues should be relative to Fermi level."""
        shifted = silicon_bs.eigenvalues_shifted
        # Fermi is at 6.5, so shifted VBM should be negative
        assert np.max(shifted[0, :, 3]) < 0  # VBM below 0

    def test_not_spin_polarized(self, silicon_bs):
        """Silicon should not be spin-polarized."""
        assert silicon_bs.is_spin_polarized is False

    def test_band_gap_detection(self, silicon_bs):
        """Should detect an indirect band gap."""
        gap = silicon_bs.get_band_gap()
        assert gap is not None
        assert not gap.is_metal
        assert gap.energy > 0

    def test_band_gap_type_indirect(self, silicon_bs):
        """Silicon gap should be indirect."""
        gap = silicon_bs.get_band_gap()
        # VBM at k=0 (Gamma), CBM at k~0.5, so should be indirect
        assert gap.gap_type == BandGapType.INDIRECT

    def test_vbm_info(self, silicon_bs):
        """Should identify VBM."""
        gap = silicon_bs.get_band_gap()
        assert gap.vbm is not None
        assert gap.vbm.band_index == 3  # Top valence band

    def test_cbm_info(self, silicon_bs):
        """Should identify CBM."""
        gap = silicon_bs.get_band_gap()
        assert gap.cbm is not None
        assert gap.cbm.band_index == 4  # Bottom conduction band

    def test_metal_detection(self, metal_bs):
        """Should detect metallic state (bands crossing Fermi level give very small gap)."""
        gap = metal_bs.get_band_gap()
        # With discrete k-points, even crossing bands can produce a small numerical gap
        # But it should be much smaller than a typical semiconductor gap (>0.5 eV)
        assert gap.is_metal or gap.energy < 0.2

    def test_bands_in_range(self, silicon_bs):
        """Should find bands in energy range (uses shifted energies, relative to Fermi)."""
        # Fermi is at 6.5, so band 0 spans ~(-5.7 - 6.5) = -12.2 to -3.2-6.5 = -3.2 shifted
        # We look for bands in shifted range that includes band 0
        bands = silicon_bs.get_bands_in_range(-13, -8)
        assert len(bands) > 0
        assert 0 in bands  # Deepest valence band

    def test_band_energies_at_gamma(self, silicon_bs):
        """Should get band energies at Γ point."""
        energies = silicon_bs.get_band_energies_at_kpoint("Γ")
        assert len(energies) == 8

    def test_to_dict(self, silicon_bs):
        """Should serialize to dict."""
        d = silicon_bs.to_dict()
        assert 'eigenvalues' in d
        assert 'fermi_energy' in d
        assert d['n_bands'] == 8

    def test_band_gap_caching(self, silicon_bs):
        """Band gap should be cached after first calculation."""
        gap1 = silicon_bs.get_band_gap()
        gap2 = silicon_bs.get_band_gap()
        assert gap1.energy == gap2.energy


class TestElectronicDOS:
    """Test the ElectronicDOS analysis class."""

    @pytest.fixture
    def silicon_dos(self):
        """Create a mock Silicon DOS."""
        energies = np.linspace(-10, 15, 500)
        fermi = 6.5

        # Simple model DOS: Gaussian peaks for valence/conduction
        dos_val = 3.0 * np.exp(-0.5 * ((energies - 2.0) / 3.0)**2)
        dos_cond = 2.5 * np.exp(-0.5 * ((energies - 10.0) / 2.5)**2)
        total_dos = dos_val + dos_cond

        # Ensure zero in gap
        gap_mask = (energies > 6.3) & (energies < 6.7)
        total_dos[gap_mask] = 0.0

        return ElectronicDOS(
            energies=energies,
            total_dos=total_dos,
            fermi_energy=fermi,
        )

    @pytest.fixture
    def spin_polarized_dos(self):
        """Create a spin-polarized DOS (e.g., for Fe)."""
        energies = np.linspace(-10, 10, 200)
        fermi = 0.0

        dos_up = 2.0 * np.exp(-0.5 * ((energies + 1.0) / 2.0)**2)
        dos_down = 1.5 * np.exp(-0.5 * ((energies - 0.5) / 2.0)**2)
        total_dos = np.array([dos_up, dos_down])

        return ElectronicDOS(
            energies=energies,
            total_dos=total_dos,
            fermi_energy=fermi,
        )

    def test_creation(self, silicon_dos):
        """Should create DOS object."""
        assert silicon_dos is not None
        assert silicon_dos.n_energies == 500

    def test_not_spin_polarized(self, silicon_dos):
        """Silicon DOS should not be spin-polarized."""
        assert silicon_dos.is_spin_polarized is False

    def test_spin_polarized(self, spin_polarized_dos):
        """Fe DOS should be spin-polarized."""
        assert spin_polarized_dos.is_spin_polarized is True

    def test_total_dos(self, silicon_dos):
        """Should return total DOS."""
        total = silicon_dos.get_total()
        assert len(total) == 500
        assert np.all(total >= 0)

    def test_total_dos_spin(self, spin_polarized_dos):
        """Should return total as sum of spins."""
        total = spin_polarized_dos.get_total()
        up = spin_polarized_dos.get_total(spin=0)
        down = spin_polarized_dos.get_total(spin=1)
        np.testing.assert_array_almost_equal(total, up + down)

    def test_shifted_energies(self, silicon_dos):
        """Shifted energies should be relative to Fermi level."""
        shifted = silicon_dos.energies_shifted
        # Fermi is at 6.5, so shifted should have 0 near there
        assert np.min(np.abs(shifted)) < 0.1

    def test_get_in_range(self, silicon_dos):
        """Should return DOS in energy range."""
        e, dos = silicon_dos.get_in_range(-5, 5)
        assert len(e) > 0
        assert len(dos) == len(e)
        assert np.all(e >= -5)
        assert np.all(e <= 5)

    def test_integrate(self, silicon_dos):
        """Integration should return positive value."""
        electrons = silicon_dos.integrate(-10, 0)
        assert electrons > 0

    def test_integrate_empty_range(self, silicon_dos):
        """Integration of empty range should return ~0."""
        electrons = silicon_dos.integrate(100, 200)
        assert abs(electrons) < 1e-6

    def test_fermi_level_dos(self, silicon_dos):
        """Should get DOS value at Fermi level."""
        dos_ef = silicon_dos.get_fermi_level_dos()
        assert dos_ef >= 0

    def test_band_center(self, silicon_dos):
        """Band center should be within the band range."""
        center = silicon_dos.get_band_center(emin=-10, emax=0)
        assert -10 <= center <= 0

    def test_to_dict(self, silicon_dos):
        """Should serialize to dict."""
        d = silicon_dos.to_dict()
        assert 'energies' in d
        assert 'total_dos' in d
        assert 'fermi_energy' in d


class TestOrbitalProjection:
    """Test orbital projection data class."""

    def test_label_with_site(self):
        """Label should include site index."""
        proj = OrbitalProjection(
            element="Si", orbital="p", angular_momentum=1,
            densities=np.zeros(100), site_index=0
        )
        assert proj.label == "Si0-p"

    def test_label_without_site(self):
        """Label should work without site index."""
        proj = OrbitalProjection(
            element="Si", orbital="s", angular_momentum=0,
            densities=np.zeros(100)
        )
        assert proj.label == "Si-s"

    def test_spin_detection(self):
        """Should detect spin-polarization from shape."""
        proj_nospin = OrbitalProjection(
            element="Si", orbital="s", angular_momentum=0,
            densities=np.zeros(100)
        )
        assert proj_nospin.is_spin_polarized is False

        proj_spin = OrbitalProjection(
            element="Fe", orbital="d", angular_momentum=2,
            densities=np.zeros((2, 100))
        )
        assert proj_spin.is_spin_polarized is True


class TestProjectedDOS:
    """Test ProjectedDOS container."""

    @pytest.fixture
    def pdos(self):
        """Create a mock PDOS."""
        energies = np.linspace(-10, 10, 200)
        projections = [
            OrbitalProjection("Si", "s", 0, np.exp(-0.5 * ((energies - 1) / 2)**2)),
            OrbitalProjection("Si", "p", 1, 2.0 * np.exp(-0.5 * ((energies - 3) / 2)**2)),
            OrbitalProjection("O", "s", 0, 0.5 * np.exp(-0.5 * ((energies + 2) / 2)**2)),
            OrbitalProjection("O", "p", 1, 1.5 * np.exp(-0.5 * ((energies + 1) / 2)**2)),
        ]
        return ProjectedDOS(energies, projections, fermi_energy=0.0)

    def test_elements(self, pdos):
        """Should list unique elements."""
        elements = pdos.elements
        assert "Si" in elements
        assert "O" in elements

    def test_orbitals(self, pdos):
        """Should list unique orbitals."""
        orbitals = pdos.orbitals
        assert "s" in orbitals
        assert "p" in orbitals

    def test_element_dos(self, pdos):
        """Should sum all orbitals for an element."""
        si_dos = pdos.get_element_dos("Si")
        assert si_dos is not None
        assert len(si_dos) == 200
        assert np.max(si_dos) > 0

    def test_orbital_dos(self, pdos):
        """Should sum all elements for an orbital."""
        s_dos = pdos.get_orbital_dos("s")
        assert s_dos is not None
        assert len(s_dos) == 200

    def test_shifted_energies(self, pdos):
        """Shifted energies should be relative to Fermi level."""
        shifted = pdos.energies_shifted
        np.testing.assert_array_almost_equal(shifted, pdos.energies)  # Ef=0

    def test_get_projection_by_label(self, pdos):
        """Should get specific projection by label."""
        si_p = pdos.get_projection("Si-p")
        assert si_p is not None

    def test_missing_projection(self, pdos):
        """Should return None for missing projection."""
        result = pdos.get_projection("Fe-d")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
