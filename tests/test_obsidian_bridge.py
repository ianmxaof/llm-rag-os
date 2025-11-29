"""
Unit tests for Obsidian Bridge module
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from src.app.utils.obsidian_bridge import (
    get_related_notes,
    crystallize_to_vault,
    inject_note_context,
    get_vault_structure
)


@pytest.fixture
def temp_vault():
    """Create a temporary vault for testing"""
    temp_dir = tempfile.mkdtemp()
    vault_path = Path(temp_dir) / "test_vault"
    vault_path.mkdir(parents=True)
    
    # Create a test note
    test_note = vault_path / "test_note.md"
    test_note.write_text("# Test Note\n\nThis is a test note.", encoding='utf-8')
    
    yield vault_path
    
    shutil.rmtree(temp_dir)


def test_get_related_notes():
    """Test related notes retrieval"""
    related = get_related_notes("test context", top_k=5)
    assert isinstance(related, list)
    
    if related:
        assert 'title' in related[0]
        assert 'source' in related[0]
        assert 'score' in related[0]
        assert 0.0 <= related[0]['score'] <= 1.0


def test_crystallize_to_vault(temp_vault):
    """Test note crystallization"""
    import os
    os.environ['OBSIDIAN_VAULT_PATH'] = str(temp_vault)
    
    note_path = crystallize_to_vault(
        title="Test Crystallization",
        content="Test content",
        tags=['test'],
        linked_notes=[]
    )
    
    assert note_path is not None
    assert note_path.exists()
    assert note_path.suffix == '.md'
    
    # Check content
    content = note_path.read_text(encoding='utf-8')
    assert "Test Crystallization" in content
    assert "Test content" in content


def test_inject_note_context(temp_vault):
    """Test note context injection"""
    import os
    os.environ['OBSIDIAN_VAULT_PATH'] = str(temp_vault)
    
    test_note = temp_vault / "test_note.md"
    content = inject_note_context(str(test_note))
    
    assert content is not None
    assert "Test Note" in content or "test note" in content.lower()


def test_get_vault_structure(temp_vault):
    """Test vault structure retrieval"""
    import os
    os.environ['OBSIDIAN_VAULT_PATH'] = str(temp_vault)
    
    structure = get_vault_structure()
    
    assert isinstance(structure, dict)
    # Structure should have some organization
    assert 'notes' in structure or 'folders' in structure or 'files' in structure


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

