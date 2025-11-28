"""
FastAPI Client Utilities
------------------------
Helper functions for communicating with the FastAPI backend.
"""

import requests
from typing import Optional, Dict, List

API_BASE = "http://127.0.0.1:8000"


def check_backend_available() -> bool:
    """Check if FastAPI backend is available."""
    try:
        response = requests.get(f"{API_BASE}/health", timeout=2)
        return response.status_code == 200
    except Exception:
        return False


def get_llm_status() -> Dict:
    """Get LM Studio status (deprecated)."""
    try:
        response = requests.get(f"{API_BASE}/llm/status", timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"running": False, "api_ready": False, "error": str(e)}


def get_ollama_status() -> Dict:
    """Get Ollama status by checking server directly."""
    try:
        # Check Ollama server directly at http://localhost:11434/api/tags
        # This checks if the server is running, not if a model is loaded
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            return {"available": True, "status": "ready", "message": "Ollama server is running"}
        else:
            return {"available": False, "status": "not_ready", "error": f"Ollama API returned status {response.status_code}"}
    except requests.exceptions.Timeout:
        return {"available": False, "status": "not_ready", "error": "Ollama server timeout. Make sure Ollama is running: `ollama serve`"}
    except requests.exceptions.ConnectionError:
        return {"available": False, "status": "not_ready", "error": "Cannot connect to Ollama server. Make sure Ollama is running: `ollama serve`"}
    except Exception as e:
        return {"available": False, "status": "not_ready", "error": str(e)}


def get_ollama_models() -> List[str]:
    """Get list of available Ollama models."""
    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [model["name"] for model in data.get("models", [])]
            return models if models else ["mistral:7b-instruct-q5_K_M"]  # Fallback to default
        else:
            return ["mistral:7b-instruct-q5_K_M"]  # Fallback on error
    except Exception:
        # Fallback to default model on any error
        return ["mistral:7b-instruct-q5_K_M"]


def start_lm_studio(server_mode: bool = False, model: Optional[str] = None) -> Dict:
    """Start LM Studio."""
    try:
        response = requests.post(
            f"{API_BASE}/llm/start",
            json={"server_mode": server_mode, "model": model},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def stop_lm_studio() -> Dict:
    """Stop LM Studio."""
    try:
        response = requests.post(f"{API_BASE}/llm/stop", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def list_documents(limit: int = 100, offset: int = 0) -> Dict:
    """List documents."""
    try:
        response = requests.get(
            f"{API_BASE}/library/list",
            params={"limit": limit, "offset": offset},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"items": [], "total": 0, "error": str(e)}


def get_chunks(limit: int = 1000, offset: int = 0) -> Dict:
    """Get chunks directly from ChromaDB collection."""
    try:
        response = requests.get(
            f"{API_BASE}/library/chunks",
            params={"limit": limit, "offset": offset},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        # Ensure we always return a dict, never None
        if result is None:
            return {"chunks": [], "total": 0, "sources": 0, "error": "Empty response from backend"}
        return result
    except Exception as e:
        return {"chunks": [], "total": 0, "sources": 0, "error": str(e)}


def get_document(doc_id: int) -> Dict:
    """Get document details."""
    try:
        response = requests.get(f"{API_BASE}/library/document/{doc_id}", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def update_document_metadata(doc_id: int, tags: Optional[List[str]] = None, notes: Optional[str] = None) -> Dict:
    """Update document metadata."""
    try:
        response = requests.post(
            f"{API_BASE}/library/document/{doc_id}/metadata",
            json={"tags": tags, "notes": notes},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def run_ingestion(path: str, fast: bool = True, parallel: bool = True):
    """Run ingestion (returns generator for streaming logs)."""
    try:
        response = requests.get(
            f"{API_BASE}/ingest/run",
            params={"path": path, "fast": fast, "parallel": parallel},
            stream=True,
            timeout=None
        )
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                yield line.decode()
    except Exception as e:
        yield f"[ERROR] {str(e)}"


def get_umap_coords(n: int = 500) -> Dict:
    """Get UMAP coordinates."""
    try:
        response = requests.get(f"{API_BASE}/visualize/umap", params={"n": n}, timeout=60)
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"coords": [], "error": "Empty response from backend"}
        return result
    except Exception as e:
        return {"coords": [], "error": str(e)}


def get_corpus_stats() -> Dict:
    """Get corpus statistics."""
    try:
        response = requests.get(f"{API_BASE}/visualize/stats", timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"error": str(e)}


def ingest_file(path: str) -> Dict:
    """Ingest a single file using Ollama embeddings."""
    try:
        response = requests.post(
            f"{API_BASE}/ingest/file",
            json={"path": path},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"success": False, "message": str(e)}


def get_graph_nodes(tags=None, min_quality=0.0) -> Dict:
    """Get graph nodes (documents and chunks)."""
    try:
        params = {"min_quality": min_quality}
        if tags:
            params["tags"] = ",".join(tags) if isinstance(tags, list) else tags
        response = requests.get(
            f"{API_BASE}/graph/nodes",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"nodes": [], "error": "Empty response from backend"}
        return result
    except Exception as e:
        return {"nodes": [], "error": str(e)}


def get_graph_edges(threshold=0.75) -> Dict:
    """Get graph edges (similarity relationships)."""
    try:
        response = requests.get(
            f"{API_BASE}/graph/edges",
            params={"threshold": threshold},
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"edges": [], "error": "Empty response from backend"}
        return result
    except Exception as e:
        return {"edges": [], "error": str(e)}


def get_archived_documents(page: int = 1, search: Optional[str] = None, limit: int = 20) -> Dict:
    """Get archived markdown files with AI summaries and tags."""
    try:
        params = {"page": page, "limit": limit}
        if search:
            params["search"] = search
        response = requests.get(
            f"{API_BASE}/library/archived",
            params=params,
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"files": [], "total": 0, "page": page, "limit": limit, "pages": 0, "error": "Empty response"}
        return result
    except Exception as e:
        return {"files": [], "total": 0, "page": page, "limit": limit, "pages": 0, "error": str(e)}


def get_tags() -> Dict:
    """Get all tags and their file counts."""
    try:
        response = requests.get(f"{API_BASE}/library/tags", timeout=10)
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"tags": [], "total": 0, "error": "Empty response"}
        return result
    except Exception as e:
        return {"tags": [], "total": 0, "error": str(e)}


def get_files_by_tag(tag: str, page: int = 1, limit: int = 20) -> Dict:
    """Get files for a specific tag."""
    try:
        response = requests.get(
            f"{API_BASE}/library/tag/{tag}",
            params={"page": page, "limit": limit},
            timeout=10
        )
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"files": [], "total": 0, "page": page, "limit": limit, "pages": 0, "error": "Empty response"}
        return result
    except Exception as e:
        return {"files": [], "total": 0, "page": page, "limit": limit, "pages": 0, "error": str(e)}


def get_ingestion_status(file_path: str) -> Dict:
    """Get ingestion status for a file."""
    try:
        # URL encode the file path
        import urllib.parse
        encoded_path = urllib.parse.quote(file_path, safe='')
        response = requests.get(
            f"{API_BASE}/ingest/status/{encoded_path}",
            timeout=5
        )
        response.raise_for_status()
        result = response.json()
        if result is None:
            return {"status": "unknown", "chunks_added": 0, "error": None}
        return result
    except Exception as e:
        return {"status": "error", "chunks_added": 0, "error": str(e)}

