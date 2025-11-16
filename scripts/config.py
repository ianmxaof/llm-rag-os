"""
Centralized Configuration Module
--------------------------------
Consolidates all paths, model settings, and processing flags into a single,
validated configuration using Pydantic for type safety and validation.
"""

import os
from pathlib import Path
from typing import List

try:
    from pydantic import BaseModel, validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Fallback to simple class if pydantic not available
    class BaseModel:
        pass
    def validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


class Config(BaseModel):
    """Centralized configuration with validation."""
    
    # Root directory (auto-detected from this file's location)
    ROOT: Path = Path(__file__).resolve().parent.parent
    
    # Knowledge base paths
    KNOWLEDGE_DIR: Path = ROOT / "knowledge"
    INBOX: Path = KNOWLEDGE_DIR / "inbox"
    PROCESSED: Path = KNOWLEDGE_DIR / "processed"
    ARCHIVE: Path = KNOWLEDGE_DIR / "archived"
    ERROR_DIR: Path = KNOWLEDGE_DIR / "error"
    
    # Vector store path
    VECTOR_DIR: Path = ROOT / "chroma"
    
    # Config file path
    CONFIG_PATH: Path = ROOT / "config" / "sources.json"
    
    # Embedding model settings
    EMBED_MODEL: str = os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "1500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    EMBED_BATCH_SIZE: int = int(os.getenv("EMBED_BATCH_SIZE", "32"))
    
    # LM Studio settings (deprecated, use Ollama instead)
    LM_EXE: str = os.getenv(
        "LM_EXE",
        r"C:\Users\{}\AppData\Local\Programs\LM Studio\LM Studio.exe".format(os.getenv("USERNAME", "USER"))
    )
    LM_API_BASE: str = os.getenv("LM_API_BASE", "http://localhost:1234/v1")
    LM_API_HEALTH: str = os.getenv("LM_API_HEALTH", "http://localhost:1234/v1/models")
    LOCAL_MODEL_ID: str = os.getenv("LOCAL_MODEL_ID", "mistral-7b-instruct-v0.2")
    LOCAL_MODEL_URL: str = os.getenv(
        "LOCAL_MODEL_URL", "http://127.0.0.1:1234/v1/chat/completions"
    )
    LOCAL_MODEL_TIMEOUT: float = float(os.getenv("LOCAL_MODEL_TIMEOUT", "120"))
    
    # Ollama settings
    OLLAMA_API_BASE: str = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/api")
    OLLAMA_EMBED_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
    OLLAMA_CHAT_MODEL: str = os.getenv("OLLAMA_CHAT_MODEL", "mistral:7b-instruct-q5_K_M")
    
    # Processing flags
    FAST_PDF: bool = os.getenv("FAST_PDF", "true").lower() == "true"
    PARALLEL: bool = os.getenv("PARALLEL", "true").lower() == "true"
    WATCH_INTERVAL: int = int(os.getenv("WATCH_INTERVAL", "5"))  # seconds
    
    # RAG settings
    DEFAULT_K: int = int(os.getenv("RAG_TOP_K", "3"))
    COLLECTION_NAME: str = os.getenv("COLLECTION_NAME", "llm_docs")
    
    # Supported file extensions
    SUPPORTED_EXTS: List[str] = [
        ".txt", ".md", ".pdf", ".docx", ".pptx", ".html", ".htm", ".csv"
    ]
    
    # Classification categories
    CATEGORIES: List[str] = [
        "hacking", "networking", "programming", "ai", "linux", "windows", "other"
    ]
    
    @validator("INBOX", "PROCESSED", "ARCHIVE", "ERROR_DIR", "VECTOR_DIR", "KNOWLEDGE_DIR")
    def ensure_directories_exist(cls, v):
        """Ensure directories exist, create if missing."""
        v.mkdir(parents=True, exist_ok=True)
        return v
    
    @validator("CHUNK_SIZE", "CHUNK_OVERLAP")
    def validate_chunk_params(cls, v):
        """Ensure chunk parameters are positive."""
        if v < 1:
            raise ValueError("Chunk size and overlap must be positive")
        return v
    
    @validator("EMBED_BATCH_SIZE")
    def validate_batch_size(cls, v):
        """Ensure batch size is reasonable."""
        if v < 1 or v > 128:
            raise ValueError("Batch size must be between 1 and 128")
        return v
    
    @validator("WATCH_INTERVAL")
    def validate_watch_interval(cls, v):
        """Ensure watch interval is reasonable."""
        if v < 1:
            raise ValueError("Watch interval must be at least 1 second")
        return v
    
    class Config:
        """Pydantic config."""
        arbitrary_types_allowed = True


