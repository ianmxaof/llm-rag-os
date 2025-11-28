"""
Semantic Categorizer
--------------------
Lightweight semantic categorization using embeddings and cosine similarity.
Categorizes files into known categories or generates keyword-based folder names.
"""

import logging
import re
from pathlib import Path
from typing import List, Optional
import numpy as np

from scripts.config import config
from backend.controllers.ollama import embed_texts

logger = logging.getLogger(__name__)

# Known categories with representative text samples
KNOWN_CATEGORIES = {
    "ChatGPT Logs": "chatgpt conversation log export chat history",
    "Prompts": "prompt engineering system prompt user prompt template",
    "Cursor Logs": "cursor ide code editor chat log conversation",
    "YouTube Transcripts": "youtube transcript video transcription subtitles",
    "Research Papers": "abstract introduction methodology conclusion research paper",
    "Personal Notes": "personal note journal diary reflection thoughts",
    "Code Snippets": "code snippet function class method programming",
    "Books": "book chapter author reading literature novel"
}

# Cache for category embeddings (computed once)
_category_embeddings_cache: Optional[dict] = None


def _get_category_embeddings() -> dict:
    """Compute and cache embeddings for known categories."""
    global _category_embeddings_cache
    
    if _category_embeddings_cache is not None:
        return _category_embeddings_cache
    
    logger.info("Computing category embeddings...")
    categories = list(KNOWN_CATEGORIES.keys())
    category_texts = list(KNOWN_CATEGORIES.values())
    
    try:
        # Generate embeddings for all category texts
        embeddings = embed_texts(category_texts, model=config.OLLAMA_EMBED_MODEL)
        _category_embeddings_cache = dict(zip(categories, embeddings))
        logger.info(f"Cached embeddings for {len(categories)} categories")
        return _category_embeddings_cache
    except Exception as e:
        logger.error(f"Failed to compute category embeddings: {e}")
        # Return empty dict, will fall back to keyword-based categorization
        return {}


def _cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    try:
        v1 = np.array(vec1)
        v2 = np.array(vec2)
        dot_product = np.dot(v1, v2)
        norm1 = np.linalg.norm(v1)
        norm2 = np.linalg.norm(v2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(dot_product / (norm1 * norm2))
    except Exception as e:
        logger.warning(f"Error computing cosine similarity: {e}")
        return 0.0


def _extract_keywords(text: str, max_keywords: int = 3) -> str:
    """Extract top keywords from text for folder naming."""
    # Remove markdown syntax, URLs, and special characters
    text_clean = re.sub(r'[#*\[\](){}]', ' ', text)
    text_clean = re.sub(r'http\S+', '', text_clean)
    text_clean = re.sub(r'[^\w\s]', ' ', text_clean)
    
    # Split into words, filter short words and common stop words
    words = text_clean.lower().split()
    stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 
                  'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'be',
                  'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
                  'could', 'should', 'may', 'might', 'must', 'can', 'this', 'that',
                  'these', 'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they'}
    
    # Filter and count word frequencies
    word_freq = {}
    for word in words:
        if len(word) > 3 and word not in stop_words:
            word_freq[word] = word_freq.get(word, 0) + 1
    
    # Get top keywords
    sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
    keywords = [word for word, _ in sorted_words[:max_keywords]]
    
    # Join with underscores, sanitize for folder name
    folder_name = '_'.join(keywords) if keywords else 'uncategorized'
    # Remove any remaining invalid characters
    folder_name = re.sub(r'[^\w\-_]', '', folder_name)
    # Limit length
    folder_name = folder_name[:50] if len(folder_name) > 50 else folder_name
    
    return folder_name if folder_name else 'uncategorized'


def categorize_file(file_path: Path, similarity_threshold: float = 0.65) -> str:
    """
    Categorize a file semantically.
    
    Args:
        file_path: Path to the file to categorize
        similarity_threshold: Minimum cosine similarity to match a category (default: 0.65)
        
    Returns:
        Category name (from known categories) or keyword-based folder name
    """
    try:
        # Read file content (first 2000 chars)
        text = file_path.read_text(encoding="utf-8", errors="ignore")[:2000]
        if not text.strip():
            logger.warning(f"Empty file: {file_path}")
            return "uncategorized"
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        return "uncategorized"
    
    # Get category embeddings (cached)
    category_embeddings = _get_category_embeddings()
    
    if not category_embeddings:
        # Fallback to keyword-based categorization
        logger.info("Category embeddings not available, using keyword-based categorization")
        return _extract_keywords(text)
    
    try:
        # Generate embedding for file content
        file_embedding = embed_texts([text], model=config.OLLAMA_EMBED_MODEL)
        if not file_embedding or len(file_embedding) == 0:
            logger.warning(f"No embedding generated for {file_path}")
            return _extract_keywords(text)
        
        file_embedding_vec = file_embedding[0]
        
        # Compute similarity with each category
        best_category = None
        best_similarity = 0.0
        
        for category, category_embedding in category_embeddings.items():
            similarity = _cosine_similarity(file_embedding_vec, category_embedding)
            if similarity > best_similarity:
                best_similarity = similarity
                best_category = category
        
        # If similarity exceeds threshold, return category
        if best_similarity >= similarity_threshold:
            logger.info(f"Categorized {file_path.name} as '{best_category}' (similarity: {best_similarity:.3f})")
            return best_category
        else:
            # Fallback to keyword-based folder name
            folder_name = _extract_keywords(text)
            logger.info(f"No category match for {file_path.name} (best: {best_category} @ {best_similarity:.3f}), using keywords: {folder_name}")
            return folder_name
            
    except Exception as e:
        logger.error(f"Error categorizing file {file_path}: {e}")
        # Fallback to keyword-based categorization
        return _extract_keywords(text)

