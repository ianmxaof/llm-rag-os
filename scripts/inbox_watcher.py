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
                    
                    # Get suggested category from response
                    suggested_category = result.get("suggested_category", "uncategorized")
                    
                    # Wait for ingestion to complete and get final category
                    file_path_obj = Path(path)
                    max_wait = 300  # 5 minutes max
                    wait_time = 0
                    final_category = suggested_category
                    
                    while wait_time < max_wait:
                        time.sleep(2)
                        try:
                            status_response = requests.get(
                                f"{self.api_base}/ingest/status/{file_path_obj.resolve()}",
                                timeout=10
                            )
                            if status_response.status_code == 200:
                                status_data = status_response.json()
                                status = status_data.get("status")
                                if status == "completed":
                                    final_category = status_data.get("category") or suggested_category
                                    break
                                elif status == "failed":
                                    logger.error(f"Ingestion failed: {status_data.get('error')}")
                                    break
                        except Exception:
                            pass
                        wait_time += 2
                    
                    # Copy to Obsidian notes folder (bidirectional sync)
                    try:
                        notes_dir = config.ROOT / "knowledge" / "notes" / "Inbox from RAG"
                        notes_dir.mkdir(parents=True, exist_ok=True)
                        
                        obsidian_target = notes_dir / file_path_obj.name
                        
                        # Handle duplicate filenames
                        counter = 1
                        while obsidian_target.exists():
                            name_parts = file_path_obj.stem, file_path_obj.suffix
                            new_filename = f"{name_parts[0]}_{counter}{name_parts[1]}"
                            obsidian_target = notes_dir / new_filename
                            counter += 1
                        
                        shutil.copy2(path, str(obsidian_target))
                        logger.info(f"Copied to Obsidian: {obsidian_target.relative_to(config.ROOT)}")
                    except Exception as e:
                        logger.error(f"Failed to copy file to Obsidian: {e}")
                    
                    # Move file to archived/Auto/<category>/ directory
                    try:
                        archive_base = config.ARCHIVE / "Auto"
                        category_dir = archive_base / final_category
                        category_dir.mkdir(parents=True, exist_ok=True)
                        
                        filename = os.path.basename(path)
                        target = category_dir / filename
                        
                        # Handle duplicate filenames
                        counter = 1
                        while target.exists():
                            name_parts = filename.rsplit(".", 1)
                            if len(name_parts) == 2:
                                new_filename = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                            else:
                                new_filename = f"{filename}_{counter}"
                            target = category_dir / new_filename
                            counter += 1
                        
                        shutil.move(path, str(target))
                        logger.info(f"Moved to archive: {target.relative_to(config.ROOT)}")
                    except Exception as e:
                        logger.error(f"Failed to move file to archive: {e}")
                else:
                    logger.error(f"Ingestion failed: {result.get('message', 'Unknown error')}")
                    # Move failed file to error directory
                    try:
                        error_dir = config.ERROR_DIR
                        error_dir.mkdir(parents=True, exist_ok=True)
                        error_target = error_dir / os.path.basename(path)
                        shutil.move(path, str(error_target))
                        logger.info(f"Moved failed file to error: {error_target}")
                    except Exception as e:
                        logger.error(f"Failed to move file to error: {e}")
            else:
                logger.error(f"API request failed: {response.status_code} - {response.text}")
                # Move failed file to error directory
                try:
                    error_dir = config.ERROR_DIR
                    error_dir.mkdir(parents=True, exist_ok=True)
                    error_target = error_dir / os.path.basename(path)
                    shutil.move(path, str(error_target))
                    logger.info(f"Moved failed file to error: {error_target}")
                except Exception as e:
                    logger.error(f"Failed to move file to error: {e}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Error calling ingestion API: {e}")
            # Move failed file to error directory
            try:
                error_dir = config.ERROR_DIR
                error_dir.mkdir(parents=True, exist_ok=True)
                error_target = error_dir / os.path.basename(path)
                shutil.move(path, str(error_target))
                logger.info(f"Moved failed file to error: {error_target}")
            except Exception as move_error:
                logger.error(f"Failed to move file to error: {move_error}")
        except Exception as e:
            logger.error(f"Unexpected error processing file {path}: {e}")
            # Move failed file to error directory
            try:
                error_dir = config.ERROR_DIR
                error_dir.mkdir(parents=True, exist_ok=True)
                error_target = error_dir / os.path.basename(path)
                shutil.move(path, str(error_target))
                logger.info(f"Moved failed file to error: {error_target}")
            except Exception as move_error:
                logger.error(f"Failed to move file to error: {move_error}")


def main():
    """Start watching the inbox directory."""
    inbox_dir = config.INBOX
    
    # Ensure inbox directory exists
    inbox_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Starting inbox watcher for: {inbox_dir}")
    
    event_handler = InboxHandler()
    observer = Observer()
    # Watch recursively to support Obsidian vaults (e.g., inbox/MyVault/)
    observer.schedule(event_handler, str(inbox_dir), recursive=True)
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

