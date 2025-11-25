"""
Crystallize Module
------------------
Export chat messages/conversations as perfectly formatted Markdown files
to Obsidian inbox for automatic ingestion. Creates a closed-loop knowledge system.
"""

import os
import re
import requests
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional

# Import config for Obsidian paths
try:
    from scripts.config import config, OLLAMA_API_BASE
except ImportError:
    # Fallback if config not available
    OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://localhost:11434/api")
    config = None


def get_relevance_emoji(score: float) -> str:
    """Return emoji based on relevance score."""
    if score >= 0.7:
        return "🟢"
    elif score >= 0.4:
        return "🟡"
    else:
        return "🔴"


def _get_existing_note_titles(vault_path: Optional[Path] = None) -> List[str]:
    """
    Scan Obsidian vault for existing note titles.
    
    Args:
        vault_path: Path to Obsidian vault (defaults to knowledge/notes/)
    
    Returns:
        List of note titles (filenames without .md extension)
    """
    if vault_path is None:
        if config and hasattr(config, 'ROOT'):
            vault_path = config.ROOT / "knowledge" / "notes"
        else:
            vault_path = Path("./knowledge/notes")
    
    if not vault_path.exists():
        return []
    
    titles = []
    try:
        # Scan for .md files in vault
        for md_file in vault_path.rglob("*.md"):
            # Skip system directories
            if any(exclude in str(md_file) for exclude in [".obsidian", "_templates", "_attachments", "_dashboard"]):
                continue
            # Get title (filename without extension)
            title = md_file.stem
            if title:  # Skip empty filenames
                titles.append(title)
    except Exception as e:
        # Silently fail if vault doesn't exist or can't be scanned
        pass
    
    return titles


def generate_wikilinks(content: str, top_k: int = 15, model: str = "llama3.1:8b") -> List[str]:
    """
    Generate wikilink suggestions using LanceDB vector similarity search.
    
    Args:
        content: Content of the note to link
        top_k: Number of similar chunks to retrieve from vector search
        model: Ollama model to use for final ranking (smaller model for speed)
    
    Returns:
        List of suggested note titles to link (as wikilinks)
    """
    try:
        # Import LanceDB and embedding dependencies
        import lancedb
        from fastembed import TextEmbedding
        from scripts.config import (
            LANCE_DB_PATH,
            OBSIDIAN_CURATED_COLLECTION,
            OBSIDIAN_RAW_COLLECTION,
            OBSIDIAN_EMBED_MODEL
        )
        
        # Connect to LanceDB
        if not LANCE_DB_PATH.exists():
            logger.debug("LanceDB not initialized, skipping wikilink generation")
            return []
        
        db = lancedb.connect(str(LANCE_DB_PATH))
        
        # Try curated collection first, fallback to raw
        table = None
        try:
            table = db.open_table(OBSIDIAN_CURATED_COLLECTION)
        except Exception:
            try:
                table = db.open_table(OBSIDIAN_RAW_COLLECTION)
            except Exception:
                logger.debug("No LanceDB collections found, skipping wikilink generation")
                return []
        
        # Embed the content
        embedder = TextEmbedding(model_name=OBSIDIAN_EMBED_MODEL)
        embedding = list(embedder.embed([content]))[0]
        
        # Query LanceDB for similar chunks
        results = table.search(embedding).limit(top_k).to_pandas()
        
        if results.empty:
            return []
        
        # Filter out soft-deleted chunks (deleted: true)
        # Check both direct column and metadata
        if 'deleted' in results.columns:
            results = results[results['deleted'] != 'true']
        else:
            # Filter by checking metadata if deleted column doesn't exist
            results = results[results.apply(
                lambda row: row.get('deleted', 'false') != 'true' if 'deleted' in row else True,
                axis=1
            )]
        
        if results.empty:
            return []
        
        # Extract unique note titles from results
        candidates = set()
        for _, row in results.iterrows():
            # LanceDB stores metadata as separate columns, so check direct columns first
            title = None
            if 'title' in row and row['title']:
                title = str(row['title'])
            elif 'source' in row and row['source']:
                title = str(row['source'])
            
            if title:
                # Extract filename without extension
                if isinstance(title, str):
                    # Handle both file paths and titles
                    if '/' in title or '\\' in title:
                        # It's a path, extract filename
                        title = Path(title).stem
                    candidates.add(title)
        
        if not candidates:
            return []
        
        # Convert to list and limit for LLM ranking
        candidate_list = list(candidates)[:20]  # Limit to 20 for LLM prompt
        
        # Use LLM to rank and select final 3-7 links
        content_preview = content[:3000]  # Limit content length
        titles_str = "\n".join(f"- {title}" for title in candidate_list)
        
        linking_prompt = f"""From these note titles found via vector similarity search, pick the 3-7 most relevant to link to.
Return ONLY wikilinks like [[Note Title]] separated by commas.
Do not include explanations or other text.

Candidate notes (from similarity search):
{titles_str}

New note content:
{content_preview}

Suggested wikilinks:"""
        
        # Call Ollama API
        api_base = OLLAMA_API_BASE.replace('/api', '') if '/api' in OLLAMA_API_BASE else OLLAMA_API_BASE
        response = requests.post(
            f"{api_base}/api/generate",
            json={
                "model": model,
                "prompt": linking_prompt,
                "stream": False,
                "options": {
                    "num_predict": 200,  # Limit response length
                    "temperature": 0.3  # Lower temperature for more focused suggestions
                }
            },
            timeout=30.0
        )
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get("response", "").strip()
            
            # Extract wikilinks from response
            wikilinks = re.findall(r'\[\[([^\]]+)\]\]', response_text)
            
            # Filter to only include titles from candidates
            valid_links = [link for link in wikilinks if link in candidate_list]
            
            # Limit to 7 links max
            return valid_links[:7]
        
    except ImportError as e:
        logger.debug(f"LanceDB or fastembed not available: {e}")
        return []
    except Exception as e:
        logger.debug(f"Error generating wikilinks: {e}")
        return []
    
    return []


