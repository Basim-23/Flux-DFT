"""
Intelligent QE Input Editor for FluxDFT.

Syntax-highlighted editor for Quantum ESPRESSO input files
with auto-completion, validation, and documentation tooltips.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from typing import Optional, Dict, List, Any
from pathlib import Path
import re
import logging

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit,
    QCompleter, QToolBar, QLabel, QComboBox, QPushButton,
    QFileDialog, QMessageBox, QListWidget, QSplitter,
    QGroupBox, QTextEdit, QListWidgetItem, QFrame,
    QSlider, QSpinBox, QDoubleSpinBox, QScrollArea, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QStringListModel, QRegularExpression, QSize
from PyQt6.QtGui import (
    QFont, QSyntaxHighlighter, QTextCharFormat, QColor,
    QTextCursor, QKeyEvent
)

logger = logging.getLogger(__name__)


# QE keyword documentation - Comprehensive Physics Reference
QE_KEYWORDS = {
    # ==================== CONTROL NAMELIST ====================
    'calculation': {
        'type': 'string',
        'values': ['scf', 'nscf', 'bands', 'relax', 'vc-relax', 'md', 'vc-md'],
        'doc': """Type of calculation to perform:
• scf: Self-consistent field (ground state energy)
• nscf: Non-self-consistent (for DOS, band structure)
• bands: Band structure along k-path
• relax: Ionic relaxation (fixed cell)
• vc-relax: Variable-cell relaxation (full optimization)
• md: Molecular dynamics (fixed cell)
• vc-md: Variable-cell molecular dynamics

For new materials: Start with 'scf', then 'relax', then 'vc-relax'.""",
    },
    'prefix': {
        'type': 'string',
        'doc': """Prefix for all output files (*.xml, *.wfc, etc.)
Default: 'pwscf'

Tip: Use descriptive name like 'Si_bulk' or 'MoS2_monolayer'
to easily identify output files.""",
    },
    'pseudo_dir': {
        'type': 'string',
        'doc': """Directory containing pseudopotential files (.UPF)
Example: './pseudo' or '/home/user/pseudopotentials'

Pseudopotentials define the effective potential of atomic cores.
SSSP library recommended for production calculations.""",
    },
    'outdir': {
        'type': 'string',
        'doc': """Directory for temporary/output files
Default: './' (current directory)

Contains: charge density, wavefunctions, restart data
Tip: Use fast local storage (SSD) for better performance.""",
    },
    'tprnfor': {
        'type': 'bool',
        'doc': """Print atomic forces in output
Default: .false. (auto .true. for relax/md)

Forces in Ry/Bohr (1 Ry/Bohr = 25.7 eV/Å)
Required for force-based analysis and visualization.""",
    },
    'tstress': {
        'type': 'bool',
        'doc': """Print stress tensor in output
Default: .false. (auto .true. for vc-relax)

Stress in kbar (1 GPa = 10 kbar)
Essential for pressure calculations and cell optimization.""",
    },
    'forc_conv_thr': {
        'type': 'float',
        'doc': """Force convergence threshold for ionic relaxation
Default: 1.0d-3 Ry/Bohr (≈ 0.026 eV/Å)

Recommended values:
• Coarse: 1.0d-3 (fast screening)
• Standard: 1.0d-4 (production)
• Tight: 1.0d-5 (phonons, elastic constants)""",
    },
    'etot_conv_thr': {
        'type': 'float',
        'doc': """Total energy convergence threshold
Default: 1.0d-4 Ry (≈ 1.4 meV)

Recommended values:
• Coarse: 1.0d-4 (geometry optimization)
• Standard: 1.0d-5 (production)
• Tight: 1.0d-6 (energy differences)""",
    },
    'max_seconds': {
        'type': 'float',
        'doc': """Maximum wall-clock time in seconds
Calculation saves checkpoint and exits cleanly.

Useful for HPC queue time limits.
Example: 86400 = 24 hours""",
    },
    'verbosity': {
        'type': 'string',
        'values': ['low', 'high'],
        'doc': """Output verbosity level
• low: Minimal output (default)
• high: Full eigenvalues, forces, timing

Use 'high' for debugging and detailed analysis.""",
    },
    'restart_mode': {
        'type': 'string',
        'values': ['from_scratch', 'restart'],
        'doc': """Restart mode for calculations
• from_scratch: Fresh calculation (default)
• restart: Continue from saved data

Use 'restart' after interrupted calculations.""",
    },
    
    # ==================== SYSTEM NAMELIST ====================
    'ibrav': {
        'type': 'int',
        'doc': """Bravais lattice index (0-14)
• 0: Free (CELL_PARAMETERS required) ← Recommended
• 1: Cubic P (sc)
• 2: Cubic F (fcc)
• 3: Cubic I (bcc)
• 4: Hexagonal
• 5: Trigonal R (3-fold axis c)
• 6: Tetragonal P
• 7: Tetragonal I
• 8: Orthorhombic P
...etc.

Tip: Use ibrav=0 with CELL_PARAMETERS for flexibility.""",
    },
    'nat': {
        'type': 'int',
        'doc': """Number of atoms in the unit cell
Must match lines in ATOMIC_POSITIONS card.

Count all atoms including equivalent positions.
For supercells: nat = nat_primitive × supercell_size""",
    },
    'ntyp': {
        'type': 'int',
        'doc': """Number of distinct atomic species
Must match entries in ATOMIC_SPECIES card.

Example: Si crystal → ntyp=1
Example: GaAs → ntyp=2 (Ga and As)""",
    },
    'ecutwfc': {
        'type': 'float',
        'doc': """Plane-wave cutoff for wavefunctions (Ry)
Critical parameter for accuracy!

Recommended values (converged):
• NC pseudopotentials: 40-60 Ry
• US pseudopotentials: 30-50 Ry  
• PAW: 40-60 Ry
• Transition metals: 60-80 Ry

Always perform convergence test: increase until
total energy changes < 1 meV/atom.""",
    },
    'ecutrho': {
        'type': 'float',
        'doc': """Plane-wave cutoff for charge density (Ry)
Default: 4 × ecutwfc (NC), 8-12 × ecutwfc (US/PAW)

For US/PAW pseudopotentials, higher ratios improve
accuracy of augmentation charges.
Some pseudos specify recommended value in header.""",
    },
    'occupations': {
        'type': 'string',
        'values': ['smearing', 'tetrahedra', 'tetrahedra_lin', 'tetrahedra_opt', 'fixed'],
        'doc': """Electronic occupation scheme
