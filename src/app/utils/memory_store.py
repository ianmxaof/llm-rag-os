"""
Memory Store Utility
--------------------
Conversation history management with restoration capabilities.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

try:
    from scripts.chat_logger import ChatLogger
except ImportError:
    ChatLogger = None
    logging.warning("ChatLogger not available")

logger = logging.getLogger(__name__)


def get_memory_streams() -> List[Dict]:
    """
    Get conversation history organized by time periods.
    
    Returns:
        List of conversation dicts with: id, title, timestamp, category, message_count
    """
    if ChatLogger is None:
        logger.warning("ChatLogger not available, returning empty memory streams")
        return []
    
    try:
        logger_instance = ChatLogger()
        
        # Query all conversations grouped by conversation_id
        # We need to get all messages and group them
        conn = logger_instance.db_path
        import sqlite3
        
        db_path = logger_instance.db_path
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all unique conversation IDs
        cursor.execute("""
            SELECT DISTINCT conversation_id 
            FROM chat_log 
            WHERE conversation_id IS NOT NULL
            ORDER BY timestamp DESC
        """)
        conversation_ids = [row[0] for row in cursor.fetchall()]
        
        streams = []
        now = datetime.now()
        
        for conv_id in conversation_ids:
            # Get all messages for this conversation
            cursor.execute("""
                SELECT role, content, timestamp
                FROM chat_log
                WHERE conversation_id = ?
                ORDER BY timestamp ASC
            """, (conv_id,))
            
            messages = cursor.fetchall()
            if not messages:
                continue
            
            # Get first user message as title
            first_user_msg = None
            for role, content, _ in messages:
                if role == 'user':
                    first_user_msg = content
                    break
            
            title = (first_user_msg[:50] + "...") if first_user_msg and len(first_user_msg) > 50 else (first_user_msg or "Untitled Conversation")
            
            # Get latest timestamp
            cursor.execute("""
                SELECT MAX(timestamp)
                FROM chat_log
                WHERE conversation_id = ?
            """, (conv_id,))
            
            latest_timestamp = cursor.fetchone()[0]
            if latest_timestamp:
                latest_dt = datetime.fromtimestamp(latest_timestamp)
                
                # Categorize by time
                diff = now - latest_dt
                if diff < timedelta(hours=24):
                    category = "today"
                elif diff < timedelta(days=7):
                    category = "week"
                else:
                    category = "month"
                
                streams.append({
                    'id': conv_id,
                    'title': title,
                    'timestamp': latest_dt,
                    'category': category,
                    'message_count': len(messages)
                })
        
        conn.close()
        
        # Sort by timestamp descending
        streams.sort(key=lambda x: x['timestamp'], reverse=True)
        
        return streams
    
    except Exception as e:
        logger.error(f"Error getting memory streams: {e}")
        return []


def load_conversation_by_id(conversation_id: str) -> Optional[Dict]:
    """
    Load a conversation by ID from the chat logger.
    
    Args:
        conversation_id: The conversation ID to load
        
    Returns:
        Dict with: id, title, messages, timestamp, message_count
        Returns None if conversation not found
    """
    if ChatLogger is None:
        logger.warning("ChatLogger not available, cannot load conversation")
        return None
    
    try:
        logger_instance = ChatLogger()
        import sqlite3
        
        db_path = logger_instance.db_path
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Get all messages for this conversation
        cursor.execute("""
            SELECT role, content, timestamp, mode, model, max_relevance, sources
            FROM chat_log
            WHERE conversation_id = ?
            ORDER BY timestamp ASC
        """, (conversation_id,))
        
        rows = cursor.fetchall()
        if not rows:
            conn.close()
            return None
        
        # Convert to message format compatible with chat_history
        messages = []
        first_user_msg = None
        
        for role, content, timestamp, mode, model, max_relevance, sources_json in rows:
            if role == 'user' and not first_user_msg:
                first_user_msg = content
            
            # Parse sources if available
            sources = []
            if sources_json:
                try:
                    import json
                    sources = json.loads(sources_json) if isinstance(sources_json, str) else sources_json
                except:
                    pass
            
            # Build message entry
            if role == 'user':
                messages.append({
                    'question': content,
                    'answer': '',
                    'sources': [],
                    'context': '',
                    'mode': mode or '🔍 RAG Mode',
                    'max_relevance': max_relevance or 0.0,
                    'model': model or 'unknown',
                    'rag_threshold': 0.25,
                    'conversation_id': conversation_id
                })
            else:  # assistant
                # Update last message with answer
                if messages:
                    messages[-1]['answer'] = content
                    messages[-1]['sources'] = sources
                    messages[-1]['mode'] = mode or '🔍 RAG Mode'
                    messages[-1]['max_relevance'] = max_relevance or 0.0
                    messages[-1]['model'] = model or 'unknown'
        
        # Get latest timestamp
        cursor.execute("""
            SELECT MAX(timestamp)
            FROM chat_log
            WHERE conversation_id = ?
        """, (conversation_id,))
        
        latest_timestamp = cursor.fetchone()[0]
        latest_dt = datetime.fromtimestamp(latest_timestamp) if latest_timestamp else datetime.now()
        
        conn.close()
        
        title = (first_user_msg[:50] + "...") if first_user_msg and len(first_user_msg) > 50 else (first_user_msg or "Restored Conversation")
        
        return {
            'id': conversation_id,
            'title': title,
            'messages': messages,
            'timestamp': latest_dt,
            'message_count': len(messages)
        }
    
    except Exception as e:
        logger.error(f"Error loading conversation {conversation_id}: {e}")
        return None

