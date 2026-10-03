"""
Powercore Vault Path Helpers
-----------------------------
Utility functions for scanning, validating, and managing model paths in the vault.
"""

import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from .vault_config import (
    VAULT_ROOT_PATH, BASE_MODELS_DIR, QUANTIZED_DIR, FUSIONS_FINAL_DIR,
    MODEL_SIZE_70B, MODEL_SIZE_13B, MODEL_SIZE_8B, MODEL_SIZE_EMBEDDINGS
)


def scan_gguf_files(directory: Path, recursive: bool = True) -> List[Path]:
    """
    Scan a directory for GGUF files.
    
    Args:
        directory: Directory to scan
        recursive: If True, scan subdirectories recursively
        
    Returns:
        List of Path objects to GGUF files
    """
    gguf_files = []
    
    if not directory.exists():
        return gguf_files
    
    if recursive:
        pattern = "**/*.gguf"
    else:
        pattern = "*.gguf"
    
    gguf_files = list(directory.glob(pattern))
    return sorted(gguf_files)


def get_models_by_category() -> Dict[str, List[Dict[str, any]]]:
    """
    Get all available models organized by category.
    
    Returns:
        Dictionary with keys: 'base', 'fusions', 'quantized', 'discovered', 'all'
        Each value is a list of model info dictionaries
    """
    models = {
        "base": [],
        "fusions": [],
        "quantized": [],
        "discovered": [],
        "all": []
    }
    
    # Track all known paths to avoid duplicates when scanning vault root
    known_paths = set()
    
    # Scan base models
    if BASE_MODELS_DIR.exists():
        for size_dir in [MODEL_SIZE_70B, MODEL_SIZE_13B, MODEL_SIZE_8B, MODEL_SIZE_EMBEDDINGS]:
            size_path = BASE_MODELS_DIR / size_dir
            for gguf_file in scan_gguf_files(size_path, recursive=False):
                path_str = str(gguf_file)
                known_paths.add(path_str)
                model_info = {
                    "path": path_str,
                    "name": gguf_file.stem,
                    "size": size_dir,
                    "category": "base",
                    "file_size": gguf_file.stat().st_size if gguf_file.exists() else 0
                }
                models["base"].append(model_info)
                models["all"].append(model_info)
    
    # Scan fusions
    if FUSIONS_FINAL_DIR.exists():
        for gguf_file in scan_gguf_files(FUSIONS_FINAL_DIR, recursive=True):
            path_str = str(gguf_file)
            known_paths.add(path_str)
            # Try to infer size from parent directory
            parent = gguf_file.parent
            size = MODEL_SIZE_13B  # Default
            if MODEL_SIZE_70B in str(parent):
                size = MODEL_SIZE_70B
            elif MODEL_SIZE_8B in str(parent):
                size = MODEL_SIZE_8B
            
            model_info = {
                "path": path_str,
                "name": gguf_file.stem,
                "size": size,
                "category": "fusion",
                "file_size": gguf_file.stat().st_size if gguf_file.exists() else 0
            }
            models["fusions"].append(model_info)
            models["all"].append(model_info)
    
    # Scan quantized models
    if QUANTIZED_DIR.exists():
        for size_dir in [MODEL_SIZE_70B, MODEL_SIZE_13B, MODEL_SIZE_8B]:
            size_path = QUANTIZED_DIR / size_dir
            for gguf_file in scan_gguf_files(size_path, recursive=False):
                path_str = str(gguf_file)
                known_paths.add(path_str)
                model_info = {
                    "path": path_str,
                    "name": gguf_file.stem,
                    "size": size_dir,
                    "category": "quantized",
                    "file_size": gguf_file.stat().st_size if gguf_file.exists() else 0
                }
                models["quantized"].append(model_info)
                models["all"].append(model_info)
    
    # Scan vault root recursively for any other GGUF files not already categorized
    # This catches models placed directly in .lmstudio\models or other subdirectories
    if VAULT_ROOT_PATH.exists():
        for gguf_file in scan_gguf_files(VAULT_ROOT_PATH, recursive=True):
            path_str = str(gguf_file)
            
            # Skip if already in a known category
            if path_str in known_paths:
                continue
            
            # Skip if it's in a powercore subdirectory (already scanned above)
            # Check if path contains powercore subdirectories we already scanned
            path_lower = path_str.lower()
            if "powercore" in path_lower:
                # Check if it's in a subdirectory we already scanned
                if any(
                    f"powercore/base/{size_dir.lower()}" in path_lower or
                    f"powercore/quantized/{size_dir.lower()}" in path_lower or
                    "powercore/fusions/final" in path_lower
                    for size_dir in [MODEL_SIZE_70B, MODEL_SIZE_13B, MODEL_SIZE_8B, MODEL_SIZE_EMBEDDINGS]
                ):
                    continue
            
            # Get metadata to infer size and category
            metadata = get_model_metadata(path_str)
            
            model_info = {
                "path": path_str,
                "name": gguf_file.stem,
                "size": metadata.get("size", "unknown"),
                "category": "discovered",
                "file_size": gguf_file.stat().st_size if gguf_file.exists() else 0,
                "quantization": metadata.get("quantization")
            }
            models["discovered"].append(model_info)
            models["all"].append(model_info)
    
    return models


