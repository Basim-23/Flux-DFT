"""
Pseudopotential Manager for FluxDFT.

Downloads, validates, and manages pseudopotentials from standard libraries:
- SSSP (Standard Solid State Pseudopotentials)
- PseudoDojo
- QE Standard Library
"""

import os
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from enum import Enum
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


class PseudoLibrary(Enum):
    """Supported pseudopotential libraries."""
    SSSP_EFFICIENCY = "sssp_efficiency"
    SSSP_PRECISION = "sssp_precision"
    PSEUDODOJO_NC = "pseudodojo_nc"
    PSEUDODOJO_PAW = "pseudodojo_paw"


# SSSP Base URL from Materials Cloud
# Reference: https://legacy.materialscloud.org/discover/sssp/table/efficiency
SSSP_BASE_URL = "https://legacy.materialscloud.org/sssplibrary/static/sssplibrary/upf_files"

# Common pseudopotential naming patterns (SSSP Efficiency v1.3.0)
PSEUDO_PATTERNS = {
    'H': 'H.pbe-rrkjus_psl.1.0.0.UPF',
    'He': 'He.pbe-kjpaw_psl.1.0.0.UPF',
    'Li': 'Li.pbe-s-kjpaw_psl.1.0.0.UPF',
    'Be': 'Be.pbe-n-kjpaw_psl.1.0.0.UPF',
    'B': 'B.pbe-n-kjpaw_psl.1.0.0.UPF',
    'C': 'C.pbe-n-kjpaw_psl.1.0.0.UPF',
    'N': 'N.pbe-n-kjpaw_psl.1.0.0.UPF',
    'O': 'O.pbe-n-kjpaw_psl.1.0.0.UPF',
    'F': 'F.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Ne': 'Ne.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Na': 'Na.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Mg': 'Mg.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Al': 'Al.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Si': 'Si.pbe-n-kjpaw_psl.1.0.0.UPF',
    'P': 'P.pbe-n-kjpaw_psl.1.0.0.UPF',
    'S': 'S.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Cl': 'Cl.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Ar': 'Ar.pbe-n-kjpaw_psl.1.0.0.UPF',
    'K': 'K.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ca': 'Ca.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Sc': 'Sc.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ti': 'Ti.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'V': 'V.pbe-spnl-kjpaw_psl.1.0.0.UPF',
    'Cr': 'Cr.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Mn': 'Mn.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Fe': 'Fe.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Co': 'Co.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ni': 'Ni.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Cu': 'Cu.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Zn': 'Zn.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Ga': 'Ga.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Ge': 'Ge.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'As': 'As.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Se': 'Se.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Br': 'Br.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Kr': 'Kr.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Rb': 'Rb.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Sr': 'Sr.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Y': 'Y.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Zr': 'Zr.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Nb': 'Nb.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Mo': 'Mo.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ru': 'Ru.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Rh': 'Rh.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Pd': 'Pd.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ag': 'Ag.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Cd': 'Cd.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'In': 'In.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Sn': 'Sn.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Sb': 'Sb.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Te': 'Te.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'I': 'I.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Xe': 'Xe.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Cs': 'Cs.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ba': 'Ba.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'La': 'La.pbe-spfn-kjpaw_psl.1.0.0.UPF',
    'Hf': 'Hf.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ta': 'Ta.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'W': 'W.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Re': 'Re.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Os': 'Os.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Ir': 'Ir.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Pt': 'Pt.pbe-spn-kjpaw_psl.1.0.0.UPF',
    'Au': 'Au.pbe-n-kjpaw_psl.1.0.0.UPF',
    'Pb': 'Pb.pbe-dn-kjpaw_psl.1.0.0.UPF',
    'Bi': 'Bi.pbe-dn-kjpaw_psl.1.0.0.UPF',
}

