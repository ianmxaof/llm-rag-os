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


def split_oversized_chunks(
    chunks: List[Dict[str, Any]],
    max_chars: int = 1600,
    overlap: int = 120,
) -> List[Dict[str, Any]]:
    """Split heading chunks that exceed max_chars into fixed windows (CPU/ONNX RAM guard)."""
    if max_chars <= 0 or not chunks:
        return chunks

    out: List[Dict[str, Any]] = []
    step = max(1, max_chars - max(0, overlap))

    for chunk in chunks:
        text = chunk.get("text") or ""
        if len(text) <= max_chars:
            out.append(chunk)
            continue
        meta_base = dict(chunk.get("metadata") or {})
        part = 0
        for start in range(0, len(text), step):
            piece = text[start : start + max_chars]
            if not piece.strip():
                continue
            meta = meta_base.copy()
            section = meta.get("section") or ""
            if section:
                meta["section"] = f"{section} (part {part + 1})"
            meta["split_from_oversized"] = "true"
            out.append({"text": piece, "metadata": meta})
            part += 1

    for idx, chunk in enumerate(out):
        chunk["metadata"]["chunk_index"] = idx
        chunk["metadata"]["total_chunks"] = len(out)
    return out


def _vault_relative_path(file_path: str) -> str:
    """Return a vault-relative POSIX path for obsidian:// and CLI read/create."""
    from scripts.config import resolve_obsidian_vault_path

    raw = Path(file_path)
    vault = resolve_obsidian_vault_path()
    try:
        return raw.resolve().relative_to(vault).as_posix()
    except (OSError, ValueError):
        pass

    normalized = str(file_path).replace("\\", "/")
    marker = "knowledge/notes/"
    if marker in normalized:
        return normalized.split(marker, 1)[-1]
    return raw.name


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
    from scripts.config import resolve_obsidian_vault_name

    rel_path = _vault_relative_path(file_path)
    rel_path_encoded = urllib.parse.quote(rel_path)
    vault_encoded = urllib.parse.quote(resolve_obsidian_vault_name())
    uri = f"obsidian://open?vault={vault_encoded}&file={rel_path_encoded}"
    
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

