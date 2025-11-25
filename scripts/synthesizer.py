"""
The Synthesizer - MOC Generation (Future Feature)
--------------------------------------------------
Enables AI to generate Map of Content (MOC) notes by synthesizing related content
from vector store. Transforms AI from librarian to knowledge engineer.

Planned for: January 2026
"""

import logging
from pathlib import Path
from typing import List, Dict, Optional
import requests

logger = logging.getLogger(__name__)

# Configuration (will be set from config.py)
OLLAMA_API_BASE = "http://localhost:11434/api"
SYNTHESIZER_MODEL = "llama3.1:70b"  # Use larger model for synthesis quality


MOC_PROMPT_TEMPLATE = """You are a knowledge engineer creating a Map of Content (MOC) note.
A MOC synthesizes multiple related notes into a structured overview.

Create a well-organized MOC that:
1. Provides a high-level overview of the topic
2. Organizes related notes by themes/categories
3. Includes key insights and connections
4. Links to all source notes using [[wikilinks]]
5. Uses clear headings and structure

Topic: {topic}

Source notes content:
{content}

Generate the MOC now:"""


def synthesize(topic: str, top_k: int = 50, collection: str = "obsidian") -> Optional[str]:
    """
    Generate a Map of Content (MOC) note by synthesizing related content.
    
    Args:
        topic: Topic/query for the MOC
        top_k: Number of related notes to retrieve
        collection: LanceDB collection to search ("obsidian" or "prompts")
    
    Returns:
        Generated MOC content as Markdown, or None on error
    """
    try:
        # Import dependencies
        import lancedb
        from fastembed import TextEmbedding
        from scripts.config import (
            LANCE_DB_PATH,
            OBSIDIAN_CURATED_COLLECTION,
            OBSIDIAN_RAW_COLLECTION,
            PROMPTS_CURATED_COLLECTION,
            OBSIDIAN_EMBED_MODEL
        )
        
        # Connect to LanceDB
        if not LANCE_DB_PATH.exists():
            logger.error("LanceDB not initialized")
            return None
        
        db = lancedb.connect(str(LANCE_DB_PATH))
        
        # Select collection
        if collection == "obsidian":
            # Try curated first, fallback to raw
            try:
                table = db.open_table(OBSIDIAN_CURATED_COLLECTION)
            except Exception:
                try:
                    table = db.open_table(OBSIDIAN_RAW_COLLECTION)
                except Exception:
                    logger.error("No Obsidian collections found")
                    return None
        elif collection == "prompts":
            try:
                table = db.open_table(PROMPTS_CURATED_COLLECTION)
            except Exception:
                logger.error("Prompts collection not found")
                return None
        else:
            logger.error(f"Unknown collection: {collection}")
            return None
        
        # Embed the topic
        embedder = TextEmbedding(model_name=OBSIDIAN_EMBED_MODEL)
        embedding = list(embedder.embed([topic]))[0]
        
        # Vector search for related notes
        results = table.search(embedding).limit(top_k).to_pandas()
        
        if results.empty:
            logger.warning(f"No related notes found for topic: {topic}")
            return None
        
        # Filter out soft-deleted chunks (deleted: true)
        if 'deleted' in results.columns:
            results = results[results['deleted'] != 'true']
        
        if results.empty:
            logger.warning(f"No non-deleted notes found for topic: {topic}")
            return None
        
        # Extract and combine content from results
        notes_content = []
        for _, row in results.iterrows():
            text = row.get('text', '')
            metadata = row.get('metadata', {})
            if isinstance(metadata, dict):
                title = metadata.get('title', 'Untitled')
                source = metadata.get('source', '')
            else:
                title = 'Untitled'
                source = ''
            
            if text:
                notes_content.append(f"## {title}\n\n{text}\n\nSource: {source}\n\n---\n\n")
        
        combined_content = "\n".join(notes_content)
        
        # Generate MOC via LLM
        prompt = MOC_PROMPT_TEMPLATE.format(topic=topic, content=combined_content[:10000])  # Limit content
        
        api_base = OLLAMA_API_BASE.replace('/api', '') if '/api' in OLLAMA_API_BASE else OLLAMA_API_BASE
        response = requests.post(
            f"{api_base}/api/generate",
            json={
                "model": SYNTHESIZER_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 2000,  # Longer response for MOC
                    "temperature": 0.7
                }
            },
            timeout=120.0  # Longer timeout for synthesis
        )
        
        if response.status_code == 200:
            result = response.json()
            moc_content = result.get("response", "").strip()
            return moc_content
        else:
            logger.error(f"Ollama API error: {response.status_code}")
            return None
    
    except ImportError as e:
        logger.error(f"Missing dependencies: {e}")
        return None
    except Exception as e:
        logger.error(f"Error synthesizing MOC: {e}", exc_info=True)
        return None


def save_as_moc(filename: str, content: str, moc_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Save generated MOC as a Markdown file.
    
    Args:
        filename: Filename for the MOC (will be prefixed with "MOC - ")
        content: MOC content
        moc_dir: Directory to save MOC (defaults to knowledge/notes/MOCs/)
    
    Returns:
        Path to saved file, or None on error
    """
    try:
        if moc_dir is None:
            from scripts.config import config
            if config and hasattr(config, 'ROOT'):
                moc_dir = config.ROOT / "knowledge" / "notes" / "MOCs"
            else:
                moc_dir = Path("./knowledge/notes/MOCs")
        
        moc_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure filename has "MOC - " prefix
        if not filename.startswith("MOC - "):
            filename = f"MOC - {filename}"
        
        # Ensure .md extension
        if not filename.endswith(".md"):
            filename += ".md"
        
        filepath = moc_dir / filename
        filepath.write_text(content, encoding="utf-8")
        
        logger.info(f"MOC saved: {filepath}")
        return filepath
    
    except Exception as e:
        logger.error(f"Error saving MOC: {e}")
        return None

