"""
Structure Logger for FluxDFT.

Implements undo/redo functionality for structure editing operations.
Based on BURAI's AtomsLogger pattern.
"""

from typing import Optional, List
from dataclasses import dataclass
import copy

try:
    from ase import Atoms
    HAS_ASE = True
except ImportError:
    HAS_ASE = False


@dataclass
class StructureState:
    """Snapshot of structure state for undo/redo."""
    positions: List[List[float]]
    symbols: List[str]
    cell: Optional[List[List[float]]] = None
    pbc: Optional[List[bool]] = None


class StructureLogger:
    """
    Undo/Redo logger for structure editing.
    
    Based on BURAI's AtomsLogger pattern - stores cell configurations
    in a stack for undo/redo operations.
    """
    
    MAX_HISTORY = 20
    
    def __init__(self):
        self.undo_stack: List[StructureState] = []
        self.redo_stack: List[StructureState] = []
        self.current_atoms: Optional['Atoms'] = None
    
    def set_atoms(self, atoms: 'Atoms'):
        """Set the current atoms object to track."""
        self.current_atoms = atoms
        # Clear history when loading new structure
        self.clear()
        # Store initial state
        self.store_state()
    
    def store_state(self):
        """Store current structure state for undo."""
        if not HAS_ASE or self.current_atoms is None:
            return
        
        state = StructureState(
            positions=self.current_atoms.get_positions().tolist(),
            symbols=self.current_atoms.get_chemical_symbols(),
            cell=self.current_atoms.cell.tolist() if self.current_atoms.cell is not None else None,
            pbc=list(self.current_atoms.pbc) if hasattr(self.current_atoms, 'pbc') else None,
        )
        
        self.undo_stack.append(state)
        
        # Clear redo stack when new action is performed
        self.redo_stack.clear()
        
        # Limit stack size
        if len(self.undo_stack) > self.MAX_HISTORY:
            self.undo_stack.pop(0)
    
    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return len(self.undo_stack) > 1  # Need at least 2 states (initial + current)
    
    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return len(self.redo_stack) > 0
    
    def undo(self) -> bool:
        """
        Undo the last structure change.
        
        Returns True if undo was successful.
        """
        if not self.can_undo() or self.current_atoms is None:
            return False
        
        # Move current state to redo stack
        current_state = self.undo_stack.pop()
        self.redo_stack.append(current_state)
        
        # Restore previous state
        previous_state = self.undo_stack[-1]
        self._apply_state(previous_state)
        
        return True
    
    def redo(self) -> bool:
        """
        Redo the last undone change.
        
        Returns True if redo was successful.
        """
        if not self.can_redo() or self.current_atoms is None:
            return False
        
        # Get state from redo stack
        state = self.redo_stack.pop()
        self.undo_stack.append(state)
        
        # Apply the state
        self._apply_state(state)
        
        return True
    
    def _apply_state(self, state: StructureState):
        """Apply a saved state to current atoms."""
        if self.current_atoms is None:
            return
        
        import numpy as np
        
        # Update positions
        self.current_atoms.set_positions(np.array(state.positions))
        
        # Update symbols if needed
        if state.symbols:
            self.current_atoms.set_chemical_symbols(state.symbols)
        
        # Update cell
        if state.cell is not None:
            self.current_atoms.set_cell(np.array(state.cell))
        
        # Update pbc
        if state.pbc is not None:
            self.current_atoms.set_pbc(state.pbc)
    
    def clear(self):
        """Clear all history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
    
    def get_history_size(self) -> int:
        """Get the number of states in history."""
        return len(self.undo_stack)
    
    def get_undo_count(self) -> int:
        """Get number of possible undos."""
        return max(0, len(self.undo_stack) - 1)
    
    def get_redo_count(self) -> int:
        """Get number of possible redos."""
        return len(self.redo_stack)
