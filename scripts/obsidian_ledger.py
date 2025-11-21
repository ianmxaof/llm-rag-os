"""
Obsidian Ingestion Ledger
-------------------------
SQLite database for tracking file ingestion state.
Provides 100% correct deduplication even if filesystem timestamps are messed up.
"""

import sqlite3
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


class IngestionLedger:
    """Manages SQLite ledger for tracking file ingestion."""
    
    def __init__(self, ledger_path: Path):
        """
        Initialize ledger database.
        
        Args:
            ledger_path: Path to SQLite database file
        """
        self.ledger_path = ledger_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(str(self.ledger_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ingestion_ledger (
                file_path TEXT PRIMARY KEY,
                last_hash TEXT NOT NULL,
                last_ingested_ts TIMESTAMP NOT NULL,
                chunk_count INTEGER DEFAULT 0
            )
        ''')
        
        # Create index on timestamp for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON ingestion_ledger(last_ingested_ts)
        ''')
        
        conn.commit()
        conn.close()
    
    def get_file_hash(self, file_path: Path) -> Optional[str]:
        """
        Get stored hash for a file.
        
        Args:
            file_path: Path to file
        
        Returns:
            Stored hash or None if file not in ledger
        """
        conn = sqlite3.connect(str(self.ledger_path))
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT last_hash FROM ingestion_ledger WHERE file_path = ?',
            (str(file_path),)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def compute_file_hash(self, file_path: Path) -> str:
        """
        Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to file
        
        Returns:
            SHA256 hash hex string
        """
        content = file_path.read_bytes()
        return hashlib.sha256(content).hexdigest()
    
    def should_reingest(self, file_path: Path) -> Tuple[bool, Optional[str]]:
        """
        Check if file should be re-ingested.
        
        Args:
            file_path: Path to file
        
        Returns:
            Tuple of (should_reingest, stored_hash)
            - should_reingest: True if file needs ingestion
            - stored_hash: Current hash in ledger (None if not found)
        """
        if not file_path.exists():
            return False, None
        
        current_hash = self.compute_file_hash(file_path)
        stored_hash = self.get_file_hash(file_path)
        
        if stored_hash is None:
            # File not in ledger, needs ingestion
            return True, None
        
        if current_hash != stored_hash:
            # Hash changed, needs re-ingestion
            return True, stored_hash
        
        # Hash matches, skip ingestion
        return False, stored_hash
    
    def record_ingestion(
        self,
        file_path: Path,
        chunk_count: int = 0
    ):
        """
        Record successful ingestion in ledger.
        
        Args:
            file_path: Path to ingested file
            chunk_count: Number of chunks created
        """
        current_hash = self.compute_file_hash(file_path)
        timestamp = datetime.now().isoformat()
        
        conn = sqlite3.connect(str(self.ledger_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO ingestion_ledger 
            (file_path, last_hash, last_ingested_ts, chunk_count)
            VALUES (?, ?, ?, ?)
        ''', (str(file_path), current_hash, timestamp, chunk_count))
        
        conn.commit()
        conn.close()
    
    def get_ingestion_stats(self) -> dict:
        """
        Get statistics about ingestion ledger.
        
        Returns:
            Dictionary with stats (total_files, oldest_ingestion, newest_ingestion)
        """
        conn = sqlite3.connect(str(self.ledger_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM ingestion_ledger')
        total_files = cursor.fetchone()[0]
        
        cursor.execute('SELECT MIN(last_ingested_ts) FROM ingestion_ledger')
        oldest = cursor.fetchone()[0]
        
        cursor.execute('SELECT MAX(last_ingested_ts) FROM ingestion_ledger')
        newest = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_files': total_files,
            'oldest_ingestion': oldest,
            'newest_ingestion': newest
        }
    
    def clear_file(self, file_path: Path):
        """
        Remove file from ledger (for force re-indexing).
        
        Args:
            file_path: Path to file to remove
        """
        conn = sqlite3.connect(str(self.ledger_path))
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM ingestion_ledger WHERE file_path = ?', (str(file_path),))
        
        conn.commit()
        conn.close()

