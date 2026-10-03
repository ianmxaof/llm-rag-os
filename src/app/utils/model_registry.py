"""
Powercore Model Registry
------------------------
Model catalog with automatic discovery and metadata management.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from .vault_config import (
    POWERCORE_MODELS, VAULT_ROOT_PATH, QUANTIZED_DIR, BASE_MODELS_DIR, FUSIONS_FINAL_DIR
)
from .vault_paths import get_models_by_category, get_model_metadata, format_file_size

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing Powercore models with auto-discovery."""
    
    def __init__(self):
        self._cached_models: Optional[Dict[str, List[Dict]]] = None
        self._cache_timestamp: Optional[float] = None
    
    def get_all_models(self, refresh: bool = False) -> Dict[str, List[Dict]]:
        """
        Get all available models, organized by category.
        
        Args:
            refresh: Force refresh of cached models
            
        Returns:
            Dictionary with model categories and lists
        """
        import time
        
        # Return cached if available and not refreshing
        if not refresh and self._cached_models is not None:
            return self._cached_models
        
        # Scan vault for models
        discovered = get_models_by_category()
        
        # Merge with predefined Powercore models
        all_models = {
            "powercore": [],
            "base": discovered.get("base", []),
            "fusions": discovered.get("fusions", []),
            "quantized": discovered.get("quantized", []),
            "discovered": discovered.get("discovered", []),
            "ollama": [],  # Will be populated from Ollama API
            "all": discovered.get("all", [])
        }
        
        # Add predefined Powercore models (check if files exist)
        for model_name, model_info in POWERCORE_MODELS.items():
            if model_name == "— Base Models —":
                continue
            
            model_path = model_info.get("path", "")
            if model_path:
                path_obj = Path(model_path)
                if path_obj.exists():
                    # Add metadata from file
                    file_metadata = get_model_metadata(model_path)
                    model_entry = {
                        **model_info,
                        **file_metadata,
                        "registry_name": model_name,
                        "category": "powercore"
                    }
                    all_models["powercore"].append(model_entry)
                    all_models["all"].append(model_entry)
        
        # Cache results
        self._cached_models = all_models
        self._cache_timestamp = time.time()
        
        return all_models
    
    def get_model_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get model information by name.
        
        Args:
            name: Model name or path
            
        Returns:
            Model info dictionary or None
        """
        all_models = self.get_all_models()
        
        # Check Powercore registry first
        for model in all_models.get("powercore", []):
            if model.get("registry_name") == name:
                return model
        
        # Check all models by path
        for category in ["base", "fusions", "quantized", "discovered", "all"]:
            for model in all_models.get(category, []):
                if model.get("name") == name or model.get("path") == name:
                    return model
        
        return None
    
    def get_model_display_list(self, include_ollama: bool = True) -> List[tuple]:
        """
        Get formatted list of models for Streamlit selectbox.
        
        Args:
            include_ollama: Include Ollama models in the list
            
        Returns:
            List of (display_name, model_identifier) tuples
        """
        all_models = self.get_all_models()
        display_list = []
        
        # Add Powercore models
        if all_models.get("powercore"):
            display_list.append(("— Powercore Fusions —", None))
            for model in all_models["powercore"]:
                registry_name = model.get("registry_name", model.get("name", "Unknown"))
                path = model.get("path", "")
                if path:
                    display_list.append((registry_name, path))
        
        # Add discovered quantized models
        if all_models.get("quantized"):
            display_list.append(("— Quantized Models —", None))
            for model in all_models["quantized"]:
                name = model.get("name", "Unknown")
                path = model.get("path", "")
                if path:
                    display_list.append((f"📦 {name}", path))
        
        # Add base models
        if all_models.get("base"):
            display_list.append(("— Base Models —", None))
            for model in all_models["base"]:
                name = model.get("name", "Unknown")
                path = model.get("path", "")
                if path:
                    display_list.append((f"📚 {name}", path))
        
        # Add fusions
        if all_models.get("fusions"):
            display_list.append(("— Custom Fusions —", None))
            for model in all_models["fusions"]:
                name = model.get("name", "Unknown")
                path = model.get("path", "")
                if path:
                    display_list.append((f"🔥 {name}", path))
        
        # Add discovered models (models found in vault root or other locations)
        if all_models.get("discovered"):
            display_list.append(("— Discovered Models —", None))
            for model in all_models["discovered"]:
                name = model.get("name", "Unknown")
                path = model.get("path", "")
                if path:
                    # Add quantization info if available for better identification
                    quant = model.get("quantization", "")
                    size = model.get("size", "")
                    display_name = name
                    if quant:
                        display_name = f"{name} ({quant})"
                    elif size != "unknown":
                        display_name = f"{name} [{size}]"
                    display_list.append((f"🔍 {display_name}", path))
        
        return display_list
    
    def refresh_cache(self):
        """Force refresh of model cache."""
        self._cached_models = None
        self._cache_timestamp = None
        return self.get_all_models(refresh=True)


# Global registry instance
_registry_instance: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    """Get or create the global model registry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = ModelRegistry()
    return _registry_instance


def get_model_info(model_path: str) -> Dict[str, Any]:
    """
    Get detailed information about a model.
    
    Args:
        model_path: Path to model file or model name
        
    Returns:
        Dictionary with model information
    """
    registry = get_model_registry()
    model_info = registry.get_model_by_name(model_path)
    
    if model_info:
        return model_info
    
    # Fallback: try to get metadata from path
    path_obj = Path(model_path)
    if path_obj.exists():
        return get_model_metadata(model_path)
    
    return {
        "name": Path(model_path).stem if path_obj.suffix else model_path,
        "path": model_path,
        "exists": False
    }

