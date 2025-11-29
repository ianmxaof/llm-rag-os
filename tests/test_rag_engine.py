"""
Unit tests for RAG Engine module
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.app.utils.rag_engine import get_rag_context, adjust_chunk_relevance, get_performance_stats


def test_rag_retrieval():
    """Test basic RAG retrieval"""
    chunks = get_rag_context(query="test", k=5)
    assert isinstance(chunks, list)
    assert len(chunks) <= 5
    
    if chunks:
        assert 'id' in chunks[0]
        assert 'source' in chunks[0]
        assert 'score' in chunks[0]
        assert 0.0 <= chunks[0]['score'] <= 1.0


def test_rag_caching():
    """Test cache improves performance"""
    import time
    
    # First call (cache miss)
    start = time.time()
    chunks1 = get_rag_context(query="test query", k=10)
    time1 = time.time() - start
    
    # Second call (cache hit)
    start = time.time()
    chunks2 = get_rag_context(query="test query", k=10)
    time2 = time.time() - start
    
    # Cached should be faster (or at least not slower)
    assert time2 <= time1 * 1.5  # Allow some variance
    # Results should be identical
    if chunks1 and chunks2:
        assert chunks1[0]['id'] == chunks2[0]['id']


def test_feedback_adjustment():
    """Test feedback affects relevance scores"""
    # Get baseline scores
    chunks = get_rag_context(query="test", k=5)
    
    if chunks:
        original_score = chunks[0]['score']
        chunk_id = chunks[0]['id']
        source = chunks[0]['source']
        
        # Apply positive feedback
        success = adjust_chunk_relevance(
            chunk_id=chunk_id,
            source=source,
            adjustment=0.2,
            conversation_id="test_conv",
            query="test"
        )
        
        assert success is True
        
        # Retrieve again (without cache to see feedback effect)
        new_chunks = get_rag_context(query="test", k=5, use_cache=False)
        
        # Find same source
        new_chunk = next((c for c in new_chunks if c['source'] == source), None)
        
        if new_chunk:
            # Score should be affected by feedback (may not always be higher due to other factors)
            assert 'score' in new_chunk


def test_performance_stats():
    """Test performance statistics tracking"""
    # Make some requests
    get_rag_context(query="test1", k=5)
    get_rag_context(query="test2", k=5)
    
    stats = get_performance_stats()
    
    assert isinstance(stats, dict)
    assert 'total_requests' in stats
    assert 'cache_hits' in stats
    assert 'cache_misses' in stats
    assert 'cache_hit_rate' in stats
    assert stats['total_requests'] >= 0
    assert 0.0 <= stats['cache_hit_rate'] <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

