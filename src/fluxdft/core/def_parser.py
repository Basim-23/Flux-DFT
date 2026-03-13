"""
DEF File Parser for Quantum ESPRESSO.

Parses .def files (INPUT_PW.def, INPUT_BANDS.def, etc.) to extract
the schema for each QE executable's input parameters.

The .def format is a custom DSL used by QE for documentation and
input validation. This parser extracts:
- Namelists and their variables
- Variable types, defaults, and options
- Documentation/help text
- Conditional visibility rules
"""

import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple


@dataclass
class Variable:
    """Represents a single input variable in a QE namelist."""
    name: str
    var_type: str  # CHARACTER, INTEGER, REAL, LOGICAL
    default: Optional[str] = None
    options: List[str] = field(default_factory=list)
    info: str = ""
    status: str = ""  # REQUIRED, optional, etc.
    see: List[str] = field(default_factory=list)
    dimension: Optional[Tuple[int, int]] = None  # For array variables


@dataclass
class Namelist:
    """Represents a namelist block (e.g., &CONTROL, &SYSTEM)."""
    name: str
    variables: Dict[str, Variable] = field(default_factory=dict)
    groups: List[Dict] = field(default_factory=list)


@dataclass
class Card:
    """Represents a card block (e.g., ATOMIC_SPECIES, K_POINTS)."""
    name: str
    options: List[str] = field(default_factory=list)
    info: str = ""
    syntax: str = ""


@dataclass
class InputSchema:
    """Complete schema for a QE executable's input file."""
    program: str
    package: str
    distribution: str
    intro: str = ""
    namelists: Dict[str, Namelist] = field(default_factory=dict)
    cards: Dict[str, Card] = field(default_factory=dict)