# Recommended cutoffs (ecutwfc, ecutrho) from SSSP Efficiency
RECOMMENDED_CUTOFFS: Dict[str, Tuple[float, float]] = {
    'H': (60, 480), 'He': (55, 440), 'Li': (40, 320), 'Be': (50, 400),
    'B': (50, 400), 'C': (45, 360), 'N': (80, 640), 'O': (75, 600),
    'F': (90, 720), 'Ne': (60, 480), 'Na': (66, 528), 'Mg': (50, 400),
    'Al': (35, 280), 'Si': (40, 320), 'P': (45, 360), 'S': (47, 376),
    'Cl': (50, 400), 'Ar': (50, 400), 'K': (60, 480), 'Ca': (45, 360),
    'Sc': (55, 440), 'Ti': (75, 600), 'V': (55, 440), 'Cr': (70, 560),
    'Mn': (90, 720), 'Fe': (90, 720), 'Co': (90, 720), 'Ni': (95, 760),
    'Cu': (55, 440), 'Zn': (50, 400), 'Ga': (80, 640), 'Ge': (50, 400),
    'As': (50, 400), 'Se': (50, 400), 'Br': (50, 400), 'Kr': (55, 440),
    'Rb': (60, 480), 'Sr': (45, 360), 'Y': (55, 440), 'Zr': (45, 360),
    'Nb': (60, 480), 'Mo': (60, 480), 'Ru': (60, 480), 'Rh': (60, 480),
    'Pd': (55, 440), 'Ag': (55, 440), 'Cd': (50, 400), 'In': (65, 520),
    'Sn': (70, 560), 'Sb': (55, 440), 'Te': (50, 400), 'I': (50, 400),
    'Xe': (60, 480), 'Cs': (60, 480), 'Ba': (45, 360), 'La': (60, 480),
    'Hf': (55, 440), 'Ta': (55, 440), 'W': (55, 440), 'Re': (60, 480),
    'Os': (60, 480), 'Ir': (55, 440), 'Pt': (55, 440), 'Au': (55, 440),
    'Pb': (55, 440), 'Bi': (55, 440),
}


@dataclass
class PseudopotentialInfo:
    """Information about a pseudopotential file."""
    element: str
    filename: str
    library: PseudoLibrary
    ecutwfc: float
    ecutrho: float
    functional: str = "PBE"
    type: str = "PAW"  # PAW, NC, US
    path: Optional[Path] = None
    is_installed: bool = False