def _generate_conversation_id() -> str:
    """Generate unique conversation ID for tracking."""
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    import random
    random_suffix = random.randint(1000, 9999)
    return f"conv_{timestamp}_{random_suffix}"


# Removed _infer_user_mood() - now using user-provided context from Streamlit sidebar


def _determine_phase_of_life(topics: List[str]) -> str:
    """
    Determine phase of life/work based on conversation topics.
    
    Args:
        topics: List of topic keywords
    
    Returns:
        Phase label: building, reflecting, researching
    """
    topics_str = " ".join(topics).lower()
    
    if any(word in topics_str for word in ["build", "create", "implement", "develop", "code"]):
        return "building"
    elif any(word in topics_str for word in ["research", "study", "learn", "investigate"]):
        return "researching"
    else:
        return "reflecting"


def _extract_conversation_metadata(history: List[Dict], current_entry: Dict) -> Dict:
    """
    Extract temporal and contextual metadata from conversation.
    
    Args:
        history: Full chat history
        current_entry: Current entry being crystallized
    
    Returns:
        Dict with metadata fields
    """
    # Generate conversation ID (use existing if available, otherwise create new)
    conversation_id = current_entry.get("conversation_id")
    if not conversation_id:
        conversation_id = _generate_conversation_id()
    
    # Infer user mood
    conversation_text = f"{current_entry.get('question', '')} {current_entry.get('answer', '')}"
    user_mood = _infer_user_mood(conversation_text)
    
    # Determine AI confidence based on mode and relevance
    mode = current_entry.get("mode", "RAG Mode")
    relevance = current_entry.get("max_relevance", 0.0)
    if relevance >= 0.7:
        ai_confidence = "high"
    elif relevance >= 0.4:
        ai_confidence = "medium"
    else:
        ai_confidence = "speculative"
    
    # Determine phase of life from topics (extract from sources or content)
    sources = current_entry.get("sources", [])
    topics = []
    if sources:
        for src in sources[:5]:
            if isinstance(src, dict):
                title = src.get("title", "")
                if title:
                    topics.append(title)
            else:
                topics.append(str(src)[:50])
    
    phase_of_life = _determine_phase_of_life(topics)
    
    # Determine session context from mode and topics
    session_context = []
    if "obsidian" in conversation_text.lower() or "vault" in conversation_text.lower():
        session_context.append("obsidian-integration")
    if "prompt" in conversation_text.lower() and "rag" in conversation_text.lower():
        session_context.append("prompt-rag")
    if not session_context:
        session_context.append("general")
    
    return {
        "conversation_id": conversation_id,
        "user_mood": user_mood,
        "ai_confidence": ai_confidence,
        "phase_of_life": phase_of_life,
        "session_context": ",".join(session_context)
    }


