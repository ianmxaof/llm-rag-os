"""
Obsidian Bridge Utility
-----------------------
Bidirectional Obsidian vault integration with change detection.
"""

import os
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

from src.rag_utils import retrieve_context

logger = logging.getLogger(__name__)


class ObsidianBridge:
    """Bidirectional Obsidian vault integration"""
    
    def __init__(self, vault_path: str):
        self.vault_path = Path(vault_path)
        self._last_scan = None
        self._file_hashes = {}
    
    def get_related_notes(self, current_context: str, top_k: int = 5) -> List[Dict]:
        """Get related notes from vault via vector store"""
        try:
            # Retrieve from vector store
            formatted_context, metadatas, documents, distances = retrieve_context(
                query=current_context,
                k=top_k * 2  # Get more to deduplicate
            )
            
            if not metadatas or not documents:
                return []
            
            # Extract unique sources
            seen_sources = set()
            unique_notes = []
            
            for idx, (text, metadata, distance) in enumerate(zip(
                documents,
                metadatas,
                distances
            )):
                source = metadata.get('source', 'unknown')
                
                if source not in seen_sources and source != 'unknown':
                    seen_sources.add(source)
                    similarity = max(0.0, 1.0 - distance)
                    
                    # Extract title from source path
                    source_path = Path(source)
                    title = source_path.stem.replace('_', ' ').title()
                    
                    unique_notes.append({
                        'id': hashlib.md5(source.encode()).hexdigest()[:8],
                        'title': title,
                        'source': source,
                        'score': similarity
                    })
                    
                    if len(unique_notes) >= top_k:
                        break
            
            return unique_notes
        
        except Exception as e:
            logger.error(f"Error retrieving related notes: {e}")
            return []
    
    def detect_vault_changes(self) -> List[Path]:
        """Detect new or modified files since last scan"""
        if not self.vault_path.exists():
            return []
        
        changed_files = []
        current_time = datetime.now()
        
        for md_file in self.vault_path.rglob("*.md"):
            # Skip templates and archive folders
            if any(skip in str(md_file) for skip in ['.trash', 'templates', 'archive', '_archive', '.obsidian']):
                continue
            
            file_hash = self._hash_file(md_file)
            
            # New or modified file
            if md_file not in self._file_hashes or self._file_hashes[md_file] != file_hash:
                changed_files.append(md_file)
                self._file_hashes[md_file] = file_hash
        
        self._last_scan = current_time
        return changed_files
    
    def crystallize_to_vault(
        self, 
        title: str, 
        content: str, 
        tags: List[str] = None,
        linked_notes: List[str] = None
    ) -> Path:
        """Write conversation insights back to Obsidian vault"""
        try:
            # Create crystallized notes folder if doesn't exist
            crystal_dir = self.vault_path / "crystallized"
            crystal_dir.mkdir(exist_ok=True)
            
            # Generate filename from title
            filename = self._sanitize_filename(title) + ".md"
            note_path = crystal_dir / filename
            
            # Build frontmatter
            frontmatter = "---\n"
            frontmatter += f"created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            frontmatter += f"tags: {', '.join(tags or ['crystallized', 'powercore'])}\n"
            frontmatter += "---\n\n"
            
            # Build content with backlinks
            full_content = frontmatter
            full_content += f"# {title}\n\n"
            full_content += content + "\n\n"
            
            if linked_notes:
                full_content += "## Connected Notes\n"
                for note in linked_notes:
                    note_name = Path(note).stem
                    full_content += f"- [[{note_name}]]\n"
            
            # Write to file
            note_path.write_text(full_content, encoding='utf-8')
            
            return note_path
        
        except Exception as e:
            logger.error(f"Error crystallizing to vault: {e}")
            raise
    
    def _hash_file(self, filepath: Path) -> str:
        """Generate hash of file content for change detection"""
        try:
            return hashlib.md5(filepath.read_bytes()).hexdigest()
        except Exception as e:
            logger.error(f"Error hashing file {filepath}: {e}")
            return ""
    
    def _sanitize_filename(self, title: str) -> str:
        """Convert title to valid filename"""
        # Remove invalid chars, replace spaces with underscores
        valid_chars = "-_.() abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        filename = ''.join(c if c in valid_chars else '_' for c in title)
        return filename[:100]  # Limit length


# Singleton instance
_bridge = None


def get_obsidian_bridge() -> ObsidianBridge:
    """Get or create Obsidian bridge instance"""
    global _bridge
    if _bridge is None:
        vault_path = os.getenv('OBSIDIAN_VAULT_PATH', './knowledge/notes')
        _bridge = ObsidianBridge(vault_path)
    return _bridge


def get_related_notes(current_context: str, top_k: int = 5) -> List[Dict]:
    """Public API for getting related notes"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.get_related_notes(current_context, top_k)
    except Exception as e:
        logger.error(f"Error in get_related_notes: {e}")
        return []

