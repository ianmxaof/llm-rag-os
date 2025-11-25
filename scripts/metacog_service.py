"""
Metacognition Service
---------------------
Background service that reviews recent uncrystallized chat logs and identifies
high-value insights that the user didn't crystallize. The AI becomes proactive
about its own memory.
"""

import os
import sys
import time
import logging
import json
import requests
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import config
try:
    from scripts.config import config, OLLAMA_API_BASE
except ImportError:
    OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/api")
    config = None

# Import crystallize module
try:
    from src.crystallize import crystallize_turn
except ImportError:
    logger.warning("crystallize module not available")
    crystallize_turn = None

# Import ChatLogger
try:
    from scripts.chat_logger import ChatLogger
except ImportError:
    logger.warning("chat_logger module not available")
    ChatLogger = None


METACOG_PROMPT = """Review these recent conversations. Identify novel, high-value, or conclusive insights that weren't crystallized.

Mark as HIGH_VALUE if the insight is:
- Novel (new information or synthesis)
- Actionable (leads to concrete next steps)
- Conclusive (resolves a question or debate)
- Foundational (important for future reference)

For each HIGH_VALUE insight, provide:
1. A brief summary (1-2 sentences)
2. Why it's valuable
3. The specific turn number or context

Return format:
HIGH_VALUE or SKIP
[Summary]
[Reason]
[Turn/Context]

Conversations:
{conversations}
"""


def scan_recent_chats(hours: int = 24, chat_logger: Optional[ChatLogger] = None) -> List[Dict]:
    """
    Load uncrystallized chat history from recent hours using ChatLogger.
    
    Args:
        hours: Number of hours to look back
        chat_logger: ChatLogger instance (creates new if None)
    
    Returns:
        List of chat entries that haven't been crystallized
    """
    if chat_logger is None:
        if ChatLogger is None:
            logger.error("ChatLogger not available")
            return []
        try:
            chat_logger = ChatLogger()
        except Exception as e:
            logger.error(f"Failed to initialize ChatLogger: {e}")
            return []
    
    try:
        # Use ChatLogger to get uncrystallized chats
        uncrystallized = chat_logger.get_uncrystallized(hours=hours)
        
        # Convert to format expected by reflection function
        chats = []
        for entry in uncrystallized:
            # Group user/assistant pairs
            if entry.get("role") == "assistant":
                # Find corresponding user message (previous entry)
                chats.append({
                    "question": "",  # Will be filled from previous entry if available
                    "answer": entry.get("content", ""),
                    "mode": entry.get("mode", "RAG Mode"),
                    "model": entry.get("model", "unknown"),
                    "max_relevance": entry.get("max_relevance", 0.0),
                    "sources": entry.get("sources", [])
                })
            elif entry.get("role") == "user":
                # If last entry was assistant, update its question
                if chats and not chats[-1].get("question"):
                    chats[-1]["question"] = entry.get("content", "")
                else:
                    # Standalone user message (shouldn't happen, but handle it)
                    chats.append({
                        "question": entry.get("content", ""),
                        "answer": "",
                        "mode": "unknown",
                        "model": "unknown",
                        "max_relevance": 0.0,
                        "sources": []
                    })
        
        return chats
    
    except Exception as e:
        logger.error(f"Error loading chat history: {e}")
        return []


def reflect_on_conversations(chats: List[Dict], model: str = "llama3.1:70b") -> List[Dict]:
    """
    Use LLM to reflect on conversations and identify HIGH_VALUE insights.
    
    Args:
        chats: List of chat entries
        model: Model to use for reflection (larger model for better judgment)
    
    Returns:
        List of insights marked as HIGH_VALUE with metadata
    """
    if not chats:
        return []
    
    # Format conversations for prompt
    conversations_text = ""
    for idx, chat in enumerate(chats, 1):
        question = chat.get("question", "")
        answer = chat.get("answer", "")
        mode = chat.get("mode", "RAG Mode")
        conversations_text += f"\n--- Turn {idx} ({mode}) ---\n"
        conversations_text += f"Q: {question}\n"
        conversations_text += f"A: {answer[:500]}\n"  # Limit answer length
    
    prompt = METACOG_PROMPT.format(conversations=conversations_text)
    
    try:
        # Call Ollama API
        api_base = OLLAMA_API_BASE.replace('/api', '') if '/api' in OLLAMA_API_BASE else OLLAMA_API_BASE
        response = requests.post(
            f"{api_base}/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": 1000,
                    "temperature": 0.5
                }
            },
            timeout=120.0
        )
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "")
            
            # Parse response for HIGH_VALUE insights
            insights = []
            lines = response_text.split('\n')
            current_insight = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("HIGH_VALUE"):
                    if current_insight:
                        insights.append(current_insight)
                    current_insight = {"status": "HIGH_VALUE", "summary": "", "reason": "", "context": ""}
                elif line.startswith("SKIP"):
                    if current_insight:
                        insights.append(current_insight)
                    current_insight = None
                elif current_insight:
                    if line.startswith("Summary:") or line.startswith("[Summary]"):
                        current_insight["summary"] = line.split(":", 1)[-1].strip()
                    elif line.startswith("Reason:") or line.startswith("[Reason]"):
                        current_insight["reason"] = line.split(":", 1)[-1].strip()
                    elif line.startswith("Turn:") or line.startswith("[Turn") or line.startswith("[Context"):
                        current_insight["context"] = line.split(":", 1)[-1].strip()
            
            if current_insight:
                insights.append(current_insight)
            
            return [insight for insight in insights if insight.get("status") == "HIGH_VALUE"]
    
    except Exception as e:
        logger.error(f"Error reflecting on conversations: {e}")
    
    return []


