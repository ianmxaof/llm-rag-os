"""
Model Download Script
---------------------
Download critical models for the Powercore Vault using Hugging Face Hub.
Downloads models to the correct vault subdirectories based on model size.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path to import vault_config
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    from huggingface_hub import hf_hub_download
    HF_HUB_AVAILABLE = True
except ImportError:
    HF_HUB_AVAILABLE = False
    print("⚠️  huggingface_hub not installed. Install with: pip install huggingface_hub hf-transfer")

from src.app.utils.vault_config import (
    VAULT_ROOT_PATH, BASE_MODELS_DIR, QUANTIZED_DIR, MODEL_SIZE_70B, 
    MODEL_SIZE_8B, MODEL_SIZE_EMBEDDINGS, ensure_vault_structure
)

# Example usage:
# python scripts/powercore_forge/download_models.py


def determine_model_size(model_name: str) -> str:
    """
    Determine model size category from model name.
    
    Args:
        model_name: Model filename or name
        
    Returns:
        Size category (70B, 8B, embeddings, etc.)
    """
    name_lower = model_name.lower()
    if "70b" in name_lower or "72b" in name_lower:
        return MODEL_SIZE_70B
    elif "8b" in name_lower:
        return MODEL_SIZE_8B
    elif "embed" in name_lower:
        return MODEL_SIZE_EMBEDDINGS
    elif "13b" in name_lower:
        return "13B"
    else:
        return MODEL_SIZE_8B  # Default to 8B if unclear


def determine_download_dir(model_name: str, is_quantized: bool = True) -> Path:
    """
    Determine the correct download directory based on model name and type.
    
    Args:
        model_name: Model filename
        is_quantized: Whether this is a quantized model (default: True)
        
    Returns:
        Path object for the download directory
    """
    size = determine_model_size(model_name)
    
    if is_quantized:
        base_dir = QUANTIZED_DIR
    else:
        base_dir = BASE_MODELS_DIR
    
    return base_dir / size


def download_model(
    repo_id: str,
    filename: str,
    model_name: str = None,
    is_quantized: bool = True,
    local_dir: Path = None
) -> Path:
    """
    Download a model from Hugging Face Hub to the vault.
    
    Args:
        repo_id: Hugging Face repository ID (e.g., "bartowski/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF")
        filename: Model filename to download (e.g., "Meta-Llama-3.1-8B-Instruct-abliterated-Q8_0.gguf")
        model_name: Optional model name for determining size (defaults to filename)
        is_quantized: Whether this is a quantized model
        local_dir: Optional custom directory (defaults to vault subdirectory)
        
    Returns:
        Path to downloaded model file
    """
    if not HF_HUB_AVAILABLE:
        raise ImportError("huggingface_hub is required. Install with: pip install huggingface_hub hf-transfer")
    
    # Ensure vault structure exists
    ensure_vault_structure()
    
    # Determine download directory
    if local_dir is None:
        model_name_for_size = model_name or filename
        local_dir = determine_download_dir(model_name_for_size, is_quantized)
    
    # Create directory if it doesn't exist
    local_dir.mkdir(parents=True, exist_ok=True)
    
    # Download file
    print(f"📥 Downloading {filename}...")
    print(f"   Repository: {repo_id}")
    print(f"   Destination: {local_dir}")
    
    try:
        # Enable faster downloads if hf-transfer is available
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "1")
        
        downloaded_path = hf_hub_download(
            repo_id=repo_id,
            filename=filename,
            local_dir=str(local_dir),
            local_dir_use_symlinks=False
        )
        
        print(f"✅ Downloaded: {downloaded_path}")
        return Path(downloaded_path)
        
    except Exception as e:
        print(f"❌ Error downloading {filename}: {e}")
        raise


def download_critical_models():
    """
    Download critical models for the Powercore Vault.
    
    Models downloaded:
    - Meta-Llama-3-70B-Instruct-abliterated-v3.5.i1-IQ4_XS.gguf
    - meta-llama-3.1-8b-instruct-abliterated.Q8_0.gguf
    - nomic-embed-text-v1.5 (if needed)
    """
    if not HF_HUB_AVAILABLE:
        print("❌ huggingface_hub is not installed.")
        print("   Install with: pip install huggingface_hub hf-transfer")
        return
    
    print("📦 Downloading critical models for Powercore Vault...")
    print(f"   Vault root: {VAULT_ROOT_PATH}\n")
    
    models_to_download = [
        {
            "repo_id": "bartowski/Meta-Llama-3-70B-Instruct-abliterated-v3.5.i1-GGUF",
            "filename": "Meta-Llama-3-70B-Instruct-abliterated-v3.5.i1-IQ4_XS.gguf",
            "is_quantized": True,
            "description": "70B Abliterated IQ4_XS (uncensored god model)"
        },
        {
            "repo_id": "bartowski/Meta-Llama-3.1-8B-Instruct-abliterated-GGUF",
            "filename": "Meta-Llama-3.1-8B-Instruct-abliterated-Q8_0.gguf",
            "is_quantized": True,
            "description": "8B Abliterated Q8_0 (uncensored daily driver)"
        },
        {
            "repo_id": "bartowski/nomic-embed-text-v1.5-GGUF",
            "filename": "nomic-embed-text-v1.5-Q8_0.gguf",
            "is_quantized": True,
            "description": "nomic-embed-text-v1.5 Q8_0 (RAG embeddings)"
        }
    ]
    
    downloaded = []
    failed = []
    
    for model_info in models_to_download:
        try:
            print(f"\n{'='*60}")
            print(f"📦 {model_info['description']}")
            print(f"{'='*60}")
            
            path = download_model(
                repo_id=model_info["repo_id"],
                filename=model_info["filename"],
                is_quantized=model_info["is_quantized"]
            )
            downloaded.append((model_info["filename"], path))
            
        except Exception as e:
            print(f"❌ Failed to download {model_info['filename']}: {e}")
            failed.append(model_info["filename"])
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 Download Summary")
    print(f"{'='*60}")
    print(f"✅ Successfully downloaded: {len(downloaded)}")
    for filename, path in downloaded:
        print(f"   • {filename}")
        print(f"     → {path}")
    
    if failed:
        print(f"\n❌ Failed: {len(failed)}")
        for filename in failed:
            print(f"   • {filename}")
    
    print(f"\n💡 Models are now available in the Powercore Vault")
    print(f"   They should appear in the dropdown menu after refreshing.")


if __name__ == "__main__":
    download_critical_models()

