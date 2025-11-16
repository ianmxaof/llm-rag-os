"""
Graph Controller
----------------
Provides endpoints for graph visualization: nodes (documents/chunks) and edges (similarity relationships).
"""

from fastapi import APIRouter, Query
from chromadb import PersistentClient
from scripts.config import config
from backend.models import DB_PATH
import sqlite3
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
from typing import List, Optional
import hashlib
import logging

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/graph", tags=["Graph"])


def get_collection():
    """Get ChromaDB collection, creating if needed."""
    client = PersistentClient(path=str(config.VECTOR_DIR))
    return client.get_or_create_collection(name=config.COLLECTION_NAME)


def doc_hash(path: str) -> str:
    """Generate consistent hash for document path."""
    return hashlib.md5(path.encode()).hexdigest()[:8]


def get_db():
    """Get SQLite database connection."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


@router.get("/nodes")
def get_nodes(
    tags: Optional[List[str]] = Query(None),
    min_quality: float = Query(0.0, ge=0.0, le=1.0)
):
    """
    Get graph nodes (documents and chunks).
    
    Args:
        tags: Optional list of tags to filter by
        min_quality: Minimum quality score (0.0-1.0)
        
    Returns:
        JSON with nodes array
    """
    try:
        collection = get_collection()
        results = collection.get(include=["metadatas", "documents"])
        nodes = []
        seen_docs = set()

        for doc, meta in zip(results["documents"], results["metadatas"]):
            source = meta["source"]
            chunk_idx = meta.get("chunk", 0)
            doc_id = f"doc_{doc_hash(source)}"
            chunk_id = f"{doc_id}_chunk_{chunk_idx}"

            # Document node (one per unique source)
            if doc_id not in seen_docs:
                seen_docs.add(doc_id)
                filename = source.split("/")[-1].replace(".md", "")
                nodes.append({
                    "id": doc_id,
                    "label": filename,
                    "type": "document",
                    "metadata": {"source": source},
                    "group": "document"
                })

            # Chunk node
            quality = meta.get("quality_score", 0.7)
            meta_tags = meta.get("tags", [])
            
            # Filter by quality
            if quality < min_quality:
                continue
            
            # Filter by tags (if tags provided)
            if tags:
                # Handle both list and comma-separated string
                tag_list = tags if isinstance(tags, list) else [t.strip() for t in str(tags).split(",")]
                if not any(t in meta_tags for t in tag_list):
                    continue

            nodes.append({
                "id": chunk_id,
                "label": f"Chunk {chunk_idx}",
                "type": "chunk",
                "metadata": {
                    "source": source,
                    "chunk_index": chunk_idx,
                    "quality_score": quality,
                    "tags": meta_tags,
                    "text": (doc[:200] + "..." if len(doc) > 200 else doc)
                },
                "group": "chunk"
            })

        logger.info(f"Returning {len(nodes)} nodes")
        return {"nodes": nodes}
        
    except Exception as e:
        logger.error(f"Error getting nodes: {e}")
        return {"nodes": [], "error": str(e)}


@router.get("/edges")
def get_edges(threshold: float = Query(0.75, ge=0.5, le=1.0)):
    """
    Get graph edges (similarity relationships between chunks).
    
    Args:
        threshold: Minimum similarity score (0.5-1.0, default 0.75)
        
    Returns:
        JSON with edges array (capped at 1000)
    """
    try:
        collection = get_collection()
        results = collection.get(include=["embeddings", "metadatas"])
        
        if not results.get("embeddings") or len(results["embeddings"]) == 0:
            return {"edges": []}
        
        embeddings = np.array(results["embeddings"])
        metadatas = results["metadatas"]

        # Calculate cosine similarity matrix
        sim_matrix = cosine_similarity(embeddings)
        edges = []

        for i, (src_meta, row) in enumerate(zip(metadatas, sim_matrix)):
            src_id = f"doc_{doc_hash(src_meta['source'])}_chunk_{src_meta.get('chunk', 0)}"
            
            for j, score in enumerate(row):
                if i == j or score < threshold:
                    continue
                    
                tgt_meta = metadatas[j]
                tgt_id = f"doc_{doc_hash(tgt_meta['source'])}_chunk_{tgt_meta.get('chunk', 0)}"
                
                edges.append({
                    "source": src_id,
                    "target": tgt_id,
                    "type": "similarity",
                    "weight": float(score),
                    "label": f"{score:.2f}"
                })
                
                # Cap at 1000 edges for performance
                if len(edges) >= 1000:
                    break
                    
            if len(edges) >= 1000:
                break

        logger.info(f"Returning {len(edges)} edges (threshold={threshold})")
        return {"edges": edges}
        
    except Exception as e:
        logger.error(f"Error getting edges: {e}")
        return {"edges": [], "error": str(e)}

