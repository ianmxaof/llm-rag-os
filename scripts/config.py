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
    TAGS_DIR: Path = KNOWLEDGE_DIR / "tags"
    
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
    LOCAL_MODEL_TIMEOUT: float = float(os.getenv("LOCAL_MODEL_TIMEOUT", "600"))
    
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
        'LOCAL_MODEL_TIMEOUT': float(os.getenv("LOCAL_MODEL_TIMEOUT", "600")),
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

# Notes vault configuration (added by Obsidian+RAG integration)
NOTES_VAULT = "knowledge/notes/"
AUTO_FOLDER = "knowledge/notes/Auto/"

# Obsidian watch paths (selective watching)
OBSIDIAN_WATCH_DIRS = [
    "knowledge/notes/Manual/",
    "knowledge/notes/Auto/"
]
OBSIDIAN_EXCLUDE_DIRS = [
    "Templates/",
    "_archive/",
    "Attachments/",
    ".obsidian/",
    "_dashboard/",
    "_templates/",
    "_attachments/"
]
OBSIDIAN_RECURSIVE = False  # Only watch specified folders, not subfolders

# Chunking settings (Obsidian-specific)
OBSIDIAN_CHUNK_OVERLAP = 150  # Characters (optimized for heading-based chunking)
OBSIDIAN_MIN_CHUNK_SIZE = 200  # Characters
OBSIDIAN_CHUNK_BY_HEADINGS = True

# Embedding model (fastembed default)
OBSIDIAN_EMBED_MODEL = "nomic-embed-text-v1.5"  # 384-dim via fastembed
OBSIDIAN_EMBED_MULTILINGUAL = True  # Use :multilingual flag for non-English sources
OBSIDIAN_EMBED_PROVIDER = "fastembed"  # Required, not optional
# Alternative: "BAAI/bge-micro-v2"

# Vector DB (LanceDB required)
USE_LANCEDB = True  # Required for elite setup
LANCE_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "lancedb_obsidian"
ENABLE_HYBRID_SEARCH = True  # BM25 + vector hybrid
TANTIVY_INDEX_PATH = Path(__file__).resolve().parent.parent / "data" / "tantivy_obsidian"

# Collections (separate by trust)
OBSIDIAN_CURATED_COLLECTION = "obsidian_curated"  # Manual/ + high-confidence
OBSIDIAN_RAW_COLLECTION = "obsidian_raw"  # Low-confidence, Reddit dumps

# Deduplication
ENABLE_HASH_DEDUP = True  # SHA256 hash check before re-embedding
INGESTION_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "obsidian_ingestion_ledger.db"  # SQLite ledger for 100% correct dedupe

# Compression
USE_LLMLINGUA = os.getenv("USE_LLMLINGUA", "true").lower() == "true"  # LLMLingua-2 compression
USE_TOON_SERIALIZATION = os.getenv("USE_TOON_SERIALIZATION", "true").lower() == "true"  # TOON format for contexts (35-45% token savings)

# Reranking
USE_RERANKER = os.getenv("USE_RERANKER", "true").lower() == "true"
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")  # CPU-only, <100ms

# Chunk Summarization (pre-compute on ingest)
PRE_COMPUTE_CHUNK_SUMMARIES = os.getenv("PRE_COMPUTE_CHUNK_SUMMARIES", "true").lower() == "true"  # Generate summaries via Ollama on ingest, cache for Streamlit
CHUNK_SUMMARY_MODEL = os.getenv("CHUNK_SUMMARY_MODEL", "mistral:7b-instruct-q5_K_M")  # Or your preferred Ollama model
CHUNK_SUMMARY_MAX_TOKENS = int(os.getenv("CHUNK_SUMMARY_MAX_TOKENS", "50"))  # Brief summary per chunk

# Performance
EMBEDDING_WORKERS = int(os.getenv("EMBEDDING_WORKERS", "2"))  # Multi-process embedding queue (2-4 workers)
# Turns 15 docs/s → 60+ docs/s on 256GB laptop

# FastAPI Reindex Endpoint (optional)
ENABLE_REINDEX_API = os.getenv("ENABLE_REINDEX_API", "true").lower() == "true"  # Expose /reindex?file=xxx endpoint
REINDEX_API_PORT = int(os.getenv("REINDEX_API_PORT", "8001"))  # Port for FastAPI server

# Prompt RAG Layer (elite prompt repository)
PROMPTS_CURATED_COLLECTION = os.getenv("PROMPTS_CURATED_COLLECTION", "prompts_curated")
PROMPT_RAG_ENABLED = os.getenv("PROMPT_RAG_ENABLED", "true").lower() == "true"
PROMPT_RAG_TOP_K = int(os.getenv("PROMPT_RAG_TOP_K", "3"))
PROMPT_MIN_SCORE = float(os.getenv("PROMPT_MIN_SCORE", "7.5"))
PROMPT_MAX_CHARS = int(os.getenv("PROMPT_MAX_CHARS", "1500"))  # Hard cap on injected prompt tokens (~400-600 tokens)
PROMPT_CACHE_TTL = int(os.getenv("PROMPT_CACHE_TTL", "60"))  # Cache TTL in seconds
PROMPT_SCORE_DECAY_DAYS = int(os.getenv("PROMPT_SCORE_DECAY_DAYS", "90"))  # Score decay after N days unused

