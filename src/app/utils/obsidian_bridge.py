"""
Obsidian Bridge Utility
-----------------------
Bidirectional Obsidian vault integration with change detection.
"""

import os
import hashlib
import json
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
    
    def inject_note_context(self, source_path: str) -> Optional[str]:
        """
        Load full note content for context injection.
        
        Args:
            source_path: Path to note file (relative to vault or absolute)
            
        Returns:
            Note content as string, or None if file not found
        """
        try:
            # Handle both relative and absolute paths
            if Path(source_path).is_absolute():
                note_path = Path(source_path)
            else:
                # Try to find in vault
                note_path = self.vault_path / source_path
            
            if not note_path.exists():
                logger.warning(f"Note not found: {source_path}")
                return None
            
            content = note_path.read_text(encoding='utf-8')
            
            # Strip YAML frontmatter if present
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            
            return content
        
        except Exception as e:
            logger.error(f"Error loading note {source_path}: {e}")
            return None
    
    def open_in_obsidian(self, source_path: str) -> bool:
        """
        Open note in Obsidian using URI scheme.
        
        Args:
            source_path: Path to note file (relative to vault)
            
        Returns:
            True if URI was opened successfully
        """
        try:
            import webbrowser
            
            # Get vault name from path
            vault_name = self.vault_path.name
            
            # Convert to relative path from vault root
            if Path(source_path).is_absolute():
                try:
                    rel_path = Path(source_path).relative_to(self.vault_path)
                except ValueError:
                    logger.warning(f"Path {source_path} not in vault {self.vault_path}")
                    return False
            else:
                rel_path = Path(source_path)
            
            # Build Obsidian URI
            uri = f"obsidian://open?vault={vault_name}&file={rel_path.as_posix()}"
            
            # Open URI
            webbrowser.open(uri)
            
            logger.info(f"Opened {source_path} in Obsidian")
            return True
        
        except Exception as e:
            logger.error(f"Error opening note in Obsidian: {e}")
            return False
    
    def get_vault_structure(self, max_depth: int = 2) -> Dict:
        """
        Get vault directory structure for navigation.
        
        Args:
            max_depth: Maximum directory depth to traverse
            
        Returns:
            Dict with folder structure
        """
        structure = {}
        
        if not self.vault_path.exists():
            return structure
        
        def build_tree(path: Path, depth: int = 0):
            if depth > max_depth:
                return {}
            
            tree = {}
            
            try:
                for item in sorted(path.iterdir()):
                    if item.name.startswith('.') or item.name in ['node_modules', '__pycache__']:
                        continue
                    
                    if item.is_dir():
                        tree[item.name] = {
                            'type': 'folder',
                            'children': build_tree(item, depth + 1),
                            'path': str(item.relative_to(self.vault_path))
                        }
                    elif item.suffix == '.md':
                        if 'files' not in tree:
                            tree['files'] = []
                        tree['files'].append({
                            'name': item.stem,
                            'path': str(item.relative_to(self.vault_path))
                        })
            except PermissionError:
                pass
            
            return tree
        
        structure = build_tree(self.vault_path)
        return structure
    
    def search_vault(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Full-text search across vault notes.
        
        Args:
            query: Search query string
            max_results: Maximum number of results
            
        Returns:
            List of matching notes with preview
        """
        results = []
        
        if not self.vault_path.exists():
            return results
        
        query_lower = query.lower()
        
        try:
            for md_file in self.vault_path.rglob("*.md"):
                # Skip hidden and system folders
                if any(skip in str(md_file) for skip in ['.trash', '.obsidian', 'templates']):
                    continue
                
                try:
                    content = md_file.read_text(encoding='utf-8')
                    content_lower = content.lower()
                    
                    # Simple text matching (could be enhanced with regex or fuzzy matching)
                    if query_lower in content_lower:
                        # Find context around match
                        idx = content_lower.find(query_lower)
                        start = max(0, idx - 100)
                        end = min(len(content), idx + len(query) + 100)
                        preview = content[start:end]
                        
                        # Extract title (first line or filename)
                        lines = content.split('\n')
                        title = lines[0].replace('#', '').strip() if lines else md_file.stem
                        
                        results.append({
                            'title': title,
                            'source': str(md_file.relative_to(self.vault_path)),
                            'preview': preview,
                            'match_position': idx
                        })
                        
                        if len(results) >= max_results:
                            break
                
                except Exception as e:
                    logger.debug(f"Error reading {md_file}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Error searching vault: {e}")
        
        # Sort by match position (earlier matches first)
        results.sort(key=lambda x: x['match_position'])
        
        return results
    
    def crystallize_to_vault(
        self, 
        title: str, 
        content: str, 
        tags: List[str] = None,
        linked_notes: List[str] = None,
        metadata: Dict = None
    ) -> Path:
        """
        Write conversation insights back to Obsidian vault with enhanced frontmatter.
        
        Args:
            title: Note title
            content: Note content
            tags: List of tags
            linked_notes: List of note paths to link
            metadata: Additional metadata dict
            
        Returns:
            Path to created note
        """
        try:
            # Create crystallized notes folder if doesn't exist
            crystal_dir = self.vault_path / "crystallized"
            crystal_dir.mkdir(exist_ok=True)
            
            # Generate filename from title
            filename = self._sanitize_filename(title) + ".md"
            note_path = crystal_dir / filename
            
            # Handle duplicates
            counter = 1
            while note_path.exists():
                name_parts = filename.rsplit(".", 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    new_name = f"{filename}_{counter}"
                note_path = crystal_dir / new_name
                counter += 1
            
            # Build enhanced frontmatter
            frontmatter = "---\n"
            frontmatter += f"created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            frontmatter += f"tags: [{', '.join([f'\"{tag}\"' for tag in (tags or ['crystallized', 'powercore'])])}]\n"
            
            # Add metadata if provided
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, str):
                        frontmatter += f"{key}: {value}\n"
                    elif isinstance(value, (int, float)):
                        frontmatter += f"{key}: {value}\n"
                    else:
                        frontmatter += f"{key}: {json.dumps(value)}\n"
            
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

def inject_note_context(source_path: str) -> Optional[str]:
    """Public API: Load note content for injection"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.inject_note_context(source_path)
    except Exception as e:
        logger.error(f"Error injecting note context: {e}")
        return None

def crystallize_to_vault(
    title: str,
    content: str,
    tags: List[str] = None,
    linked_notes: List[str] = None,
    metadata: Dict = None
) -> Path:
    """Public API: Crystallize content to Obsidian vault"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.crystallize_to_vault(title, content, tags, linked_notes, metadata)
    except Exception as e:
        logger.error(f"Error crystallizing to vault: {e}")
        raise

def open_in_obsidian(source_path: str) -> bool:
    """Public API: Open note in Obsidian"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.open_in_obsidian(source_path)
    except Exception as e:
        logger.error(f"Error opening in Obsidian: {e}")
        return False

def detect_vault_changes() -> List[Path]:
    """Public API: Detect vault changes"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.detect_vault_changes()
    except Exception as e:
        logger.error(f"Error detecting vault changes: {e}")
        return []

def get_vault_structure(max_depth: int = 2) -> Dict:
    """Public API: Get vault structure"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.get_vault_structure(max_depth)
    except Exception as e:
        logger.error(f"Error getting vault structure: {e}")
        return {}

def search_vault(query: str, max_results: int = 20) -> List[Dict]:
    """Public API: Search vault"""
    try:
        bridge = get_obsidian_bridge()
        return bridge.search_vault(query, max_results)
    except Exception as e:
        logger.error(f"Error searching vault: {e}")
        return []