def validate_model_file(model_path: str) -> Tuple[bool, Optional[str]]:
    """
    Validate that a model file exists and is accessible.
    
    Args:
        model_path: Path to model file (GGUF or directory)
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    path = Path(model_path)
    
    if not path.exists():
        return False, f"Model file not found: {model_path}"
    
    if path.is_file() and not path.suffix == ".gguf":
        return False, f"File is not a GGUF file: {model_path}"
    
    if path.is_file() and path.stat().st_size == 0:
        return False, f"Model file is empty: {model_path}"
    
    return True, None


def get_model_metadata(model_path: str) -> Dict[str, any]:
    """
    Extract metadata from a model file path.
    
    Args:
        model_path: Path to GGUF file
        
    Returns:
        Dictionary with metadata (size, quantization, name, etc.)
    """
    path = Path(model_path)
    
    metadata = {
        "name": path.stem,
        "path": str(path),
        "exists": path.exists(),
        "file_size": path.stat().st_size if path.exists() else 0,
        "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2) if path.exists() else 0,
        "file_size_gb": round(path.stat().st_size / (1024 * 1024 * 1024), 2) if path.exists() else 0,
    }
    
    # Try to extract quantization from filename (case-insensitive, handle variations)
    name_lower = path.stem.lower()
    # Extended quantization list including IQ variants
    quantizations = [
        "iq3_xxs", "iq3_xs", "iq3_s", "iq3_m", "iq3_l",
        "iq4_xs", "iq4_s", "iq4_m", "iq4_l",
        "q8_0", "q6_k", "q5_k_m", "q5_k_s", "q4_k_m", "q4_k_s", "q4_0", 
        "q3_k_l", "q3_k_m", "q3_k_s", "q2_k", "f16", "f32"
    ]
    for quant in quantizations:
        if quant in name_lower:
            # Preserve original case from filename if possible, otherwise uppercase
            metadata["quantization"] = quant.upper()
            break
    
    # Try to extract size from path or filename (case-insensitive)
    # Handle variations like "Meta-Llama-3-70B", "meta-llama-3.1-8b", etc.
    path_str = str(path).lower()
    name_str = path.stem.lower()
    
    # Check for 70B/72B variants
    if any(marker in path_str or marker in name_str for marker in ["70b", "72b", "-70-", "-72-"]):
        metadata["size"] = MODEL_SIZE_70B
    # Check for 13B variants
    elif any(marker in path_str or marker in name_str for marker in ["13b", "-13-"]):
        metadata["size"] = MODEL_SIZE_13B
    # Check for 8B variants
    elif any(marker in path_str or marker in name_str for marker in ["8b", "-8-"]):
        metadata["size"] = MODEL_SIZE_8B
    # Check for embeddings
    elif "embed" in path_str or "embed" in name_str:
        metadata["size"] = MODEL_SIZE_EMBEDDINGS
    else:
        metadata["size"] = "unknown"
    
    # Determine category from path
    path_str_full = str(path).lower()
    if "base" in path_str_full and "powercore" in path_str_full:
        metadata["category"] = "base"
    elif "fusion" in path_str_full:
        metadata["category"] = "fusion"
    elif "quantized" in path_str_full:
        metadata["category"] = "quantized"
    else:
        metadata["category"] = "discovered"
    
    return metadata


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

