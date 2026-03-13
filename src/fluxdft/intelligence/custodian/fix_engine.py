"""
Fix Suggestion Engine for FluxDFT.

Intelligent fix suggestion system that analyzes calculation
state and provides actionable recommendations.

Copyright (c) 2024 FluxDFT. All rights reserved.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from pathlib import Path
import logging

from .error_handlers import get_all_handlers, ErrorAction

logger = logging.getLogger(__name__)


class FixCategory(Enum):
    """Category of fix suggestion."""
    CONVERGENCE = "convergence"
    PERFORMANCE = "performance"
    ACCURACY = "accuracy"
    STABILITY = "stability"
    RESOURCES = "resources"


class FixPriority(Enum):
    """Priority level for fix application."""
    CRITICAL = 1  # Must fix before running
    HIGH = 2      # Strongly recommended
    MEDIUM = 3    # Recommended
    LOW = 4       # Optional optimization


@dataclass
class FixSuggestion:
    """
    A suggested fix for a calculation issue.
    
    Attributes:
        title: Short title for the fix
        description: Detailed explanation
        category: Type of issue being addressed
        priority: How urgent is this fix
        modifications: Parameter changes to apply
        reasoning: Why this fix should work
        alternatives: Alternative approaches
    """
    title: str
    description: str
    category: FixCategory
    priority: FixPriority
    modifications: Dict[str, Any] = field(default_factory=dict)
    reasoning: str = ""
    alternatives: List[str] = field(default_factory=list)
    
    def apply_to_input(self, input_data: Dict) -> Dict:
        """
        Apply modifications to input data dict.
        
        Returns new dict with modifications applied.
        """
        result = dict(input_data)
        for key, value in self.modifications.items():
            # Handle nested keys with dot notation
            if '.' in key:
                parts = key.split('.')
                target = result
                for part in parts[:-1]:
                    if part not in target:
                        target[part] = {}
                    target = target[part]
                target[parts[-1]] = value
            else:
                result[key] = value
        return result


class FixSuggestionEngine:
    """
    Intelligent fix suggestion engine.
    
    Analyzes calculation state (input parameters, output errors,
    validation results) and generates prioritized fix suggestions.
    
    Usage:
        >>> engine = FixSuggestionEngine()
        >>> 
        >>> # From error detection
        >>> suggestions = engine.from_errors(output_path)
        >>> 
        >>> # From validation results
        >>> suggestions = engine.from_validation(validation_results)
        >>> 
        >>> # Pre-calculation checks
        >>> suggestions = engine.pre_calculation_checks(input_data)
        >>> 
        >>> # Apply fixes
        >>> for fix in suggestions:
        ...     if fix.priority == FixPriority.CRITICAL:
        ...         input_data = fix.apply_to_input(input_data)
    """
    
    def __init__(self, mp_client=None):
        """
        Initialize fix suggestion engine.
        
        Args:
            mp_client: Optional MaterialsProjectClient for reference data
        """
        self.mp_client = mp_client
        self.error_handlers = get_all_handlers()
    
    def from_errors(self, output_path: Path) -> List[FixSuggestion]:
        """
        Generate fixes from detected errors in output file.
        
        Args:
            output_path: Path to QE output file
            
        Returns:
            List of FixSuggestion objects
        """
        suggestions = []
        
        for handler in self.error_handlers:
            if handler.check(output_path):
                action = handler.correct(output_path)
                if action:
                    suggestion = self._action_to_suggestion(action, handler.name)
                    suggestions.append(suggestion)
        
        # Sort by priority
        suggestions.sort(key=lambda x: x.priority.value)
        return suggestions
    
    def from_validation(
        self,
        validation_results: List,
    ) -> List[FixSuggestion]:
        """
        Generate fixes from validation results.
        
        Args:
            validation_results: List of ValidationResult objects
            
        Returns:
            List of FixSuggestion objects
        """
        suggestions = []
        
        for result in validation_results:
            if not result.passed and result.suggestions:
                # Create fix suggestion from validation result
                priority = (FixPriority.HIGH if result.level.value == 'error'
                           else FixPriority.MEDIUM)
                
                suggestion = FixSuggestion(
                    title=f"Fix: {result.check_name.replace('_', ' ').title()}",
                    description=result.message,
                    category=self._categorize_validation(result.check_name),
                    priority=priority,
                    modifications={},  # Validations don't have specific mods
                    reasoning=result.suggestions[0] if result.suggestions else "",
                    alternatives=result.suggestions[1:] if len(result.suggestions) > 1 else [],
                )
                suggestions.append(suggestion)
        
        return suggestions
    
    def pre_calculation_checks(
        self,
        input_data: Dict,
        formula: Optional[str] = None,
    ) -> List[FixSuggestion]:
        """
        Generate pre-calculation optimization suggestions.
        
        Args:
            input_data: Input parameters dict
            formula: Chemical formula (for MP lookup)
            
        Returns:
            List of FixSuggestion objects
        """
        suggestions = []
        
        # Check ecutwfc
        ecutwfc = input_data.get('system', {}).get('ecutwfc', 
                  input_data.get('ecutwfc', 30))
        
        if ecutwfc < 40:
            suggestions.append(FixSuggestion(
                title="Increase ecutwfc",
                description=f"Current ecutwfc ({ecutwfc} Ry) may be too low",
                category=FixCategory.ACCURACY,
                priority=FixPriority.MEDIUM,
                modifications={'system.ecutwfc': 60},
                reasoning="Higher cutoff improves accuracy. Check pseudopotential header for recommended values.",
                alternatives=["Run convergence test to determine optimal ecutwfc"],
            ))
        
        # Check ecutrho ratio
        ecutrho = input_data.get('system', {}).get('ecutrho',
                  input_data.get('ecutrho'))
        if ecutrho and ecutrho / ecutwfc < 4:
            suggestions.append(FixSuggestion(
                title="Adjust ecutrho/ecutwfc ratio",
                description=f"ecutrho/ecutwfc = {ecutrho/ecutwfc:.1f} < 4 (recommended minimum)",
                category=FixCategory.ACCURACY,
                priority=FixPriority.HIGH,
                modifications={'system.ecutrho': ecutwfc * 4},
                reasoning="ecutrho should be at least 4x ecutwfc for NC/PAW pseudopotentials",
            ))
        
        # Check k-points for metals
        if formula and self._is_likely_metal(formula):
            kpoints = input_data.get('k_points', {})
            if self._is_kgrid_sparse(kpoints):
                suggestions.append(FixSuggestion(
                    title="Increase k-point density for metal",
                    description=f"{formula} is likely metallic - dense k-grid recommended",
                    category=FixCategory.ACCURACY,
                    priority=FixPriority.HIGH,
                    modifications={},  # Can't automatically modify k-points
                    reasoning="Metals require dense k-grids near Fermi level",
                    alternatives=["Use automatic k-grid with spacing < 0.03 Å⁻¹"],
                ))
            
            # Check smearing
            occupations = input_data.get('system', {}).get('occupations', 'fixed')
            if occupations == 'fixed' or occupations == 'tetrahedra':
                suggestions.append(FixSuggestion(
                    title="Enable smearing for metal",
                    description="Fixed occupations may cause convergence issues for metals",
                    category=FixCategory.CONVERGENCE,
                    priority=FixPriority.HIGH,
                    modifications={
                        'system.occupations': 'smearing',
                        'system.smearing': 'mv',
                        'system.degauss': 0.02,
                    },
                    reasoning="Marzari-Vanderbilt cold smearing is robust for metals",
                ))
        
        # Check mixing_beta
        mixing_beta = input_data.get('electrons', {}).get('mixing_beta', 0.7)
        if mixing_beta > 0.5:
            suggestions.append(FixSuggestion(
                title="Reduce mixing_beta for stability",
                description=f"mixing_beta={mixing_beta:.2f} may cause SCF oscillations",
                category=FixCategory.STABILITY,
                priority=FixPriority.LOW,
                modifications={'electrons.mixing_beta': 0.3},
                reasoning="Lower mixing improves stability at cost of more iterations",
            ))
        
        return suggestions
    
    def get_optimal_settings(
        self,
        formula: str,
        calculation_type: str = 'scf',
    ) -> Dict[str, Any]:
        """
        Get recommended settings for a material.
        
        Args:
            formula: Chemical formula
            calculation_type: 'scf', 'bands', 'relax', 'md'
            
        Returns:
            Dict of recommended parameters
        """
        settings = {}
        
        # Get MP reference
        mp_ref = None
        if self.mp_client and self.mp_client.is_configured():
            try:
                mp_ref = self.mp_client.find_best_match(formula)
            except Exception:
                pass
        
        # Base settings
        settings['ecutwfc'] = 60  # Safe default
        settings['ecutrho'] = 480
        settings['conv_thr'] = 1e-8
        
        # Metal detection
        is_metal = mp_ref.is_metal if mp_ref else self._is_likely_metal(formula)
        
        if is_metal:
            settings['occupations'] = 'smearing'
            settings['smearing'] = 'mv'
            settings['degauss'] = 0.02
        else:
            settings['occupations'] = 'fixed'
        
        # Calculation-specific
        if calculation_type == 'relax':
            settings['forc_conv_thr'] = 1e-4
            settings['etot_conv_thr'] = 1e-5
        elif calculation_type == 'bands':
            settings['nbnd'] = 'auto'  # Will need to be set based on nelectron
        elif calculation_type == 'md':
            settings['ion_temperature'] = 'rescaling'
            settings['tempw'] = 300
        
        return settings
    
    def _action_to_suggestion(
        self,
        action: ErrorAction,
        handler_name: str,
    ) -> FixSuggestion:
        """Convert ErrorAction to FixSuggestion."""
        priority = FixPriority.HIGH if action.action_type == 'fatal' else FixPriority.MEDIUM
        
        category_map = {
            'modify_input': FixCategory.CONVERGENCE,
            'restart': FixCategory.STABILITY,
            'reduce_parallelism': FixCategory.RESOURCES,
            'skip': FixCategory.STABILITY,
            'fatal': FixCategory.STABILITY,
        }
        
        return FixSuggestion(
            title=f"Fix: {handler_name}",
            description=action.description,
            category=category_map.get(action.action_type, FixCategory.STABILITY),
            priority=priority,
            modifications=action.modifications,
            reasoning=f"Detected by {handler_name} error handler",
        )
    
    def _categorize_validation(self, check_name: str) -> FixCategory:
        """Map validation check to fix category."""
        if 'convergence' in check_name.lower() or 'force' in check_name.lower():
            return FixCategory.CONVERGENCE
        elif 'gap' in check_name.lower() or 'metal' in check_name.lower():
            return FixCategory.ACCURACY
        elif 'magnet' in check_name.lower():
            return FixCategory.ACCURACY
        else:
            return FixCategory.STABILITY
    
    def _is_likely_metal(self, formula: str) -> bool:
        """Simple heuristic for metallic character."""
        # List of common metals
        metals = {
            'Li', 'Na', 'K', 'Rb', 'Cs',  # Alkali
            'Be', 'Mg', 'Ca', 'Sr', 'Ba',  # Alkaline
            'Al', 'Ga', 'In', 'Tl', 'Sn', 'Pb',  # Post-transition
            'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',  # 3d
            'Zr', 'Nb', 'Mo', 'Ru', 'Rh', 'Pd', 'Ag',  # 4d
            'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au',  # 5d
        }
        
        # Check if formula is pure metal
        # Simple check: all elements are metals
        import re
        elements = re.findall(r'[A-Z][a-z]?', formula)
        
        return all(el in metals for el in elements)
    
    def _is_kgrid_sparse(self, kpoints: Dict) -> bool:
        """Check if k-grid is likely too sparse."""
        if not kpoints:
            return True
        
        # Check for automatic grid
        if 'nk1' in kpoints:
            total = kpoints.get('nk1', 1) * kpoints.get('nk2', 1) * kpoints.get('nk3', 1)
            return total < 27  # Less than 3x3x3
        
        return False