def crystallize_turn(
    user_prompt: str,
    ai_response: str,
    metadata: Dict,
    inbox_path: str = "./knowledge/inbox",
    conversation_history: Optional[List[Dict]] = None,
    user_focus: Optional[str] = None,
    project_tag: Optional[str] = None
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
    
    # Extract temporal/contextual metadata (use user-provided context if available)
    current_entry = {
        "question": user_prompt,
        "answer": ai_response,
        "mode": mode,
        "max_relevance": relevance,
        "sources": sources,
        "conversation_id": metadata.get("conversation_id")
    }
    
    # Use user-provided context or extract from conversation
    if user_focus:
        user_mood = user_focus.lower()  # Use focus as mood
        phase_of_life = user_focus.lower()
    else:
        temporal_metadata = _extract_conversation_metadata(conversation_history or [], current_entry)
        user_mood = temporal_metadata.get("user_mood", "focused")
        phase_of_life = temporal_metadata.get("phase_of_life", "general")
    
    # Determine session context
    session_context = []
    if project_tag:
        session_context.append(project_tag.lower().replace(" ", "-"))
    if "obsidian" in user_prompt.lower() or "obsidian" in ai_response.lower():
        session_context.append("obsidian-integration")
    if "prompt" in user_prompt.lower() and "rag" in user_prompt.lower():
        session_context.append("prompt-rag")
    if not session_context:
        session_context.append("general")
    
    emoji = get_relevance_emoji(relevance)
    crystallized_at = datetime.now().isoformat()
    
    # Get conversation ID
    conversation_id = metadata.get("conversation_id") or _generate_conversation_id()
    
    # Determine AI confidence
    if relevance >= 0.7:
        ai_confidence = "high"
    elif relevance >= 0.4:
        ai_confidence = "medium"
    else:
        ai_confidence = "speculative"
    
    # Build Obsidian-ready Markdown with rich frontmatter
    frontmatter = f"""---
date: {crystallized_at}
crystallized_at: {crystallized_at}
model: {model}
mode: {mode}
relevance: {relevance:.3f}
conversation_id: {conversation_id}
user_mood: {user_mood}
ai_confidence: {ai_confidence}
phase_of_life: {phase_of_life}
session_context: {",".join(session_context)}
tags: [crystallized, llm, {mode.lower().replace(" ", "-").replace("☠️", "raw").replace("⚡", "auto").replace("🔍", "rag")}, {user_mood}, {phase_of_life}]
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
    
    # Generate and add wikilinks (Connective Tissue feature)
    try:
        # Combine user prompt and AI response for better linking context
        linking_content = f"{user_prompt}\n\n{ai_response}"
        suggested_links = generate_wikilinks(linking_content)
        
        if suggested_links:
            frontmatter += "## Related\n\n"
            for link in suggested_links:
                frontmatter += f"- [[{link}]]\n"
            frontmatter += "\n"
    except Exception as e:
        # Silently fail - linking is optional
        pass
    
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
    
    # Extract conversation-level metadata
    # Use first entry's conversation_id if available, otherwise generate new
    conversation_id = history[0].get("conversation_id") if history else _generate_conversation_id()
    
    # Default to "general" if no user context provided
    # In future, could extract from history entries if they have user_focus
    user_mood = "general"
    phase_of_life = "general"
    
    # Try to infer from conversation content if no explicit context
    all_text = " ".join([f"{h.get('question', '')} {h.get('answer', '')}" for h in history])
    if "research" in all_text.lower():
        phase_of_life = "researching"
    elif "build" in all_text.lower() or "create" in all_text.lower():
        phase_of_life = "building"
    elif "reflect" in all_text.lower() or "think" in all_text.lower():
        phase_of_life = "reflecting"
    
    crystallized_at = datetime.now().isoformat()
    
    # Build conversation Markdown with rich metadata
    content = f"""---
date: {crystallized_at}
crystallized_at: {crystallized_at}
type: conversation
conversation_id: {conversation_id}
turns: {len(history)}
user_mood: {user_mood}
phase_of_life: {phase_of_life}
tags: [crystallized, conversation, llm, {user_mood}, {phase_of_life}]
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

