"""
Embed Worker
-----------
Watches knowledge/processed/ for new markdown files, embeds them in batches,
and archives them. Runs as a background worker process.
"""

import hashlib
import logging
import os
import shutil
import time
from pathlib import Path

import chromadb

from scripts.config import config
from scripts.preprocess import preprocess_text
from scripts.enrichment import enrich_document
from backend.controllers.ollama import embed_texts, force_unload_model

# Try watchdog for file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

# Warm model tracking for sustained mode optimization
_model_last_used: dict[str, float] = {}


def should_use_sustained_mode(file_path: Path) -> tuple[bool, int, str]:
    """
    Determine if a file should use sustained model loading based on heuristics.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        Tuple of (use_sustained: bool, estimated_chunks: int, reason: str)
    """
    try:
        size_kb = file_path.stat().st_size / 1024
        name = file_path.name.lower()
        
        # Heuristic 1: Raw size >800 KB
        if size_kb > 800:
            est_chunks = int(size_kb * 1.5)  # Rough estimate: ~1.5 chunks per KB
            return True, est_chunks, f"{size_kb:.1f} KB file size"
        
        # Heuristic 2: Dense patterns >400 KB
        dense_patterns = ["cursor_", "chatlog_", "export_", "history", "log", "session"]
        if size_kb > 400 and any(p in name for p in dense_patterns):
            est_chunks = int(size_kb * 1.5)
            return True, est_chunks, f"{size_kb:.1f} KB + dense pattern ({', '.join([p for p in dense_patterns if p in name])})"
        
        # Heuristic 3: Accurate chunk count estimation
        try:
            text = file_path.read_text(encoding="utf-8")
            est_chunks = len(text) // 1400 + 1  # ~1500 chars per chunk
            if est_chunks > 600:
                return True, est_chunks, f"{est_chunks} estimated chunks"
        except Exception:
            pass
        
        return False, 0, ""
    except Exception as e:
        logger.warning(f"Error in should_use_sustained_mode: {e}")
        return False, 0, ""


