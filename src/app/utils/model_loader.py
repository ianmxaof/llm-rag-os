"""
Powercore Model Loader
----------------------
Handles loading of GGUF models via llama-cpp-python with session state management.
"""

import logging
from pathlib import Path
from typing import Optional, Dict, Any
import streamlit as st

logger = logging.getLogger(__name__)

# Try to import llama-cpp-python, fallback to None if not available
try:
    from llama_cpp import Llama
    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    logger.warning("llama-cpp-python not available. GGUF loading will be disabled.")


def load_gguf_model(
    path: str,
    n_ctx: int = 8192,
    n_threads: Optional[int] = None,
    n_gpu_layers: int = 0,
    verbose: bool = False
) -> Optional[Any]:
    """
    Load a GGUF model using llama-cpp-python.
    
    Args:
        path: Path to GGUF file
        n_ctx: Context window size (default: 8192)
        n_threads: Number of CPU threads (default: auto-detect)
        n_gpu_layers: Number of GPU layers (default: 0 for CPU-only)
        verbose: Enable verbose logging
        
    Returns:
        Llama model instance or None if loading fails
    """
    if not LLAMA_CPP_AVAILABLE:
        logger.error("llama-cpp-python is not installed. Cannot load GGUF models.")
        return None
    
    path_obj = Path(path)
    if not path_obj.exists():
        logger.error(f"Model file not found: {path}")
        return None
    
    try:
        # Auto-detect thread count if not specified
        if n_threads is None:
            import os
            n_threads = int(os.getenv("OMP_NUM_THREADS", "8"))
        
        logger.info(f"Loading GGUF model: {path}")
        logger.info(f"Context: {n_ctx}, Threads: {n_threads}, GPU layers: {n_gpu_layers}")
        
        model = Llama(
            model_path=str(path),
            n_ctx=n_ctx,
            n_threads=n_threads,
            n_gpu_layers=n_gpu_layers,
            verbose=verbose
        )
        
        logger.info(f"Successfully loaded model: {path}")
        return model
        
    except Exception as e:
        logger.error(f"Failed to load GGUF model {path}: {e}")
        return None


def unload_model():
    """Unload the currently loaded model from session state."""
    if "loaded_model_instance" in st.session_state:
        try:
            # llama-cpp-python models don't have explicit cleanup
            # Just remove from session state
            del st.session_state.loaded_model_instance
            logger.info("Model unloaded from session state")
        except Exception as e:
            logger.warning(f"Error unloading model: {e}")


def get_model_info(path: str) -> Dict[str, Any]:
    """
    Extract basic metadata from a GGUF file path.
    
    Args:
        path: Path to GGUF file
        
    Returns:
        Dictionary with model information
    """
    path_obj = Path(path)
    
    info = {
        "path": str(path),
        "name": path_obj.stem,
        "exists": path_obj.exists(),
        "file_size": path_obj.stat().st_size if path_obj.exists() else 0,
    }
    
    if path_obj.exists():
        info["file_size_mb"] = round(info["file_size"] / (1024 * 1024), 2)
        info["file_size_gb"] = round(info["file_size"] / (1024 * 1024 * 1024), 2)
    
    return info


def is_gguf_path(model_identifier: str) -> bool:
    """
    Check if a model identifier is a GGUF file path.
    
    Args:
        model_identifier: Model name or path
        
    Returns:
        True if it's a GGUF path, False otherwise
    """
    return model_identifier.endswith(".gguf") or Path(model_identifier).suffix == ".gguf"


def get_or_load_model(
    model_identifier: str,
    n_ctx: int = 8192,
    n_threads: Optional[int] = None,
    n_gpu_layers: int = 0
) -> Optional[Any]:
    """
    Get or load a model, using session state cache if available.
    
    Args:
        model_identifier: Model path (GGUF) or Ollama model name
        n_ctx: Context window size
        n_threads: Number of CPU threads
        n_gpu_layers: Number of GPU layers
        
    Returns:
        Model instance (Llama for GGUF, None for Ollama - handled by API)
    """
    # Only handle GGUF files here
    if not is_gguf_path(model_identifier):
        return None  # Ollama models handled by API
    
    # Check if same model is already loaded
    if "loaded_model_instance" in st.session_state:
        if "selected_model_path" in st.session_state:
            if st.session_state.selected_model_path == model_identifier:
                logger.debug("Using cached model instance")
                return st.session_state.loaded_model_instance
    
    # Load new model
    model = load_gguf_model(
        path=model_identifier,
        n_ctx=n_ctx,
        n_threads=n_threads,
        n_gpu_layers=n_gpu_layers
    )
    
    if model:
        # Cache in session state
        st.session_state.loaded_model_instance = model
        st.session_state.selected_model_path = model_identifier
        st.session_state.model_loader_type = "gguf"
    
    return model


def generate_with_gguf(
    model_instance: Any,
    prompt: str,
    temperature: float = 0.7,
    max_tokens: int = 2000,
    top_p: float = 0.95,
    stop: Optional[list] = None
) -> str:
    """
    Generate text using a loaded GGUF model instance.
    
    Args:
        model_instance: Loaded Llama model instance
        prompt: Input prompt
        temperature: Sampling temperature
        max_tokens: Maximum tokens to generate
        top_p: Top-p sampling parameter
        stop: Stop sequences
        
    Returns:
        Generated text
    """
    if not model_instance:
        raise ValueError("Model instance is None")
    
    try:
        response = model_instance(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            stop=stop or [],
            echo=False
        )
        
        # Extract text from response
        if isinstance(response, dict):
            if "choices" in response and len(response["choices"]) > 0:
                return response["choices"][0].get("text", "")
            elif "text" in response:
                return response["text"]
        
        # Fallback: try to get text directly
        if hasattr(response, "text"):
            return response.text
        
        return str(response)
        
    except Exception as e:
        logger.error(f"Error generating with GGUF model: {e}")
        raise