• smearing: Gaussian/Fermi smearing (metals, default)
• tetrahedra: Tetrahedron method (DOS, insulators)
• tetrahedra_opt: Optimized tetrahedra (best for DOS)
• fixed: Fixed occupations (molecules, insulators)

Metals require 'smearing' with degauss > 0.""",
    },
    'smearing': {
        'type': 'string',
        'values': ['gaussian', 'methfessel-paxton', 'marzari-vanderbilt', 'fermi-dirac', 'mv', 'mp', 'fd'],
        'doc': """Smearing function for metals
• gaussian/gauss: Simple Gaussian (safe default)
• mp/methfessel-paxton: Better for metals
• mv/marzari-vanderbilt: Cold smearing (best)
• fd/fermi-dirac: Physical temperature

'mv' recommended for accurate forces in metals.""",
    },
    'degauss': {
        'type': 'float',
        'doc': """Smearing width in Ry
Typical: 0.01-0.05 Ry (0.14-0.68 eV)

Rules:
• Too small → poor k-convergence
• Too large → artificial temperature effects
• Metals: 0.02-0.03 Ry
• Semiconductors: 0.01 Ry or use tetrahedra

Extrapolate to degauss→0 for accurate energies.""",
    },
    'nspin': {
        'type': 'int',
        'values': [1, 2, 4],
        'doc': """Spin polarization
• 1: Non-spin-polarized (default)
• 2: Spin-polarized (collinear magnetism)
• 4: Non-collinear + spin-orbit

Use nspin=2 for magnetic materials (Fe, Ni, Co).
Requires starting_magnetization for each species.""",
    },
    'starting_magnetization': {
        'type': 'float',
        'doc': """Initial magnetization per species [-1, 1]
Required when nspin=2

Example for Fe: starting_magnetization(1) = 0.5
Positive = majority spin up
Converges to actual magnetic moment.""",
    },
    'nosym': {
        'type': 'bool',
        'doc': """Disable crystal symmetry
Default: .false.

Set .true. for:
• Defect calculations
• Symmetry-breaking distortions
• When symmetry auto-detection fails""",
    },
    'noncolin': {
        'type': 'bool',
        'doc': """Enable non-collinear magnetism
Requires nspin=4

For: spin textures, spin spirals, magnetic domain walls
Memory: 2× collinear calculation""",
    },
    'lspinorb': {
        'type': 'bool',
        'doc': """Enable spin-orbit coupling
Requires: noncolin=.true., fully-relativistic pseudos

Essential for:
• Heavy elements (Au, Pt, Bi, Pb)
• Topological materials
• Rashba/Dresselhaus effects""",
    },
    'input_dft': {
        'type': 'string',
        'doc': """Override XC functional from pseudopotential
Examples: 'PBE', 'PBEsol', 'SCAN', 'LDA', 'vdW-DF'

Usually best to match pseudopotential functional.
Hybrid functionals require HSE/PBE0 pseudos.""",
    },
    'nbnd': {
        'type': 'int',
        'doc': """Number of electronic bands to compute
Default: automatic (nelec/2 + 4)

Increase for:
• Band structure (see unoccupied states)
• Optical properties
• NSCF/DOS calculations""",
    },
    'tot_charge': {
        'type': 'float',
        'doc': """Total system charge in electrons
Default: 0.0 (neutral)

Positive = electrons removed (holes)
Negative = electrons added
Requires compensating background for periodic systems.""",
    },
    
    # ==================== ELECTRONS NAMELIST ====================
    'conv_thr': {
        'type': 'float',
        'doc': """SCF convergence threshold (Ry)
Calculation stops when ΔE < conv_thr

Recommended:
• Coarse: 1.0d-6 (fast screening)
• Standard: 1.0d-8 (production)
• Tight: 1.0d-10 (phonons, forces)

1.0d-8 Ry ≈ 0.14 μeV accuracy.""",
    },
    'mixing_beta': {
        'type': 'float',
        'doc': """Charge density mixing factor [0-1]
Default: 0.7

Smaller values = more stable but slower:
• Metals: 0.3-0.5
• Insulators: 0.7
• Difficult systems: 0.1-0.3

If SCF oscillates, reduce mixing_beta.""",
    },
    'mixing_mode': {
        'type': 'string',
        'values': ['plain', 'TF', 'local-TF'],
        'doc': """Charge mixing algorithm
• plain: Simple linear mixing
• TF: Thomas-Fermi screening (metals)
• local-TF: Local TF (inhomogeneous systems)

'TF' recommended for metals and surfaces.""",
    },
    'diagonalization': {
        'type': 'string',
        'values': ['david', 'cg', 'ppcg', 'paro'],
        'doc': """Eigenvalue solver algorithm
• david: Davidson (default, fastest)
• cg: Conjugate gradient (robust)
• ppcg: Parallel PCG (large systems)
• paro: ParO (very large systems)

'cg' if Davidson fails to converge.""",
    },
    'electron_maxstep': {
        'type': 'int',
        'doc': """Maximum SCF iterations
Default: 100

If SCF doesn't converge in 100 steps:
1. Check input geometry
2. Reduce mixing_beta
3. Increase ecutwfc
4. Try different diagonalization""",
    },
    'startingwfc': {
        'type': 'string',
        'values': ['atomic', 'atomic+random', 'random', 'file'],
        'doc': """Initial wavefunctions
• atomic: From pseudopotential (default)
• atomic+random: Atomic + random (recommended)
• random: Pure random (special cases)
• file: Read from previous calculation

'atomic+random' prevents symmetry artifacts.""",
    },
    'startingpot': {
        'type': 'string',
        'values': ['atomic', 'file'],
        'doc': """Initial potential
• atomic: Superposition of atomic potentials
• file: Read from previous calculation

Use 'file' for NSCF or restart calculations.""",
    },
    
    # ==================== IONS NAMELIST ====================
    'ion_dynamics': {
        'type': 'string',
        'values': ['bfgs', 'damp', 'verlet', 'langevin', 'langevin-smc'],
        'doc': """Ionic relaxation/dynamics algorithm
• bfgs: Quasi-Newton optimization (default for relax)
• damp: Damped dynamics (robust)
• verlet: Verlet MD (default for md)
• langevin: Langevin thermostat MD

BFGS is fastest for geometry optimization.""",
    },
    'ion_temperature': {
        'type': 'string',
        'values': ['rescaling', 'rescale-v', 'rescale-T', 'reduce-T', 'berendsen', 'andersen', 'initial', 'not_controlled'],
        'doc': """MD temperature control
