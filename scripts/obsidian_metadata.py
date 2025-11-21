"""
Obsidian Metadata Extraction
-----------------------------
Extracts YAML frontmatter, inline tags, and summary blocks from Obsidian markdown files.
Includes graceful fallback for broken YAML to prevent watcher crashes.
"""

import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional


def extract_yaml_frontmatter(content: str) -> tuple[Dict[str, Any], str]:
    """
    Extract YAML frontmatter from markdown content.
    
    Returns:
        tuple: (metadata_dict, body_content)
        - If YAML is broken, returns empty dict and full content
        - If no frontmatter, returns empty dict and full content
    """
    # Match YAML frontmatter pattern
    yaml_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    
    if not yaml_match:
        return {}, content
    
    yaml_str = yaml_match.group(1)
    body = content[yaml_match.end():] if yaml_match else content
    
    try:
        metadata = yaml.safe_load(yaml_str) or {}
        # Ensure all values are JSON-serializable
        metadata = _sanitize_metadata(metadata)
        return metadata, body
    except (yaml.YAMLError, yaml.MarkedYAMLError) as e:
        # Graceful fallback: log error but don't crash
        print(f"[WARN] Failed to parse YAML frontmatter: {e}")
        print(f"[WARN] Using empty metadata dict, continuing with body content")
        return {}, body


def extract_inline_tags(content: str) -> List[str]:
    """
    Extract inline tags from markdown content (#tag format).
    
    Returns:
        List of tag strings without the # prefix
    """
    # Match #tag patterns (not in code blocks)
    tag_pattern = r'(?<!`)#([a-zA-Z0-9_-]+)'
    tags = re.findall(tag_pattern, content)
    # Remove duplicates while preserving order
    seen = set()
    unique_tags = []
    for tag in tags:
        if tag.lower() not in seen:
            seen.add(tag.lower())
            unique_tags.append(tag)
    return unique_tags


def extract_summary_block(content: str) -> Optional[str]:
    """
    Extract summary from ^summary block format if present.
    
    Returns:
        Summary string or None if not found
    """
    summary_match = re.search(
        r'^\^summary\s*\n(.*?)(?=\n^|\Z)', 
        content, 
        re.MULTILINE | re.DOTALL
    )
    if summary_match:
        return summary_match.group(1).strip()
    return None


def extract_entities(metadata: Dict[str, Any]) -> List[str]:
    """
    Extract entities from AI Tagging Universe metadata.
    
    Looks for 'entities' field in metadata (can be list or comma-separated string).
    
    Returns:
        List of entity strings
    """
    entities = []
    if 'entities' in metadata:
        entities_value = metadata['entities']
        if isinstance(entities_value, list):
            entities = [str(e) for e in entities_value]
        elif isinstance(entities_value, str):
            # Handle comma-separated string
            entities = [e.strip() for e in entities_value.split(',') if e.strip()]
    return entities


def extract_all_metadata(file_path: Path) -> Dict[str, Any]:
    """
    Extract all metadata from an Obsidian markdown file.
    
    Combines:
    - YAML frontmatter
    - Inline tags
    - Summary blocks
    - Entities from AI Tagging Universe
    
    Returns:
        Complete metadata dictionary with all extracted fields
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"[ERROR] Failed to read file {file_path}: {e}")
        return {}
    
    # Extract YAML frontmatter (with graceful fallback)
    metadata, body = extract_yaml_frontmatter(content)
    
    # Add source file path
    metadata['source_file'] = str(file_path)
    
    # Extract inline tags and merge with YAML tags
    inline_tags = extract_inline_tags(body)
    if inline_tags:
        existing_tags = metadata.get('tags', [])
        if isinstance(existing_tags, str):
            existing_tags = [existing_tags]
        elif not isinstance(existing_tags, list):
            existing_tags = []
        # Merge and deduplicate
        all_tags = list(set(existing_tags + inline_tags))
        metadata['tags'] = all_tags
    
    # Extract summary block if not in YAML
    if 'summary' not in metadata or not metadata['summary']:
        summary_block = extract_summary_block(body)
        if summary_block:
            metadata['summary'] = summary_block
    
    # Extract entities
    entities = extract_entities(metadata)
    if entities:
        metadata['entities'] = entities
    
    return metadata


def _sanitize_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize metadata to ensure all values are JSON-serializable.
    
    Converts non-serializable types to strings.
    """
    sanitized = {}
    for key, value in metadata.items():
        if isinstance(value, (str, int, float, bool, type(None))):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [_sanitize_value(v) for v in value]
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_metadata(value)
        else:
            sanitized[key] = str(value)
    return sanitized


def _sanitize_value(value: Any) -> Any:
    """Sanitize a single value for JSON serialization."""
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    elif isinstance(value, (list, tuple)):
        return [_sanitize_value(v) for v in value]
    elif isinstance(value, dict):
        return _sanitize_metadata(value)
    else:
        return str(value)


def strip_frontmatter(content: str) -> str:
    """
    Remove YAML frontmatter from content, returning only the body.
    
    Returns:
        Content without frontmatter
    """
    yaml_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if yaml_match:
        return content[yaml_match.end():]
    return content

