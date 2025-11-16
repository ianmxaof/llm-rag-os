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
    """Get Ollama status."""
    try:
        response = requests.get(f"{API_BASE}/ollama/status", timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        return {"available": False, "error": str(e)}


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
        return response.json()
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
        return response.json()
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
        return response.json()
    except Exception as e:
        return {"edges": [], "error": str(e)}

