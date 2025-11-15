"""
Preprocessing Module
--------------------
Centralized markdown cleaning and text chunking functions.
"""

import re
import logging
from typing import List

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    logging.warning("langchain not available. Install with: pip install langchain")

from scripts.config import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def clean_markdown(text: str) -> str:
    """
    Clean markdown text by removing headers, images, links, and excessive whitespace.
    
    Args:
        text: Raw markdown text
        
    Returns:
        Cleaned text ready for embedding
    """
    if not text or not isinstance(text, str):
        return ""
    
    # Remove images: ![alt](url)
    text = re.sub(r'!\[.*?\]\(.*?\)', '', text)
    
    # Remove headers: # Header text
    text = re.sub(r'^#+\s+.*$', '', text, flags=re.MULTILINE)
    
    # Convert links to plain text: [text](url) -> text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove URLs
    text = re.sub(
        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+',
        '',
        text
    )
    
    # Normalize whitespace: multiple spaces/newlines -> single space
    text = re.sub(r'\s{2,}', ' ', text)
    
    # Remove leading/trailing whitespace
    text = text.strip()
    
    return text


def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    """
    Split text into chunks using RecursiveCharacterTextSplitter.
    
    Args:
        text: Text to chunk
        chunk_size: Maximum chunk size (defaults to config.CHUNK_SIZE)
        chunk_overlap: Overlap between chunks (defaults to config.CHUNK_OVERLAP)
        
    Returns:
        List of text chunks
    """
    if not text or not text.strip():
        return []
    
    chunk_size = chunk_size or config.CHUNK_SIZE
    chunk_overlap = chunk_overlap or config.CHUNK_OVERLAP
    
    if not LANGCHAIN_AVAILABLE:
        # Fallback: simple character-based chunking
        logging.warning("Using fallback chunking (langchain not available)")
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - chunk_overlap
        return chunks
    
    try:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            separators=["\n\n", "\n", ". ", " ", ""]
        )
        chunks = splitter.split_text(text)
        return [chunk.strip() for chunk in chunks if chunk.strip()]
    except Exception as e:
        logging.error(f"Error during chunking: {e}")
        # Fallback to simple chunking
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunk = text[start:end]
            if chunk.strip():
                chunks.append(chunk.strip())
            start = end - chunk_overlap
        return chunks


def preprocess_text(text: str, clean: bool = True) -> List[str]:
    """
    Complete preprocessing pipeline: clean and chunk text.
    
    Args:
        text: Raw text to preprocess
        clean: Whether to clean markdown (default: True)
        
    Returns:
        List of cleaned and chunked text segments
    """
    if not text or not isinstance(text, str):
        return []
    
    # Clean markdown if requested
    if clean:
        text = clean_markdown(text)
    
    # Chunk the text
    chunks = chunk_text(text)
    
    return chunks


if __name__ == "__main__":
    # Test the preprocessing functions
    sample_text = """
    # Test Document
    
    This is a [test link](http://example.com) with some content.
    
    ![Image](http://example.com/image.png)
    
    Here is some more text that should be chunked properly.
    This paragraph contains multiple sentences. Each sentence should be preserved.
    """
    
    print("Original text:")
    print(sample_text)
    print("\n" + "="*50 + "\n")
    
    cleaned = clean_markdown(sample_text)
    print("Cleaned text:")
    print(cleaned)
    print("\n" + "="*50 + "\n")
    
    chunks = preprocess_text(sample_text)
    print(f"Chunks ({len(chunks)}):")
    for i, chunk in enumerate(chunks, 1):
        print(f"\nChunk {i}:")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)