class DEFParser:
    """
    Parser for Quantum ESPRESSO .def input definition files.
    
    Usage:
        parser = DEFParser()
        schema = parser.parse_file("/path/to/INPUT_PW.def")
        
        # Access namelist variables
        for var_name, var in schema.namelists["CONTROL"].variables.items():
            print(f"{var_name}: {var.var_type} = {var.default}")
    """
    
    def __init__(self):
        self.content = ""
        self.pos = 0
        self.schemas: Dict[str, InputSchema] = {}
    
    def parse_file(self, filepath: str | Path) -> InputSchema:
        """Parse a .def file and return the input schema."""
        filepath = Path(filepath)
        
        if not filepath.exists():
            raise FileNotFoundError(f"DEF file not found: {filepath}")
        
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            self.content = f.read()
        
        self.pos = 0
        return self._parse_input_description()
    
    def parse_string(self, content: str) -> InputSchema:
        """Parse DEF content from a string."""
        self.content = content
        self.pos = 0
        return self._parse_input_description()
    
    def _skip_whitespace(self) -> None:
        """Skip whitespace and comments."""
        while self.pos < len(self.content):
            # Skip whitespace
            if self.content[self.pos].isspace():
                self.pos += 1
                continue
            # Skip comments (# at start of line)
            if self.content[self.pos] == '#':
                while self.pos < len(self.content) and self.content[self.pos] != '\n':
                    self.pos += 1
                continue
            break
    
    def _read_until(self, char: str) -> str:
        """Read content until the specified character."""
        start = self.pos
        depth = 0
        
        while self.pos < len(self.content):
            c = self.content[self.pos]
            
            if c == '{':
                depth += 1
            elif c == '}':
                if depth == 0:
                    break
                depth -= 1
            elif c == char and depth == 0:
                break
            
            self.pos += 1
        
        return self.content[start:self.pos]
    
    def _read_braced_content(self) -> str:
        """Read content between { and }."""
        self._skip_whitespace()
        
        if self.pos >= len(self.content) or self.content[self.pos] != '{':
            return ""
        
        self.pos += 1  # Skip opening brace
        start = self.pos
        depth = 1
        
        while self.pos < len(self.content) and depth > 0:
            if self.content[self.pos] == '{':
                depth += 1
            elif self.content[self.pos] == '}':
                depth -= 1
            self.pos += 1
        
        return self.content[start:self.pos - 1].strip()
    
    def _read_word(self) -> str:
        """Read the next word (identifier)."""
        self._skip_whitespace()
        start = self.pos
        
        while self.pos < len(self.content) and (
            self.content[self.pos].isalnum() or self.content[self.pos] in "_-"
        ):
            self.pos += 1
        
        return self.content[start:self.pos]
    
    def _parse_input_description(self) -> InputSchema:
        """Parse the top-level input_description block."""
        schema = InputSchema(program="", package="", distribution="")
        
        self._skip_whitespace()
        
        # Find input_description
        match = re.search(r'input_description\s+', self.content[self.pos:])
        if not match:
            return schema
        
        self.pos += match.end()
        
        # Parse attributes
        attrs = self._parse_attributes()
        schema.distribution = attrs.get("-distribution", "")
        schema.package = attrs.get("-package", "")
        schema.program = attrs.get("-program", "")
        
        # Parse body
        body = self._read_braced_content()
        
        # Parse the body content
        self._parse_body(body, schema)
        
        return schema
    
    def _parse_attributes(self) -> Dict[str, str]:
        """Parse key-value attributes like -distribution {Quantum ESPRESSO}."""
        attrs = {}
        
        while True:
            self._skip_whitespace()
            
            if self.pos >= len(self.content):
                break
            
            if self.content[self.pos] == '{':
                break
            
            if self.content[self.pos] == '-':
                # Read attribute name
                start = self.pos
                while self.pos < len(self.content) and not self.content[self.pos].isspace() and self.content[self.pos] != '{':
                    self.pos += 1
                key = self.content[start:self.pos]
                
                # Read attribute value
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    value = self._read_braced_content()
                    attrs[key] = value
            else:
                break
        
        return attrs
    
    def _parse_body(self, body: str, schema: InputSchema) -> None:
        """Parse the body of input_description."""
        # Save current state
        old_content, old_pos = self.content, self.pos
        self.content = body
        self.pos = 0
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            if self.pos >= len(self.content):
                break
            
            word = self._read_word()
            
            if word == "namelist":
                self._parse_namelist(schema)
            elif word == "card":
                self._parse_card(schema)
            elif word == "intro":
                schema.intro = self._read_braced_content()
            elif word == "toc":
                self._read_braced_content()  # Skip table of contents
            elif word == "section":
                self._skip_section()
            elif word:
                # Skip unknown content
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    self._read_braced_content()
        
        # Restore state
        self.content, self.pos = old_content, old_pos
    
    def _parse_namelist(self, schema: InputSchema) -> None:
        """Parse a namelist block."""
        name = self._read_word()
        body = self._read_braced_content()
        
        namelist = Namelist(name=name)
        
        # Parse namelist body
        old_content, old_pos = self.content, self.pos
        self.content = body
        self.pos = 0
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            if self.pos >= len(self.content):
                break
            
            word = self._read_word()
            
            if word == "var":
                var = self._parse_variable()
                if var:
                    namelist.variables[var.name] = var
            elif word == "vargroup":
                vars_list = self._parse_vargroup()
                for var in vars_list:
                    namelist.variables[var.name] = var
            elif word == "dimension":
                var = self._parse_dimension()
                if var:
                    namelist.variables[var.name] = var
            elif word == "group":
                self._read_braced_content()  # Skip group for now
            elif word:
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    self._read_braced_content()
        
        self.content, self.pos = old_content, old_pos
        schema.namelists[name] = namelist
    
    def _parse_variable(self) -> Optional[Variable]:
        """Parse a var block."""
        name = self._read_word()
        attrs = self._parse_attributes()
        body = self._read_braced_content()
        
        var_type = attrs.get("-type", "CHARACTER")
        
        var = Variable(name=name, var_type=var_type)
        
        # Parse variable body for default, options, info
        self._parse_var_body(body, var)
        
        return var
    
    def _parse_var_body(self, body: str, var: Variable) -> None:
        """Parse the body of a variable definition."""
        old_content, old_pos = self.content, self.pos
        self.content = body
        self.pos = 0
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            if self.pos >= len(self.content):
                break
            
            word = self._read_word()
            
            if word == "default":
                var.default = self._read_braced_content()
            elif word == "info":
                var.info = self._read_braced_content()
            elif word == "options":
                self._parse_options(var)
            elif word == "status":
                var.status = self._read_braced_content()
            elif word == "see":
                var.see = self._read_braced_content().split(",")
            elif word:
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    self._read_braced_content()
        
        self.content, self.pos = old_content, old_pos
    
    def _parse_options(self, var: Variable) -> None:
        """Parse options block for a variable."""
        body = self._read_braced_content()
        
        # Extract option values
        opt_pattern = re.compile(r"opt\s+-val\s+['\"]?([^'\"}\s]+)['\"]?")
        for match in opt_pattern.finditer(body):
            var.options.append(match.group(1))
    
    def _parse_vargroup(self) -> List[Variable]:
        """Parse a vargroup block (multiple related variables)."""
        attrs = self._parse_attributes()
        body = self._read_braced_content()
        
        var_type = attrs.get("-type", "CHARACTER")
        variables = []
        
        # Extract variable names from body
        old_content, old_pos = self.content, self.pos
        self.content = body
        self.pos = 0
        
        info = ""
        while self.pos < len(self.content):
            self._skip_whitespace()
            if self.pos >= len(self.content):
                break
            
            word = self._read_word()
            
            if word == "var":
                name = self._read_word()
                variables.append(Variable(name=name, var_type=var_type))
            elif word == "info":
                info = self._read_braced_content()
            elif word:
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    self._read_braced_content()
        
        # Apply shared info to all variables
        for var in variables:
            var.info = info
        
        self.content, self.pos = old_content, old_pos
        return variables
    
    def _parse_dimension(self) -> Optional[Variable]:
        """Parse a dimension block (array variable)."""
        name = self._read_word()
        attrs = self._parse_attributes()
        body = self._read_braced_content()
        
        var_type = attrs.get("-type", "REAL")
        start = int(attrs.get("-start", "1"))
        end = attrs.get("-end", "1")
        
        # Handle variable end like 'ntyp'
        try:
            end = int(end)
        except ValueError:
            end = None
        
        var = Variable(
            name=name,
            var_type=var_type,
            dimension=(start, end)
        )
        
        self._parse_var_body(body, var)
        return var
    
    def _parse_card(self, schema: InputSchema) -> None:
        """Parse a card block."""
        attrs = self._parse_attributes()
        body = self._read_braced_content()
        
        name = attrs.get("-name", "").upper()
        if not name:
            return
        
        options = []
        flag = attrs.get("-flag", "")
        if flag:
            options = [opt.strip() for opt in flag.split("|")]
        
        card = Card(name=name, options=options)
        
        # Parse card body for syntax and info
        old_content, old_pos = self.content, self.pos
        self.content = body
        self.pos = 0
        
        while self.pos < len(self.content):
            self._skip_whitespace()
            if self.pos >= len(self.content):
                break
            
            word = self._read_word()
            
            if word == "syntax":
                card.syntax = self._read_braced_content()
            elif word == "info":
                card.info = self._read_braced_content()
            elif word:
                self._skip_whitespace()
                if self.pos < len(self.content) and self.content[self.pos] == '{':
                    self._read_braced_content()
        
        self.content, self.pos = old_content, old_pos
        schema.cards[name] = card
    
    def _skip_section(self) -> None:
        """Skip a section block."""
        self._parse_attributes()
        self._read_braced_content()
    
    def load_all_schemas(self, qe_root: str | Path) -> Dict[str, InputSchema]:
        """
        Load all .def schemas from a QE installation.
        
        Args:
            qe_root: Path to QE root directory (e.g., /usr/local/share/quantum-espresso)
        
        Returns:
            Dictionary mapping program names to their schemas
        """
        qe_root = Path(qe_root)
        schemas = {}
        
        # Known locations for .def files
        def_locations = [
            qe_root / "PW" / "Doc",
            qe_root / "PP" / "Doc",
            qe_root / "PHonon" / "Doc",
            qe_root / "CPV" / "Doc",
            qe_root / "atomic" / "Doc",
            qe_root / "NEB" / "Doc",
            qe_root / "TDDFPT" / "Doc",
        ]
        
        for location in def_locations:
            if not location.exists():
                continue
            
            for def_file in location.glob("INPUT_*.def"):
                try:
                    schema = self.parse_file(def_file)
                    if schema.program:
                        schemas[schema.program] = schema
                except Exception as e:
                    print(f"Warning: Could not parse {def_file}: {e}")
        
        self.schemas = schemas
        return schemas
    
    def get_schema(self, program: str) -> Optional[InputSchema]:
        """Get schema for a specific program."""
        return self.schemas.get(program)


# Convenience function
def parse_def_file(filepath: str | Path) -> InputSchema:
    """Parse a DEF file and return its schema."""
    parser = DEFParser()
    return parser.parse_file(filepath)
