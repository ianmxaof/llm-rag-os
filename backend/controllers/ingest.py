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
from backend.utils.semantic_categorizer import categorize_file

logger = logging.getLogger(__name__)
router = APIRouter()


class IngestFileRequest(BaseModel):
    """Request model for file ingestion."""
    path: str

# Track background processes for cleanup
_watcher_process: Optional[subprocess.Popen] = None
_embed_worker_process: Optional[subprocess.Popen] = None
_notes_watcher_process: Optional[subprocess.Popen] = None

# Track ingestion jobs for status polling
_ingestion_jobs: dict[str, dict] = {}

# Rate limiting for batch ingestion
_last_batch_ingest_time = 0
_batch_ingest_lock = None
import threading
_batch_ingest_lock = threading.Lock()


def cleanup_processes():
    """Cleanup background processes on shutdown."""
    global _watcher_process, _embed_worker_process, _notes_watcher_process
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
    if _notes_watcher_process:
        try:
            _notes_watcher_process.terminate()
            _notes_watcher_process.wait(timeout=5)
        except Exception as e:
            logger.warning(f"Error terminating notes watcher: {e}")


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


def start_notes_watcher() -> tuple[bool, str]:
    """Start notes watcher process."""
    global _notes_watcher_process
    
    if _notes_watcher_process and _notes_watcher_process.poll() is None:
        return True, "Notes watcher already running"
    
    try:
        script_path = Path(__file__).parent.parent.parent / "scripts" / "notes_watcher.py"
        _notes_watcher_process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info("Started notes watcher")
        return True, "Notes watcher started successfully"
    except Exception as e:
        logger.error(f"Failed to start notes watcher: {e}")
        return False, f"Failed to start notes watcher: {str(e)}"


def stop_notes_watcher() -> tuple[bool, str]:
    """Stop notes watcher process."""
    global _notes_watcher_process
    
    if not _notes_watcher_process or _notes_watcher_process.poll() is not None:
        return True, "Notes watcher is not running"
    
    try:
        _notes_watcher_process.terminate()
        _notes_watcher_process.wait(timeout=5)
        logger.info("Stopped notes watcher")
        return True, "Notes watcher stopped successfully"
    except subprocess.TimeoutExpired:
        _notes_watcher_process.kill()
        return True, "Notes watcher force-killed"
    except Exception as e:
        logger.error(f"Error stopping notes watcher: {e}")
        return False, f"Error stopping notes watcher: {str(e)}"


@router.post("/watch/notes/start")
def start_notes_watcher_endpoint():
    """Start notes watcher."""
    success, message = start_notes_watcher()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.post("/watch/notes/stop")
def stop_notes_watcher_endpoint():
    """Stop notes watcher."""
    success, message = stop_notes_watcher()
    if success:
        return {"success": True, "message": message}
    else:
        raise HTTPException(status_code=500, detail=message)


@router.get("/watch/status")
def get_watcher_status():
    """Get status of all watchers."""
    inbox_watcher_running = _watcher_process is not None and _watcher_process.poll() is None
    notes_watcher_running = _notes_watcher_process is not None and _notes_watcher_process.poll() is None
    
    return {
        "inbox_watcher": "running" if inbox_watcher_running else "stopped",
        "notes_watcher": "running" if notes_watcher_running else "stopped"
    }