class PseudopotentialManager:
    """Manages pseudopotential downloads and validation."""
    
    def __init__(self, pseudo_dir: Optional[Path] = None):
        """
        Initialize the manager.
        
        Args:
            pseudo_dir: Directory to store pseudopotentials.
                       Defaults to ~/.fluxdft/pseudopotentials
        """
        if pseudo_dir is None:
            pseudo_dir = Path.home() / ".fluxdft" / "pseudopotentials"
        
        self.pseudo_dir = Path(pseudo_dir)
        self.pseudo_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, PseudopotentialInfo] = {}
        self._scan_installed()
    
    def _scan_installed(self):
        """Scan pseudo_dir for installed pseudopotentials."""
        for upf_file in self.pseudo_dir.glob("*.UPF"):
            element = upf_file.stem.split(".")[0]
            if element.isalpha():
                cuts = RECOMMENDED_CUTOFFS.get(element, (50, 400))
                self._cache[element] = PseudopotentialInfo(
                    element=element,
                    filename=upf_file.name,
                    library=PseudoLibrary.SSSP_EFFICIENCY,
                    ecutwfc=cuts[0],
                    ecutrho=cuts[1],
                    path=upf_file,
                    is_installed=True
                )
    
    def get_info(self, element: str) -> Optional[PseudopotentialInfo]:
        """Get info for an element's pseudopotential."""
        return self._cache.get(element)
    
    def is_installed(self, element: str) -> bool:
        """Check if pseudopotential is installed for element."""
        info = self._cache.get(element)
        return info is not None and info.is_installed
    
    def get_path(self, element: str) -> Optional[Path]:
        """Get path to installed pseudopotential."""
        info = self._cache.get(element)
        if info and info.path and info.path.exists():
            return info.path
        return None
    
    def get_recommended_cutoffs(self, elements: List[str]) -> Tuple[float, float]:
        """
        Get recommended ecutwfc and ecutrho for a set of elements.
        
        Returns the maximum of individual element recommendations.
        """
        max_wfc = 50.0
        max_rho = 400.0
        
        for el in elements:
            cuts = RECOMMENDED_CUTOFFS.get(el, (50, 400))
            max_wfc = max(max_wfc, cuts[0])
            max_rho = max(max_rho, cuts[1])
        
        return (max_wfc, max_rho)
    
    def download_pseudo(
        self, 
        element: str, 
        library: PseudoLibrary = PseudoLibrary.SSSP_EFFICIENCY,
        progress_callback=None
    ) -> bool:
        """
        Download pseudopotential for an element from Materials Cloud SSSP.
        
        Args:
            element: Element symbol
            library: Which library to download from
            progress_callback: Optional callback(percent: int, message: str)
        
        Returns:
            True if successful, False otherwise
        """
        if element not in PSEUDO_PATTERNS:
            logger.warning(f"No pseudopotential pattern known for {element}")
            return False
        
        filename = PSEUDO_PATTERNS[element]
        dest_path = self.pseudo_dir / filename
        
        if dest_path.exists():
            logger.info(f"Pseudopotential for {element} already exists")
            cuts = RECOMMENDED_CUTOFFS.get(element, (50, 400))
            self._cache[element] = PseudopotentialInfo(
                element=element,
                filename=filename,
                library=library,
                ecutwfc=cuts[0],
                ecutrho=cuts[1],
                path=dest_path,
                is_installed=True
            )
            return True
        
        # Download from Materials Cloud SSSP
        try:
            if progress_callback:
                progress_callback(10, f"Downloading {filename}...")
            
            url = f"{SSSP_BASE_URL}/{filename}"
            logger.info(f"Downloading from: {url}")
            
            # Download with progress
            urllib.request.urlretrieve(url, dest_path)
            
            cuts = RECOMMENDED_CUTOFFS.get(element, (50, 400))
            self._cache[element] = PseudopotentialInfo(
                element=element,
                filename=filename,
                library=library,
                ecutwfc=cuts[0],
                ecutrho=cuts[1],
                path=dest_path,
                is_installed=True
            )
            
            if progress_callback:
                progress_callback(100, f"Downloaded {filename}")
            
            logger.info(f"Successfully downloaded {filename}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return False
    
    def download_for_structure(
        self,
        elements: List[str],
        library: PseudoLibrary = PseudoLibrary.SSSP_EFFICIENCY,
        progress_callback=None
    ) -> Dict[str, bool]:
        """
        Download pseudopotentials for all elements in a structure.
        
        Returns dict mapping element to success status.
        """
        results = {}
        total = len(elements)
        
        for i, element in enumerate(elements):
            if progress_callback:
                pct = int((i / total) * 100)
                progress_callback(pct, f"Processing {element}...")
            
            results[element] = self.download_pseudo(element, library)
        
        if progress_callback:
            progress_callback(100, "Complete")
        
        return results
    
    def validate_upf(self, path: Path) -> Tuple[bool, str]:
        """
        Validate a UPF pseudopotential file.
        
        Returns (is_valid, message).
        """
        if not path.exists():
            return False, "File not found"
        
        try:
            content = path.read_text(errors='ignore')
            
            # Check for UPF markers
            if '<UPF version="' in content or 'PP_HEADER' in content:
                return True, "Valid UPF format"
            elif content.startswith("!"):
                return True, "Placeholder file"
            else:
                return False, "Unrecognized format"
                
        except Exception as e:
            return False, f"Error reading file: {e}"
    
    def list_available(self) -> List[str]:
        """List elements with known pseudopotential patterns."""
        return list(PSEUDO_PATTERNS.keys())
    
    def list_installed(self) -> List[str]:
        """List elements with installed pseudopotentials."""
        return [el for el, info in self._cache.items() if info.is_installed]
