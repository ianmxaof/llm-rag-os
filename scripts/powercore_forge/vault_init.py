"""
Vault Initialization Script
----------------------------
Creates the Powercore vault directory structure.
"""

import os
from pathlib import Path

# Get vault root from environment or use default
VAULT_ROOT = os.getenv("POWERCORE_VAULT", os.path.expanduser(r"~\.lmstudio\models"))
VAULT_ROOT_PATH = Path(VAULT_ROOT)

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

# Model size directories
MODEL_SIZE_70B = "70B"
MODEL_SIZE_13B = "13B"
MODEL_SIZE_8B = "8B"
MODEL_SIZE_EMBEDDINGS = "embeddings"

def initialize_vault():
    """Create vault directory structure."""
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
    
    print(f"Initializing Powercore Vault at: {VAULT_ROOT_PATH}")
    
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        print(f"  ✓ {directory}")
    
    print("\n✅ Vault structure initialized successfully!")
    return True

if __name__ == "__main__":
    initialize_vault()

