"""
Unit tests for Memory Store module
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.app.utils.memory_store import (
    store_conversation,
    load_conversation_by_id,
    get_memory_streams,
    mark_crystallized,
    search_conversations,
    get_memory_statistics
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing"""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_memory.db"
    
    # Set environment variable
    import os
    os.environ['MEMORY_DB_PATH'] = str(db_path)
    
    yield db_path
    
    shutil.rmtree(temp_dir)


def test_store_conversation(temp_db):
    """Test conversation storage"""
    messages = [
        {'role': 'user', 'content': 'Hello'},
        {'role': 'assistant', 'content': 'Hi there!'}
    ]
    
    store_conversation(
        conversation_id="test_conv_1",
        messages=messages,
        title="Test Conversation",
        tags=['test']
    )
    
    # Verify it was stored
    loaded = load_conversation_by_id("test_conv_1")
    assert loaded is not None
    assert loaded['title'] == "Test Conversation"
    assert len(loaded['messages']) == 2


def test_load_conversation_by_id(temp_db):
    """Test conversation loading"""
    messages = [
        {'role': 'user', 'content': 'Test question'},
        {'role': 'assistant', 'content': 'Test answer'}
    ]
    
    store_conversation(
        conversation_id="test_conv_2",
        messages=messages,
        title="Load Test"
    )
    
    loaded = load_conversation_by_id("test_conv_2")
    assert loaded is not None
    assert loaded['title'] == "Load Test"
    assert loaded['messages'][0]['content'] == 'Test question'
    assert loaded['messages'][1]['content'] == 'Test answer'


def test_get_memory_streams(temp_db):
    """Test memory streams retrieval"""
    # Store a few conversations
    for i in range(3):
        store_conversation(
            conversation_id=f"test_conv_{i}",
            messages=[{'role': 'user', 'content': f'Message {i}'}],
            title=f"Conversation {i}"
        )
    
    streams = get_memory_streams(days_back=30)
    assert isinstance(streams, list)
    assert len(streams) >= 3


def test_mark_crystallized(temp_db):
    """Test crystallization marking"""
    store_conversation(
        conversation_id="test_conv_3",
        messages=[{'role': 'user', 'content': 'Test'}],
        title="Crystallization Test"
    )
    
    mark_crystallized("test_conv_3", "/path/to/note.md")
    
    loaded = load_conversation_by_id("test_conv_3")
    assert loaded is not None
    assert loaded.get('crystallized_path') == "/path/to/note.md"


def test_search_conversations(temp_db):
    """Test conversation search"""
    store_conversation(
        conversation_id="test_conv_4",
        messages=[
            {'role': 'user', 'content': 'Python programming'},
            {'role': 'assistant', 'content': 'Python is great'}
        ],
        title="Python Chat"
    )
    
    results = search_conversations("Python", limit=10)
    assert isinstance(results, list)
    assert len(results) > 0
    assert any("Python" in r['title'] or "python" in r['title'].lower() for r in results)


def test_get_memory_statistics(temp_db):
    """Test memory statistics"""
    # Store some conversations
    for i in range(5):
        store_conversation(
            conversation_id=f"stats_conv_{i}",
            messages=[{'role': 'user', 'content': f'Message {i}'}],
            title=f"Stats Test {i}"
        )
    
    stats = get_memory_statistics()
    assert isinstance(stats, dict)
    assert 'total_conversations' in stats
    assert stats['total_conversations'] >= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

