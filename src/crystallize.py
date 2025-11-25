"""
Crystallize Module
------------------
Export chat messages/conversations as perfectly formatted Markdown files
to Obsidian inbox for automatic ingestion. Creates a closed-loop knowledge system.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional


def get_relevance_emoji(score: float) -> str:
    """Return emoji based on relevance score."""
    if score >= 0.7:
        return "🟢"
    elif score >= 0.4:
        return "🟡"
    else:
        return "🔴"


def crystallize_turn(
    user_prompt: str,
    ai_response: str,
    metadata: Dict,
    inbox_path: str = "./knowledge/inbox"
) -> str:
    """
    Export a single chat turn as Markdown to Obsidian inbox.
    
    Args:
        user_prompt: User's question/prompt
        ai_response: AI's response
        metadata: Dict with keys: mode, model, max_relevance, sources, context
        inbox_path: Path to inbox directory
    
    Returns:
        Filepath of created file
    """
    inbox = Path(inbox_path)
    inbox.mkdir(parents=True, exist_ok=True)
    
    # Generate smart filename
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    preview = user_prompt.replace("\n", " ")[:50]
    safe_preview = "".join(c if c.isalnum() or c in (" ", "-", "_") else "_" for c in preview)
    safe_preview = safe_preview.replace(" ", "_").strip("_")
    filename = f"{timestamp}_{safe_preview}_crystallized.md"
    filepath = inbox / filename
    
    # Extract metadata
    mode = metadata.get("mode", "RAG Mode")
    model = metadata.get("model", os.getenv("OLLAMA_CHAT_MODEL", "unknown"))
    relevance = metadata.get("max_relevance", 0.0)
    sources = metadata.get("sources", [])
    context = metadata.get("context", "")
    
    emoji = get_relevance_emoji(relevance)
    
    # Build Obsidian-ready Markdown with frontmatter
    frontmatter = f"""---
date: {datetime.now().isoformat()}
model: {model}
mode: {mode}
relevance: {relevance:.3f}
tags: [crystallized, llm, {mode.lower().replace(" ", "-").replace("☠️", "raw").replace("⚡", "auto").replace("🔍", "rag")}]
prompt: {user_prompt[:200]}
---

# 💎 Crystallized Thought ({mode})

**Model:** `{model}` | **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")} | **Relevance:** {relevance:.3f} {emoji}

## User Prompt

{user_prompt}

## AI Response

{ai_response}

"""
    
    # Add sources section if available
    if sources:
        frontmatter += "## Sources\n\n"
        # Handle both dict sources (with title/obsidian_link) and string sources
        for idx, src in enumerate(sources[:10], 1):  # Limit to top 10
            if isinstance(src, dict):
                title = src.get("title", "Untitled")
                link = src.get("obsidian_link") or src.get("source", "")
                frontmatter += f"{idx}. [[{title}]]"
                if link:
                    frontmatter += f" → {link}"
                frontmatter += "\n"
            else:
                # String source
                frontmatter += f"{idx}. {src}\n"
        frontmatter += "\n"
    
    # Add mode-specific warnings
    if mode == "☠️ Raw Mode" or "Raw Mode" in mode:
        frontmatter += "> ⚠️ **Pure uncensored mode** — no RAG context used.\n\n"
    elif mode == "⚡ Auto-Fallback" or "Auto-Fallback" in mode:
        threshold = metadata.get("rag_threshold", 0.25)
        frontmatter += f"> ⚠️ **RAG skipped** (relevance {relevance:.3f} < threshold {threshold:.2f}) → fell back to pure model.\n\n"
    
    # Optionally include context if available
    if context and mode not in ["☠️ Raw Mode", "⚡ Auto-Fallback"]:
        frontmatter += "## Retrieved Context\n\n"
        frontmatter += f"```\n{context[:1000]}\n```\n\n"  # Limit context preview
    
    # Write file
    filepath.write_text(frontmatter.strip() + "\n", encoding="utf-8")
    
    return str(filepath)


def crystallize_conversation(
    history: List[Dict],
    inbox_path: str = "./knowledge/inbox"
) -> str:
    """
    Export entire conversation as single Markdown file.
    
    Args:
        history: List of chat history entries, each with question/answer/metadata
        inbox_path: Path to inbox directory
    
    Returns:
        Filepath of created file
    """
    inbox = Path(inbox_path)
    inbox.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    filename = f"{timestamp}_conversation_crystallized.md"
    filepath = inbox / filename
    
    # Build conversation Markdown
    content = f"""---
date: {datetime.now().isoformat()}
type: conversation
turns: {len(history)}
tags: [crystallized, conversation, llm]
---

# 💎 Crystallized Conversation

**Turns:** {len(history)} | **Time:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

"""
    
    # Add each turn
    for idx, entry in enumerate(history, 1):
        question = entry.get("question", "")
        answer = entry.get("answer", "")
        mode = entry.get("mode", "RAG Mode")
        model = entry.get("model", "unknown")
        relevance = entry.get("max_relevance", 0.0)
        emoji = get_relevance_emoji(relevance)
        
        content += f"""## Turn {idx}: {mode}

**Model:** `{model}` | **Relevance:** {relevance:.3f} {emoji}

### User

{question}

### Assistant

{answer}

"""
        
        # Add sources if available
        sources = entry.get("sources", [])
        if sources:
            content += "**Sources:**\n"
            for src in sources[:5]:
                if isinstance(src, dict):
                    title = src.get("title", "Untitled")
                    content += f"- [[{title}]]\n"
                else:
                    content += f"- {src}\n"
            content += "\n"
        
        content += "---\n\n"
    
    # Write file
    filepath.write_text(content.strip() + "\n", encoding="utf-8")
    
    return str(filepath)

