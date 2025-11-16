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
from backend.controllers.ollama import embed_texts

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
    
    Args:
        md_path: Path to markdown file
        batch_size: Batch size for embedding (defaults to config.EMBED_BATCH_SIZE)
    """
    batch_size = batch_size or config.EMBED_BATCH_SIZE
    
    try:
        # Read markdown file
        text = md_path.read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read {md_path}: {e}")
        return False
    
    # Preprocess and chunk
    chunks = preprocess_text(text, clean=True)
    if not chunks:
        logger.warning(f"No chunks created for {md_path}")
        return False
    
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
        
        logger.info(f"Starting embedding process for {len(chunks)} chunks using {config.OLLAMA_EMBED_MODEL}")
        
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            
            # Use Ollama to embed the batch (auto-loads model, embeds, then unloads)
            logger.info(f"Embedding batch {i//batch_size + 1} ({len(batch)} chunks)...")
            batch_embeddings = embed_texts(batch, model=config.OLLAMA_EMBED_MODEL)
            logger.info(f"Batch {i//batch_size + 1} embedded successfully. Model unloaded.")
            
            for j, (chunk, embedding) in enumerate(zip(batch, batch_embeddings)):
                chunk_id = f"{file_hash_val}_{i+j}"
                all_ids.append(chunk_id)
                all_documents.append(chunk)
                all_metadatas.append({
                    "source": str(md_path),
                    "chunk": i + j,
                    "file_hash": file_hash_val
                })
                all_embeddings.append(embedding)
        
        # Upsert to ChromaDB
        collection.upsert(
            ids=all_ids,
            documents=all_documents,
            metadatas=all_metadatas,
            embeddings=all_embeddings
        )
        
        logger.info(f"Indexed {len(chunks)} chunks from {md_path.name}")
        
        # Archive the processed file
        try:
            config.ARCHIVE.mkdir(parents=True, exist_ok=True)
            archive_path = config.ARCHIVE / md_path.name
            shutil.move(str(md_path), str(archive_path))
            logger.info(f"Archived {md_path.name} to {archive_path}")
        except Exception as e:
            logger.warning(f"Could not archive {md_path}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Error embedding {md_path}: {e}")
        return False


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

