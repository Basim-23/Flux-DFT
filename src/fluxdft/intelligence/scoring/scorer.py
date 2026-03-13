"""
Publishability Scorer for FluxDFT.

Provides a quantitative assessment of calculation quality
for publication readiness.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Callable
from enum import Enum


class Grade(Enum):
    """Publication readiness grades."""
    A = ("A", "Publication Ready", "#a6e3a1", 90)
    B = ("B", "Minor Issues", "#f9e2af", 75)
    C = ("C", "Significant Issues", "#fab387", 50)
    D = ("D", "Not Suitable", "#f38ba8", 0)
    
    @property
    def letter(self) -> str:
        return self.value[0]
    
    @property
    def status(self) -> str:
        return self.value[1]
    
    @property
    def color(self) -> str:
        return self.value[2]
    
    @property
    def threshold(self) -> int:
        return self.value[3]


@dataclass
class CriterionResult:
    """Result of evaluating a single scoring criterion."""
    criterion_id: str
    name: str
    category: str
    max_points: int
    earned_points: int
    percentage: float
    passed: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class PublishabilityReport:
    """Complete publishability assessment."""
    score: float                    # 0-100
    grade: Grade
    criteria_results: List[CriterionResult]
    blocking_issues: List[str]
    suggestions: List[str]
    
    @property
    def is_publishable(self) -> bool:
        return self.grade in (Grade.A, Grade.B)
    
    @property
    def summary(self) -> str:
        return f"{self.score:.0f}/100 (Grade {self.grade.letter}): {self.grade.status}"
    
    def get_by_category(self, category: str) -> List[CriterionResult]:
        return [r for r in self.criteria_results if r.category == category]


class PublishabilityScorer:
    """
    Calculates publication-readiness score.
    
    Evaluates calculations against multiple criteria:
    - Convergence (40%): cutoffs, k-points, SCF
    - Methodology (35%): XC, pseudo, smearing, spin
    - Documentation (25%): convergence tests, reproducibility
    
    Usage:
        scorer = PublishabilityScorer()
        report = scorer.score(input_data, output_data, convergence_tests)
        
        print(f"Score: {report.score}/100 ({report.grade.letter})")
    """
    
    def __init__(self):
        self.criteria = self._build_criteria()
    
    def _build_criteria(self) -> List[Dict]:
        """Build the scoring criteria."""
        return [
            # Convergence (40%)
            {
                "id": "CONV_ECUTWFC",
                "name": "Plane-wave cutoff",
                "category": "convergence",
                "weight": 15,
                "evaluator": self._eval_ecutwfc,
            },
            {
                "id": "CONV_KPOINTS",
                "name": "K-point sampling",
                "category": "convergence",
                "weight": 15,
                "evaluator": self._eval_kpoints,
            },
            {
                "id": "CONV_SCF",
                "name": "SCF convergence",
                "category": "convergence",
                "weight": 10,
                "evaluator": self._eval_scf,
            },
            
            # Methodology (35%)
            {
                "id": "METHOD_XC",
                "name": "XC functional",
                "category": "methodology",
                "weight": 10,
                "evaluator": self._eval_xc,
            },
            {
                "id": "METHOD_PSEUDO",
                "name": "Pseudopotentials",
                "category": "methodology",
                "weight": 10,
                "evaluator": self._eval_pseudo,
            },
            {
                "id": "METHOD_SMEAR",
                "name": "Smearing",
                "category": "methodology",
                "weight": 5,
                "evaluator": self._eval_smearing,
            },
            {
                "id": "METHOD_SPIN",
                "name": "Spin treatment",
                "category": "methodology",
                "weight": 5,
                "evaluator": self._eval_spin,
            },
            {
                "id": "METHOD_RELAX",
                "name": "Structure optimization",
                "category": "methodology",
                "weight": 5,
                "evaluator": self._eval_relaxation,
            },
            
            # Documentation (25%)
            {
                "id": "DOC_CONVERGENCE",
                "name": "Convergence tests",
                "category": "documentation",
                "weight": 10,
                "evaluator": self._eval_conv_tests,
            },
            {
                "id": "DOC_REPRODUCIBLE",
                "name": "Reproducibility",
                "category": "documentation",
                "weight": 10,
                "evaluator": self._eval_reproducibility,
            },
            {
                "id": "DOC_COMPLETE",
                "name": "Documentation",
                "category": "documentation",
                "weight": 5,
                "evaluator": self._eval_documentation,
            },
        ]
    
    def score(
        self,
        input_data,
        output_data = None,
        convergence_tests: Optional[Dict] = None,
    ) -> PublishabilityReport:
        """
        Calculate comprehensive publishability score.
        
        Args:
            input_data: PWInput object
            output_data: PWOutput object (optional)
            convergence_tests: Dict of convergence test results (optional)
            
        Returns:
            PublishabilityReport with score, grade, and details
        """
        results = []
        total_earned = 0
        total_max = 0
        blocking_issues = []
        suggestions = []
        
        for criterion in self.criteria:
            try:
                points, issues, sugg = criterion["evaluator"](
                    input_data, output_data, convergence_tests
                )
                earned = min(points, criterion["weight"])
            except Exception as e:
                earned = 0
                issues = [f"Could not evaluate: {e}"]
                sugg = []
            
            max_pts = criterion["weight"]
            total_earned += earned
            total_max += max_pts
            
            results.append(CriterionResult(
                criterion_id=criterion["id"],
                name=criterion["name"],
                category=criterion["category"],
                max_points=max_pts,
                earned_points=earned,
                percentage=(earned / max_pts * 100) if max_pts > 0 else 0,
                passed=earned >= max_pts * 0.8,
                issues=issues if isinstance(issues, list) else [issues] if issues else [],
                suggestions=sugg if isinstance(sugg, list) else [sugg] if sugg else [],
            ))
            
            if earned < max_pts * 0.5:
                blocking_issues.extend(issues if isinstance(issues, list) else [issues])
            suggestions.extend(sugg if isinstance(sugg, list) else [sugg])
        
        # Calculate overall score
        score = (total_earned / total_max * 100) if total_max > 0 else 0
        
        # Determine grade
        grade = Grade.D
        for g in [Grade.A, Grade.B, Grade.C, Grade.D]:
            if score >= g.threshold:
                grade = g
                break
        
        return PublishabilityReport(
            score=score,
            grade=grade,
            criteria_results=results,
            blocking_issues=blocking_issues,
            suggestions=list(set(suggestions)),  # Deduplicate
        )
    
    # --- Evaluators ---
    
    def _eval_ecutwfc(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate plane-wave cutoff."""
        issues = []
        suggestions = []
        points = 15
        
        ecutwfc = getattr(input_data, 'ecutwfc', None)
        if not ecutwfc:
            return 0, ["ecutwfc not specified"], ["Set ecutwfc parameter"]
        
        # Check if convergence test exists
        if conv_tests and 'ecutwfc' in conv_tests:
            if conv_tests['ecutwfc'].get('is_converged'):
                return 15, [], []
            else:
                return 10, ["Cutoff not fully converged"], ["Complete convergence test"]
        
        # Heuristic: award points based on value
        if ecutwfc >= 60:
            points = 12
        elif ecutwfc >= 40:
            points = 8
            suggestions.append("Run ecutwfc convergence test")
        else:
            points = 4
            issues.append(f"ecutwfc ({ecutwfc} Ry) may be too low")
            suggestions.append("Increase ecutwfc and run convergence test")
        
        return points, issues, suggestions
    
    def _eval_kpoints(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate k-point sampling."""
        issues = []
        suggestions = []
        
        kpoints = getattr(input_data, 'kpoints', None)
        if not kpoints:
            return 0, ["K-points not specified"], ["Add K_POINTS card"]
        
        if conv_tests and 'kpoints' in conv_tests:
            if conv_tests['kpoints'].get('is_converged'):
                return 15, [], []
            return 10, ["K-points not fully converged"], []
        
        mode = getattr(kpoints, 'mode', 'automatic')
        if mode == 'gamma':
            return 5, ["Gamma-only k-points"], ["Consider denser grid"]
        
        grid = getattr(kpoints, 'grid', (4, 4, 4))
        min_k = min(grid[:3]) if grid else 1
        
        if min_k >= 8:
            return 12, [], ["Run k-points convergence test for verification"]
        elif min_k >= 4:
            return 8, [], ["Run k-points convergence test"]
        else:
            return 4, [f"K-grid {grid} may be too coarse"], ["Increase k-grid density"]
    
    def _eval_scf(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate SCF convergence quality."""
        conv_thr = getattr(input_data, 'conv_thr', 1e-6)
        
        if conv_thr <= 1e-9:
            return 10, [], []
        elif conv_thr <= 1e-8:
            return 8, [], []
        elif conv_thr <= 1e-6:
            return 5, ["conv_thr could be tighter"], ["Set conv_thr = 1e-8"]
        else:
            return 2, ["conv_thr is too loose"], ["Set conv_thr = 1e-8"]
    
    def _eval_xc(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate XC functional choice."""
        input_dft = getattr(input_data, 'input_dft', 'PBE')
        
        # Standard functionals get full points
        standard_xc = ['pbe', 'pbesol', 'lda', 'pw', 'b3lyp', 'hse']
        if input_dft and input_dft.lower() in standard_xc:
            return 10, [], []
        
        return 7, [], ["Document XC functional choice in paper"]
    
    def _eval_pseudo(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate pseudopotential quality."""
        # Full implementation would check:
        # - Known library (SSSP, PseudoDojo, GBRV)
        # - Consistency across elements
        # For now, give partial credit
        return 7, [], ["Document pseudopotential source"]
    
    def _eval_smearing(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate smearing settings."""
        occupations = getattr(input_data, 'occupations', 'fixed')
        
        if occupations == 'fixed':
            return 5, [], []  # Fine for insulators
        
        degauss = getattr(input_data, 'degauss', 0.02)
        if degauss <= 0.02:
            return 5, [], []
        
        return 3, ["Large smearing width"], ["Reduce degauss"]
    
    def _eval_spin(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate spin treatment."""
        nspin = getattr(input_data, 'nspin', 1)
        
        # Check for magnetic elements
        # Simplified: assume OK for now
        return 5, [], []
    
    def _eval_relaxation(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate structure optimization quality."""
        calculation = getattr(input_data, 'calculation', 'scf')
        
        if calculation not in ('relax', 'vc-relax'):
            return 5, [], []  # Not applicable
        
        forc_conv_thr = getattr(input_data, 'forc_conv_thr', 1e-3)
        
        if forc_conv_thr <= 1e-4:
            return 5, [], []
        
        return 3, ["Force threshold may be loose"], ["Set forc_conv_thr = 1e-4"]
    
    def _eval_conv_tests(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate convergence test documentation."""
        if not conv_tests:
            return 2, ["No convergence tests found"], ["Run ecutwfc and k-points tests"]
        
        tested = list(conv_tests.keys())
        
        if 'ecutwfc' in tested and 'kpoints' in tested:
            return 10, [], []
        elif 'ecutwfc' in tested or 'kpoints' in tested:
            return 6, [f"Only {tested} tested"], ["Test both ecutwfc and k-points"]
        
        return 2, ["Insufficient convergence tests"], []
    
    def _eval_reproducibility(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate reproducibility information."""
        issues = []
        points = 10
        
        # Check for version info, pseudo sources, etc.
        # Simplified implementation
        points = 5
        issues.append("Document QE version")
        
        return points, issues, ["Include QE version and pseudo sources"]
    
    def _eval_documentation(self, input_data, output_data, conv_tests) -> Tuple[int, List, List]:
        """Evaluate overall documentation."""
        # Placeholder
        return 3, [], ["Document calculation parameters in paper methods section"]