• berendsen: Berendsen thermostat (equilibration)
• andersen: Andersen thermostat (canonical)
• rescaling: Velocity rescaling
• not_controlled: NVE ensemble

Use 'berendsen' for equilibration, 'andersen' for production.""",
    },
    'tempw': {
        'type': 'float',
        'doc': """Target ionic temperature in Kelvin
Default: 300 K

Example: tempw = 300 for room temperature
For high-T simulations, consider quantum effects.""",
    },
    'upscale': {
        'type': 'float',
        'doc': """Threshold for BFGS step rescaling
Default: 100.0

Larger values allow larger ionic steps.
Reduce if relaxation oscillates.""",
    },
    
    # ==================== CELL NAMELIST ====================
    'cell_dynamics': {
        'type': 'string',
        'values': ['none', 'sd', 'damp-pr', 'damp-w', 'bfgs'],
        'doc': """Cell relaxation algorithm
• bfgs: Quasi-Newton (default, fastest)
• damp-pr: Parrinello-Rahman damped
• damp-w: Wentzcovitch damped
• sd: Steepest descent (robust)

BFGS recommended for vc-relax calculations.""",
    },
    'press': {
        'type': 'float',
        'doc': """Target external pressure in kbar
Default: 0.0 (ambient)

1 GPa = 10 kbar
For high-pressure calculations:
press = 100 → 10 GPa""",
    },
    'press_conv_thr': {
        'type': 'float',
        'doc': """Pressure convergence threshold (kbar)
Default: 0.5 kbar

For accurate lattice constants: 0.1-0.5 kbar
For high-pressure work: 0.1 kbar""",
    },
    'cell_dofree': {
        'type': 'string',
        'values': ['all', 'x', 'y', 'z', 'xy', 'xz', 'yz', 'xyz', 'shape', 'volume', '2Dxy', '2Dshape', 'ibrav'],
        'doc': """Cell degrees of freedom to relax
• all: Full cell optimization (default)
• shape: Fix volume, relax shape
• volume: Fix shape, relax volume
• 2Dxy: 2D materials (fixed c-axis)
• ibrav: Preserve Bravais lattice type

Use '2Dxy' for layered materials with vacuum.""",
    },
}

# Namelist sections
NAMELISTS = ['&CONTROL', '&SYSTEM', '&ELECTRONS', '&IONS', '&CELL']

# Card keywords
CARDS = [
    'ATOMIC_SPECIES', 'ATOMIC_POSITIONS', 'K_POINTS',
    'CELL_PARAMETERS', 'CONSTRAINTS', 'OCCUPATIONS',
    'ATOMIC_FORCES', 'HUBBARD'
]


class QESyntaxHighlighter(QSyntaxHighlighter):
    """Syntax highlighter for QE input files."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_formats()
        self._init_rules()
    
    def _init_formats(self):
        """Initialize text formats."""
        # Namelist names (&CONTROL, etc.)
        self.namelist_format = QTextCharFormat()
        self.namelist_format.setForeground(QColor('#C586C0'))  # Purple
        self.namelist_format.setFontWeight(700)
        
        # Keywords (ecutwfc, etc.)
        self.keyword_format = QTextCharFormat()
        self.keyword_format.setForeground(QColor('#9CDCFE'))  # Light blue
        
        # Values
        self.string_format = QTextCharFormat()
        self.string_format.setForeground(QColor('#CE9178'))  # Orange-brown
        
        self.number_format = QTextCharFormat()
        self.number_format.setForeground(QColor('#B5CEA8'))  # Light green
        
        self.bool_format = QTextCharFormat()
        self.bool_format.setForeground(QColor('#569CD6'))  # Blue
        
        # Cards
        self.card_format = QTextCharFormat()
        self.card_format.setForeground(QColor('#DCDCAA'))  # Yellow
        self.card_format.setFontWeight(700)
        
        # Comments
        self.comment_format = QTextCharFormat()
        self.comment_format.setForeground(QColor('#6A9955'))  # Green
        self.comment_format.setFontItalic(True)
        
        # Errors (for validation)
        self.error_format = QTextCharFormat()
        self.error_format.setUnderlineStyle(QTextCharFormat.WaveUnderline)
        self.error_format.setUnderlineColor(QColor('#F44336'))
    
    def _init_rules(self):
        """Initialize highlighting rules."""
        self.rules = []
        
        # Namelist headers
        pattern = QRegularExpression(r'&[A-Z]+')
        self.rules.append((pattern, self.namelist_format))
        
        # End of namelist
        pattern = QRegularExpression(r'^/', QRegularExpression.MultilineOption)
        self.rules.append((pattern, self.namelist_format))
        
        # Keywords
        keyword_pattern = '|'.join(QE_KEYWORDS.keys())
        pattern = QRegularExpression(rf'\b({keyword_pattern})\b', QRegularExpression.CaseInsensitiveOption)
        self.rules.append((pattern, self.keyword_format))
        
        # Cards
        card_pattern = '|'.join(CARDS)
        pattern = QRegularExpression(rf'^({card_pattern})\b', 
                                      QRegularExpression.MultilineOption | QRegularExpression.CaseInsensitiveOption)
        self.rules.append((pattern, self.card_format))
        
        # Booleans
        pattern = QRegularExpression(r'\.(true|false|t|f)\.', QRegularExpression.CaseInsensitiveOption)
        self.rules.append((pattern, self.bool_format))
        
        # Numbers
        pattern = QRegularExpression(r'\b[+-]?(\d+\.?\d*|\d*\.?\d+)([eEdD][+-]?\d+)?\b')
        self.rules.append((pattern, self.number_format))
        
        # Strings
        pattern = QRegularExpression(r"'[^']*'")
        self.rules.append((pattern, self.string_format))
        
        # Comments
        pattern = QRegularExpression(r'!.*$', QRegularExpression.MultilineOption)
        self.rules.append((pattern, self.comment_format))
    
    def highlightBlock(self, text: str):
        """Apply syntax highlighting to a block of text."""
        for pattern, fmt in self.rules:
            match_iter = pattern.globalMatch(text)
            while match_iter.hasNext():
                match = match_iter.next()
                self.setFormat(match.capturedStart(), match.capturedLength(), fmt)


class CompletionPopup(QListWidget):
    """Auto-completion popup."""
    
    item_selected = pyqtSignal(str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.WindowType.Popup)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMouseTracking(True)
        
        self.itemClicked.connect(self._on_item_clicked)
    
    def _on_item_clicked(self, item):
        self.item_selected.emit(item.text())
        self.hide()
    
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            item = self.currentItem()
            if item:
                self.item_selected.emit(item.text())
            self.hide()
        elif event.key() == Qt.Key.Key_Escape:
            self.hide()
        else:
            super().keyPressEvent(event)


