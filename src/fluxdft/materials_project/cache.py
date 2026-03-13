"""
Local cache for Materials Project queries.
"""

import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Any


class MPCache:
    """
    Local cache for MP queries.
    
    - Reduces API calls
    - Enables offline comparisons after initial query
    - Expires after configurable number of days
    """
    
    DEFAULT_EXPIRY_DAYS = 30
    
    def __init__(self, cache_dir: Path, expiry_days: int = None):
        """
        Initialize the cache.
        
        Args:
            cache_dir: Directory to store cache files
            expiry_days: Days before cache entries expire
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.expiry_days = expiry_days or self.DEFAULT_EXPIRY_DAYS
        
        self.index_file = self.cache_dir / "index.json"
        self.index: Dict[str, Dict] = {}
        self._load_index()
    
    def _load_index(self):
        """Load the cache index."""
        if self.index_file.exists():
            try:
                with open(self.index_file) as f:
                    self.index = json.load(f)
            except Exception:
                self.index = {}
    
    def _save_index(self):
        """Save the cache index."""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f, indent=2)
        except Exception:
            pass
    
    def _formula_key(self, formula: str) -> str:
        """Generate cache key for formula."""
        # Normalize formula
        return formula.replace(" ", "").lower()
    
    def _is_expired(self, timestamp_str: str) -> bool:
        """Check if a cache entry is expired."""
        try:
            timestamp = datetime.fromisoformat(timestamp_str)
            expiry = timestamp + timedelta(days=self.expiry_days)
            return datetime.now() > expiry
        except Exception:
            return True
    
    def get_formula(self, formula: str) -> Optional[List]:
        """
        Get cached results for formula.
        
        Returns list of MPMaterial dicts if cached and valid, None otherwise.
        """
        key = self._formula_key(formula)
        
        if key not in self.index:
            return None
        
        entry = self.index[key]
        
        if self._is_expired(entry.get("timestamp", "")):
            return None
        
        # Load from file
        cache_file = self.cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file) as f:
                data = json.load(f)
            
            # Import here to avoid circular imports
            from .client import MPMaterial
            return [MPMaterial.from_dict(m) for m in data]
        except Exception:
            return None
    
    def set_formula(self, formula: str, materials: List):
        """
        Cache results for formula.
        
        Args:
            formula: Chemical formula
            materials: List of MPMaterial objects
        """
        key = self._formula_key(formula)
        
        # Save to file
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, 'w') as f:
                json.dump([m.to_dict() for m in materials], f, indent=2)
        except Exception:
            return
        
        # Update index
        self.index[key] = {
            "formula": formula,
            "timestamp": datetime.now().isoformat(),
            "count": len(materials),
        }
        self._save_index()
    
    def clear(self):
        """Clear all cached data."""
        import shutil
        
        try:
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self.index = {}
        except Exception:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_entries = len(self.index)
        expired = sum(
            1 for entry in self.index.values()
            if self._is_expired(entry.get("timestamp", ""))
        )
        
        return {
            "total_entries": total_entries,
            "valid_entries": total_entries - expired,
            "expired_entries": expired,
            "cache_dir": str(self.cache_dir),
        }
