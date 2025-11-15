"""
Ingestion Controller
--------------------
Manages document ingestion, watchers, and refinement processes.
"""

import logging
import subprocess
import atexit
import signal
import sys
from pathlib import Path
from typing import Optional, Generator

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from scripts.config import config
from scripts.embed_worker import embed_and_upsert

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestFileRequest(BaseModel):
    """Request model for file ingestion."""
    path: str

# Track background processes for cleanup
_watcher_process: Optional[subprocess.Popen] = None
_embed_worker_process: Optional[subprocess.Popen] = None


def cleanup_processes():
    """Cleanup background processes on shutdown."""
    global _watcher_process, _embed_worker_process
    if _watcher_process:
        try:
            _watcher_process.terminate()
            _watcher_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error terminating watcher: {e}")
    if _embed_worker_process:
        try:
            _embed_worker_process.terminate()
            _embed_worker_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error terminating embed worker: {e}")


# Register cleanup handlers
atexit.register(cleanup_processes)


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    cleanup_processes()
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


def run_ingestion_subprocess(
    path: str, fast: bool = True, parallel: bool = True
) -> Generator[str, None, None]:
    """
    Run ingestion script as subprocess and yield log lines.
    
    Args:
        path: Path to folder to ingest
        fast: Use fast PDF mode
        parallel: Use parallel processing
        
    Yields:
        Log lines as strings
    """
    args = [
        sys.executable,
        str(Path(__file__).parent.parent.parent / "scripts" / "ingest.py"),
        "--src", path,
        "--no-reset"
    ]
    
    if fast:
        args.append("--fast")
    if parallel:
        args.append("--parallel")
    
    try:
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        for line in proc.stdout:
            yield line.rstrip("\n")
        
        proc.wait()
        if proc.returncode != 0:
            yield f"[ERROR] Ingestion failed with return code {proc.returncode}"
            
    except Exception as e:
        logger.error(f"Error running ingestion: {e}")
        yield f"[ERROR] {str(e)}"


def start_watcher() -> tuple[bool, str]:
    """Start inbox watcher process."""
    global _watcher_process
    
    if _watcher_process and _watcher_process.poll() is None:
        return True, "Watcher already running"
    
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "watch_and_ingest.py"
        _watcher_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("Started inbox watcher")
        return True, "Watcher started successfully"
    except Exception as e:
        logger.error(f"Failed to start watcher: {e}")
        return False, f"Failed to start watcher: {str(e)}"


def stop_watcher() -> tuple[bool, str]:
    """Stop inbox watcher process."""
    global _watcher_process
    
    if not _watcher_process or _watcher_process.poll() is not None:
        return True, "Watcher is not running"
    
    try:
        _watcher_process.terminate()
        _watcher_process.wait(timeout=5)
        logger.info("Stopped inbox watcher")
        return True, "Watcher stopped successfully"
    except subprocess.TimeoutExpired:
        _watcher_process.kill()
        return True, "Watcher force-killed"
    except Exception as e:
        logger.error(f"Error stopping watcher: {e}")
        return False, f"Error stopping watcher: {str(e)}"


def start_embed_worker() -> tuple[bool, str]:
    """Start embed worker process."""
    global _embed_worker_process
    
    if _embed_worker_process and _embed_worker_process.poll() is None:
        return True, "Embed worker already running"
    
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "embed_worker.py"
        _embed_worker_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("Started embed worker")
        return True, "Embed worker started successfully"
    except FileNotFoundError:
        return False, "embed_worker.py not found. Create it first."
    except Exception as e:
        logger.error(f"Failed to start embed worker: {e}")
        return False, f"Failed to start embed worker: {str(e)}"


def stop_embed_worker() -> tuple[bool, str]:
    """Stop embed worker process."""
    global _embed_worker_process
    
    if not _embed_worker_process or _embed_worker_process.poll() is not None:
        return True, "Embed worker is not running"
    
    try:
        _embed_worker_process.terminate()
        _embed_worker_process.wait(timeout=5)
        logger.info("Stopped embed worker")
        return True, "Embed worker stopped successfully"
    except subprocess.TimeoutExpired:
        _embed_worker_process.kill()
        return True, "Embed worker force-killed"
    except Exception as e:
        logger.error(f"Error stopping embed worker: {e}")
        return False, f"Error stopping embed worker: {str(e)}"


@router.post("/run")
def run_ingestion(
    path: str = Query(..., description="Path to folder to ingest"),
    fast: bool = Query(True, description="Use fast PDF mode"),
    parallel: bool = Query(True, description="Use parallel processing")
):
    """Run ingestion and stream logs."""
    path_obj = Path(path)
    if not path_obj.exists():
        raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")
    
    def event_stream():
        for line in run_ingestion_subprocess(str(path_obj), fast=fast, parallel=parallel):
            yield f"data: {json.dumps({'log': line})}\n\n"
    
    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/watch/start")
def start_watcher_endpoint():
    """Start inbox watcher."""
    success, message = start_watcher()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/watch/stop")
def stop_watcher_endpoint():
    """Stop inbox watcher."""
    success, message = stop_watcher()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/embed/start")
def start_embed_worker_endpoint():
    """Start embed worker."""
    success, message = start_embed_worker()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/embed/stop")
def stop_embed_worker_endpoint():
    """Stop embed worker."""
    success, message = stop_embed_worker()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/file")
def ingest_file_endpoint(request: IngestFileRequest, background_tasks: BackgroundTasks):
    """
    Ingest a single file (markdown) using Ollama embeddings.
    
    Request body: {"path": "path/to/file.md"}
    """
    file_path = Path(request.path)
    
    if not file_path.exists():
        raise HTTPException(status_code=400, detail=f"File does not exist: {request.path}")
    
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only .md files are supported for direct ingestion")
    
    # Run embedding in background
    background_tasks.add_task(embed_and_upsert, file_path)
    
    return {
        "success": True,
        "message": f"Ingestion started for {file_path.name}",
        "file": file_path.name
    }


@router.post("/refine")
def refine_document(
    document_id: Optional[int] = None,
    source_path: Optional[str] = None,
    chunk_size: Optional[int] = None,
    chunk_overlap: Optional[int] = None
):
    """Refine (reprocess and re-embed) a document."""
    # This will be implemented when refine.py is created
    return {
        "success": False,
        "message": "Refine functionality not yet implemented. Create scripts/refine.py first."
    }

