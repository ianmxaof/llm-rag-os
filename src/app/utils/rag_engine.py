"""
RAG Engine Utility
------------------
Provides RAG context retrieval with caching and error handling.
"""

import hashlib
import json
import logging
from typing import Dict, List, Optional

import streamlit as st

from src.rag_utils import retrieve_context

logger = logging.getLogger(__name__)


def _compute_context_hash(messages: list, settings: dict) -> str:
    """Create hash of conversation state for caching"""
    content = "".join([
        m.get('content', m.get('question', '')) 
        for m in messages[-5:]
    ])
    settings_str = json.dumps(settings, sort_keys=True)
    return hashlib.md5(f"{content}{settings_str}".encode()).hexdigest()


@st.cache_data(ttl=300)  # Cache for 5 minutes
def get_rag_context_cached(context_hash: str, query: str, k: int, settings: dict):
    """Cached RAG context retrieval"""
    return get_rag_context(query, k=k, settings=settings)


def get_rag_context(query: str, k: int = None, settings: Dict = None) -> List[Dict]:
    """
    Retrieve RAG context chunks with similarity scores.
    
    Args:
        query: Search query string
        k: Number of chunks to retrieve (defaults to settings['top_k'] or 8)
        settings: Settings dict with 'top_k' key
        
    Returns:
        List of dicts with: id, source, score, preview, content
    """
    try:
        if k is None:
            k = settings.get('top_k', 8) if settings else 8
        
        # Retrieve context from vector store
        formatted_context, metadatas, documents, distances = retrieve_context(query, k=k)
        
        # Convert distances to similarities
        similarities = [max(0.0, 1.0 - dist) for dist in distances] if distances else [0.0]
        
        # Build result list
        chunks = []
        for idx, (doc, meta, similarity) in enumerate(zip(documents, metadatas, similarities)):
            source = meta.get('source', 'unknown')
            chunk_id = hashlib.md5(f"{source}_{idx}".encode()).hexdigest()[:8]
            
            chunks.append({
                'id': chunk_id,
                'source': source,
                'score': similarity,
                'preview': doc[:150] + '...' if len(doc) > 150 else doc,
                'content': doc,
                'metadata': meta
            })
        
        return chunks
    
    except Exception as e:
        logger.error(f"Error retrieving RAG context: {e}")
        return []


def adjust_chunk_relevance(
    chunk_id: str, 
    source: str, 
    adjustment: float,
    conversation_id: str
) -> bool:
    """
    Store user feedback on RAG chunk relevance.
    
    This can be used to:
    1. Immediately re-rank current results
    2. Train a relevance model over time
    3. Adjust retrieval parameters
    
    Args:
        chunk_id: Unique identifier for the chunk
        source: Source file path
        adjustment: Relevance adjustment (+0.1 for boost, -0.1 for lower)
        conversation_id: Current conversation ID
        
    Returns:
        True if feedback was logged successfully
    """
    from datetime import datetime
    
    try:
        # Log feedback for future model training
        feedback_log = {
            'chunk_id': chunk_id,
            'source': source,
            'adjustment': adjustment,
            'conversation_id': conversation_id,
            'timestamp': datetime.now().isoformat()
        }
        logger.info(f"RAG Feedback: {feedback_log}")
        
        # TODO: Store in metadata or separate feedback DB
        # For now, just log it
        # Optionally: Update metadata with user preference
        # This is database-specific
        # collection.update(
        #     ids=[chunk_id],
        #     metadatas=[{'user_relevance_boost': adjustment}]
        # )
        
        return True
    
    except Exception as e:
        logger.error(f"Failed to adjust relevance: {e}")
        return False

