"""
Production Memory Store Utility
--------------------------------
SQLite-based conversation persistence with density scoring and search.
"""

import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class MemoryStore:
    """
    Production-grade memory store with:
    - SQLite persistence
    - Time-based organization
    - Density scoring
    - Full-text search
    - Statistics and analytics
    """
    
    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()
        
        # Conversations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                message_count INTEGER DEFAULT 0,
                tags TEXT,
                metadata TEXT,
                crystallized_path TEXT,
                density_score REAL DEFAULT 0.0,
                upvotes INTEGER DEFAULT 0,
                references_count INTEGER DEFAULT 0
            )
        """)
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # References table (for tracking which conversations reference others)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS references (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_conversation_id TEXT NOT NULL,
                to_conversation_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (from_conversation_id) REFERENCES conversations(id),
                FOREIGN KEY (to_conversation_id) REFERENCES conversations(id)
            )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_updated ON conversations(updated_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_tags ON conversations(tags)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_conv ON messages(conversation_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON messages(timestamp)")
        
        conn.commit()
        conn.close()
    
    def store_conversation(
        self,
        conversation_id: str,
        messages: List[Dict],
        title: Optional[str] = None,
        tags: List[str] = None,
        metadata: Dict = None
    ) -> bool:
        """
        Store conversation with all messages.
        
        Args:
            conversation_id: Unique conversation identifier
            messages: List of message dicts
            title: Conversation title (defaults to first user message)
            tags: List of tags
            metadata: Additional metadata dict
            
        Returns:
            True if stored successfully
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Extract title from first user message if not provided
            if not title:
                for msg in messages:
                    if msg.get('role') == 'user' or 'question' in msg:
                        title = msg.get('question', msg.get('content', ''))[:100]
                        break
                title = title or "Untitled Conversation"
            
            # Calculate density score
            density_score = self._calculate_density_score(messages, conversation_id)
            
            # Store or update conversation
            cursor.execute("""
                INSERT OR REPLACE INTO conversations 
                (id, title, updated_at, message_count, tags, metadata, density_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                conversation_id,
                title,
                datetime.now().isoformat(),
                len(messages),
                json.dumps(tags or []),
                json.dumps(metadata or {}),
                density_score
            ))
            
            # Delete old messages and insert new ones
            cursor.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            
            for idx, msg in enumerate(messages):
                role = msg.get('role', 'user' if 'question' in msg else 'assistant')
                content = msg.get('question', msg.get('content', msg.get('answer', '')))
                
                # Store message metadata
                msg_metadata = {
                    'mode': msg.get('mode'),
                    'model': msg.get('model'),
                    'max_relevance': msg.get('max_relevance'),
                    'sources': msg.get('sources', [])
                }
                
                cursor.execute("""
                    INSERT INTO messages 
                    (conversation_id, role, content, timestamp, metadata)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    conversation_id,
                    role,
                    content,
                    datetime.now().isoformat(),
                    json.dumps(msg_metadata)
                ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored conversation {conversation_id} with {len(messages)} messages")
            return True
        
        except Exception as e:
            logger.error(f"Error storing conversation: {e}")
            return False
    
    def _calculate_density_score(
        self,
        messages: List[Dict],
        conversation_id: str
    ) -> float:
        """
        Calculate memory density score.
        
        Formula: (upvotes + references) / message_count / age_in_days
        Higher score = more valuable conversation
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get upvotes and references
            cursor.execute("""
                SELECT upvotes, references_count 
                FROM conversations 
                WHERE id = ?
            """, (conversation_id,))
            
            row = cursor.fetchone()
            upvotes = row[0] if row else 0
            references = row[1] if row else 0
            
            conn.close()
            
            # Calculate age (default to 1 day for new conversations)
            age_days = 1.0
            
            # Score calculation
            message_count = max(1, len(messages))
            score = (upvotes + references) / message_count / age_days
            
            return score
        
        except Exception as e:
            logger.error(f"Error calculating density score: {e}")
            return 0.0
    
    def get_memory_streams(self, days_back: int = 30) -> List[Dict]:
        """
        Get conversations organized by time periods.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            List of conversation dicts with: id, title, timestamp, category, message_count
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            cursor.execute("""
                SELECT id, title, updated_at, message_count, density_score
                FROM conversations
                WHERE updated_at >= ?
                ORDER BY updated_at DESC
            """, (cutoff_date.isoformat(),))
            
            rows = cursor.fetchall()
            conn.close()
            
            streams = []
            now = datetime.now()
            
            for conv_id, title, updated_str, msg_count, density in rows:
                updated_dt = datetime.fromisoformat(updated_str)
                
                # Categorize by time
                diff = now - updated_dt
                if diff < timedelta(hours=24):
                    category = "today"
                elif diff < timedelta(days=7):
                    category = "week"
                else:
                    category = "month"
                
                streams.append({
                    'id': conv_id,
                    'title': title,
                    'timestamp': updated_dt,
                    'category': category,
                    'message_count': msg_count,
                    'density_score': density
                })
            
            return streams
        
        except Exception as e:
            logger.error(f"Error getting memory streams: {e}")
            return []
    
    def load_conversation_by_id(self, conversation_id: str) -> Optional[Dict]:
        """
        Load full conversation by ID.
        
        Args:
            conversation_id: Conversation ID to load
            
        Returns:
            Dict with: id, title, messages, timestamp, message_count
            Returns None if not found
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Get conversation metadata
            cursor.execute("""
                SELECT title, created_at, updated_at, message_count, tags, metadata
                FROM conversations
                WHERE id = ?
            """, (conversation_id,))
            
            row = cursor.fetchone()
            if not row:
                conn.close()
                return None
            
            title, created_str, updated_str, msg_count, tags_json, metadata_json = row
            
            # Get all messages
            cursor.execute("""
                SELECT role, content, timestamp, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conversation_id,))
            
            message_rows = cursor.fetchall()
            conn.close()
            
            # Convert messages to chat_history format
            messages = []
            for role, content, timestamp_str, msg_metadata_json in message_rows:
                msg_metadata = json.loads(msg_metadata_json) if msg_metadata_json else {}
                
                if role == 'user':
                    messages.append({
                        'question': content,
                        'answer': '',
                        'sources': msg_metadata.get('sources', []),
                        'context': '',
                        'mode': msg_metadata.get('mode', '🔍 RAG Mode'),
                        'max_relevance': msg_metadata.get('max_relevance', 0.0),
                        'model': msg_metadata.get('model', 'unknown'),
                        'rag_threshold': 0.25,
                        'conversation_id': conversation_id
                    })
                else:  # assistant
                    if messages:
                        messages[-1]['answer'] = content
                        messages[-1]['sources'] = msg_metadata.get('sources', [])
                        messages[-1]['mode'] = msg_metadata.get('mode', '🔍 RAG Mode')
                        messages[-1]['max_relevance'] = msg_metadata.get('max_relevance', 0.0)
                        messages[-1]['model'] = msg_metadata.get('model', 'unknown')
            
            updated_dt = datetime.fromisoformat(updated_str) if updated_str else datetime.now()
            tags = json.loads(tags_json) if tags_json else []
            metadata = json.loads(metadata_json) if metadata_json else {}
            
            return {
                'id': conversation_id,
                'title': title,
                'messages': messages,
                'timestamp': updated_dt,
                'message_count': len(messages),
                'tags': tags,
                'metadata': metadata
            }
        
        except Exception as e:
            logger.error(f"Error loading conversation {conversation_id}: {e}")
            return None
    
    def mark_crystallized(self, conversation_id: str, note_path: str) -> bool:
        """Mark conversation as crystallized with note path"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE conversations
                SET crystallized_path = ?
                WHERE id = ?
            """, (note_path, conversation_id))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Marked conversation {conversation_id} as crystallized")
            return True
        
        except Exception as e:
            logger.error(f"Error marking crystallized: {e}")
            return False
    
    def search_conversations(self, query: str, limit: int = 20) -> List[Dict]:
        """
        Search conversations by title and content.
        
        Args:
            query: Search query string
            limit: Maximum results
            
        Returns:
            List of matching conversations
        """
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            query_lower = f"%{query.lower()}%"
            
            # Search in titles and message content
            cursor.execute("""
                SELECT DISTINCT c.id, c.title, c.updated_at, c.message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.title LIKE ? OR m.content LIKE ?
                ORDER BY c.updated_at DESC
                LIMIT ?
            """, (query_lower, query_lower, limit))
            
            rows = cursor.fetchall()
            conn.close()
            
            results = []
            for conv_id, title, updated_str, msg_count in rows:
                updated_dt = datetime.fromisoformat(updated_str) if updated_str else datetime.now()
                results.append({
                    'id': conv_id,
                    'title': title,
                    'timestamp': updated_dt,
                    'message_count': msg_count
                })
            
            return results
        
        except Exception as e:
            logger.error(f"Error searching conversations: {e}")
            return []
    
    def get_memory_statistics(self) -> Dict:
        """Get memory store statistics"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Total conversations
            cursor.execute("SELECT COUNT(*) FROM conversations")
            total_conversations = cursor.fetchone()[0]
            
            # Total messages
            cursor.execute("SELECT COUNT(*) FROM messages")
            total_messages = cursor.fetchone()[0]
            
            # Crystallized count
            cursor.execute("SELECT COUNT(*) FROM conversations WHERE crystallized_path IS NOT NULL")
            crystallized_count = cursor.fetchone()[0]
            
            # High density conversations
            cursor.execute("SELECT COUNT(*) FROM conversations WHERE density_score > 1.0")
            high_density_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'total_conversations': total_conversations,
                'total_messages': total_messages,
                'crystallized_count': crystallized_count,
                'high_density_count': high_density_count,
                'avg_messages_per_conversation': total_messages / total_conversations if total_conversations > 0 else 0
            }
        
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            return {}


# ============================================================================
# PUBLIC API
# ============================================================================

# Singleton instance
_store = None

def get_memory_store() -> MemoryStore:
    """Get or create memory store singleton"""
    global _store
    if _store is None:
        db_path = os.getenv('MEMORY_DB_PATH', './data/memory.db')
        _store = MemoryStore(db_path=db_path)
    return _store

def store_conversation(
    conversation_id: str,
    messages: List[Dict],
    title: Optional[str] = None,
    tags: List[str] = None,
    metadata: Dict = None
) -> bool:
    """Public API: Store conversation"""
    store = get_memory_store()
    return store.store_conversation(conversation_id, messages, title, tags, metadata)

def get_memory_streams(days_back: int = 30) -> List[Dict]:
    """Public API: Get memory streams"""
    store = get_memory_store()
    return store.get_memory_streams(days_back)

def load_conversation_by_id(conversation_id: str) -> Optional[Dict]:
    """Public API: Load conversation by ID"""
    store = get_memory_store()
    return store.load_conversation_by_id(conversation_id)

def mark_crystallized(conversation_id: str, note_path: str) -> bool:
    """Public API: Mark conversation as crystallized"""
    store = get_memory_store()
    return store.mark_crystallized(conversation_id, note_path)

def search_conversations(query: str, limit: int = 20) -> List[Dict]:
    """Public API: Search conversations"""
    store = get_memory_store()
    return store.search_conversations(query, limit)

def get_memory_statistics() -> Dict:
    """Public API: Get memory statistics"""
    store = get_memory_store()
    return store.get_memory_statistics()