class QEInputEditor(QPlainTextEdit):
    """
    Intelligent QE input file editor.
    
    Features:
        - Syntax highlighting
        - Auto-completion for keywords
        - Real-time validation
        - Documentation tooltips
        - Template insertion
    """
    
    validation_changed = pyqtSignal(list)  # List of validation errors
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup editor
        self.setFont(QFont("Consolas", 11))
        self.setTabStopDistance(30)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                border: 1px solid #3c3c3c;
                selection-background-color: #264f78;
            }
        """)
        
        # Syntax highlighter
        self.highlighter = QESyntaxHighlighter(self.document())
        
        # Completion popup
        self.completion_popup = CompletionPopup(self)
        self.completion_popup.item_selected.connect(self._insert_completion)
        
        # Validation errors
        self._validation_errors: List[Dict] = []
        
        # Connect signals
        self.textChanged.connect(self._on_text_changed)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Handle key events for completion."""
        if self.completion_popup.isVisible():
            if event.key() in (Qt.Key.Key_Up, Qt.Key.Key_Down):
                self.completion_popup.keyPressEvent(event)
                return
            elif event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
                item = self.completion_popup.currentItem()
                if item:
                    self._insert_completion(item.text())
                    return
            elif event.key() == Qt.Key.Key_Escape:
                self.completion_popup.hide()
                return
        
        super().keyPressEvent(event)
        
        # Trigger completion on letters
        if event.text().isalpha():
            self._show_completions()
    
    def _show_completions(self):
        """Show auto-completion popup."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfWord, QTextCursor.KeepAnchor)
        prefix = cursor.selectedText().lower()
        
        if len(prefix) < 2:
            self.completion_popup.hide()
            return
        
        # Find matching keywords
        matches = [k for k in QE_KEYWORDS if k.startswith(prefix)]
        
        if not matches:
            self.completion_popup.hide()
            return
        
        # Update popup
        self.completion_popup.clear()
        self.completion_popup.addItems(matches)
        self.completion_popup.setCurrentRow(0)
        
        # Position popup
        cursor_rect = self.cursorRect()
        popup_pos = self.mapToGlobal(cursor_rect.bottomLeft())
        self.completion_popup.move(popup_pos)
        self.completion_popup.resize(200, min(150, len(matches) * 20))
        self.completion_popup.show()
    
    def _insert_completion(self, completion: str):
        """Insert selected completion."""
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.StartOfWord, QTextCursor.KeepAnchor)
        cursor.insertText(completion)
        self.setTextCursor(cursor)
        self.completion_popup.hide()
    
    def _on_text_changed(self):
        """Handle text changes."""
        self._validate()
    
    def _validate(self):
        """Validate input content using SmartValidator."""
        text = self.toPlainText()
        errors = []
        
        try:
            from .smart_validator import SmartValidator
            errors = SmartValidator.validate(text)
        except Exception as e:
            # Fallback if validator fails/missing
            logger.error(f"SmartValidator failed: {e}")
            # Basic fallback checks
            if '&CONTROL' not in text.upper():
                errors.append({'message': "Missing &CONTROL", 'severity': 'error'})
        
        self._validation_errors = errors
        self.validation_changed.emit(errors)
    
    def get_keyword_doc(self, keyword: str) -> str:
        """Get documentation for a keyword."""
        if keyword in QE_KEYWORDS:
            info = QE_KEYWORDS[keyword]
            doc = info.get('doc', 'No documentation available')
            type_str = info.get('type', 'unknown')
            values = info.get('values', [])
            
            result = f"{keyword} ({type_str})\n\n{doc}"
            if values:
                result += f"\n\nValues: {', '.join(str(v) for v in values)}"
            
            return result
        return f"Unknown keyword: {keyword}"
    
    def insert_template(self, template_name: str):
        """Insert a predefined template."""
        templates = {
            'scf': """&CONTROL
  calculation = 'scf'
  prefix = 'pwscf'
  pseudo_dir = './pseudo'
  outdir = './tmp'
/

&SYSTEM
  ibrav = 0
  nat = 2
  ntyp = 1
  ecutwfc = 60.0
  ecutrho = 480.0
/

&ELECTRONS
  conv_thr = 1.0d-8
  mixing_beta = 0.7
/

ATOMIC_SPECIES
  Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF

CELL_PARAMETERS angstrom
  5.43  0.00  0.00
  0.00  5.43  0.00
  0.00  0.00  5.43

ATOMIC_POSITIONS crystal
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25

K_POINTS automatic
  8 8 8 0 0 0
""",
            'relax': """&CONTROL
  calculation = 'relax'
  prefix = 'pwscf'
  pseudo_dir = './pseudo'
  outdir = './tmp'
  forc_conv_thr = 1.0d-4
/

&SYSTEM
  ibrav = 0
  nat = 2
  ntyp = 1
  ecutwfc = 60.0
/

&ELECTRONS
  conv_thr = 1.0d-8
/

&IONS
  ion_dynamics = 'bfgs'
/

ATOMIC_SPECIES
  Si  28.0855  Si.UPF

CELL_PARAMETERS angstrom
  5.43  0.00  0.00
  0.00  5.43  0.00
  0.00  0.00  5.43

ATOMIC_POSITIONS crystal
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25

K_POINTS automatic
  8 8 8 0 0 0
""",
            'bands': """&CONTROL
  calculation = 'bands'
  prefix = 'pwscf'
  pseudo_dir = './pseudo'
  outdir = './tmp'
/

&SYSTEM
  ibrav = 0
  nat = 2
  ntyp = 1
  ecutwfc = 60.0
/

&ELECTRONS
  conv_thr = 1.0d-8
/

ATOMIC_SPECIES
  Si  28.0855  Si.UPF

CELL_PARAMETERS angstrom
  5.43  0.00  0.00
  0.00  5.43  0.00
  0.00  0.00  5.43

ATOMIC_POSITIONS crystal
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25

K_POINTS crystal_b
5
  0.5  0.5  0.5  20  ! L
  0.0  0.0  0.0  20  ! Gamma
  0.5  0.0  0.5  20  ! X
  0.5  0.25 0.75 20  ! W
  0.5  0.5  0.5  0   ! L
