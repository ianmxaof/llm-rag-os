"""
FastAPI Main Application
------------------------
Main FastAPI app with CORS, logging, and route registration.
"""

import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.controllers import llm, ingest, library, visualize, prompts, ollama
from backend.models import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize database on startup
init_db()
logger.info("Database initialized")

# Create FastAPI app
app = FastAPI(
    title="RAG Control Panel API",
    description="Backend API for local RAG pipeline control",
    version="1.0.0"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],  # Streamlit default
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(ollama.router, prefix="/ollama", tags=["Ollama"])
app.include_router(llm.router, prefix="/llm", tags=["LM Studio"])  # Deprecated, kept for backward compatibility
app.include_router(ingest.router, prefix="/ingest", tags=["Ingestion"])
app.include_router(library.router, prefix="/library", tags=["Library"])
app.include_router(visualize.router, prefix="/visualize", tags=["Visualization"])
app.include_router(prompts.router, prefix="/prompts", tags=["Prompts"])


@app.post("/open/cursor")
def open_in_cursor(path: str):
    """Open file or folder in Cursor IDE."""
    import subprocess
    import os
    
    path_obj = Path(path)
    if not path_obj.exists():
        return {"success": False, "message": f"Path does not exist: {path}"}
    
    try:
        # Try Cursor CLI first
        if path_obj.is_file():
            subprocess.Popen(["cursor", str(path_obj)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["cursor", str(path_obj)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {"success": True, "message": f"Opened {path} in Cursor"}
    except FileNotFoundError:
        # Fallback to OS default
        try:
            if os.name == "nt":  # Windows
                os.startfile(str(path_obj))
            else:  # macOS/Linux
                subprocess.Popen(["xdg-open", str(path_obj)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return {"success": True, "message": f"Opened {path} in default application"}
        except Exception as e:
            return {"success": False, "message": f"Could not open: {str(e)}"}


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "RAG Control Panel API"}


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "message": "RAG Control Panel API",
        "version": "1.0.0",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="127.0.0.1", port=8000, reload=True)

