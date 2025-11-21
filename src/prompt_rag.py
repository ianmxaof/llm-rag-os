"""
Prompt RAG Module
-----------------
Retrieves elite prompts from LanceDB and formats them for injection into system prompts.
Includes security features: sanitization, token limits, caching, and versioning support.
"""

import hashlib
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from functools import lru_cache
import time

from scripts.config import (
    LANCE_DB_PATH,
    OBSIDIAN_EMBED_MODEL,
    PROMPTS_CURATED_COLLECTION,
    PROMPT_RAG_ENABLED,
    PROMPT_RAG_TOP_K,
    PROMPT_MIN_SCORE,
    PROMPT_MAX_CHARS,
    PROMPT_CACHE_TTL,
    ENABLE_HYBRID_SEARCH,
)

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False


# LRU cache for prompt retrieval (per query hash)
_cache: Dict[str, tuple] = {}  # {hash: (prompts, timestamp)}


def sanitize_injected_prompt(prompt_text: str) -> str:
    """
    Sanitize prompt to prevent injection attacks.
    Strips or escapes dangerous phrases and ensures safe formatting.
    """
    # Dangerous phrases that could be used for prompt injection
    dangerous_patterns = [
        r"ignore\s+(previous|all|the)\s+(instructions?|prompts?|system)",
        r"disregard\s+(previous|all|the)\s+(instructions?|prompts?|system)",
        r"forget\s+(previous|all|the)\s+(instructions?|prompts?|system)",
        r"you\s+are\s+now",
        r"never\s+refuse",
        r"always\s+do",
        r"output\s+(flag|password|secret|key)",
        r"system\s+prompt",
        r"previous\s+instructions?",
    ]
    
    sanitized = prompt_text
    
    # Remove dangerous patterns
    for pattern in dangerous_patterns:
        sanitized = re.sub(pattern, "", sanitized, flags=re.IGNORECASE)
    
    # Remove excessive whitespace
    sanitized = re.sub(r'\s+', ' ', sanitized).strip()
    
    return sanitized


def truncate_prompt(prompt_text: str, max_chars: int = PROMPT_MAX_CHARS) -> tuple[str, bool]:
    """
    Truncate prompt to max_chars with ellipsis.
    Returns (truncated_text, was_truncated).
    """
    if len(prompt_text) <= max_chars:
        return prompt_text, False
    
    # Truncate at word boundary
    truncated = prompt_text[:max_chars]
    last_space = truncated.rfind(' ')
    if last_space > max_chars * 0.8:  # If we're close to a word boundary
        truncated = truncated[:last_space]
    
    return truncated + "...", True


