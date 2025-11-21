"""
Obsidian Semantic Chunking by Headings
---------------------------------------
Chunks markdown content by H1-H6 headings with configurable overlap.
Preserves document metadata on each chunk and attaches section headings.
"""

import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, List


def chunk_by_headings(
    body: str,
    metadata: Dict[str, Any],
    overlap: int = 150,
    min_chunk_size: int = 200
) -> List[Dict[str, Any]]:
    """
    Chunk markdown content by headings (H1-H6) with overlap.
    
    Args:
        body: Markdown content (without frontmatter)
        metadata: Document metadata to attach to each chunk
        overlap: Number of characters to overlap between chunks
        min_chunk_size: Minimum chunk size in characters
    
    Returns:
        List of chunk dictionaries with 'text' and 'metadata' keys
    """
    if not body.strip():
        return []
    
    chunks = []
    
    # Split on headings (H1-H6)
    # Pattern matches: # Heading, ## Heading, etc.
    heading_pattern = r'(^#{1,6}\s+.+?$)'
    sections = re.split(heading_pattern, body, flags=re.MULTILINE)
    
    current_chunk = {
        'text': '',
        'metadata': metadata.copy()
    }
    
    for i, part in enumerate(sections):
        if not part.strip():
            continue
        
        # Check if this part is a heading
        if re.match(r'^#{1,6}\s+.+?$', part, re.MULTILINE):
            # New heading: finalize previous chunk if big enough
            if len(current_chunk['text'].strip()) >= min_chunk_size:
                chunks.append(current_chunk)
            
            # Start new chunk with heading
            current_chunk = {
                'text': part + '\n',
                'metadata': metadata.copy()
            }
            current_chunk['metadata']['section'] = part.strip()
        else:
            # Content: add to current chunk
            current_chunk['text'] += part
            
            # Add overlap from previous chunk if available
            if len(chunks) > 0 and len(part) > 0:
                prev_text = chunks[-1]['text']
                if len(prev_text) > overlap:
                    overlap_text = prev_text[-overlap:]
                    # Only add overlap if not already present
                    if not current_chunk['text'].startswith(overlap_text):
                        current_chunk['text'] = overlap_text + current_chunk['text']
    
    # Final chunk
    if len(current_chunk['text'].strip()) >= min_chunk_size:
        chunks.append(current_chunk)
    elif len(current_chunk['text'].strip()) > 0 and len(chunks) == 0:
        # If only one small chunk, include it anyway
        chunks.append(current_chunk)
    
    # Add chunk index to metadata
    for idx, chunk in enumerate(chunks):
        chunk['metadata']['chunk_index'] = idx
        chunk['metadata']['total_chunks'] = len(chunks)
    
    return chunks


def generate_obsidian_uri(file_path: str, chunk_index: int, section: str = None) -> str:
    """
    Generate obsidian:// URI for deep linking to specific section.
    
    Args:
        file_path: Full path to Obsidian note
        chunk_index: Chunk index in document
        section: Section heading (optional)
    
    Returns:
        obsidian:// URI string
    """
    import urllib.parse
    
    # Convert Windows path to Obsidian vault-relative path
    # Assuming vault root is knowledge/notes/
    file_path_normalized = file_path.replace('\\', '/')
    
    if 'knowledge/notes/' in file_path_normalized:
        rel_path = file_path_normalized.split('knowledge/notes/')[-1]
    elif 'knowledge\\notes\\' in file_path:
        rel_path = file_path.split('knowledge\\notes\\')[-1].replace('\\', '/')
    else:
        # Try to extract relative path
        rel_path = Path(file_path).name
    
    # URL encode the path
    rel_path_encoded = urllib.parse.quote(rel_path)
    
    # Build URI (Obsidian uses vault name, not full path)
    # For now, use file parameter - vault detection happens in Obsidian
    uri = f"obsidian://open?file={rel_path_encoded}"
    
    # Add block reference if section provided
    if section:
        # Convert heading to block ID (Obsidian block format: ^block-id)
        # Remove markdown heading markers
        block_text = re.sub(r'^#+\s+', '', section).strip()
        # Convert to block ID format
        block_id = block_text.lower().replace(' ', '-')
        # Remove special characters, keep hyphens
        block_id = re.sub(r'[^\w-]', '', block_id)
        # Add block reference
        uri += f"&block=^{block_id}"
    
    return uri

