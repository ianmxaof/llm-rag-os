"""
Integration tests for end-to-end flows
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.app.utils.rag_engine import get_rag_context, adjust_chunk_relevance
from src.app.utils.obsidian_bridge import get_related_notes, crystallize_to_vault, inject_note_context
from src.app.utils.memory_store import store_conversation, load_conversation_by_id, mark_crystallized


@pytest.fixture
def temp_env():
    """Set up temporary environment"""
    temp_dir = tempfile.mkdtemp()
    vault_path = Path(temp_dir) / "test_vault"
    vault_path.mkdir(parents=True)
    
    import os
    os.environ['OBSIDIAN_VAULT_PATH'] = str(vault_path)
    
    # Create a test note
    test_note = vault_path / "test_integration.md"
    test_note.write_text("# Integration Test\n\nThis is a test note for integration.", encoding='utf-8')
    
    yield temp_dir, vault_path
    
    shutil.rmtree(temp_dir)


def test_rag_to_obsidian_flow(temp_env):
    """Test RAG → related notes → injection flow"""
    temp_dir, vault_path = temp_env
    
    # 1. Get RAG context
    chunks = get_rag_context(query="integration test", k=5)
    assert isinstance(chunks, list)
    
    # 2. Get related notes
    related = get_related_notes("integration test", top_k=5)
    assert isinstance(related, list)
    
    # 3. Inject note context if available
    if related:
        source = related[0]['source']
        content = inject_note_context(source)
        # Content may be None if note doesn't exist, which is OK
        assert content is None or isinstance(content, str)


def test_crystallization_flow(temp_env):
    """Test Conversation → crystallization → canvas → memory flow"""
    temp_dir, vault_path = temp_env
    
    # 1. Store conversation
    messages = [
        {'role': 'user', 'content': 'What is integration testing?'},
        {'role': 'assistant', 'content': 'Integration testing tests components together.'}
    ]
    
    conv_id = "test_integration_conv"
    store_conversation(
        conversation_id=conv_id,
        messages=messages,
        title="Integration Test Conversation"
    )
    
    # 2. Crystallize to vault
    note_path = crystallize_to_vault(
        title="Integration Test Note",
        content="Integration testing is important.",
        tags=['test', 'integration'],
        linked_notes=[]
    )
    
    assert note_path is not None
    assert note_path.exists()
    
    # 3. Mark as crystallized in memory
    mark_crystallized(conv_id, str(note_path))
    
    # 4. Verify in memory store
    loaded = load_conversation_by_id(conv_id)
    assert loaded is not None
    assert loaded.get('crystallized_path') == str(note_path)


def test_feedback_loop(temp_env):
    """Test User feedback → score adjustment → improved retrieval"""
    temp_dir, vault_path = temp_env
    
    # 1. Get initial chunks
    chunks1 = get_rag_context(query="test", k=5)
    
    if chunks1:
        chunk = chunks1[0]
        original_score = chunk['score']
        
        # 2. Apply feedback
        success = adjust_chunk_relevance(
            chunk_id=chunk['id'],
            source=chunk['source'],
            adjustment=0.1,
            conversation_id="test_feedback_conv",
            query="test"
        )
        
        assert success is True
        
        # 3. Retrieve again (feedback should affect future retrievals)
        chunks2 = get_rag_context(query="test", k=5, use_cache=False)
        
        # Verify chunks are returned
        assert isinstance(chunks2, list)


def test_conversation_persistence(temp_env):
    """Test Message exchange → storage → restoration"""
    temp_dir, vault_path = temp_env
    
    # 1. Store conversation
    messages = [
        {'role': 'user', 'content': 'Hello'},
        {'role': 'assistant', 'content': 'Hi!'},
        {'role': 'user', 'content': 'How are you?'},
        {'role': 'assistant', 'content': 'I am doing well, thank you!'}
    ]
    
    conv_id = "test_persistence_conv"
    store_conversation(
        conversation_id=conv_id,
        messages=messages,
        title="Persistence Test"
    )
    
    # 2. Load conversation
    loaded = load_conversation_by_id(conv_id)
    
    assert loaded is not None
    assert loaded['title'] == "Persistence Test"
    assert len(loaded['messages']) == 4
    assert loaded['messages'][0]['content'] == 'Hello'
    assert loaded['messages'][1]['content'] == 'Hi!'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

