"""
Smart Pseudopotential Logic.
Analyzes project requirements and manages pseudopotential health.
"""

from typing import List, Dict, Tuple
from pathlib import Path
from ..core.pseudo_manager import PseudopotentialManager, RECOMMENDED_CUTOFFS

class SmartPseudoManager:
    """Intelligent manager for project pseudopotentials."""
    
    def __init__(self):
        # Try to find the project's pseudo/ folder (next to the qe-gui root)
        project_pseudo = Path(__file__).resolve().parent.parent.parent.parent / "pseudo"
        if project_pseudo.exists():
            self.manager = PseudopotentialManager(pseudo_dir=project_pseudo)
        else:
            self.manager = PseudopotentialManager()
        
    def analyze_coverage(self, elements: List[str]) -> Dict:
        """
        Analyze pseudopotential coverage for a set of elements.
        
        Returns dict with:
        - missing: List of elements needing download
        - installed: List of elements ready to use
        - recommendations: Dict of {element: (ecutwfc, ecutrho)}
        """
        missing = []
        installed = []
        recommendations = {}
        
        for el in elements:
            if self.manager.is_installed(el):
                installed.append(el)
            else:
                missing.append(el)
            
            # Helper logic for cutoffs (defaults provided by pseudo_manager constant)
            if el in RECOMMENDED_CUTOFFS:
                recommendations[el] = RECOMMENDED_CUTOFFS[el]
            else:
                recommendations[el] = (40.0, 320.0) # Conservative default
                
        return {
            "missing": missing,
            "installed": installed,
            "recommendations": recommendations,
            "status": "ok" if not missing else "incomplete"
        }

    def auto_fix_project(self, elements: List[str], progress_callback=None) -> bool:
        """
        Download all missing pseudopotentials for the project.
        """
        missing = [el for el in elements if not self.manager.is_installed(el)]
        
        if not missing:
            return True
        
        total = len(missing)
        for i, el in enumerate(missing):
            if progress_callback:
                progress_callback(el, int((i / total) * 100))
            
            success = self.manager.download_pseudo(el)
            if not success:
                return False
                
        if progress_callback:
            progress_callback("Done", 100)
            
        return True
