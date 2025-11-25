"""
Chat Logger
-----------
Persistent SQLite database for tracking all chat messages with is_crystallized flag.
Enables true metacognition by providing perfect recall of conversations.
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import json

logger = logging.getLogger(__name__)


class ChatLogger:
    """Manages SQLite database for tracking chat history."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize chat logger database.
        
        Args:
            db_path: Path to SQLite database file (defaults to data/chat_history.db)
        """
        if db_path is None:
            # Default to data/chat_history.db
            from scripts.config import config
            if config and hasattr(config, 'ROOT'):
                db_path = config.ROOT / "data" / "chat_history.db"
            else:
                db_path = Path("./data/chat_history.db")
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """Initialize database schema if it doesn't exist."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS chat_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                mode TEXT,
                model TEXT,
                max_relevance REAL,
                sources TEXT,
                is_crystallized INTEGER DEFAULT 0,
                crystallized_path TEXT,
                conversation_id TEXT
            )
        ''')
        
        # Create indexes for fast queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_session 
            ON chat_log(session_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_timestamp 
            ON chat_log(timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_crystallized 
            ON chat_log(is_crystallized)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_conversation 
            ON chat_log(conversation_id)
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Chat logger initialized: {self.db_path}")
    
    def log_message(
        self,
        session_id: str,
        role: str,
        content: str,
        mode: Optional[str] = None,
        model: Optional[str] = None,
        max_relevance: Optional[float] = None,
        sources: Optional[List] = None,
        conversation_id: Optional[str] = None
    ) -> int:
        """
        Log a chat message to the database.
        
        Args:
            session_id: Unique session identifier
            role: "user" or "assistant"
            content: Message content
            mode: RAG mode (RAG Mode, Raw Mode, Auto-Fallback)
            model: Model used
            max_relevance: Relevance score
            sources: List of sources (will be JSON serialized)
            conversation_id: Conversation ID for grouping
        
        Returns:
            ID of inserted row
        """
        timestamp = int(datetime.now().timestamp())
        sources_json = json.dumps(sources) if sources else None
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO chat_log 
            (session_id, timestamp, role, content, mode, model, max_relevance, sources, conversation_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (session_id, timestamp, role, content, mode, model, max_relevance, sources_json, conversation_id))
        
        row_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        logger.debug(f"Logged {role} message (id={row_id})")
        return row_id
    
    def mark_crystallized(self, chat_log_id: int, file_path: str):
        """
        Mark a chat message as crystallized.
        
        Args:
            chat_log_id: ID of chat log entry
            file_path: Path to crystallized file
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE chat_log 
            SET is_crystallized = 1, crystallized_path = ?
            WHERE id = ?
        ''', (file_path, chat_log_id))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Marked chat log {chat_log_id} as crystallized: {file_path}")
    
    def get_uncrystallized(self, hours: int = 24) -> List[Dict]:
        """
        Get uncrystallized chat messages from last N hours.
        
        Args:
            hours: Number of hours to look back
        
        Returns:
            List of chat log entries
        """
        cutoff_timestamp = int((datetime.now().timestamp() - (hours * 3600)))
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row  # Enable column access by name
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chat_log
            WHERE is_crystallized = 0 
            AND timestamp > ?
            ORDER BY timestamp ASC
        ''', (cutoff_timestamp,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert rows to dicts
        chats = []
        for row in rows:
            chat = dict(row)
            # Parse sources JSON
            if chat.get('sources'):
                try:
                    chat['sources'] = json.loads(chat['sources'])
                except:
                    chat['sources'] = []
            chats.append(chat)
        
        logger.debug(f"Found {len(chats)} uncrystallized chats from last {hours} hours")
        return chats
    
    def get_recent_chats(self, hours: int = 24, limit: Optional[int] = None) -> List[Dict]:
        """
        Get recent chat messages from last N hours.
        
        Args:
            hours: Number of hours to look back
            limit: Optional limit on number of results
        
        Returns:
            List of chat log entries
        """
        cutoff_timestamp = int((datetime.now().timestamp() - (hours * 3600)))
        
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        query = '''
            SELECT * FROM chat_log
            WHERE timestamp > ?
            ORDER BY timestamp ASC
        '''
        
        if limit:
            query += f' LIMIT {limit}'
        
        cursor.execute(query, (cutoff_timestamp,))
        
        rows = cursor.fetchall()
        conn.close()
        
        # Convert rows to dicts
        chats = []
        for row in rows:
            chat = dict(row)
            # Parse sources JSON
            if chat.get('sources'):
                try:
                    chat['sources'] = json.loads(chat['sources'])
                except:
                    chat['sources'] = []
            chats.append(chat)
        
        return chats
    
    def get_conversation(self, conversation_id: str) -> List[Dict]:
        """
        Get all messages for a specific conversation.
        
        Args:
            conversation_id: Conversation ID
        
        Returns:
            List of chat log entries for the conversation
        """
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM chat_log
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        ''', (conversation_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        chats = []
        for row in rows:
            chat = dict(row)
            if chat.get('sources'):
                try:
                    chat['sources'] = json.loads(chat['sources'])
                except:
                    chat['sources'] = []
            chats.append(chat)
        
        return chats
    
    def get_stats(self) -> Dict:
        """
        Get statistics about chat log.
        
        Returns:
            Dictionary with stats
        """
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM chat_log')
        total = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM chat_log WHERE is_crystallized = 1')
        crystallized = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM chat_log WHERE is_crystallized = 0')
        uncrystallized = cursor.fetchone()[0]
        
        cursor.execute('SELECT MIN(timestamp) FROM chat_log')
        oldest = cursor.fetchone()[0]
        
        cursor.execute('SELECT MAX(timestamp) FROM chat_log')
        newest = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            'total_messages': total,
            'crystallized': crystallized,
            'uncrystallized': uncrystallized,
            'oldest_timestamp': oldest,
            'newest_timestamp': newest
        }