""",
            'vc-relax': """&CONTROL
  calculation = 'vc-relax'
  prefix = 'pwscf'
  pseudo_dir = './pseudo'
  outdir = './tmp'
  forc_conv_thr = 1.0d-4
/

&SYSTEM
  ibrav = 0
  nat = 2
  ntyp = 1
  ecutwfc = 60.0
  ecutrho = 480.0
/

&ELECTRONS
  conv_thr = 1.0d-8
  mixing_beta = 0.7
/

&IONS
  ion_dynamics = 'bfgs'
/

&CELL
  cell_dynamics = 'bfgs'
  press_conv_thr = 0.5
/

ATOMIC_SPECIES
  Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF

CELL_PARAMETERS angstrom
  5.43  0.00  0.00
  0.00  5.43  0.00
  0.00  0.00  5.43

ATOMIC_POSITIONS crystal
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25

K_POINTS automatic
  6 6 6 0 0 0
""",
            'nscf': """&CONTROL
  calculation = 'nscf'
  prefix = 'pwscf'
  pseudo_dir = './pseudo'
  outdir = './tmp'
/

&SYSTEM
  ibrav = 0
  nat = 2
  ntyp = 1
  ecutwfc = 60.0
  occupations = 'tetrahedra'
/

&ELECTRONS
  conv_thr = 1.0d-8
/

ATOMIC_SPECIES
  Si  28.0855  Si.pbe-n-rrkjus_psl.1.0.0.UPF

CELL_PARAMETERS angstrom
  5.43  0.00  0.00
  0.00  5.43  0.00
  0.00  0.00  5.43

ATOMIC_POSITIONS crystal
  Si  0.00  0.00  0.00
  Si  0.25  0.25  0.25

K_POINTS automatic
  12 12 12 0 0 0
""",
        }
        
        if template_name in templates:
            self.setPlainText(templates[template_name])
    
    def load_file(self, filepath: Path):
        """Load content from file."""
        with open(filepath, 'r') as f:
            self.setPlainText(f.read())
    
    def save_file(self, filepath: Path):
        """Save content to file."""
        with open(filepath, 'w') as f:
            f.write(self.toPlainText())



class ValidationItemWidget(QFrame):
    """Clean validation item with proper text wrapping and button placement."""
    
    fix_requested = pyqtSignal(dict)
    
    def __init__(self, error: Dict, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setStyleSheet("""
            ValidationItemWidget {
                background: rgba(30, 30, 46, 0.5);
                border-radius: 6px;
                margin: 2px;
            }
            ValidationItemWidget:hover {
                background: rgba(49, 50, 68, 0.7);
            }
        """)
        
        # Main vertical layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)
        
        # Severity colors
        is_error = error['severity'] == 'error'
        prefix = "ERROR" if is_error else "WARN"
        badge_bg = "#f38ba8" if is_error else "#f9e2af"
        badge_fg = "#1e1e2e" if is_error else "#1e1e2e"
        text_color = "#f38ba8" if is_error else "#cdd6f4"
        
        # Top row: Badge + Message
        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        
        # Severity badge
        badge = QLabel(prefix)
        badge.setFixedWidth(50)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setStyleSheet(f"""
            QLabel {{
                background: {badge_bg};
                color: {badge_fg};
                font-size: 9px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
            }}
        """)
        top_row.addWidget(badge)
        
        # Message text
        msg_label = QLabel(error['message'])
        msg_label.setWordWrap(True)
        msg_label.setStyleSheet(f"color: {text_color}; font-size: 11px;")
        msg_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        top_row.addWidget(msg_label, 1)
        
        main_layout.addLayout(top_row)
        
        # Bottom row: Fix button (if available)
        if 'fix' in error:
            btn_row = QHBoxLayout()
            btn_row.setContentsMargins(0, 4, 0, 0)
            btn_row.addStretch(1)
            
            fix_data = error['fix']  # Capture in local variable
            
            btn = QPushButton("Apply Fix")
            btn.setMinimumWidth(80)
            btn.setFixedHeight(26)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    background: #89b4fa;
                    color: #1e1e2e;
                    border: none;
                    border-radius: 4px;
                    padding: 4px 14px;
                    font-size: 10px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background: #b4befe;
                }
                QPushButton:pressed {
                    background: #74c7ec;
                }
            """)
            
            def on_fix_clicked(checked, fix=fix_data):
                print(f"[DEBUG] Button clicked, emitting: {fix}")
                self.fix_requested.emit(fix)
            
            btn.clicked.connect(on_fix_clicked)
            btn_row.addWidget(btn)
            
            main_layout.addLayout(btn_row)

