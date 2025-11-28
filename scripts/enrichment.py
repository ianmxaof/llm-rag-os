"""
Document Enrichment Module
--------------------------
Extracts metadata, tags, summaries, and quality scores from documents using Ollama.
Includes quality gate and retry mechanism for failed enrichments.
"""

import json
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional

import requests

from backend.controllers.ollama import chat as ollama_chat
from scripts.config import config

logger = logging.getLogger(__name__)


def _extract_yaml_tags(text: str) -> List[str]:
    """Extract tags from YAML frontmatter."""
    try:
        yaml_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if yaml_match:
            yaml_str = yaml_match.group(1)
            # Simple YAML parsing for tags
            for line in yaml_str.split('\n'):
                if 'tags:' in line.lower():
                    # Extract tags from YAML
                    tag_line = line.split(':', 1)[1].strip()
                    if tag_line.startswith('['):
                        # Array format
                        tags = re.findall(r'"([^"]+)"|\'([^\']+)\'|([^\s,]+)', tag_line)
                        return [t[0] or t[1] or t[2] for t in tags if t[0] or t[1] or t[2]]
                    else:
                        # Single tag or comma-separated
                        return [t.strip() for t in tag_line.split(',') if t.strip()]
    except Exception:
        pass
    return []


def _extract_hashtags(text: str) -> List[str]:
    """Extract hashtags from text."""
    hashtags = re.findall(r'#[\w-]+', text)
    return [tag[1:] if tag.startswith('#') else tag for tag in hashtags[:5]]  # Remove # and limit to 5


def _retry_ollama_call(func, max_retries: int = 3, *args, **kwargs):
    """Retry Ollama call with exponential backoff."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ReadTimeout) as e:
            if attempt == max_retries - 1:
                logger.warning(f"Ollama call failed after {max_retries} attempts: {e}")
                raise
            delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s
            logger.debug(f"Ollama timeout (attempt {attempt + 1}/{max_retries}), retrying in {delay}s...")
            time.sleep(delay)
        except Exception as e:
            # For non-timeout errors, don't retry
            logger.warning(f"Ollama call failed with non-timeout error: {e}")
            raise


def extract_tags(text: str, max_chars: int = 2000, keep_alive: Optional[str] = None) -> List[str]:
    """
    Extract relevant tags from document text using Ollama with retry logic and fallbacks.
    
    Args:
        text: Document text to analyze
        max_chars: Maximum characters to analyze (for performance)
        keep_alive: Optional keep_alive duration for Ollama model
        
    Returns:
        List of tag strings
    """
    # First try YAML frontmatter and hashtags as fallback
    yaml_tags = _extract_yaml_tags(text)
    hashtags = _extract_hashtags(text)
    
    try:
        # Truncate text if needed
        text_sample = text[:max_chars] if len(text) > max_chars else text
        
        prompt = f"""Extract 3-5 relevant tags from the following text. 
Return ONLY a JSON array of tag strings, no other text.

Text:
{text_sample}

Tags (JSON array):"""

        # Retry with exponential backoff
        response = _retry_ollama_call(
            ollama_chat,
            max_retries=3,
            prompt=prompt,
            model=config.OLLAMA_CHAT_MODEL,
            stream=False,
            keep_alive=keep_alive,
            timeout=60
        )
        
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
        logger.warning(f"Error extracting tags via LLM: {e}")
        # Fallback: use YAML tags + hashtags
        combined = list(set(yaml_tags + hashtags))
        return combined[:5] if combined else []


def generate_summary(text: str, max_chars: int = 4000, keep_alive: Optional[str] = None) -> str:
    """
    Generate a 2-sentence summary of the document using Ollama with retry logic.
    
    Args:
        text: Document text to summarize
        max_chars: Maximum characters to analyze
        keep_alive: Optional keep_alive duration for Ollama model
        
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

        # Retry with exponential backoff
        response = _retry_ollama_call(
            ollama_chat,
            max_retries=3,
            prompt=prompt,
            model=config.OLLAMA_CHAT_MODEL,
            stream=False,
            keep_alive=keep_alive,
            timeout=60
        )
        
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


def extract_title(text: str, max_chars: int = 1000, keep_alive: Optional[str] = None) -> str:
    """
    Extract title from document text using Ollama with retry logic and fallbacks.
    
    Args:
        text: Document text to analyze
        max_chars: Maximum characters to analyze
        keep_alive: Optional keep_alive duration for Ollama model
        
    Returns:
        Title string
    """
    # Try YAML frontmatter first
    try:
        yaml_match = re.search(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if yaml_match:
            yaml_str = yaml_match.group(1)
            for line in yaml_str.split('\n'):
                if 'title:' in line.lower():
                    title = line.split(':', 1)[1].strip().strip('"').strip("'")
                    if title:
                        return title[:100]
    except Exception:
        pass
    
    # Fallback to first line (will use if LLM fails)
    first_line = text.split("\n")[0].strip()[:100]
    first_line_title = first_line if first_line and not first_line.startswith('#') else None
    
    try:
        # Truncate text if needed
        text_sample = text[:max_chars] if len(text) > max_chars else text
        
        prompt = f"""Extract the title or main topic from the following text. 
Return ONLY the title, no other text.

Text:
{text_sample}

Title:"""

        # Retry with exponential backoff
        response = _retry_ollama_call(
            ollama_chat,
            max_retries=3,
            prompt=prompt,
            model=config.OLLAMA_CHAT_MODEL,
            stream=False,
            keep_alive=keep_alive,
            timeout=60
        )
        
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
        
        return title if title else (first_line_title or "Untitled")
        
    except Exception as e:
        logger.warning(f"Error extracting title via LLM: {e}")
        # Fallback: return first line or filename
        return first_line_title if first_line_title else "Untitled"


def calculate_quality_score(text: str) -> int:
    """
    Calculate quality score based on word count.
    Score ranges from 1-10, based on words per 100.
    
    Args:
        text: Document text
        
    Returns:
        Quality score (1-10), defaults to 8 if calculation fails
    """
    try:
        word_count = len(text.split())
        # Calculate words per 100, cap at 10
        quality = word_count / 100
        quality_score = min(10, max(1, int(round(quality))))
        return quality_score
    except Exception as e:
        logger.warning(f"Error calculating quality score: {e}")
        return 8  # Default fallback


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


def enrich_document(text: str, keep_alive: Optional[str] = None) -> Dict:
    """
    Main enrichment function that extracts all metadata from a document.
    Parallelizes title, tags, and summary extraction for better performance.
    Includes quality gate - returns error dict with retry flag on failure.
    
    Args:
        text: Full document text to enrich
        keep_alive: Optional keep_alive duration for Ollama model
        
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
        
        # Parallelize metadata extraction using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=3) as executor:
            # Submit all three tasks in parallel
            future_summary = executor.submit(generate_summary, text, keep_alive=keep_alive)
            future_tags = executor.submit(extract_tags, text, keep_alive=keep_alive)
            future_title = executor.submit(extract_title, text, keep_alive=keep_alive)
            
            # Wait for all tasks to complete
            summary = future_summary.result()
            tags = future_tags.result()
            title = future_title.result()
        
        # Calculate quality score (fast, synchronous)
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