# Create global config instance
if PYDANTIC_AVAILABLE:
    try:
        config = Config()
    except Exception as e:
        print(f"[WARN] Config validation failed: {e}. Using defaults.")
        # Fallback to basic config
        config = Config()
else:
    # Fallback: create config object without validation
    print("[WARN] Pydantic not available. Install with: pip install pydantic")
    config = type('Config', (), {
        'ROOT': Path(__file__).resolve().parent.parent,
        'KNOWLEDGE_DIR': Path(__file__).resolve().parent.parent / "knowledge",
        'INBOX': Path(__file__).resolve().parent.parent / "knowledge" / "inbox",
        'PROCESSED': Path(__file__).resolve().parent.parent / "knowledge" / "processed",
        'ARCHIVE': Path(__file__).resolve().parent.parent / "knowledge" / "archived",
        'ERROR_DIR': Path(__file__).resolve().parent.parent / "knowledge" / "error",
        'VECTOR_DIR': Path(__file__).resolve().parent.parent / "chroma",
        'CONFIG_PATH': Path(__file__).resolve().parent.parent / "config" / "sources.json",
        'EMBED_MODEL': os.getenv("EMBED_MODEL_NAME", "BAAI/bge-small-en-v1.5"),
        'CHUNK_SIZE': int(os.getenv("CHUNK_SIZE", "1500")),
        'CHUNK_OVERLAP': int(os.getenv("CHUNK_OVERLAP", "200")),
        'EMBED_BATCH_SIZE': int(os.getenv("EMBED_BATCH_SIZE", "32")),
        'LM_EXE': os.getenv("LM_EXE", r"C:\Users\{}\AppData\Local\Programs\LM Studio\LM Studio.exe".format(os.getenv("USERNAME", "USER"))),
        'LM_API_BASE': os.getenv("LM_API_BASE", "http://localhost:1234/v1"),
        'LM_API_HEALTH': os.getenv("LM_API_HEALTH", "http://localhost:1234/v1/models"),
        'LOCAL_MODEL_ID': os.getenv("LOCAL_MODEL_ID", "mistral-7b-instruct-v0.2"),
        'LOCAL_MODEL_URL': os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:1234/v1/chat/completions"),
        'LOCAL_MODEL_TIMEOUT': float(os.getenv("LOCAL_MODEL_TIMEOUT", "120")),
        'OLLAMA_API_BASE': os.getenv("OLLAMA_API_BASE", "http://localhost:11434/api"),
        'OLLAMA_EMBED_MODEL': os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
        'OLLAMA_CHAT_MODEL': os.getenv("OLLAMA_CHAT_MODEL", "mistral:7b-instruct-q5_K_M"),
        'FAST_PDF': os.getenv("FAST_PDF", "true").lower() == "true",
        'PARALLEL': os.getenv("PARALLEL", "true").lower() == "true",
        'WATCH_INTERVAL': int(os.getenv("WATCH_INTERVAL", "5")),
        'DEFAULT_K': int(os.getenv("RAG_TOP_K", "3")),
        'COLLECTION_NAME': os.getenv("COLLECTION_NAME", "llm_docs"),
        'SUPPORTED_EXTS': [".txt", ".md", ".pdf", ".docx", ".pptx", ".html", ".htm", ".csv"],
        'CATEGORIES': ["hacking", "networking", "programming", "ai", "linux", "windows", "other"],
    })()
    # Ensure directories exist
    for attr in ['INBOX', 'PROCESSED', 'ARCHIVE', 'VECTOR_DIR', 'KNOWLEDGE_DIR']:
        path = getattr(config, attr)
        path.mkdir(parents=True, exist_ok=True)