def _is_already_ingested(file_path: Path) -> bool:
    """Check if file is already in ChromaDB by source path."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        collection = client.get_or_create_collection(name=config.COLLECTION_NAME)
        
        # Check if any chunks exist for this source
        results = collection.get(
            where={"source": str(file_path.resolve())},
            limit=1
        )
        return len(results.get("ids", [])) > 0
    except Exception as e:
        logger.warning(f"Could not check ChromaDB for {file_path}: {e}")
        return False


def _should_process_file(file_path: Path, exclude_dirs: set) -> bool:
    """Check if file should be processed (not in exclude dirs, is .md file)."""
    # Skip if already in archived folder (to avoid loops)
    if "archived" in str(file_path).lower():
        return False
    
    # Skip if in exclude directories
    parts = file_path.parts
    for exclude_dir in exclude_dirs:
        if exclude_dir in parts:
            return False
    
    # Only process .md files
    if file_path.suffix.lower() != ".md":
        return False
    
    return True


@router.post("/watch/notes/ingest-all")
def ingest_all_existing_notes(background_tasks: BackgroundTasks):
    """
    One-time ingestion of all existing Obsidian notes in knowledge/notes/.
    Excludes system directories and already-ingested files.
    Returns count of files queued for ingestion.
    """
    notes_dir = config.ROOT / "knowledge" / "notes"
    
    if not notes_dir.exists():
        raise HTTPException(status_code=400, detail=f"Notes directory does not exist: {notes_dir}")
    
    # Same exclusion logic as notes_watcher.py
    exclude_dirs = {
        ".obsidian",
        "_templates",
        "_dashboard",
        "_attachments",
        "Templates",
        "_archive",
        "Attachments",
        "Auto",
        "Inbox from RAG"
    }
    
    # Find all .md files recursively
    all_md_files = list(notes_dir.rglob("*.md"))
    
    # Filter files
    files_to_ingest = []
    skipped_count = 0
    
    for file_path in all_md_files:
        if not _should_process_file(file_path, exclude_dirs):
            skipped_count += 1
            continue
        
        # Check if already ingested
        if _is_already_ingested(file_path):
            skipped_count += 1
            logger.info(f"Skipping already ingested: {file_path.name}")
            continue
        
        files_to_ingest.append(file_path)
    
    # Queue all files for ingestion in background with rate limiting
    # Process sequentially with 2-second delay between tasks
    import time as time_module
    for idx, file_path in enumerate(files_to_ingest):
        # Add 2-second delay between tasks (except for the first one)
        delay = 2.0 if idx > 0 else 0.0
        background_tasks.add_task(_ingest_with_status, file_path, delay)
    
    logger.info(f"Queued {len(files_to_ingest)} files for ingestion (skipped {skipped_count} duplicates/excluded)")
    
    return {
        "success": True,
        "count": len(files_to_ingest),
        "skipped": skipped_count,
        "message": f"Queued {len(files_to_ingest)} files for ingestion"
    }


def _update_ingestion_status(file_path: str, status: str, chunks_added: int = 0, error: Optional[str] = None, 
                             sustained_mode: bool = False, estimated_chunks: int = 0, reason: str = "", category: Optional[str] = None):
    """Update ingestion job status."""
    _ingestion_jobs[file_path] = {
        "status": status,
        "chunks_added": chunks_added,
        "error": error,
        "sustained_mode": sustained_mode,
        "estimated_chunks": estimated_chunks,
        "reason": reason,
        "category": category
    }


def _ingest_with_status(file_path: Path, delay: float = 0):
    """Wrapper for embed_and_upsert that updates status."""
    # Add delay if specified (for batch ingestion rate limiting)
    if delay > 0:
        import time as time_module
        time_module.sleep(delay)
    
    file_path_str = str(file_path.resolve())
    category = None
    try:
        # Categorize file before ingestion
        try:
            category = categorize_file(file_path)
            logger.info(f"Categorized {file_path.name} as: {category}")
        except Exception as e:
            logger.warning(f"Failed to categorize file {file_path}: {e}")
        
        _update_ingestion_status(file_path_str, "processing", category=category)
        result = embed_and_upsert(file_path)
        
        # Extract sustained mode metadata from result
        sustained_mode = result.get("sustained_mode", False) if isinstance(result, dict) else False
        estimated_chunks = result.get("estimated_chunks", 0) if isinstance(result, dict) else 0
        reason = result.get("reason", "") if isinstance(result, dict) else ""
        
        if result and (isinstance(result, bool) and result) or (isinstance(result, dict) and result.get("success", False)):
            # Count chunks by checking ChromaDB
            try:
                import chromadb
                client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
                collection = client.get_or_create_collection(name=config.COLLECTION_NAME)
                # Count chunks for this file
                results = collection.get(
                    where={"source": str(file_path)}
                )
                chunks_count = len(results.get("ids", [])) if results else 0
            except Exception:
                chunks_count = 0
            
            _update_ingestion_status(file_path_str, "completed", chunks_added=chunks_count,
                                    sustained_mode=sustained_mode, estimated_chunks=estimated_chunks, reason=reason, category=category)
        else:
            _update_ingestion_status(file_path_str, "failed", error="Embedding failed",
                                    sustained_mode=sustained_mode, estimated_chunks=estimated_chunks, reason=reason, category=category)
    except Exception as e:
        logger.error(f"Error in ingestion task: {e}")
        _update_ingestion_status(file_path_str, "failed", error=str(e), category=category)


@router.post("/file")
def ingest_file_endpoint(request: IngestFileRequest, background_tasks: BackgroundTasks):
    """
    Ingest a single file (markdown) using Ollama embeddings.
    
    Request body: {"path": "path/to/file.md"}
    Returns suggested_category in response.
    """
    file_path = Path(request.path)
    
    if not file_path.exists():
        raise HTTPException(status_code=400, detail=f"File does not exist: {request.path}")
    
    if file_path.suffix.lower() != ".md":
        raise HTTPException(status_code=400, detail="Only .md files are supported for direct ingestion")
    
    # Categorize file before ingestion (synchronous for immediate response)
    suggested_category = None
    try:
        suggested_category = categorize_file(file_path)
        logger.info(f"Suggested category for {file_path.name}: {suggested_category}")
    except Exception as e:
        logger.warning(f"Failed to categorize file {file_path}: {e}")
    
    # Initialize status
    file_path_str = str(file_path.resolve())
    _update_ingestion_status(file_path_str, "pending", category=suggested_category)
    
    # Run embedding in background with status tracking
    background_tasks.add_task(_ingest_with_status, file_path)
    
    return {
        "success": True,
        "message": f"Ingestion started for {file_path.name}",
        "file": file_path.name,
        "suggested_category": suggested_category
    }


@router.get("/status/{file_path:path}")
def get_ingestion_status(file_path: str):
    """Get ingestion status for a file."""
    # Normalize path
    try:
        normalized_path = str(Path(file_path).resolve())
    except Exception:
        normalized_path = file_path
    
    job = _ingestion_jobs.get(normalized_path, {})
    if not job:
        return {
            "status": "not_found",
            "chunks_added": 0,
            "error": None,
            "category": None
        }
    
    return {
        "status": job.get("status", "unknown"),
        "chunks_added": job.get("chunks_added", 0),
        "error": job.get("error"),
        "sustained_mode": job.get("sustained_mode", False),
        "estimated_chunks": job.get("estimated_chunks", 0),
        "reason": job.get("reason", ""),
        "category": job.get("category")
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

