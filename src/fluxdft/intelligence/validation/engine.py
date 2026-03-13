"""
Validation Engine for FluxDFT.

Orchestrates all validation rules and produces comprehensive reports.
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml
import json

from .rule_base import ValidationRule, ValidationContext
from .validation_result import ValidationResult, ValidationReport, Severity
from .rules import (
    EcutwfcMinimumRule,
    EcutrhoRatioRule,
    KPointDensityRule,
    KPointShiftRule,
    MetalSmearingRule,
    DegaussValueRule,
    PseudoXCConsistencyRule,
    PseudoExistsRule,
    ConvThrRule,
    ForcConvThrRule,
)


class ValidationEngine:
    """
    Orchestrates all validation rules.
    
    Provides pre-execution validation of QE inputs to catch
    errors and problematic settings before running calculations.
    
    Usage:
        engine = ValidationEngine()
        report = engine.validate(pw_input)
        
        if not report.can_proceed:
            for error in report.get_errors():
                print(f"ERROR: {error.message}")
                print(f"  Fix: {error.fix_suggestion}")
    """
    
    # Default rules to load
    DEFAULT_RULES = [
        # Cutoff rules
        EcutwfcMinimumRule,
        EcutrhoRatioRule,
        # K-points rules
        KPointDensityRule,
        KPointShiftRule,
        # Smearing rules
        MetalSmearingRule,
        DegaussValueRule,
        # Pseudopotential rules
        PseudoXCConsistencyRule,
        PseudoExistsRule,
        # Convergence rules
        ConvThrRule,
        ForcConvThrRule,
    ]
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the validation engine.
        
        Args:
            config_path: Optional path to YAML config for rule customization
        """
        self.rules: List[ValidationRule] = []
        self.config: Dict[str, Any] = {}
        
        # Load configuration
        if config_path and config_path.exists():
            self._load_config(config_path)
        
        # Load default rules
        self._load_default_rules()
    
    def _load_config(self, path: Path):
        """Load rule configuration from YAML."""
        try:
            with open(path, 'r') as f:
                self.config = yaml.safe_load(f) or {}
        except Exception as e:
            print(f"Warning: Could not load validation config: {e}")
    
    def _load_default_rules(self):
        """Load all default validation rules."""
        disabled_rules = set(self.config.get('disabled_rules', []))
        
        for rule_class in self.DEFAULT_RULES:
            rule = rule_class()
            
            # Check if disabled in config
            if rule.rule_id in disabled_rules:
                continue
            
            # Apply config overrides
            rule_config = self.config.get('rules', {}).get(rule.rule_id, {})
            if rule_config.get('enabled', True) is False:
                continue
            
            self.rules.append(rule)
    
    def add_rule(self, rule: ValidationRule):
        """Add a custom validation rule."""
        self.rules.append(rule)
    
    def remove_rule(self, rule_id: str):
        """Remove a rule by ID."""
        self.rules = [r for r in self.rules if r.rule_id != rule_id]
    
    def validate(self, input_data) -> ValidationReport:
        """
        Run all applicable rules and return comprehensive report.
        
        Args:
            input_data: PWInput object to validate
            
        Returns:
            ValidationReport with all results
        """
        # Build context once (shared by all rules)
        context = ValidationContext.from_input(input_data)
        
        results = []
        
        for rule in self.rules:
            # Check if rule applies to this input
            if not rule.is_applicable(input_data):
                continue
            
            # Run the rule
            try:
                result = rule.validate(input_data, context)
                results.append(result)
            except Exception as e:
                # Rule crashed - report as info
                results.append(ValidationResult(
                    rule_id=rule.rule_id,
                    severity=Severity.INFO,
                    category=rule.category,
                    message=f"Rule {rule.rule_id} could not be evaluated",
                    explanation=str(e),
                ))
        
        return ValidationReport(results=results)
    
    def validate_quick(self, input_data) -> bool:
        """
        Quick check if input can proceed (no blocking errors).
        
        Args:
            input_data: PWInput object
            
        Returns:
            True if no blocking errors
        """
        report = self.validate(input_data)
        return report.can_proceed
    
    def get_blocking_errors(self, input_data) -> List[ValidationResult]:
        """
        Get only the blocking errors.
        
        Args:
            input_data: PWInput object
            
        Returns:
            List of error results
        """
        report = self.validate(input_data)
        return report.get_errors()
    
    def get_rule_info(self) -> List[Dict[str, str]]:
        """Get information about all loaded rules."""
        return [
            {
                'id': rule.rule_id,
                'name': rule.name,
                'category': rule.category,
                'description': rule.description,
            }
            for rule in self.rules
        ]
    
    def export_report(self, report: ValidationReport, format: str = 'json') -> str:
        """
        Export validation report to string.
        
        Args:
            report: ValidationReport to export
            format: 'json' or 'text'
            
        Returns:
            Formatted string
        """
        if format == 'json':
            return json.dumps({
                'summary': report.summary(),
                'can_proceed': report.can_proceed,
                'error_count': report.error_count,
                'warning_count': report.warning_count,
                'results': [r.to_dict() for r in report.results],
            }, indent=2)
        
        # Text format
        lines = [
            "=" * 60,
            "FLUXDFT VALIDATION REPORT",
            "=" * 60,
            "",
            report.summary(),
            "",
        ]
        
        if report.get_errors():
            lines.append("ERRORS (must fix):")
            for r in report.get_errors():
                lines.append(f"  ❌ {r.message}")
                if r.explanation:
                    lines.append(f"     → {r.explanation}")
                if r.fix_suggestion:
                    lines.append(f"     Fix: {r.fix_suggestion}")
            lines.append("")
        
        if report.get_warnings():
            lines.append("WARNINGS (should fix):")
            for r in report.get_warnings():
                lines.append(f"  ⚠️ {r.message}")
                if r.fix_suggestion:
                    lines.append(f"     Fix: {r.fix_suggestion}")
            lines.append("")
        
        lines.append("=" * 60)
        
        return '\n'.join(lines)
