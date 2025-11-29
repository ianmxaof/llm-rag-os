"""
Production RAG Engine with caching, feedback loop, and performance optimization.
Connects to existing vector store and provides intelligent context retrieval.
"""

import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import time

import streamlit as st

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGEngine:
    """
    Production-grade RAG engine with:
    - Intelligent caching
    - User feedback integration
    - Performance monitoring
    - Adaptive retrieval
    """
    
    def __init__(self, feedback_log_path: str = "./logs/rag_feedback.jsonl"):
        self.feedback_log_path = Path(feedback_log_path)
        self.feedback_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Performance tracking
        self.retrieval_times = []
        self.cache_hits = 0
        self.cache_misses = 0
    
    def get_rag_context(
        self,
        query: str,
        k: int = None,
        settings: Dict = None,
        conversation_id: str = None,
        use_cache: bool = True
    ) -> List[Dict]:
        """
        Retrieve RAG context with caching and performance monitoring.
        
        Args:
            query: Search query
            k: Number of chunks to retrieve (defaults to settings['top_k'])
            settings: Configuration dict with 'top_k', 'relevance_threshold', etc.
            conversation_id: Current conversation ID for tracking
            use_cache: Whether to use cached results
            
        Returns:
            List of dicts with: id, source, score, preview, content
        """
        start_time = time.time()
        
        try:
            # Default settings
            settings = settings or {}
            k = k or settings.get('top_k', 8)
            threshold = settings.get('relevance_threshold', 0.25)
            
            # Try cache first
            if use_cache:
                cache_key = self._generate_cache_key(query, k, threshold)
                cached_result = self._get_cached_context(cache_key)
                
                if cached_result:
                    self.cache_hits += 1
                    logger.info(f"Cache hit for query: {query[:50]}...")
                    return cached_result
            
            self.cache_misses += 1
            
            # Import here to avoid circular dependencies
            from src.rag_utils import retrieve_context
            
            # Retrieve from vector store
            formatted_context, metadatas, documents, distances = retrieve_context(query, k=k * 2)  # Get 2x for filtering
            
            if not documents or not metadatas:
                logger.warning(f"No results for query: {query[:50]}...")
                return []
            
            # Process results
            chunks = self._process_retrieval_results(
                results={'documents': [documents], 'metadatas': [metadatas], 'distances': [distances]},
                threshold=threshold,
                max_chunks=k,
                conversation_id=conversation_id
            )
            
            # Cache results
            if use_cache and chunks:
                self._cache_context(cache_key, chunks)
            
            # Track performance
            retrieval_time = time.time() - start_time
            self.retrieval_times.append(retrieval_time)
            
            if retrieval_time > 2.0:
                logger.warning(f"Slow retrieval: {retrieval_time:.2f}s for query: {query[:50]}...")
            
            return chunks
        
        except Exception as e:
            logger.error(f"RAG context retrieval failed: {e}")
            return []
    
    def _process_retrieval_results(
        self,
        results: Dict,
        threshold: float,
        max_chunks: int,
        conversation_id: Optional[str] = None
    ) -> List[Dict]:
        """Process raw retrieval results into structured chunks."""
        
        documents = results.get('documents', [[]])[0]
        metadatas = results.get('metadatas', [[]])[0]
        distances = results.get('distances', [[]])[0]
        
        if not documents:
            return []
        
        chunks = []
        seen_sources = set()  # Deduplicate by source
        
        for idx, (text, metadata, distance) in enumerate(zip(documents, metadatas, distances)):
            # Convert distance to similarity score
            similarity = max(0.0, 1.0 - distance)
            
            # Apply user feedback adjustments
            adjusted_score = self._apply_feedback_adjustment(
                source=metadata.get('source', 'unknown'),
                base_score=similarity,
                conversation_id=conversation_id
            )
            
            # Filter by threshold
            if adjusted_score < threshold:
                continue
            
            # Extract source
            source = metadata.get('source', 'unknown')
            
            # Deduplicate by source (keep highest score)
            if source in seen_sources:
                # Check if this score is higher than existing
                existing_idx = next((i for i, c in enumerate(chunks) if c['source'] == source), None)
                if existing_idx is not None and adjusted_score > chunks[existing_idx]['score']:
                    chunks[existing_idx] = self._create_chunk_dict(
                        idx, text, metadata, adjusted_score
                    )
                continue
            
            seen_sources.add(source)
            
            # Create chunk
            chunk = self._create_chunk_dict(idx, text, metadata, adjusted_score)
            chunks.append(chunk)
            
            if len(chunks) >= max_chunks:
                break
        
        # Sort by adjusted score
        chunks.sort(key=lambda x: x['score'], reverse=True)
        
        return chunks[:max_chunks]
    
    def _create_chunk_dict(
        self,
        idx: int,
        text: str,
        metadata: Dict,
        score: float
    ) -> Dict:
        """Create standardized chunk dictionary."""
        
        source = metadata.get('source', 'unknown')
        
        return {
            'id': f"chunk_{idx}_{hashlib.md5(text.encode()).hexdigest()[:8]}",
            'source': source,
            'score': score,
            'preview': text[:150].strip() + "..." if len(text) > 150 else text.strip(),
            'content': text.strip(),
            'metadata': metadata
        }
    
    def adjust_chunk_relevance(
        self,
        chunk_id: str,
        source: str,
        adjustment: float,
        conversation_id: str,
        query: Optional[str] = None
    ) -> bool:
        """
        Store user feedback on chunk relevance.
        
        This creates a feedback loop that improves retrieval over time.
        
        Args:
            chunk_id: Unique chunk identifier
            source: Source document/note path
            adjustment: Score adjustment (+0.1 for boost, -0.1 for lower)
            conversation_id: Current conversation ID
            query: The query that retrieved this chunk
            
        Returns:
            True if feedback stored successfully
        """
        try:
            feedback_entry = {
                'timestamp': datetime.now().isoformat(),
                'chunk_id': chunk_id,
                'source': source,
                'adjustment': adjustment,
                'conversation_id': conversation_id,
                'query': query
            }
            
            # Append to feedback log (JSONL format)
            with open(self.feedback_log_path, 'a') as f:
                f.write(json.dumps(feedback_entry) + '\n')
            
            logger.info(f"Stored feedback: {adjustment:+.1f} for {source}")
            
            # Clear cache since feedback affects scores
            self._clear_cache()
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to store feedback: {e}")
            return False
    
    def _apply_feedback_adjustment(
        self,
        source: str,
        base_score: float,
        conversation_id: Optional[str] = None
    ) -> float:
        """
        Apply user feedback adjustments to base relevance score.
        
        Feedback decays over time and across conversations.
        """
        if not self.feedback_log_path.exists():
            return base_score
        
        try:
            # Load recent feedback for this source
            feedback_entries = []
            cutoff_date = datetime.now() - timedelta(days=30)  # 30-day memory
            
            with open(self.feedback_log_path, 'r') as f:
                for line in f:
                    entry = json.loads(line)
                    
                    # Filter by source and recency
                    if entry['source'] == source:
                        entry_date = datetime.fromisoformat(entry['timestamp'])
                        if entry_date > cutoff_date:
                            feedback_entries.append(entry)
            
            if not feedback_entries:
                return base_score
            
            # Calculate weighted adjustment
            total_adjustment = 0.0
            total_weight = 0.0
            
            for entry in feedback_entries:
                # Time decay: recent feedback has more weight
                entry_date = datetime.fromisoformat(entry['timestamp'])
                days_ago = (datetime.now() - entry_date).days
                time_weight = max(0.1, 1.0 - (days_ago / 30.0))  # Linear decay over 30 days
                
                # Conversation relevance: same conversation = higher weight
                conv_weight = 2.0 if entry['conversation_id'] == conversation_id else 1.0
                
                # Combined weight
                weight = time_weight * conv_weight
                
                total_adjustment += entry['adjustment'] * weight
                total_weight += weight
            
            # Average weighted adjustment
            if total_weight > 0:
                avg_adjustment = total_adjustment / total_weight
                adjusted_score = base_score + avg_adjustment
                
                # Clamp to [0, 1]
                adjusted_score = max(0.0, min(1.0, adjusted_score))
                
                return adjusted_score
            
            return base_score
        
        except Exception as e:
            logger.error(f"Failed to apply feedback adjustment: {e}")
            return base_score
    
    def _generate_cache_key(self, query: str, k: int, threshold: float) -> str:
        """Generate cache key from query parameters."""
        key_string = f"{query}_{k}_{threshold}"
        return hashlib.md5(key_string.encode()).hexdigest()
    
    # In-memory cache using LRU
    _cache = {}
    _cache_max_size = 100
    
    def _get_cached_context(self, cache_key: str) -> Optional[List[Dict]]:
        """Get cached context results."""
        return self._cache.get(cache_key)
    
    def _cache_context(self, cache_key: str, chunks: List[Dict]):
        """Cache context results."""
        # Simple LRU: remove oldest if at capacity
        if len(self._cache) >= self._cache_max_size:
            # Remove oldest entry (simple FIFO)
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        
        self._cache[cache_key] = chunks
    
    def _clear_cache(self):
        """Clear cache when feedback is updated."""
        self._cache.clear()
        logger.info("Cache cleared due to feedback update")
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics."""
        total_requests = self.cache_hits + self.cache_misses
        
        return {
            'total_requests': total_requests,
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'cache_hit_rate': self.cache_hits / total_requests if total_requests > 0 else 0.0,
            'avg_retrieval_time': sum(self.retrieval_times) / len(self.retrieval_times) if self.retrieval_times else 0.0,
            'max_retrieval_time': max(self.retrieval_times) if self.retrieval_times else 0.0,
            'min_retrieval_time': min(self.retrieval_times) if self.retrieval_times else 0.0
        }
    
    def export_feedback_summary(self, days: int = 30) -> Dict:
        """
        Export summary of user feedback for analysis.
        
        Useful for understanding which sources are consistently helpful.
        """
        if not self.feedback_log_path.exists():
            return {}
        
        cutoff_date = datetime.now() - timedelta(days=days)
        source_stats = {}
        
        with open(self.feedback_log_path, 'r') as f:
            for line in f:
                entry = json.loads(line)
                entry_date = datetime.fromisoformat(entry['timestamp'])
                
                if entry_date < cutoff_date:
                    continue
                
                source = entry['source']
                if source not in source_stats:
                    source_stats[source] = {
                        'total_feedback': 0,
                        'positive_feedback': 0,
                        'negative_feedback': 0,
                        'avg_adjustment': 0.0
                    }
                
                source_stats[source]['total_feedback'] += 1
                if entry['adjustment'] > 0:
                    source_stats[source]['positive_feedback'] += 1
                else:
                    source_stats[source]['negative_feedback'] += 1
                source_stats[source]['avg_adjustment'] += entry['adjustment']
        
        # Calculate averages
        for source in source_stats:
            count = source_stats[source]['total_feedback']
            source_stats[source]['avg_adjustment'] /= count
        
        return source_stats

# ============================================================================
# PUBLIC API
# ============================================================================

# Singleton instance
_engine = None

def get_rag_engine() -> RAGEngine:
    """Get or create RAG engine singleton."""
    global _engine
    if _engine is None:
        feedback_log = os.getenv('RAG_FEEDBACK_LOG', './logs/rag_feedback.jsonl')
        _engine = RAGEngine(feedback_log_path=feedback_log)
    return _engine

def get_rag_context(
    query: str,
    k: int = None,
    settings: Dict = None,
    conversation_id: str = None
) -> List[Dict]:
    """
    Public API: Retrieve RAG context with intelligent caching.
    
    Usage:
        chunks = get_rag_context(
            query="How do I implement RAG?",
            k=8,
            settings={'relevance_threshold': 0.25},
            conversation_id="abc123"
        )
    """
    engine = get_rag_engine()
    return engine.get_rag_context(query, k, settings, conversation_id)

def adjust_chunk_relevance(
    chunk_id: str,
    source: str,
    adjustment: float,
    conversation_id: str,
    query: Optional[str] = None
) -> bool:
    """
    Public API: Store user feedback on chunk relevance.
    
    Usage:
        success = adjust_chunk_relevance(
            chunk_id="chunk_0_a1b2c3d4",
            source="notes/rag_implementation.md",
            adjustment=0.1,  # +0.1 for boost, -0.1 for lower
            conversation_id="abc123",
            query="How do I implement RAG?"
        )
    """
    engine = get_rag_engine()
    return engine.adjust_chunk_relevance(chunk_id, source, adjustment, conversation_id, query)

def get_performance_stats() -> Dict:
    """Get RAG engine performance statistics."""
    engine = get_rag_engine()
    return engine.get_performance_stats()

def export_feedback_summary(days: int = 30) -> Dict:
    """Export summary of user feedback."""
    engine = get_rag_engine()
    return engine.export_feedback_summary(days)

# Keep backward compatibility
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
    """Cached RAG context retrieval - backward compatibility wrapper"""
    return get_rag_context(query, k=k, settings=settings)
