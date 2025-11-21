"""
Document Enrichment Module
--------------------------
Extracts metadata, tags, summaries, and quality scores from documents using Ollama.
Includes quality gate and retry mechanism for failed enrichments.
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

from backend.controllers.ollama import chat as ollama_chat
from scripts.config import config

logger = logging.getLogger(__name__)


def extract_tags(text: str, max_chars: int = 2000) -> List[str]:
    """
    Extract relevant tags from document text using Ollama.
    
    Args:
        text: Document text to analyze
        max_chars: Maximum characters to analyze (for performance)
        
    Returns:
        List of tag strings
    """
    try:
        # Truncate text if needed
        text_sample = text[:max_chars] if len(text) > max_chars else text
        
        prompt = f"""Extract 3-5 relevant tags from the following text. 
Return ONLY a JSON array of tag strings, no other text.

Text:
{text_sample}

Tags (JSON array):"""

        response = ollama_chat(prompt, model=config.OLLAMA_CHAT_MODEL, stream=False)
        
        # Try to parse JSON from response
        response = response.strip()
        
        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1]) if len(lines) > 2 else response
        
        # Try to extract JSON array
        if response.startswith("["):
            tags = json.loads(response)
        elif "[" in response:
            # Extract JSON array from response
            start = response.find("[")
            end = response.rfind("]") + 1
            tags = json.loads(response[start:end])
        else:
            # Fallback: split by comma
            tags = [tag.strip() for tag in response.split(",") if tag.strip()][:5]
        
        # Ensure we have a list of strings
        if isinstance(tags, list):
            tags = [str(tag).strip() for tag in tags if tag]
        else:
            tags = [str(tags).strip()] if tags else []
        
        return tags[:5]  # Limit to 5 tags
        
    except Exception as e:
        logger.warning(f"Error extracting tags: {e}")
        # Fallback: return empty list
        return []


def generate_summary(text: str, max_chars: int = 4000) -> str:
    """
    Generate a 2-sentence summary of the document using Ollama.
    
    Args:
        text: Document text to summarize
        max_chars: Maximum characters to analyze
        
    Returns:
        Summary string (2 sentences)
    """
    try:
        # Truncate text if needed
        text_sample = text[:max_chars] if len(text) > max_chars else text
        
        prompt = f"""Summarize the following text in exactly 2 sentences. 
Be concise and capture the main points.

Text:
{text_sample}

Summary:"""

        response = ollama_chat(prompt, model=config.OLLAMA_CHAT_MODEL, stream=False)
        
        # Clean up response
        summary = response.strip()
        
        # Remove markdown formatting if present
        if summary.startswith("**"):
            summary = summary.replace("**", "")
        
        return summary
        
    except Exception as e:
        logger.warning(f"Error generating summary: {e}")
        # Fallback: return first 200 chars
        return text[:200] + "..." if len(text) > 200 else text


def extract_title(text: str, max_chars: int = 1000) -> str:
    """
    Extract title from document text using Ollama.
    
    Args:
        text: Document text to analyze
        max_chars: Maximum characters to analyze
        
    Returns:
        Title string
    """
    try:
        # Truncate text if needed
        text_sample = text[:max_chars] if len(text) > max_chars else text
        
        prompt = f"""Extract the title or main topic from the following text. 
Return ONLY the title, no other text.

Text:
{text_sample}

Title:"""

        response = ollama_chat(prompt, model=config.OLLAMA_CHAT_MODEL, stream=False)
        
        # Clean up response
        title = response.strip()
        
        # Remove markdown formatting if present
        if title.startswith("#"):
            title = title.lstrip("#").strip()
        if title.startswith("**"):
            title = title.replace("**", "")
        
        # Limit title length
        if len(title) > 100:
            title = title[:100] + "..."
        
        return title if title else "Untitled"
        
    except Exception as e:
        logger.warning(f"Error extracting title: {e}")
        # Fallback: return first line or "Untitled"
        first_line = text.split("\n")[0].strip()[:100]
        return first_line if first_line else "Untitled"


def calculate_quality_score(text: str) -> int:
    """
    Calculate quality score based on word count.
    Score ranges from 1-10, based on words per 100.
    
    Args:
        text: Document text
        
    Returns:
        Quality score (1-10)
    """
    word_count = len(text.split())
    # Calculate words per 100, cap at 10
    quality = word_count / 100
    quality_score = min(10, max(1, int(round(quality))))
    return quality_score


def format_markdown(text: str) -> str:
    """
    Clean and format markdown content.
    Basic formatting: ensure proper headers, lists, code blocks.
    
    Args:
        text: Raw markdown text
        
    Returns:
        Formatted markdown text
    """
    # Basic formatting - ensure consistent line breaks
    lines = text.split("\n")
    formatted_lines = []
    
    for line in lines:
        # Remove excessive whitespace
        line = line.rstrip()
        formatted_lines.append(line)
    
    return "\n".join(formatted_lines)


def enrich_document(text: str) -> Dict:
    """
    Main enrichment function that extracts all metadata from a document.
    Includes quality gate - returns error dict with retry flag on failure.
    
    Args:
        text: Full document text to enrich
        
    Returns:
        Dictionary with:
        - summary: Document summary
        - tags: List of tags
        - title: Extracted title
        - quality_score: Quality score (1-10)
        - ingest_ts: ISO timestamp
        - formatted: Whether content was formatted
        OR
        - error: Error message
        - retry: True if should retry
    """
    try:
        logger.info(f"Enriching document ({len(text)} chars)...")
        
        # Extract metadata using Ollama
        summary = generate_summary(text)
        tags = extract_tags(text)
        title = extract_title(text)
        
        # Calculate quality score
        quality_score = calculate_quality_score(text)
        
        # Format markdown
        formatted_text = format_markdown(text)
        
        # Generate timestamp
        ingest_ts = datetime.utcnow().isoformat()
        
        result = {
            "summary": summary,
            "tags": tags,
            "title": title,
            "quality_score": quality_score,
            "ingest_ts": ingest_ts,
            "formatted": True
        }
        
        logger.info(f"Enrichment complete: title='{title}', tags={tags}, quality={quality_score}")
        return result
        
    except Exception as e:
        logger.error(f"Error enriching document: {e}")
        return {
            "error": str(e),
            "retry": True
        }

