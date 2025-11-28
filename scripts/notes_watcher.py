"""
Notes Watcher
-------------
Watches knowledge/notes/ (Obsidian vault) for new/modified .md files
and automatically ingests them, then moves them to archived/Auto/<category>/
"""

import hashlib
import logging
import os
import shutil
import threading
import time
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from scripts.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# API base URL
API_BASE = "http://localhost:8000"

# Directories to exclude from watching
EXCLUDE_DIRS = {
    ".obsidian",
    "_templates",
    "_dashboard",
    "_attachments",
    "Templates",
    "_archive",
    "Attachments",
    "Auto",  # Don't watch archived files
    "Inbox from RAG"  # Don't re-ingest files we copied here
}

# Track processed files to avoid duplicates
_processed_files = set()

# Rate limiting: semaphore to limit concurrent enrichments to max 3
_enrichment_semaphore = threading.Semaphore(3)

# Track last processing time for rate limiting
_last_process_time = 0
_process_lock = threading.Lock()


def file_hash(path: Path) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
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
        return ""


def is_already_ingested(file_path: Path) -> bool:
    """Check if file is already in ChromaDB by source path."""
    try:
        import chromadb
        client = chromadb.PersistentClient(path=str(config.VECTOR_DIR))
        collection = client.get_or_create_collection(name=config.COLLECTION_NAME)
        
        # Check if any chunks exist for this source
        results = collection.get(
            where={"source": str(file_path.resolve())},
            limit=1
        )
        return len(results.get("ids", [])) > 0
    except Exception as e:
        logger.warning(f"Could not check ChromaDB for {file_path}: {e}")
        return False


def should_process_file(file_path: Path) -> bool:
    """Check if file should be processed."""
    # Skip if already in archived folder (to avoid loops)
    if "archived" in str(file_path).lower():
        return False
    
    # Skip if in exclude directories
    parts = file_path.parts
    for exclude_dir in EXCLUDE_DIRS:
        if exclude_dir in parts:
            return False
    
    # Only process .md files
    if file_path.suffix.lower() != ".md":
        return False
    
    return True


class NotesHandler(FileSystemEventHandler):
    """Handle file system events for Obsidian notes."""
    
    def __init__(self):
        self.api_base = API_BASE
        super().__init__()
    
    def on_created(self, event):
        """Handle file creation."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not should_process_file(file_path):
            return
        
        # Avoid processing the same file twice
        file_id = str(file_path.resolve())
        if file_id in _processed_files:
            return
        
        # Wait for file write to complete
        time.sleep(2)
        
        if not file_path.exists():
            return
        
        self._process_file(file_path)
    
    def on_modified(self, event):
        """Handle file modification."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if not should_process_file(file_path):
            return
        
        # Check if file was recently modified (avoid rapid re-processing)
        try:
            mtime = file_path.stat().st_mtime
            if time.time() - mtime < 3:  # Modified less than 3 seconds ago
                return
        except Exception:
            pass
        
        self._process_file(file_path)
    
    def _process_file(self, file_path: Path):
        """Process a single file: ingest and move to archive."""
        file_id = str(file_path.resolve())
        
        # Skip if already processed
        if file_id in _processed_files:
            return
        
        # Rate limiting: ensure 2-second delay between processing
        global _last_process_time
        with _process_lock:
            current_time = time.time()
            time_since_last = current_time - _last_process_time
            if time_since_last < 2.0:
                sleep_time = 2.0 - time_since_last
                logger.debug(f"Rate limiting: waiting {sleep_time:.1f}s before processing {file_path.name}")
                time.sleep(sleep_time)
            _last_process_time = time.time()
        
        # Acquire semaphore to limit concurrent enrichments
        _enrichment_semaphore.acquire()
        try:
            logger.info(f"Processing note: {file_path.name}")
            
            # Check if already ingested
            if is_already_ingested(file_path):
                logger.info(f"File {file_path.name} already ingested, skipping")
                _processed_files.add(file_id)
                return
            
            try:
            # Trigger ingestion via FastAPI endpoint
            response = requests.post(
                f"{self.api_base}/ingest/file",
                json={"path": str(file_path.resolve())},
                timeout=60
            )
            
            if response.status_code != 200:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                return
            
            result = response.json()
            if not result.get("success"):
                logger.error(f"Ingestion failed: {result.get('message', 'Unknown error')}")
                return
            
            # Get suggested category from response
            suggested_category = result.get("suggested_category", "uncategorized")
            logger.info(f"Suggested category: {suggested_category}")
            
            # Wait for ingestion to complete (poll status)
            max_wait = 300  # 5 minutes max
            wait_time = 0
            while wait_time < max_wait:
                time.sleep(2)
                status_response = requests.get(
                    f"{self.api_base}/ingest/status/{file_path.resolve()}",
                    timeout=10
                )
                if status_response.status_code == 200:
                    status_data = status_response.json()
                    status = status_data.get("status")
                    if status == "completed":
                        # Update category from status if available
                        category = status_data.get("category") or suggested_category
                        logger.info(f"Ingestion completed. Category: {category}")
                        break
                    elif status == "failed":
                        logger.error(f"Ingestion failed: {status_data.get('error')}")
                        return
                wait_time += 2
            
            if wait_time >= max_wait:
                logger.warning(f"Ingestion timeout for {file_path.name}, proceeding anyway")
                category = suggested_category
            else:
                category = status_data.get("category") or suggested_category
            
            # Move file to archived/Auto/<category>/
            archive_base = config.ARCHIVE / "Auto"
            category_dir = archive_base / category
            category_dir.mkdir(parents=True, exist_ok=True)
            
            target = category_dir / file_path.name
            
            # Handle duplicate filenames
            counter = 1
            while target.exists():
                name_parts = file_path.stem, file_path.suffix
                new_filename = f"{name_parts[0]}_{counter}{name_parts[1]}"
                target = category_dir / new_filename
                counter += 1
            
            shutil.move(str(file_path), str(target))
            logger.info(f"Moved to archive: {target.relative_to(config.ROOT)}")
            
            _processed_files.add(file_id)
            
            except requests.exceptions.RequestException as e:
                logger.error(f"Error calling ingestion API: {e}")
            except Exception as e:
                logger.error(f"Unexpected error processing file {file_path}: {e}")
        finally:
            # Release semaphore
            _enrichment_semaphore.release()


def main():
    """Start watching the notes directory."""
    notes_dir = config.ROOT / "knowledge" / "notes"
    
    # Ensure notes directory exists
    notes_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting notes watcher for: {notes_dir}")
    logger.info(f"Excluding directories: {', '.join(EXCLUDE_DIRS)}")
    
    event_handler = NotesHandler()
    observer = Observer()
    # Watch recursively but exclude certain directories
    observer.schedule(event_handler, str(notes_dir), recursive=True)
    observer.start()
    
    try:
        logger.info("Notes watcher running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping notes watcher...")
        observer.stop()
    
    observer.join()
    logger.info("Notes watcher stopped.")


if __name__ == "__main__":
    main()