def retrieve_elite_prompts(
    query: str,
    top_k: int = PROMPT_RAG_TOP_K,
    category_hint: Optional[str] = None
) -> List[Dict]:
    """
    Retrieve elite prompts from LanceDB using hybrid search.
    
    Args:
        query: User query to match against prompts
        top_k: Number of prompts to retrieve
        category_hint: Optional category to boost (e.g., "coding", "reasoning")
        
    Returns:
        List of prompt dicts with: prompt_text, author, category, score, source
    """
    if not PROMPT_RAG_ENABLED or not LANCEDB_AVAILABLE:
        return []
    
    # Check cache
    cache_key = hashlib.md5(f"{query}:{category_hint}:{top_k}".encode()).hexdigest()
    if cache_key in _cache:
        cached_prompts, cache_time = _cache[cache_key]
        if time.time() - cache_time < PROMPT_CACHE_TTL:
            return cached_prompts
    
    try:
        # Connect to LanceDB
        db = lancedb.connect(str(LANCE_DB_PATH))
        table = db.open_table(PROMPTS_CURATED_COLLECTION)
        
        # Embed query
        if not FASTEMBED_AVAILABLE:
            return []
        
        embedder = TextEmbedding(model_name=OBSIDIAN_EMBED_MODEL)
        query_vector = embedder.embed_documents([query])[0]
        
        # Build search query with hybrid search if available
        # Note: LanceDB search API may vary - using basic vector search
        search = table.search(query_vector).limit(top_k * 3)  # Get more for filtering
        
        # Execute search
        try:
            results = search.to_list()
        except Exception as e:
            print(f"[WARN] Search failed: {e}")
            return []
        
        # Filter by score threshold
        results = [r for r in results if r.get("score", 0) >= PROMPT_MIN_SCORE]
        
        # Category boost (if hint provided) - prioritize matching category
        if category_hint:
            category_results = [r for r in results if r.get("category", "") == category_hint]
            other_results = [r for r in results if r.get("category", "") != category_hint]
            results = category_results + other_results
        
        # Process results
        prompts = []
        for result in results[:top_k]:
            prompt_text = result.get("prompt_text", "")
            
            # Sanitize
            sanitized = sanitize_injected_prompt(prompt_text)
            
            # Truncate if needed
            truncated, was_truncated = truncate_prompt(sanitized, PROMPT_MAX_CHARS)
            
            if was_truncated:
                print(f"[WARN] Prompt {result.get('id')} truncated from {len(prompt_text)} to {len(truncated)} chars")
            
            prompts.append({
                "prompt_text": truncated,
                "author": result.get("author", "Unknown"),
                "category": result.get("category", "general"),
                "score": result.get("score", 0.0),
                "source": result.get("source", ""),
                "id": result.get("id", ""),
            })
        
        # Update cache
        _cache[cache_key] = (prompts, time.time())
        
        # Clean old cache entries
        current_time = time.time()
        _cache.clear()  # Simple: clear cache when TTL expires (could be optimized)
        _cache[cache_key] = (prompts, current_time)
        
        return prompts
        
    except Exception as e:
        print(f"[WARN] Prompt retrieval failed: {e}")
        return []


def format_prompts_for_injection(prompts: List[Dict]) -> str:
    """
    Format prompts for injection into system prompt.
    Uses XML tags with role="example" for safety.
    """
    if not prompts:
        return ""
    
    formatted_parts = []
    
    for prompt in prompts:
        author = prompt.get("author", "Unknown")
        category = prompt.get("category", "general")
        score = prompt.get("score", 0.0)
        prompt_text = prompt.get("prompt_text", "")
        
        formatted = f"""<prompt author='{author}' category='{category}' score='{score:.1f}' role='example'>
{prompt_text}
</prompt>"""
        
        formatted_parts.append(formatted)
    
    return "\n\n".join(formatted_parts)


def increment_prompt_uses(prompt_id: str):
    """
    Increment usage counter for a prompt (for Darwinian selection).
    This should be called after successful prompt retrieval.
    
    Note: LanceDB doesn't have a direct update API, so we track usage
    in a separate SQLite database or update via delete+reinsert.
    For now, this is a placeholder - implement based on your tracking needs.
    """
    if not LANCEDB_AVAILABLE:
        return
    
    # TODO: Implement usage tracking
    # Options:
    # 1. Use SQLite ledger (like obsidian_ledger.py) to track uses
    # 2. Delete and re-insert with updated uses counter
    # 3. Use external tracking system
    
    # For now, just log the usage
    try:
        print(f"[DEBUG] Prompt {prompt_id} used")
    except Exception:
        pass


def get_category_hint(query: str) -> Optional[str]:
    """
    Extract category hint from query for better prompt matching.
    """
    query_lower = query.lower()
    
    category_keywords = {
        "coding": ["code", "program", "function", "class", "algorithm", "debug", "implement"],
        "reasoning": ["think", "reason", "analyze", "logic", "deduce", "infer"],
        "agentic": ["agent", "autonomous", "tool", "action", "execute", "plan"],
        "redteam": ["exploit", "vulnerability", "security", "hack", "bypass"],
    }
    
    for category, keywords in category_keywords.items():
        if any(keyword in query_lower for keyword in keywords):
            return category
    
    return None

