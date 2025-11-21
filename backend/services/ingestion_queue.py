"""
Ingestion Queue Service
-----------------------
Manages deduplication and batch processing of refined items.
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path
import json

from scripts.config import config


class IngestionQueue:
    """Queue for managing refined items before ingestion."""
    
    def __init__(self, queue_dir: Optional[Path] = None):
        """
        Initialize ingestion queue.
        
        Args:
            queue_dir: Directory to store queue data
        """
        self.queue_dir = queue_dir or (config.ROOT / "intelligence-data" / "queue")
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.processed_file = self.queue_dir / "processed.jsonl"
        self.pending_file = self.queue_dir / "pending.jsonl"
        
    def add_item(self, item: Dict) -> bool:
        """
        Add an item to the queue if not already processed.
        
        Args:
            item: Refined item to add
            
        Returns:
            True if added, False if duplicate
        """
        item_hash = self._hash_item(item)
        
        # Check if already processed
        if self._is_processed(item_hash):
            return False
        
        # Add to pending queue
        with open(self.pending_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "hash": item_hash,
                "item": item,
                "added_at": datetime.now().isoformat(),
            }) + "\n")
        
        return True
    
    def get_pending_items(self, limit: Optional[int] = None) -> List[Dict]:
        """
        Get pending items from queue.
        
        Args:
            limit: Maximum number of items to return
            
        Returns:
            List of pending items
        """
        items = []
        
        if not self.pending_file.exists():
            return items
        
        with open(self.pending_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        items.append(data["item"])
                        if limit and len(items) >= limit:
                            break
                    except json.JSONDecodeError:
                        continue
        
        return items
    
    def mark_processed(self, item_hash: str):
        """
        Mark an item as processed.
        
        Args:
            item_hash: Hash of the processed item
        """
        with open(self.processed_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "hash": item_hash,
                "processed_at": datetime.now().isoformat(),
            }) + "\n")
    
    def clear_pending(self):
        """Clear the pending queue (after processing)."""
        if self.pending_file.exists():
            self.pending_file.unlink()
    
    def _hash_item(self, item: Dict) -> str:
        """Generate hash for an item based on URL and content."""
        url = item.get("source_url", "")
        content = item.get("content", "")[:500]  # Use first 500 chars
        hash_input = f"{url}:{content}"
        return hashlib.md5(hash_input.encode("utf-8")).hexdigest()
    
    def _is_processed(self, item_hash: str) -> bool:
        """Check if an item hash has been processed."""
        if not self.processed_file.exists():
            return False
        
        with open(self.processed_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        data = json.loads(line)
                        if data.get("hash") == item_hash:
                            return True
                    except json.JSONDecodeError:
                        continue
        
        return False
    
    def get_stats(self) -> Dict:
        """Get queue statistics."""
        processed_count = 0
        pending_count = 0
        
        if self.processed_file.exists():
            with open(self.processed_file, "r", encoding="utf-8") as f:
                processed_count = sum(1 for line in f if line.strip())
        
        if self.pending_file.exists():
            with open(self.pending_file, "r", encoding="utf-8") as f:
                pending_count = sum(1 for line in f if line.strip())
        
        return {
            "processed": processed_count,
            "pending": pending_count,
            "queue_dir": str(self.queue_dir),
        }

