"""
Tests for the DEF parser and input builder.
"""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from qe_gui.core.def_parser import DEFParser, parse_def_file
from qe_gui.core.input_builder import InputBuilder, PWInput, AtomicSpecies, Atom, KPoints


class TestDEFParser:
    """Test the DEF file parser."""
    
    def test_parser_creation(self):
        """Test that parser can be created."""
        parser = DEFParser()
        assert parser is not None
    
    def test_parse_simple_def(self):
        """Test parsing a simple DEF content."""
        content = '''
        input_description -distribution {Quantum ESPRESSO} -package PWscf -program pw.x {
            namelist CONTROL {
                var calculation -type CHARACTER {
                    default { 'scf' }
                    info { Type of calculation }
                }
            }
        }
        '''
        
        parser = DEFParser()
        schema = parser.parse_string(content)
        
        assert schema.program == "pw.x"
        assert schema.package == "PWscf"
        assert "CONTROL" in schema.namelists
        assert "calculation" in schema.namelists["CONTROL"].variables


class TestInputBuilder:
    """Test the input file builder."""
    
    def test_builder_creation(self):
        """Test that builder can be created."""
        builder = InputBuilder()
        assert builder is not None
    
    def test_format_values(self):
        """Test value formatting for Fortran input."""
        builder = InputBuilder()
        
        assert builder._format_value(True) == ".true."
        assert builder._format_value(False) == ".false."
        assert builder._format_value("scf") == "'scf'"
        assert builder._format_value(42) == "42"
        assert builder._format_value(3.14) == "3.14"
    
    def test_build_simple_input(self):
        """Test building a simple pw.x input."""
        builder = InputBuilder()
        
        pw_input = PWInput(
            calculation="scf",
            prefix="test",
            ecutwfc=40.0,
            species=[AtomicSpecies("Si", 28.0855, "Si.upf")],
            atoms=[Atom("Si", (0.0, 0.0, 0.0))],
            kpoints=KPoints(mode="gamma"),
        )
        
        content = builder.build_pw_input(pw_input)
        
        assert "&CONTROL" in content
        assert "calculation = 'scf'" in content
        assert "&SYSTEM" in content
        assert "ecutwfc = 40.0" in content
        assert "ATOMIC_SPECIES" in content
        assert "Si" in content
        assert "K_POINTS {gamma}" in content
    
    def test_build_bands_input(self):
        """Test building a bands.x input."""
        builder = InputBuilder()
        
        content = builder.build_bands_input(
            prefix="silicon",
            outdir="./tmp",
            filband="bands.out",
        )
        
        assert "&BANDS" in content
        assert "prefix = 'silicon'" in content
        assert "filband = 'bands.out'" in content
    
    def test_build_dos_input(self):
        """Test building a dos.x input."""
        builder = InputBuilder()
        
        content = builder.build_dos_input(
            prefix="silicon",
            Emin=-10.0,
            Emax=10.0,
            DeltaE=0.01,
        )
        
        assert "&DOS" in content
        assert "prefix = 'silicon'" in content
        assert "Emin = -10.0" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
