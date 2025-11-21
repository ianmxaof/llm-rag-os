"""
Obsidian FastAPI Reindex Endpoint
----------------------------------
HTTP endpoint for force-reindexing specific Obsidian notes.
Can be called from Streamlit or QuickAdd macros.
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import uvicorn

from scripts.config import config, REINDEX_API_PORT
from scripts.obsidian_rag_ingester import ObsidianIngester

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Obsidian RAG Reindex API")

# Global ingester instance (initialized on startup)
ingester: Optional[ObsidianIngester] = None


@app.on_event("startup")
async def startup_event():
    """Initialize ingester on startup."""
    global ingester
    try:
        ingester = ObsidianIngester()
        logger.info("Obsidian ingester initialized")
    except Exception as e:
        logger.error(f"Failed to initialize ingester: {e}")
        ingester = None


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Obsidian RAG Reindex API",
        "status": "running",
        "endpoints": {
            "reindex": "/reindex?file=path/to/note.md"
        }
    }


@app.post("/reindex")
async def reindex_note(
    file: str = Query(..., description="Path to Obsidian note file (relative to vault root)")
):
    """
    Force reindex a specific Obsidian note.
    
    Args:
        file: Path to note file (e.g., "Manual/MyNote.md" or "Auto/SomeNote.md")
    
    Returns:
        JSON response with status and chunk count
    """
    if ingester is None:
        raise HTTPException(status_code=503, detail="Ingester not initialized")
    
    # Resolve file path
    vault_root = Path(config.ROOT) / "knowledge" / "notes"
    
    # Handle both relative and absolute paths
    if Path(file).is_absolute():
        file_path = Path(file)
    else:
        file_path = vault_root / file
    
    # Normalize path
    file_path = file_path.resolve()
    
    # Verify file exists
    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {file_path}"
        )
    
    # Verify it's a markdown file
    if file_path.suffix != ".md":
        raise HTTPException(
            status_code=400,
            detail=f"File is not a markdown file: {file_path.suffix}"
        )
    
    # Verify it's within the vault
    try:
        file_path.relative_to(vault_root)
    except ValueError:
        raise HTTPException(
            status_code=403,
            detail=f"File is outside vault root: {file_path}"
        )
    
    # Clear from ledger to force re-indexing
    ingester.ledger.clear_file(file_path)
    
    # Process file (force=True bypasses hash check)
    try:
        result = ingester.process_note(file_path, force=True)
        
        if result.get("status") == "success":
            return JSONResponse({
                "status": "success",
                "chunks": result.get("chunks", 0),
                "trust_level": result.get("trust_level", "unknown"),
                "file": str(file_path)
            })
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {result.get('error', 'unknown error')}"
            )
    except Exception as e:
        logger.error(f"Reindex failed for {file_path}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Reindex failed: {str(e)}"
        )


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "ingester_initialized": ingester is not None
    }


def main():
    """Run FastAPI server."""
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=REINDEX_API_PORT,
        log_level="info"
    )


if __name__ == "__main__":
    main()

