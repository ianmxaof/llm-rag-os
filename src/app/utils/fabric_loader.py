"""
Fabric Pattern Loader
---------------------
Loads and registers Fabric patterns from danielmiessler/fabric repository.
Supports official patterns, Powercore-optimized patterns, and auto-generated resonance patterns.
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
import subprocess
import shutil

logger = logging.getLogger(__name__)

# Fabric patterns directory structure
FABRIC_PATTERNS_DIR = Path("fabric_patterns")
FABRIC_OFFICIAL_DIR = FABRIC_PATTERNS_DIR / "official"
FABRIC_POWERCORE_DIR = FABRIC_PATTERNS_DIR / "powercore"
FABRIC_RESONANCE_DIR = FABRIC_PATTERNS_DIR / "resonance"

# Ensure directories exist
FABRIC_PATTERNS_DIR.mkdir(parents=True, exist_ok=True)
FABRIC_OFFICIAL_DIR.mkdir(parents=True, exist_ok=True)
FABRIC_POWERCORE_DIR.mkdir(parents=True, exist_ok=True)
FABRIC_RESONANCE_DIR.mkdir(parents=True, exist_ok=True)

FABRIC_REPO_URL = "https://github.com/danielmiessler/fabric.git"


class FabricLoader:
    """Loads and manages Fabric patterns."""
    
    def __init__(self):
        self.patterns: Dict[str, Dict] = {}
        self._load_all_patterns()
    
    def _load_all_patterns(self):
        """Load all patterns from all directories."""
        self.patterns = {}
        
        # Load official patterns
        if FABRIC_OFFICIAL_DIR.exists():
            self._load_patterns_from_dir(FABRIC_OFFICIAL_DIR, "official")
        
        # Load Powercore patterns
        if FABRIC_POWERCORE_DIR.exists():
            self._load_patterns_from_dir(FABRIC_POWERCORE_DIR, "powercore")
        
        # Load resonance patterns
        if FABRIC_RESONANCE_DIR.exists():
            self._load_patterns_from_dir(FABRIC_RESONANCE_DIR, "resonance")
    
    def _load_patterns_from_dir(self, directory: Path, category: str):
        """Load all .yaml files from a directory."""
        for yaml_file in directory.glob("*.yaml"):
            try:
                pattern_data = yaml.safe_load(yaml_file.read_text(encoding='utf-8'))
                if pattern_data:
                    pattern_name = pattern_data.get('name', yaml_file.stem)
                    pattern_key = f"!{pattern_name}"
                    self.patterns[pattern_key] = {
                        **pattern_data,
                        'category': category,
                        'file_path': str(yaml_file)
                    }
                    logger.debug(f"Loaded Fabric pattern: {pattern_key} from {category}")
            except Exception as e:
                logger.error(f"Error loading pattern {yaml_file}: {e}")
    
    def download_official_patterns(self, force: bool = False) -> bool:
        """
        Clone/download Fabric patterns from GitHub.
        
        Args:
            force: If True, re-clone even if directory exists
            
        Returns:
            True if successful
        """
        if FABRIC_OFFICIAL_DIR.exists() and not force:
            # Check if it's a git repo
            if (FABRIC_OFFICIAL_DIR / ".git").exists():
                logger.info("Fabric patterns already cloned, skipping download")
                return True
        
        try:
            # Clone the repo
            if FABRIC_OFFICIAL_DIR.exists():
                shutil.rmtree(FABRIC_OFFICIAL_DIR)
            
            logger.info(f"Cloning Fabric patterns from {FABRIC_REPO_URL}")
            result = subprocess.run(
                ["git", "clone", FABRIC_REPO_URL, str(FABRIC_OFFICIAL_DIR / "fabric")],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                # Move patterns from fabric/patterns to official/
                source_patterns = FABRIC_OFFICIAL_DIR / "fabric" / "patterns"
                if source_patterns.exists():
                    # Copy patterns
                    for pattern_file in source_patterns.glob("*.yaml"):
                        shutil.copy2(pattern_file, FABRIC_OFFICIAL_DIR / pattern_file.name)
                    
                    logger.info(f"Downloaded {len(list(source_patterns.glob('*.yaml')))} official patterns")
                
                # Reload patterns
                self._load_all_patterns()
                return True
            else:
                logger.error(f"Failed to clone Fabric repo: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("Timeout cloning Fabric repo")
            return False
        except Exception as e:
            logger.error(f"Error downloading Fabric patterns: {e}")
            return False
    
    def get_pattern(self, pattern_name: str) -> Optional[Dict]:
        """
        Get a pattern by name (with or without ! prefix).
        
        Args:
            pattern_name: Pattern name (e.g., "extract_resonance" or "!extract_resonance")
            
        Returns:
            Pattern dictionary or None
        """
        if not pattern_name.startswith("!"):
            pattern_name = f"!{pattern_name}"
        
        return self.patterns.get(pattern_name)
    
    def list_patterns(self, category: Optional[str] = None) -> List[str]:
        """
        List all available pattern names.
        
        Args:
            category: Optional category filter ("official", "powercore", "resonance")
            
        Returns:
            List of pattern names (with ! prefix)
        """
        if category:
            return [
                name for name, pattern in self.patterns.items()
                if pattern.get('category') == category
            ]
        return list(self.patterns.keys())
    
    def get_pattern_system_prompt(self, pattern_name: str) -> Optional[str]:
        """Get the system prompt from a pattern."""
        pattern = self.get_pattern(pattern_name)
        if pattern:
            return pattern.get('system_prompt', '')
        return None
    
    def inject_pattern_into_prompt(self, pattern_name: str, user_input: str) -> Optional[str]:
        """
        Inject a Fabric pattern into a prompt.
        
        Args:
            pattern_name: Pattern name (e.g., "!extract_resonance")
            user_input: User input text
            
        Returns:
            Combined prompt or None if pattern not found
        """
        pattern = self.get_pattern(pattern_name)
        if not pattern:
            return None
        
        system_prompt = pattern.get('system_prompt', '')
        user_prompt_template = pattern.get('user_prompt', '{{input}}')
        
        # Replace {{input}} placeholder
        user_prompt = user_prompt_template.replace('{{input}}', user_input)
        
        # Combine system and user prompts
        combined = f"{system_prompt}\n\n{user_prompt}"
        return combined
    
    def save_resonance_pattern(self, chain_data: Dict, combo_score: float, resonance_count: int) -> bool:
        """
        Auto-convert a 100% combo chain to a Fabric pattern.
        
        Args:
            chain_data: Chain configuration
            combo_score: Combo score (should be 100.0)
            resonance_count: Resonance count for naming
            
        Returns:
            True if saved successfully
        """
        if combo_score < 100.0:
            return False
        
        try:
            # Create pattern from chain
            pattern_name = f"resonance_{resonance_count}__{chain_data.get('name', 'chain').replace(' ', '_').lower()}"
            
            # Extract system prompt from first step or create one
            steps = chain_data.get('steps', [])
            if steps:
                system_prompt = steps[0].get('prompt', '')
            else:
                system_prompt = f"Powercore resonance pattern from {chain_data.get('name', 'chain')}"
            
            pattern_data = {
                'name': pattern_name,
                'description': f"Auto-generated from {chain_data.get('name', 'chain')} (combo: {combo_score}%)",
                'author': 'Powercore Mind',
                'version': '1.0',
                'license': 'MIT',
                'system_prompt': system_prompt,
                'user_prompt': '{{input}}',
                'output_format': '{{response}}',
                'metadata': {
                    'combo_score': combo_score,
                    'resonance_count': resonance_count,
                    'chain_name': chain_data.get('name', ''),
                    'created': str(Path(__file__).stat().st_mtime)
                }
            }
            
            # Save to resonance directory
            pattern_path = FABRIC_RESONANCE_DIR / f"{pattern_name}.yaml"
            pattern_path.write_text(
                yaml.dump(pattern_data, default_flow_style=False, sort_keys=False),
                encoding='utf-8'
            )
            
            # Reload patterns
            self._load_all_patterns()
            
            logger.info(f"Saved resonance pattern: {pattern_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving resonance pattern: {e}")
            return False


# Global loader instance
_fabric_loader_instance: Optional[FabricLoader] = None


def get_fabric_loader() -> FabricLoader:
    """Get or create the global Fabric loader instance."""
    global _fabric_loader_instance
    if _fabric_loader_instance is None:
        _fabric_loader_instance = FabricLoader()
    return _fabric_loader_instance

