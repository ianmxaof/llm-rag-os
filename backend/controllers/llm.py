"""
LM Studio Controller
--------------------
Manages LM Studio process lifecycle: start, stop, load/unload models, status checks.
"""

import logging
import subprocess
import time
from typing import Dict, Optional

import psutil
import requests
from fastapi import APIRouter, HTTPException

from scripts.config import config

logger = logging.getLogger(__name__)
router = APIRouter()


def is_running() -> bool:
    """Check if LM Studio process is running."""
    try:
        for proc in psutil.process_iter(["name"]):
            try:
                name = proc.info["name"] or ""
                if "LM Studio" in name or "lmstudio" in name.lower():
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        logger.error(f"Error checking LM Studio process: {e}")
    return False


def api_available(timeout: int = 2) -> bool:
    """Check if LM Studio API is responding."""
    try:
        response = requests.get(config.LM_API_HEALTH, timeout=timeout)
        return response.status_code == 200
    except Exception:
        return False


def wait_for_api(timeout: int = 60) -> bool:
    """Wait for LM Studio API to become available."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if api_available():
            return True
        time.sleep(1)
    return False


def start_lmstudio(server_mode: bool = False, model_name: Optional[str] = None) -> tuple[bool, str]:
    """
    Start LM Studio (GUI or server mode).
    
    Args:
        server_mode: If True, try to start in server mode (requires CLI support)
        model_name: Model to load (for server mode)
        
    Returns:
        (success, message) tuple
    """
    if is_running():
        if api_available():
            return True, "LM Studio already running and API available"
        return True, "LM Studio already running but API not yet available"
    
    try:
        if server_mode and model_name:
            # Try to start in server mode (if CLI supports it)
            try:
                cmd = ["lmstudio", "start-server", "--model", model_name, "--port", "1234"]
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                logger.info(f"Started LM Studio server mode with model {model_name}")
            except FileNotFoundError:
                # Fallback to GUI mode
                logger.warning("LM Studio CLI not found, starting GUI mode")
                subprocess.Popen([config.LM_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            # Start GUI mode
            subprocess.Popen([config.LM_EXE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info("Started LM Studio GUI")
        
        # Wait for API to become available
        if wait_for_api(timeout=60):
            return True, "LM Studio started and API is ready"
        else:
            return False, "LM Studio started but API not available after 60s"
            
    except Exception as e:
        logger.error(f"Failed to start LM Studio: {e}")
        return False, f"Failed to start LM Studio: {str(e)}"


def stop_lmstudio() -> tuple[bool, str]:
    """Stop LM Studio gracefully."""
    if not is_running():
        return True, "LM Studio is not running"
    
    try:
        terminated = False
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                name = proc.info["name"] or ""
                if "LM Studio" in name or "lmstudio" in name.lower():
                    proc.terminate()
                    terminated = True
                    logger.info(f"Terminated LM Studio process {proc.info['pid']}")
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.warning(f"Could not terminate process: {e}")
                continue
        
        if terminated:
            # Wait a bit for process to terminate
            time.sleep(2)
            return True, "LM Studio stopped successfully"
        else:
            return False, "LM Studio process not found"
            
    except Exception as e:
        logger.error(f"Error stopping LM Studio: {e}")
        return False, f"Error stopping LM Studio: {str(e)}"


def load_model(model_name: Optional[str] = None) -> tuple[bool, str]:
    """
    Load a model via LM Studio API.
    
    Note: This requires LM Studio to expose a model loading endpoint.
    If not available, this will return an error.
    """
    if not api_available():
        return False, "LM Studio API is not available"
    
    model = model_name or config.LOCAL_MODEL_ID
    try:
        # Try to load model via API (endpoint may vary by LM Studio version)
        # This is a placeholder - actual endpoint depends on LM Studio version
        response = requests.post(
            f"{config.LM_API_BASE}/models/load",
            json={"model": model},
            timeout=30
        )
        if response.status_code == 200:
            return True, f"Model {model} loaded successfully"
        else:
            return False, f"Failed to load model: {response.text}"
    except requests.exceptions.RequestException as e:
        # Endpoint may not exist - that's okay, user can load manually
        logger.warning(f"Model loading endpoint not available: {e}")
        return False, "Model loading API not available. Please load model manually in LM Studio."


def unload_model() -> tuple[bool, str]:
    """Unload current model via LM Studio API."""
    if not api_available():
        return False, "LM Studio API is not available"
    
    try:
        response = requests.post(
            f"{config.LM_API_BASE}/models/unload",
            timeout=30
        )
        if response.status_code == 200:
            return True, "Model unloaded successfully"
        else:
            return False, f"Failed to unload model: {response.text}"
    except requests.exceptions.RequestException as e:
        logger.warning(f"Model unloading endpoint not available: {e}")
        return False, "Model unloading API not available. Please unload model manually in LM Studio."


@router.get("/status")
def get_status():
    """Get LM Studio status."""
    running = is_running()
    api_ready = api_available() if running else False
    
    return {
        "running": running,
        "api_ready": api_ready,
        "api_url": config.LM_API_BASE if api_ready else None
    }


@router.post("/start")
def start_lm_studio(server_mode: bool = False, model: Optional[str] = None):
    """Start LM Studio."""
    success, message = start_lmstudio(server_mode=server_mode, model_name=model)
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/stop")
def stop_lm_studio():
    """Stop LM Studio."""
    success, message = stop_lmstudio()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/load-model")
def load_model_endpoint(model: Optional[str] = None):
    """Load a model in LM Studio."""
    success, message = load_model(model_name=model)
    if success:
        return {"success": True, "message": message}
    else:
        # Don't raise exception - model loading may not be supported
        return {"success": False, "message": message}


@router.post("/unload-model")
def unload_model_endpoint():
    """Unload current model in LM Studio."""
    success, message = unload_model()
    if success:
        return {"success": True, "message": message}
    else:
        # Don't raise exception - model unloading may not be supported
        return {"success": False, "message": message}

