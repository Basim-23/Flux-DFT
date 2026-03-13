"""
Configuration management for FluxDFT.
Handles loading/saving user preferences and application settings.
"""

import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List

from .constants import DEFAULT_QE_PATH, DEFAULT_PSEUDO_PATH, DEFAULT_WORK_DIR, APP_NAME


@dataclass
class RemoteServer:
    """Configuration for a remote HPC server."""
    name: str
    hostname: str
    username: str
    port: int = 22
    key_file: Optional[str] = None
    qe_path: str = "/usr/local/bin"
    work_dir: str = "/scratch"
    scheduler: str = "slurm"
    queue: str = "default"
    

@dataclass
class AppConfig:
    """Application configuration."""
    # Paths
    qe_path: str = str(DEFAULT_QE_PATH)
    pseudo_dir: str = str(DEFAULT_PSEUDO_PATH)
    work_dir: str = str(DEFAULT_WORK_DIR)
    
    # License
    license_key: str = ""
    license_email: str = ""
    
    # UI preferences
    theme: str = "dark"
    font_size: int = 12
    show_tooltips: bool = True
    show_welcome: bool = True
    recent_files: List[str] = field(default_factory=list)
    max_recent_files: int = 10
    
    # Calculation defaults
    default_ecutwfc: float = 40.0
    default_ecutrho: float = 320.0
    default_kpoints: List[int] = field(default_factory=lambda: [4, 4, 4])
    
    # Materials Project
    mp_api_key: str = ""
    mp_enabled: bool = True
    mp_cache_days: int = 30
    
    # Cloud (Supabase)
    supabase_url: str = ""
    supabase_key: str = ""
    supabase_enabled: bool = True
    
    # AI Assistant (FluxAI)
    openai_api_key: str = ""
    ai_model: str = "gpt-3.5-turbo"
    ai_enabled: bool = True
    
    # Auto-graphing
    auto_generate_plots: bool = True
    auto_navigate_to_plots: bool = True
    plot_format: str = "png"
    plot_dpi: int = 300
    
    # Remote servers
    remote_servers: List[Dict] = field(default_factory=list)
    
    # Window state
    window_geometry: Optional[str] = None
    window_state: Optional[str] = None


class Config:
    """
    Configuration manager for FluxDFT.
    Handles persistent storage of user preferences.
    """
    
    CONFIG_DIR = Path.home() / ".config" / "fluxdft"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    LICENSE_FILE = CONFIG_DIR / "license.key"
    
    def __init__(self):
        self.config = AppConfig()
        self._ensure_config_dir()
        self.load()
    
    def _ensure_config_dir(self) -> None:
        """Create configuration directory if it doesn't exist."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    
    def load(self) -> None:
        """Load configuration from disk."""
        if self.CONFIG_FILE.exists():
            try:
                with open(self.CONFIG_FILE, "r") as f:
                    data = json.load(f)
                
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                        
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Could not load config: {e}")
    
    def save(self) -> None:
        """Save configuration to disk."""
        try:
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(asdict(self.config), f, indent=2)
        except IOError as e:
            print(f"Warning: Could not save config: {e}")
    
    def get(self, key: str, default=None):
        """Get a configuration value."""
        return getattr(self.config, key, default)
    
    def set(self, key: str, value) -> None:
        """Set a configuration value and save."""
        if hasattr(self.config, key):
            setattr(self.config, key, value)
            self.save()
            
    def __getattr__(self, name):
        """Delegate attribute access to AppConfig."""
        if hasattr(self.config, name):
            return getattr(self.config, name)
        raise AttributeError(f"'Config' object has no attribute '{name}'")
    
    def add_recent_file(self, filepath: str) -> None:
        """Add a file to the recent files list."""
        files = self.config.recent_files
        
        if filepath in files:
            files.remove(filepath)
        
        files.insert(0, filepath)
        self.config.recent_files = files[:self.config.max_recent_files]
        self.save()
    
    def get_remote_servers(self) -> List[RemoteServer]:
        """Get list of configured remote servers."""
        return [RemoteServer(**s) for s in self.config.remote_servers]
    
    def add_remote_server(self, server: RemoteServer) -> None:
        """Add a remote server configuration."""
        self.config.remote_servers.append(asdict(server))
        self.save()
    
    def remove_remote_server(self, name: str) -> None:
        """Remove a remote server by name."""
        self.config.remote_servers = [
            s for s in self.config.remote_servers if s.get("name") != name
        ]
        self.save()
    
    @property
    def qe_path(self) -> Path:
        """Get Quantum ESPRESSO executable path."""
        return Path(self.config.qe_path)
    
    @property
    def pseudo_dir(self) -> Path:
        """Get pseudopotential directory."""
        return Path(self.config.pseudo_dir)
    
    @property
    def work_dir(self) -> Path:
        """Get working directory for projects."""
        path = Path(self.config.work_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    @property
    def is_licensed(self) -> bool:
        """Check if the software is licensed."""
        return bool(self.config.license_key)
