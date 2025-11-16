"""
Inbox Watcher
-------------
Automatically watches the knowledge/inbox/ directory for new .md files
and triggers ingestion via the FastAPI backend.
"""

import os
import time
import shutil
import requests
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from scripts.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)


class InboxHandler(FileSystemEventHandler):
    """Handle file creation events in the inbox directory."""
    
    def __init__(self):
        self.api_base = "http://localhost:8000"
        super().__init__()
    
    def on_created(self, event):
        """Called when a file is created in the watched directory."""
        if event.is_directory:
            return
        
        if not event.src_path.endswith(".md"):
            return
        
        # Wait a moment for file write to complete
        time.sleep(1)
        
        path = event.src_path
        logger.info(f"New file detected: {path}")
        
        try:
            # Trigger ingestion via FastAPI endpoint
            response = requests.post(
                f"{self.api_base}/ingest/file",
                json={"path": path},
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"Successfully ingested: {path}")
                    
                    # Move file to processed directory
                    try:
                        processed_dir = config.PROCESSED_DIR
                        processed_dir.mkdir(parents=True, exist_ok=True)
                        
                        filename = os.path.basename(path)
                        target = processed_dir / filename
                        
                        # Handle duplicate filenames
                        counter = 1
                        while target.exists():
                            name_parts = filename.rsplit(".", 1)
                            if len(name_parts) == 2:
                                new_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                            else:
                                new_filename = f"{filename}_{counter}"
                            target = processed_dir / new_filename
                            counter += 1
                        
                        shutil.move(path, str(target))
                        logger.info(f"Moved to processed: {target}")
                    except Exception as e:
                        logger.error(f"Failed to move file to processed: {e}")
                else:
                    logger.error(f"Ingestion failed: {result.get('message', 'Unknown error')}")
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling ingestion API: {e}")
        except Exception as e:
            logger.error(f"Unexpected error processing file {path}: {e}")


def main():
    """Start watching the inbox directory."""
    inbox_dir = config.INBOX_DIR
    
    # Ensure inbox directory exists
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting inbox watcher for: {inbox_dir}")
    
    event_handler = InboxHandler()
    observer = Observer()
    observer.schedule(event_handler, str(inbox_dir), recursive=False)
    observer.start()
    
    try:
        logger.info("Inbox watcher running. Press Ctrl+C to stop.")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Stopping inbox watcher...")
        observer.stop()
    
    observer.join()
    logger.info("Inbox watcher stopped.")


if __name__ == "__main__":
    main()

