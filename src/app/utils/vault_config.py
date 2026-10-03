"""
Powercore Model Vault Configuration
-----------------------------------
Central configuration for the Powercore Model Vault system.
Supports environment variable override for easy migration to external storage.
"""

import os
from pathlib import Path
from typing import Dict, Optional

# Vault root with environment variable override
# Default: ~\.lmstudio\models (expands to C:\Users\ianmp\.lmstudio\models on Windows)
# Override: Set POWERCORE_VAULT=E:\Powercore-Vault in .env or Windows environment variables
VAULT_ROOT = os.getenv("POWERCORE_VAULT", os.path.expanduser(r"~\.lmstudio\models"))

# Ensure vault root is a Path object
VAULT_ROOT_PATH = Path(VAULT_ROOT)

# Vault subdirectories
POWERCORE_DIR = VAULT_ROOT_PATH / "powercore"
BASE_MODELS_DIR = POWERCORE_DIR / "base"
FUSIONS_DIR = POWERCORE_DIR / "fusions"
FUSIONS_WORKING_DIR = FUSIONS_DIR / "working"
FUSIONS_FINAL_DIR = FUSIONS_DIR / "final"
QUANTIZED_DIR = POWERCORE_DIR / "quantized"
TRAINING_DATA_DIR = POWERCORE_DIR / "training-data"
CONVERSATIONS_DIR = TRAINING_DATA_DIR / "conversations"
RESONANCE_PAIRS_DIR = TRAINING_DATA_DIR / "resonance-pairs"
DPO_DATASETS_DIR = TRAINING_DATA_DIR / "dpo-datasets"

# Model size categories
MODEL_SIZE_70B = "70B"
MODEL_SIZE_13B = "13B"
MODEL_SIZE_8B = "8B"
MODEL_SIZE_EMBEDDINGS = "embeddings"

# Powercore Model Registry
# Predefined models with metadata (paths, speeds, descriptions)
POWERCORE_MODELS: Dict[str, Dict[str, any]] = {
    "⚡ Powercore Raw 8B (instant)": {
        "path": str(QUANTIZED_DIR / MODEL_SIZE_8B / "Powercore-Raw-8B-Q8_0.gguf"),
        "speed": "60+ t/s",
        "description": "Instant responses, zero refusal",
        "size": MODEL_SIZE_8B,
        "quantization": "Q8_0",
        "capabilities": ["speed", "uncensored"]
    },
    "⭐ Powercore Ultimate 13B (recommended)": {
        "path": str(QUANTIZED_DIR / MODEL_SIZE_13B / "Powercore-Ultimate-13B-Q6_K.gguf"),
        "speed": "35-45 t/s",
        "description": "Best balance: coding + creative + uncensored",
        "size": MODEL_SIZE_13B,
        "quantization": "Q6_K",
        "capabilities": ["coding", "creative", "uncensored"]
    },
    "🌙 Powercore Apocalypse 70B (god mode)": {
        "path": str(QUANTIZED_DIR / MODEL_SIZE_70B / "Powercore-Apocalypse-70B-IQ4_XS.gguf"),
        "speed": "12-16 t/s",
        "description": "Maximum intelligence, no compromises",
        "size": MODEL_SIZE_70B,
        "quantization": "IQ4_XS",
        "capabilities": ["reasoning", "intelligence", "uncensored"]
    },
    "— Base Models —": {
        "path": "",
        "speed": "",
        "description": "",
        "size": "",
        "quantization": "",
        "capabilities": []
    },
    "Llama-3.1-70B-abliterated": {
        "path": str(BASE_MODELS_DIR / MODEL_SIZE_70B / "Llama-3.1-70B-abliterated-IQ4_XS.gguf"),
        "speed": "14 t/s",
        "description": "Original uncensored king",
        "size": MODEL_SIZE_70B,
        "quantization": "IQ4_XS",
        "capabilities": ["reasoning", "uncensored"]
    },
    "Dolphin-2.9.3-70B": {
        "path": str(BASE_MODELS_DIR / MODEL_SIZE_70B / "Dolphin-2.9.3-70B-Q4_K_M.gguf"),
        "speed": "14 t/s",
        "description": "Most aggressive uncensored",
        "size": MODEL_SIZE_70B,
        "quantization": "Q4_K_M",
        "capabilities": ["uncensored", "aggressive"]
    }
}


def get_vault_root() -> Path:
    """Get the vault root directory path."""
    return VAULT_ROOT_PATH


def ensure_vault_structure():
    """Create vault directory structure if it doesn't exist."""
    directories = [
        POWERCORE_DIR,
        BASE_MODELS_DIR,
        BASE_MODELS_DIR / MODEL_SIZE_70B,
        BASE_MODELS_DIR / MODEL_SIZE_13B,
        BASE_MODELS_DIR / MODEL_SIZE_8B,
        BASE_MODELS_DIR / MODEL_SIZE_EMBEDDINGS,
        FUSIONS_DIR,
        FUSIONS_WORKING_DIR,
        FUSIONS_FINAL_DIR,
        QUANTIZED_DIR,
        QUANTIZED_DIR / MODEL_SIZE_70B,
        QUANTIZED_DIR / MODEL_SIZE_13B,
        QUANTIZED_DIR / MODEL_SIZE_8B,
        TRAINING_DATA_DIR,
        CONVERSATIONS_DIR,
        RESONANCE_PAIRS_DIR,
        DPO_DATASETS_DIR,
    ]
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
    
    return True


def get_model_path(model_name: str) -> Optional[str]:
    """Get the full path for a registered model."""
    if model_name in POWERCORE_MODELS:
        model_info = POWERCORE_MODELS[model_name]
        path_str = model_info.get("path", "")
        if path_str:
            # Check if file exists, return path if it does
            path = Path(path_str)
            if path.exists():
                return str(path)
            # If not, return None (model not downloaded yet)
            return None
    return None


def is_powercore_model(model_name: str) -> bool:
    """Check if a model name is in the Powercore registry."""
    return model_name in POWERCORE_MODELS and model_name != "— Base Models —"

