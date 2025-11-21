"""
Visualization Controller
------------------------
Provides visualization endpoints: UMAP, similarity heatmaps, corpus stats.
"""

import logging
from typing import List, Dict, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

try:
    import umap
    UMAP_AVAILABLE = True
except ImportError:
    UMAP_AVAILABLE = False

import chromadb
from scripts.config import config

logger = logging.getLogger(__name__)
router = APIRouter()


def compute_umap_sample(n: int = 1000) -> List[Dict]:
    """Compute UMAP coordinates for a sample of embeddings."""
    if not UMAP_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="UMAP not available. Install with: pip install umap-learn"
        )
    
    try:
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        
        # Check if collection exists
        try:
            collection = client.get_collection(config.COLLECTION_NAME)
        except Exception as e:
            logger.error(f"Collection {config.COLLECTION_NAME} does not exist: {e}")
            raise HTTPException(
                status_code=404,
                detail=f"Collection '{config.COLLECTION_NAME}' does not exist. Ingest some documents first."
            )
        
        # Check collection count
        try:
            count = collection.count()
            if count == 0:
                logger.info("Collection is empty")
                return []
        except Exception as e:
            logger.warning(f"Could not get collection count: {e}")
        
        # Get all embeddings (this may be memory-intensive for large collections)
        # For now, we'll get a sample
        try:
            results = collection.get(limit=n, include=["embeddings", "metadatas", "documents"])
        except Exception as e:
            logger.error(f"Error getting embeddings from collection: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error querying collection: {str(e)}"
            )
        
        embeddings = results.get("embeddings", [])
        metadatas = results.get("metadatas", [])
        documents = results.get("documents", [])
        
        # Check if we have any embeddings before processing
        if not embeddings or len(embeddings) == 0:
            logger.info("No embeddings found in collection")
            return []
        
        # Convert to numpy array
        X = np.array(embeddings)
        
        # Check numpy array size (can't use truthiness check on numpy arrays)
        if X.size == 0:
            logger.info("Empty embeddings array after conversion")
            return []
        
        # Ensure we have at least n_neighbors samples for UMAP
        if len(embeddings) < 15:
            logger.warning(f"Only {len(embeddings)} embeddings found, but UMAP needs at least 15. Returning empty result.")
            return []
        
        # Compute UMAP
        try:
            reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=min(15, len(embeddings) - 1), min_dist=0.1)
            coords = reducer.fit_transform(X)
        except Exception as umap_error:
            logger.error(f"UMAP fit_transform failed: {umap_error}")
            raise HTTPException(status_code=500, detail=f"UMAP computation failed: {str(umap_error)}")
        
        # Build result list
        result = []
        # Ensure all arrays have the same length
        min_len = min(len(coords), len(metadatas), len(documents))
        for i in range(min_len):
            coord = coords[i]
            meta = metadatas[i] if i < len(metadatas) else {}
            doc = documents[i] if i < len(documents) else ""
            result.append({
                "x": float(coord[0]),
                "y": float(coord[1]),
                "meta": meta,
                "doc_preview": doc[:200] if doc else ""
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Error computing UMAP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_corpus_stats() -> Dict:
    """Get corpus statistics."""
    try:
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        collection = client.get_collection(config.COLLECTION_NAME)
        
        # Get count (approximate)
        count_result = collection.count()
        
        # Get sample to analyze
        sample = collection.get(limit=100, include=["metadatas"])
        metadatas = sample.get("metadatas", [])
        
        # Count unique sources
        sources = set()
        for meta in metadatas:
            if meta and "source" in meta:
                sources.add(meta["source"])
        
        return {
            "total_chunks": count_result,
            "unique_sources": len(sources),
            "sample_size": len(metadatas)
        }
        
    except Exception as e:
        logger.error(f"Error getting corpus stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/umap")
def get_umap_coords(n: int = Query(500, ge=10, le=5000, description="Number of samples")):
    """Get UMAP coordinates for visualization."""
    coords = compute_umap_sample(n=n)
    return {"coords": coords, "count": len(coords)}


@router.get("/stats")
def get_stats():
    """Get corpus statistics."""
    return get_corpus_stats()

