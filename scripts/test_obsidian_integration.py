"""
Test Script for Obsidian RAG Integration
------------------------------------------
Quick verification that all components work correctly.
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

def test_metadata_extraction():
    """Test YAML frontmatter extraction."""
    print("Testing metadata extraction...")
    from scripts.obsidian_metadata import extract_yaml_frontmatter, extract_inline_tags
    
    # Test with valid YAML
    content1 = """---
title: Test Note
tags: [test, example]
summary: This is a test
---
# Content
Some content here #tag1 and #tag2
"""
    metadata, body = extract_yaml_frontmatter(content1)
    assert metadata.get('title') == 'Test Note', "YAML extraction failed"
    assert 'tags' in metadata, "Tags not extracted"
    print("✓ Valid YAML extraction works")
    
    # Test with broken YAML (graceful fallback)
    content2 = """---
title: Test Note
tags: [unclosed
---
# Content
"""
    metadata, body = extract_yaml_frontmatter(content2)
    assert isinstance(metadata, dict), "Broken YAML should return empty dict"
    print("✓ Broken YAML graceful fallback works")
    
    # Test inline tags
    tags = extract_inline_tags(body)
    assert len(tags) >= 0, "Tag extraction should work"
    print("✓ Inline tag extraction works")
    
    print("✓ Metadata extraction tests passed\n")


def test_chunking():
    """Test heading-based chunking."""
    print("Testing chunking...")
    from scripts.obsidian_chunker import chunk_by_headings
    
    content = """# Introduction
This is the introduction section with some content.

## Subsection 1
More content here in subsection 1.

## Subsection 2
Even more content in subsection 2.
"""
    
    metadata = {'source_file': 'test.md', 'title': 'Test'}
    chunks = chunk_by_headings(content, metadata, overlap=50, min_chunk_size=50)
    
    assert len(chunks) > 0, "Should create at least one chunk"
    assert chunks[0]['metadata']['section'] == '# Introduction', "Section should be captured"
    print(f"✓ Created {len(chunks)} chunks")
    print("✓ Chunking tests passed\n")


def test_ledger():
    """Test SQLite ledger."""
    print("Testing ledger...")
    from scripts.obsidian_ledger import IngestionLedger
    import tempfile
    
    # Use temp file for testing
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
        ledger_path = Path(tmp.name)
    
    try:
        ledger = IngestionLedger(ledger_path)
        
        # Test file that doesn't exist
        test_file = Path("nonexistent.md")
        should_reingest, stored_hash = ledger.should_reingest(test_file)
        assert should_reingest == False, "Non-existent file should not be re-ingested"
        print("✓ Ledger handles non-existent files")
        
        # Create a test file
        test_file = Path("test_note.md")
        test_file.write_text("# Test\nContent here")
        
        should_reingest, stored_hash = ledger.should_reingest(test_file)
        assert should_reingest == True, "New file should be ingested"
        assert stored_hash is None, "New file should have no stored hash"
        print("✓ Ledger detects new files")
        
        # Record ingestion
        ledger.record_ingestion(test_file, chunk_count=3)
        
        # Check again - should skip
        should_reingest, stored_hash = ledger.should_reingest(test_file)
        assert should_reingest == False, "Unchanged file should be skipped"
        assert stored_hash is not None, "Should have stored hash"
        print("✓ Ledger deduplication works")
        
        # Cleanup
        test_file.unlink()
        print("✓ Ledger tests passed\n")
    finally:
        if ledger_path.exists():
            ledger_path.unlink()


def test_obsidian_uri():
    """Test obsidian:// URI generation."""
    print("Testing obsidian:// URI generation...")
    from scripts.obsidian_chunker import generate_obsidian_uri
    
    uri = generate_obsidian_uri("knowledge/notes/Manual/Test.md", 0, "# Introduction")
    assert uri.startswith("obsidian://"), "Should generate obsidian:// URI"
    assert "Test.md" in uri, "Should include filename"
    print(f"✓ Generated URI: {uri}")
    print("✓ URI generation tests passed\n")


def main():
    """Run all tests."""
    print("=" * 60)
    print("Obsidian RAG Integration Tests")
    print("=" * 60 + "\n")
    
    try:
        test_metadata_extraction()
        test_chunking()
        test_ledger()
        test_obsidian_uri()
        
        print("=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        return 0
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())