def file_hash(path: Path) -> str:
    """Compute MD5 hash of file."""
    h = hashlib.md5()
    try:
        with open(path, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except Exception as e:
        logger.error(f"Error computing hash for {path}: {e}")
        return path.stem


def embed_and_upsert(md_path: Path, batch_size: int = None):
    """
    Preprocess, embed, and upsert a markdown file to ChromaDB.
    Implements dual-model lifecycle control for sustained mode.
    
    Args:
        md_path: Path to markdown file
        batch_size: Batch size for embedding (defaults to config.EMBED_BATCH_SIZE)
        
    Returns:
        Dict with success status and metadata (sustained_mode, estimated_chunks, reason)
    """
    batch_size = batch_size or config.EMBED_BATCH_SIZE
    
    # Detect if sustained mode should be used
    use_sustained, est_chunks, reason = should_use_sustained_mode(md_path)
    sustained_mode_used = False
    
    try:
        # Read markdown file
        text = md_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {md_path}: {e}")
        return {"success": False, "sustained_mode": False, "estimated_chunks": 0, "reason": ""}
    
    # Enrichment phase: use chat model with keep_alive if sustained mode
    chat_keep_alive = "10m" if use_sustained else None
    if use_sustained:
        logger.info(f"🚀 Sustained mode activated for {md_path.name}: {reason}")
        logger.info(f"   Estimated chunks: {est_chunks}")
        sustained_mode_used = True
    
    # Enrich document with metadata (tags, summary, title, quality score)
    logger.info(f"Enriching document: {md_path.name}")
    enrichment_result = enrich_document(text, keep_alive=chat_keep_alive)
    
    # Quality gate: check if enrichment failed
    if "retry" in enrichment_result and enrichment_result.get("retry"):
        logger.error(f"Enrichment failed for {md_path.name}: {enrichment_result.get('error', 'Unknown error')}")
        # Move to error directory
        try:
            config.ERROR_DIR.mkdir(parents=True, exist_ok=True)
            error_path = config.ERROR_DIR / md_path.name
            shutil.move(str(md_path), str(error_path))
            logger.info(f"Moved failed file to error directory: {error_path}")
        except Exception as e:
            logger.error(f"Failed to move file to error directory: {e}")
        # Cleanup models if sustained mode was used
        if sustained_mode_used:
            try:
                force_unload_model(config.OLLAMA_CHAT_MODEL, "1s")
                time.sleep(0.5)
                force_unload_model(config.OLLAMA_EMBED_MODEL, "1s")
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
        return {"success": False, "sustained_mode": sustained_mode_used, "estimated_chunks": est_chunks, "reason": reason}
    
    # Extract enrichment metadata
    doc_summary = enrichment_result.get("summary", "")
    doc_tags = enrichment_result.get("tags", [])
    doc_title = enrichment_result.get("title", md_path.stem)
    quality_score = enrichment_result.get("quality_score", 5)
    ingest_ts = enrichment_result.get("ingest_ts", "")
    
    # Preprocess and chunk
    chunks = preprocess_text(text, clean=True)
    if not chunks:
        logger.warning(f"No chunks created for {md_path}")
        # Cleanup models if sustained mode was used
        if sustained_mode_used:
            try:
                force_unload_model(config.OLLAMA_CHAT_MODEL, "1s")
                time.sleep(0.5)
                force_unload_model(config.OLLAMA_EMBED_MODEL, "1s")
            except Exception as e:
                logger.warning(f"Error during cleanup: {e}")
        return {"success": False, "sustained_mode": sustained_mode_used, "estimated_chunks": est_chunks, "reason": reason}
    
    # Compute file hash for deduplication
    file_hash_val = file_hash(md_path)
    
    # Initialize ChromaDB
    client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
    collection = client.get_or_create_collection(
        name=config.COLLECTION_NAME
    )
    
    # Embed in batches using Ollama
    try:
        all_ids = []
        all_documents = []
        all_metadatas = []
        all_embeddings = []
        
        # Embedding phase: use embedding model with keep_alive if sustained mode
        embed_keep_alive = "8m" if use_sustained else None
        
        logger.info(f"Starting embedding process for {len(chunks)} chunks using {config.OLLAMA_EMBED_MODEL}")
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Use Ollama to embed the batch with keep_alive if sustained mode
            logger.info(f"Embedding batch {i//batch_size + 1} ({len(batch)} chunks)...")
            batch_embeddings = embed_texts(batch, model=config.OLLAMA_EMBED_MODEL, keep_alive=embed_keep_alive)
            if use_sustained:
                logger.info(f"Batch {i//batch_size + 1} embedded successfully. Model kept alive.")
            else:
                logger.info(f"Batch {i//batch_size + 1} embedded successfully. Model unloaded.")
            
            for j, (chunk, embedding) in enumerate(zip(batch, batch_embeddings)):
                chunk_id = f"{file_hash_val}_{i+j}"
                all_ids.append(chunk_id)
                all_documents.append(chunk)
                
                # Add enriched metadata to each chunk
                chunk_metadata = {
                    "source": str(md_path),
                    "chunk": i + j,
                    "file_hash": file_hash_val,
                    "title": doc_title,
                    "summary": doc_summary,
                    "tags": ", ".join(doc_tags) if doc_tags else "",  # ChromaDB requires scalar values (comma-separated string)
                    "quality_score": quality_score,
                    "ingest_ts": ingest_ts
                }
                all_metadatas.append(chunk_metadata)
                all_embeddings.append(embedding)
        
        # Upsert to ChromaDB
        collection.upsert(
            ids=all_ids,
            documents=all_documents,
            metadatas=all_metadatas,
            embeddings=all_embeddings
        )
        
        logger.info(f"Indexed {len(chunks)} chunks from {md_path.name}")
        
        # Cleanup: force unload models if sustained mode was used
        if sustained_mode_used:
            try:
                logger.info("Cleaning up models after sustained mode ingestion...")
                force_unload_model(config.OLLAMA_CHAT_MODEL, "1s")
                time.sleep(0.5)
                force_unload_model(config.OLLAMA_EMBED_MODEL, "1s")
                logger.info("Models unloaded successfully")
            except Exception as e:
                logger.warning(f"Error during model cleanup: {e} — OS will reclaim on exit")
        
        # Archive the processed file
        try:
            config.ARCHIVE.mkdir(parents=True, exist_ok=True)
            archive_path = config.ARCHIVE / md_path.name
            
            # Handle duplicate filenames
            counter = 1
            while archive_path.exists():
                name_parts = md_path.name.rsplit(".", 1)
                if len(name_parts) == 2:
                    new_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    new_filename = f"{md_path.name}_{counter}"
                archive_path = config.ARCHIVE / new_filename
                counter += 1
            
            shutil.move(str(md_path), str(archive_path))
            logger.info(f"Archived {md_path.name} to {archive_path}")
            
            # Create auto-tag folder structure with symlinks
            if doc_tags:
                try:
                    config.TAGS_DIR.mkdir(parents=True, exist_ok=True)
                    for tag in doc_tags:
                        # Normalize tag: lowercase, replace spaces with underscores
                        tag_normalized = tag.lower().replace(" ", "_").replace("/", "_")
                        tag_dir = config.TAGS_DIR / tag_normalized
                        tag_dir.mkdir(parents=True, exist_ok=True)
                        
                        # Create symlink
                        symlink_path = tag_dir / archive_path.name
                        if not symlink_path.exists():
                            try:
                                symlink_path.symlink_to(archive_path)
                                logger.info(f"Created symlink: {symlink_path} -> {archive_path}")
                            except OSError as e:
                                # Symlinks might not be supported on Windows, use copy instead
                                if hasattr(os, "symlink"):
                                    logger.warning(f"Could not create symlink: {e}")
                                    # Fallback: copy file
                                    shutil.copy2(archive_path, symlink_path)
                                    logger.info(f"Copied file to tag directory: {symlink_path}")
                                else:
                                    # Windows fallback: copy file
                                    shutil.copy2(archive_path, symlink_path)
                                    logger.info(f"Copied file to tag directory: {symlink_path}")
                        else:
                            logger.debug(f"Symlink already exists: {symlink_path}")
                except Exception as e:
                    logger.warning(f"Could not create tag folders: {e}")
            
        except Exception as e:
            logger.warning(f"Could not archive {md_path}: {e}")
        
        return {
            "success": True,
            "sustained_mode": sustained_mode_used,
            "estimated_chunks": est_chunks,
            "reason": reason
        }
        
    except Exception as e:
        logger.error(f"Error embedding {md_path}: {e}")
        # Cleanup models if sustained mode was used
        if sustained_mode_used:
            try:
                force_unload_model(config.OLLAMA_CHAT_MODEL, "1s")
                time.sleep(0.5)
                force_unload_model(config.OLLAMA_EMBED_MODEL, "1s")
            except Exception as cleanup_error:
                logger.warning(f"Error during cleanup: {cleanup_error}")
        return {"success": False, "sustained_mode": sustained_mode_used, "estimated_chunks": est_chunks, "reason": reason}


class MarkdownHandler(FileSystemEventHandler):
    """Watchdog handler for markdown files."""
    
    def __init__(self):
        self.processed = set()
    
    def on_created(self, event):
        """Handle file creation event."""
        if event.is_directory:
            return
        
        path = Path(event.src_path)
        if path.suffix.lower() != ".md":
            return
        
        # Wait a bit for file to be fully written
        time.sleep(1)
        
        if str(path) in self.processed:
            return
        
        if not path.exists():
            return
        
        logger.info(f"New markdown file detected: {path.name}")
        success = embed_and_upsert(path)
        
        if success:
            self.processed.add(str(path))


def watch_loop():
    """Main watch loop."""
    logger.info(f"Starting embed worker on {config.PROCESSED}")
    
    if not config.PROCESSED.exists():
        config.PROCESSED.mkdir(parents=True, exist_ok=True)
    
    if WATCHDOG_AVAILABLE:
        # Use watchdog for efficient file system monitoring
        event_handler = MarkdownHandler()
        observer = Observer()
        observer.schedule(event_handler, str(config.PROCESSED), recursive=False)
        observer.start()
        
        try:
            logger.info("Embed worker running (press Ctrl+C to stop)")
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Stopping embed worker...")
            observer.stop()
        observer.join()
    else:
        # Fallback to polling
        logger.warning("watchdog not available, using polling mode")
        seen = set()
        
        try:
            while True:
                for md_file in config.PROCESSED.glob("*.md"):
                    if str(md_file) not in seen:
                        logger.info(f"Processing {md_file.name}")
                        embed_and_upsert(md_file)
                        seen.add(str(md_file))
                time.sleep(config.WATCH_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Stopping embed worker...")


if __name__ == "__main__":
    watch_loop()