class InputEditorWidget(QWidget):
    """
    Premium input editor widget with toolbar and validation panel.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
    
    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Premium Toolbar
        toolbar = QToolBar()
        toolbar.setStyleSheet("""
            QToolBar {
                background: #181825;
                border: none;
                border-bottom: 1px solid #313244;
                padding: 8px 16px;
                spacing: 8px;
            }
        """)
        
        # Template selector
        template_label = QLabel("Template:")
        template_label.setStyleSheet("color: #a6adc8; font-size: 11px; margin-right: 4px;")
        toolbar.addWidget(template_label)
        
        self.template_combo = QComboBox()
        self.template_combo.addItems(['scf', 'relax', 'vc-relax', 'bands', 'nscf'])
        self.template_combo.setStyleSheet("""
            QComboBox {
                background: #313244;
                color: #cdd6f4;
                border: none;
                border-radius: 6px;
                padding: 6px 12px;
                min-width: 80px;
            }
            QComboBox:hover { background: #45475a; }
            QComboBox::drop-down { border: none; width: 20px; }
        """)
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        toolbar.addWidget(self.template_combo)
        
        toolbar.addSeparator()
        
        # File operations
        open_btn = QPushButton("Open")
        open_btn.setStyleSheet(self._button_style("#3b82f6"))
        open_btn.clicked.connect(self._open_file)
        toolbar.addWidget(open_btn)
        
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(self._button_style("#10b981"))
        save_btn.clicked.connect(self._save_file)
        toolbar.addWidget(save_btn)
        
        toolbar.addSeparator()
        
        # Validate button
        validate_btn = QPushButton("Validate")
        validate_btn.setStyleSheet(self._button_style("#8b5cf6"))
        validate_btn.clicked.connect(self._validate)
        toolbar.addWidget(validate_btn)
        
        layout.addWidget(toolbar)
        
        # Main splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background: #313244; width: 2px; }")
        
        # Editor with premium styling
        self.editor = QEInputEditor()
        self.editor.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e2e;
                color: #cdd6f4;
                border: none;
                selection-background-color: rgba(137, 180, 250, 0.3);
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 12px;
                padding: 12px;
            }
        """)
        splitter.addWidget(self.editor)
        
        # === SIDE PANEL (Two columns: params left, validation/docs right) ===
        side_panel = QWidget()
        side_panel.setMinimumWidth(500)
        side_panel.setStyleSheet("background: #0a0a0f;")
        side_main_layout = QHBoxLayout(side_panel)
        side_main_layout.setContentsMargins(0, 0, 0, 0)
        side_main_layout.setSpacing(0)
        
        # Style helpers
        combo_style = """
            QComboBox { background: #151520; color: #cdd6f4; border: 1px solid #2a2a3a; border-radius: 6px; padding: 6px 10px; min-height: 18px; }
            QComboBox:hover { border-color: #89b4fa; }
            QComboBox::drop-down { border: none; width: 18px; }
        """
        spin_style = """
            QSpinBox, QDoubleSpinBox { 
                background: #151520; 
                color: #cdd6f4; 
                border: 1px solid #2a2a3a; 
                border-radius: 6px; 
                padding: 4px 8px; 
                min-height: 22px;
                min-width: 45px;
            }
            QSpinBox:hover, QDoubleSpinBox:hover { border-color: #89b4fa; }
        """
        label_style = "color: #89b4fa; font-size: 10px; font-weight: 600; border: none;"
        header_style = "color: #6c7086; font-size: 9px; font-weight: 600; letter-spacing: 2px; border: none;"
        
        # === LEFT COLUMN: Parameters ===
        left_col = QWidget()
        left_col.setStyleSheet("background: #0a0a0f; border-right: 1px solid #1a1a24;")
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(8)
        
        params_header = QLabel("QUICK PARAMETERS")
        params_header.setStyleSheet(header_style)
        left_layout.addWidget(params_header)
        
        # Calculation Type
        calc_lbl = QLabel("Calculation")
        calc_lbl.setStyleSheet(label_style)
        left_layout.addWidget(calc_lbl)
        self.calc_combo = QComboBox()
        self.calc_combo.addItems(['scf', 'relax', 'vc-relax', 'bands', 'nscf', 'md'])
        self.calc_combo.setStyleSheet(combo_style)
        left_layout.addWidget(self.calc_combo)
        
        # Wavefunction Cutoff
        ecut_lbl = QLabel("ecutwfc")
        ecut_lbl.setStyleSheet(label_style)
        left_layout.addWidget(ecut_lbl)
        self.ecut_spin = QSpinBox()
        self.ecut_spin.setRange(20, 200)
        self.ecut_spin.setValue(60)
        self.ecut_spin.setSuffix(" Ry")
        self.ecut_spin.setStyleSheet(spin_style)
        left_layout.addWidget(self.ecut_spin)
        
        # K-Point Grid
        kpt_lbl = QLabel("K-grid")
        kpt_lbl.setStyleSheet(label_style)
        left_layout.addWidget(kpt_lbl)
        kpt_row = QHBoxLayout()
        kpt_row.setSpacing(4)
        self.kx_spin = QSpinBox()
        self.kx_spin.setRange(1, 20)
        self.kx_spin.setValue(8)
        self.kx_spin.setStyleSheet(spin_style)
        kpt_row.addWidget(self.kx_spin)
        self.ky_spin = QSpinBox()
        self.ky_spin.setRange(1, 20)
        self.ky_spin.setValue(8)
        self.ky_spin.setStyleSheet(spin_style)
        kpt_row.addWidget(self.ky_spin)
        self.kz_spin = QSpinBox()
        self.kz_spin.setRange(1, 20)
        self.kz_spin.setValue(8)
        self.kz_spin.setStyleSheet(spin_style)
        kpt_row.addWidget(self.kz_spin)
        left_layout.addLayout(kpt_row)
        
        # Smearing
        smear_lbl = QLabel("Smearing")
        smear_lbl.setStyleSheet(label_style)
        left_layout.addWidget(smear_lbl)
        self.smear_combo = QComboBox()
        self.smear_combo.addItems(['fixed', 'gaussian', 'mv', 'mp', 'fd'])
        self.smear_combo.setStyleSheet(combo_style)
        left_layout.addWidget(self.smear_combo)
        
        # Degauss
        degauss_lbl = QLabel("degauss")
        degauss_lbl.setStyleSheet(label_style)
        left_layout.addWidget(degauss_lbl)
        self.degauss_spin = QDoubleSpinBox()
        self.degauss_spin.setRange(0.001, 0.1)
        self.degauss_spin.setSingleStep(0.005)
        self.degauss_spin.setValue(0.02)
        self.degauss_spin.setDecimals(3)
        self.degauss_spin.setSuffix(" Ry")
        self.degauss_spin.setStyleSheet(spin_style)
        left_layout.addWidget(self.degauss_spin)
        
        left_layout.addStretch()
        
        # Buttons
        apply_btn = QPushButton("Apply")
        apply_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        apply_btn.setStyleSheet("QPushButton { background: #3b82f6; color: white; border: none; border-radius: 6px; padding: 8px; font-weight: 600; } QPushButton:hover { background: #60a5fa; }")
        apply_btn.clicked.connect(self._apply_params_to_editor)
        left_layout.addWidget(apply_btn)
        
        autofix_btn = QPushButton("Auto-fix All")
        autofix_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        autofix_btn.setStyleSheet("QPushButton { background: #10b981; color: white; border: none; border-radius: 6px; padding: 8px; font-weight: 600; } QPushButton:hover { background: #34d399; }")
        autofix_btn.clicked.connect(self._autofix_all)
        left_layout.addWidget(autofix_btn)
        
        side_main_layout.addWidget(left_col)
        
        # === RIGHT COLUMN: Validation + Docs ===
        right_col = QWidget()
        right_col.setStyleSheet("background: #0a0a0f;")
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(8)
        
        # Validation
        val_header = QLabel("VALIDATION")
        val_header.setStyleSheet(header_style)
        right_layout.addWidget(val_header)
        # Validation - Use QScrollArea for proper widget sizing
        self.errors_scroll = QScrollArea()
        self.errors_scroll.setWidgetResizable(True)
        self.errors_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.errors_scroll.setStyleSheet("""
            QScrollArea { 
                background: #0d0d12; 
                border: 1px solid #1a1a24; 
                border-radius: 6px; 
            }
            QScrollBar:vertical {
                background: #181825;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #45475a;
                min-height: 20px;
                border-radius: 4px;
            }
        """)
        
        # Container widget for validation items
        self.errors_container = QWidget()
        self.errors_container.setStyleSheet("background: transparent;")
        self.errors_layout = QVBoxLayout(self.errors_container)
        self.errors_layout.setContentsMargins(6, 6, 6, 6)
        self.errors_layout.setSpacing(6)
        self.errors_layout.addStretch()  # Push items to top
        
        self.errors_scroll.setWidget(self.errors_container)
        right_layout.addWidget(self.errors_scroll, 2)
        
        # Documentation
        doc_header = QLabel("DOCUMENTATION")
        doc_header.setStyleSheet(header_style)
        right_layout.addWidget(doc_header)
        
        self.doc_text = QTextEdit()
        self.doc_text.setReadOnly(True)
        self.doc_text.setStyleSheet("QTextEdit { background: #0d0d12; color: #a6adc8; border: 1px solid #1a1a24; border-radius: 6px; padding: 8px; font-size: 11px; }")
        self.doc_text.setPlaceholderText("Hover over keyword...")
        right_layout.addWidget(self.doc_text, 1)
        
        side_main_layout.addWidget(right_col)
        
        splitter.addWidget(side_panel)
        splitter.setSizes([600, 500])
        
        layout.addWidget(splitter)
        
        # Connect signals
        self.editor.validation_changed.connect(self._update_errors)
        self.editor.cursorPositionChanged.connect(self._update_doc)
        self.editor.textChanged.connect(self._sync_params_from_editor)
    
    def _button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background: {color};
                color: white;
                border: none;
                border-radius: 6px;
                padding: 6px 14px;
                font-size: 11px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {color}dd;
            }}
        """
    
    def _on_template_changed(self, template: str):
        """Load selected template."""
        if template in ['scf', 'relax', 'bands']:
            self.editor.insert_template(template)
    
    def _open_file(self):
        """Open file dialog."""
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Open QE Input", "",
            "QE Input Files (*.in *.pwi);;All Files (*)"
        )
        if filepath:
            self.editor.load_file(Path(filepath))
    
    def _save_file(self):
        """Save file dialog."""
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save QE Input", "",
            "QE Input Files (*.in);;All Files (*)"
        )
        if filepath:
            self.editor.save_file(Path(filepath))
    
    def _validate(self):
        """Trigger validation."""
        self.editor._validate()
    
    def _update_errors(self, errors: List[Dict]):
        """Update validation panel with dynamic widgets."""
        # Clear existing items (except the stretch at the end)
        while self.errors_layout.count() > 1:
            item = self.errors_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not errors:
            # Show success message
            success_widget = QFrame()
            success_widget.setStyleSheet("""
                QFrame {
                    background: rgba(166, 227, 161, 0.1);
                    border-radius: 6px;
                    padding: 8px;
                }
            """)
            success_layout = QHBoxLayout(success_widget)
            success_layout.setContentsMargins(12, 12, 12, 12)
            
            check_icon = QLabel("✓")
            check_icon.setStyleSheet("color: #a6e3a1; font-size: 18px; font-weight: bold;")
            success_layout.addWidget(check_icon)
            
            success_msg = QLabel("Input is valid - no issues found")
            success_msg.setStyleSheet("color: #a6e3a1; font-size: 12px; font-weight: 500;")
            success_layout.addWidget(success_msg, 1)
            
            self.errors_layout.insertWidget(0, success_widget)
            return

        # Add validation items
        for i, error in enumerate(errors):
            widget = ValidationItemWidget(error)
            widget.fix_requested.connect(self._apply_fix)
            self.errors_layout.insertWidget(i, widget)
            
    def _apply_fix(self, fix: Dict):
        """Apply a smart fix to the editor content."""
        logger.info(f"Applying fix: {fix}")
        print(f"[DEBUG] _apply_fix called with: {fix}")
        text = self.editor.toPlainText()
        
        try:
            if fix['type'] == 'insert':
                if fix['position'] == 'top':
                    text = fix['text'] + text
                elif fix['position'] == 'after_control':
                    match = re.search(r'&CONTROL.*?/', text, re.DOTALL | re.IGNORECASE)
                    if match:
                        end_pos = match.end()
                        text = text[:end_pos] + "\n\n" + fix['text'] + text[end_pos:]
                    else:
                        text = text + "\n\n" + fix['text']
                elif fix['position'] == 'after_system':
                    match = re.search(r'&SYSTEM.*?/', text, re.DOTALL | re.IGNORECASE)
                    if match:
                        end_pos = match.end()
                        text = text[:end_pos] + "\n\n" + fix['text'] + text[end_pos:]
                    else:
                        text = text + "\n\n" + fix['text']
                        
            elif fix['type'] == 'inject_var':
                namelist = fix['namelist']
                # Find namelist pattern: &NAME ... /
                # We want to insert before the closing slash
                pattern = rf"(&{namelist}.*?)(/)"
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    content_start, content, slash_start = match.start(), match.group(1), match.end() - 1
                    # Insert on new line before slash
                    new_content = content.rstrip() + "\n" + fix['text'] + "\n"
                    # Reconstruct text: before_match + new_content + slash + after_match
                    text = text[:content_start] + new_content + text[slash_start:]
                else:
                    QMessageBox.warning(self, "Fix Warning", f"Could not find namelist &{namelist} to inject variable.")
            
            elif fix['type'] == 'replace_var':
                var = fix['var']
                new_val = fix['value']
                # Search for var = val
                pattern = rf"({var}\s*=\s*)([^,\n/]*)"
                text = re.sub(pattern, rf"\g<1>{new_val}", text, count=1, flags=re.IGNORECASE)
            
            elif fix['type'] == 'replace_card':
                card_name = fix['card']
                # Try to find existing card
                # Match from CARD_NAME until next card (start of line with CAPS) or EOF
                pattern = rf"({card_name}\s+.*?)(\n\s*[A-Z&]|\Z)"
                match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
                if match:
                    # Replace existing, keeping the delimiter of the next card
                    text = re.sub(pattern, fix['text'] + r"\g<2>", text, count=1, flags=re.DOTALL | re.IGNORECASE)
                else:
                    # Append at end
                    text = text.rstrip() + "\n\n" + fix['text']
                
            self.editor.setPlainText(text)
            self._validate() # Re-validate
            
        except Exception as e:
            logger.error(f"Fix failed: {e}")
            QMessageBox.warning(self, "Fix Failed", f"Could not apply fix: {e}")
    
    def _update_doc(self):
        """Update documentation for word under cursor."""
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.WordUnderCursor)
        word = cursor.selectedText().lower()
        
        if word in QE_KEYWORDS:
            doc = self.editor.get_keyword_doc(word)
            self.doc_text.setPlainText(doc)
    
    def _on_param_change(self):
        """Handle parameter control changes."""
        pass  # Spinboxes update automatically
    
    def _apply_params_to_editor(self):
        """Apply UI parameter values to the editor text."""
        text = self.editor.toPlainText()
        
        calc_type = self.calc_combo.currentText()
        ecutwfc = self.ecut_spin.value()
        kx, ky, kz = self.kx_spin.value(), self.ky_spin.value(), self.kz_spin.value()
        smearing = self.smear_combo.currentText()
        degauss = self.degauss_spin.value()
        
        # Update calculation type
        if re.search(r"calculation\s*=", text, re.IGNORECASE):
            text = re.sub(r"(calculation\s*=\s*)['\"]?\w+['\"]?", f"\\1'{calc_type}'", text, flags=re.IGNORECASE)
        elif '&control' in text.lower():
            text = re.sub(r"(&CONTROL.*?)(\n)", rf"\1\n  calculation = '{calc_type}'\2", text, count=1, flags=re.DOTALL | re.IGNORECASE)
        
        # Update ecutwfc
        if re.search(r"ecutwfc\s*=", text, re.IGNORECASE):
            text = re.sub(r"(ecutwfc\s*=\s*)[0-9.]+", f"\\g<1>{ecutwfc}.0", text, flags=re.IGNORECASE)
        elif '&system' in text.lower():
            text = re.sub(r"(&SYSTEM.*?)(\n\s*/)", rf"\1\n  ecutwfc = {ecutwfc}.0\2", text, count=1, flags=re.DOTALL | re.IGNORECASE)
        
        # Update or add K_POINTS
        kpoint_pattern = r"(K_POINTS\s+automatic\s*\n)\s*\d+\s+\d+\s+\d+\s+\d+\s+\d+\s+\d+"
        if re.search(kpoint_pattern, text, re.IGNORECASE):
            text = re.sub(kpoint_pattern, rf"\g<1>  {kx} {ky} {kz} 0 0 0", text, flags=re.IGNORECASE)
        elif 'k_points' not in text.lower():
            # Add K_POINTS card at the end
            text = text.rstrip() + f"\n\nK_POINTS automatic\n  {kx} {ky} {kz} 0 0 0\n"
        
        # Update smearing
        if smearing != 'none':
            if re.search(r"occupations\s*=", text, re.IGNORECASE):
                text = re.sub(r"(occupations\s*=\s*)['\"]?\w+['\"]?", "\\1'smearing'", text, flags=re.IGNORECASE)
            if re.search(r"smearing\s*=", text, re.IGNORECASE):
                text = re.sub(r"(smearing\s*=\s*)['\"]?\w+['\"]?", f"\\1'{smearing}'", text, flags=re.IGNORECASE)
            if re.search(r"degauss\s*=", text, re.IGNORECASE):
                text = re.sub(r"(degauss\s*=\s*)[0-9.]+", f"\\g<1>{degauss}", text, flags=re.IGNORECASE)
        
        self.editor.setPlainText(text)
    
    def _sync_params_from_editor(self):
        """Sync UI controls from editor text (bi-directional)."""
        text = self.editor.toPlainText().lower()
        
        # Block signals to prevent recursion
        self.calc_combo.blockSignals(True)
        self.ecut_spin.blockSignals(True)
        self.kx_spin.blockSignals(True)
        self.ky_spin.blockSignals(True)
        self.kz_spin.blockSignals(True)
        self.smear_combo.blockSignals(True)
        self.degauss_spin.blockSignals(True)
        
        try:
            # Parse calculation type
            calc_match = re.search(r"calculation\s*=\s*['\"]?(\S+?)['\"]?[\s,/]", text)
            if calc_match:
                calc_type = calc_match.group(1).strip("'\"")
                idx = self.calc_combo.findText(calc_type)
                if idx >= 0:
                    self.calc_combo.setCurrentIndex(idx)
            
            # Parse ecutwfc
            ecut_match = re.search(r"ecutwfc\s*=\s*([0-9.]+)", text)
            if ecut_match:
                try:
                    val = int(float(ecut_match.group(1)))
                    self.ecut_spin.setValue(min(200, max(20, val)))
                except:
                    pass
            
            # Parse k-points
            kpt_match = re.search(r"k_points\s+automatic\s*\n\s*(\d+)\s+(\d+)\s+(\d+)", text)
            if kpt_match:
                self.kx_spin.setValue(int(kpt_match.group(1)))
                self.ky_spin.setValue(int(kpt_match.group(2)))
                self.kz_spin.setValue(int(kpt_match.group(3)))
            
            # Parse smearing
            smear_match = re.search(r"smearing\s*=\s*['\"]?(\w+)['\"]?", text)
            if smear_match:
                smear = smear_match.group(1)
                idx = self.smear_combo.findText(smear)
                if idx >= 0:
                    self.smear_combo.setCurrentIndex(idx)
            
            # Parse degauss
            degauss_match = re.search(r"degauss\s*=\s*([0-9.]+)", text)
            if degauss_match:
                try:
                    self.degauss_spin.setValue(float(degauss_match.group(1)))
                except:
                    pass
        finally:
            self.calc_combo.blockSignals(False)
            self.ecut_spin.blockSignals(False)
            self.kx_spin.blockSignals(False)
            self.ky_spin.blockSignals(False)
            self.kz_spin.blockSignals(False)
            self.smear_combo.blockSignals(False)
            self.degauss_spin.blockSignals(False)
    
    def _autofix_all(self):
        """Automatically fix all validation errors that have auto-fix available."""
        from .smart_validator import SmartValidator
        
        max_iterations = 10  # Prevent infinite loops
        total_fixed = 0
        
        for i in range(max_iterations):
            text = self.editor.toPlainText()
            try:
                errors = SmartValidator.validate(text)
            except Exception as e:
                logger.error(f"Validation failed: {e}")
                break
            
            # Find first fixable error
            fixable = [e for e in errors if 'fix' in e]
            if not fixable:
                break  # No more fixable errors
            
            # Apply first fix
            self._apply_fix(fixable[0]['fix'])
            total_fixed += 1
        
        # Re-validate to show remaining errors
        self._validate()
        
        if total_fixed > 0:
            logger.info(f"Auto-fixed {total_fixed} issues")