def auto_crystallize_draft(insight: Dict, source_chat: Dict, drafts_folder: Optional[Path] = None) -> Optional[str]:
    """
    Save draft insight to _drafts folder for user review.
    
    Args:
        insight: Insight dict with summary, reason, context
        source_chat: Original chat entry that contains the insight
        drafts_folder: Path to drafts folder
    
    Returns:
        Filepath of created draft or None if failed
    """
    if drafts_folder is None:
        if config and hasattr(config, 'ROOT'):
            drafts_folder = config.ROOT / "knowledge" / "notes" / "Auto" / "_drafts"
        else:
            drafts_folder = Path("./knowledge/notes/Auto/_drafts")
    
    drafts_folder.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}_metacog_draft.md"
    filepath = drafts_folder / filename
    
    # Build draft content
    content = f"""---
date: {datetime.now().isoformat()}
type: metacog_draft
status: draft
source: auto-detected
tags: [metacog, draft, ai-suggested]
---

# 🧠 Metacognition Draft

**AI Detected High-Value Insight**

## Summary

{insight.get('summary', 'No summary provided')}

## Why This Matters

{insight.get('reason', 'No reason provided')}

## Context

{insight.get('context', 'No context provided')}

## Original Conversation

**Question:** {source_chat.get('question', 'N/A')}

**Answer:** {source_chat.get('answer', 'N/A')[:1000]}

**Mode:** {source_chat.get('mode', 'N/A')}
**Model:** {source_chat.get('model', 'N/A')}

---

> 💡 **Note:** This was automatically detected by the Metacognition Service. Review and promote to main notes if valuable, or delete if not.
"""
    
    try:
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"Created metacog draft: {filepath}")
        return str(filepath)
    except Exception as e:
        logger.error(f"Failed to create draft: {e}")
        return None


def notify_user(message: str, draft_path: Optional[str] = None):
    """
    Notify user about proposed crystallization.
    
    Args:
        message: Notification message
        draft_path: Path to draft file (if created)
    """
    logger.info(f"🧠 {message}")
    if draft_path:
        logger.info(f"   Draft saved: {draft_path}")
    
    # In a real implementation, this could:
    # - Send Streamlit notification
    # - Send system notification (desktop notification)
    # - Send email
    # - Update a notification queue for UI display


def run_metacog_cycle(hours: int = 24, model: str = "llama3.1:70b", chat_logger: Optional[ChatLogger] = None):
    """
    Run one cycle of metacognition review.
    
    Args:
        hours: Hours to look back
        model: Model to use for reflection
        chat_logger: ChatLogger instance (creates new if None)
    """
    logger.info(f"Starting metacognition cycle (last {hours} hours)")
    
    # Initialize ChatLogger if needed
    if chat_logger is None:
        if ChatLogger is None:
            logger.error("ChatLogger not available, cannot run metacognition")
            return
        try:
            chat_logger = ChatLogger()
        except Exception as e:
            logger.error(f"Failed to initialize ChatLogger: {e}")
            return
    
    # Scan recent chats using ChatLogger
    recent_chats = scan_recent_chats(hours=hours, chat_logger=chat_logger)
    if not recent_chats:
        logger.info("No uncrystallized chats found")
        return
    
    logger.info(f"Found {len(recent_chats)} uncrystallized chats")
    
    # Reflect on conversations
    insights = reflect_on_conversations(recent_chats, model=model)
    
    if not insights:
        logger.info("No high-value insights detected")
        return
    
    logger.info(f"Detected {len(insights)} high-value insights")
    
    # Create drafts for each insight
    for insight in insights:
        # Find source chat (simplified - in real implementation would match better)
        source_chat = recent_chats[0] if recent_chats else {}
        
        draft_path = auto_crystallize_draft(insight, source_chat)
        if draft_path:
            notify_user(
                f"I noticed something important from our talk earlier. Draft saved.",
                draft_path
            )


def main():
    """Main entry point for metacognition service."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Metacognition Service - AI Insight Detection")
    parser.add_argument("--hours", type=int, default=24, help="Hours to look back")
    parser.add_argument("--model", type=str, default="llama3.1:70b", help="Model for reflection")
    parser.add_argument("--interval", type=int, default=21600, help="Run interval in seconds (default: 6 hours)")
    parser.add_argument("--once", action="store_true", help="Run once and exit (don't loop)")
    
    args = parser.parse_args()
    
    if args.once:
        run_metacog_cycle(hours=args.hours, model=args.model)
    else:
        logger.info(f"Metacognition service running (interval: {args.interval}s)")
        while True:
            try:
                run_metacog_cycle(hours=args.hours, model=args.model)
            except Exception as e:
                logger.error(f"Error in metacognition cycle: {e}")
            
            time.sleep(args.interval)


if __name__ == "__main__":
    main()

