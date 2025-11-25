import os
import sys
import time
import logging
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import webbrowser

logger = logging.getLogger(__name__)

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import rag_utils
from src.api_client import (
    check_backend_available, get_llm_status, start_lm_studio, stop_lm_studio,
    get_ollama_status, get_ollama_models, list_documents, get_chunks, get_document, update_document_metadata, 
    run_ingestion, ingest_file, get_umap_coords, get_corpus_stats,
    get_graph_nodes, get_graph_edges, get_archived_documents, get_tags, get_files_by_tag
)
from src.crystallize import crystallize_turn, crystallize_conversation
from scripts.chat_logger import ChatLogger
import uuid
from scripts.config import config
import psutil

st.set_page_config(page_title="Powercore RAG Control Panel", layout="wide")

st.title("🔍 Powercore RAG Control Panel")
st.caption("Local RAG pipeline with Ollama integration")

# Check backend availability
backend_available = check_backend_available()
if not backend_available:
    st.warning("⚠️ FastAPI backend is not running. Start it with: `python -m backend.app` or `scripts/run_backend.bat`")

# Create tabs
tabs = st.tabs(["Dashboard", "Chat", "Library", "Ingest", "Visualize", "Graph", "Prompts"])

# Dashboard Tab
with tabs[0]:
    st.header("Dashboard")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Backend Status", "✅ Running" if backend_available else "❌ Offline")
    
    with col2:
        if backend_available:
            ollama_status = get_ollama_status()
            st.metric("Ollama", "✅ Ready" if ollama_status.get("available") else "❌ Not Ready")
        else:
            st.metric("Ollama", "N/A")
    
    with col3:
        if backend_available:
            stats = get_corpus_stats()
            if "error" not in stats:
                st.metric("Total Chunks", stats.get("total_chunks", "N/A"))
            else:
                st.metric("Total Chunks", "N/A")
        else:
            st.metric("Total Chunks", "N/A")
    
    st.markdown("---")
    
    # Ollama Status
    st.subheader("Ollama Status")
    if backend_available:
        ollama_status = get_ollama_status()
        if ollama_status.get("available"):
            st.success("✅ Ollama is running and ready")
            if ollama_status.get("loaded_models"):
                st.write("**Loaded models:**")
                for model in ollama_status.get("loaded_models", []):
                    st.write(f"- {model}")
            st.write(f"**Embed model:** {ollama_status.get('embed_model', 'N/A')}")
            st.write(f"**Chat model:** {ollama_status.get('chat_model', 'N/A')}")
        else:
            st.error(f"❌ Ollama is not available: {ollama_status.get('error', 'Unknown error')}")
            st.info("💡 Make sure Ollama is running: `ollama serve`")
        st.json(ollama_status)
    else:
        st.warning("Backend not available")

# Chat Tab (existing functionality)
with tabs[1]:
    st.header("Chat")
    st.caption("Query your local knowledge base. Make sure Ollama is running: `ollama serve`")
    
    # Initialize chat history and ChatLogger
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    # Initialize session ID and conversation ID
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    
    if "conversation_id" not in st.session_state:
        st.session_state.conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
    
    # Initialize ChatLogger
    if "chat_logger" not in st.session_state:
        try:
            st.session_state.chat_logger = ChatLogger()
        except Exception as e:
            logger.warning(f"Failed to initialize ChatLogger: {e}")
            st.session_state.chat_logger = None
    
    # Crystallize entire conversation button
    if st.session_state.chat_history:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💎 Crystallize Entire Conversation", type="primary", use_container_width=True):
                try:
                    filepath = crystallize_conversation(st.session_state.chat_history)
                    
                    # Mark all messages in conversation as crystallized
                    if st.session_state.chat_logger:
                        for entry in st.session_state.chat_history:
                            if entry.get("ai_log_id"):
                                try:
                                    st.session_state.chat_logger.mark_crystallized(
                                        entry["ai_log_id"],
                                        filepath
                                    )
                                except Exception as e:
                                    logger.warning(f"Failed to mark message as crystallized: {e}")
                    
                    st.success(f"✅ Conversation crystallized → `{filepath}`\n\nReady for Obsidian ingestion!")
                except Exception as e:
                    st.error(f"Failed to crystallize conversation: {e}")
        st.markdown("---")
    
    # Mode selector and controls
    col1, col2, col3 = st.columns([1, 3, 2])
    with col1:
        raw_mode = st.checkbox("☠️ Uncensored Raw Mode", value=False, 
                              help="Bypass RAG entirely — pure uncensored model chat (like LM Studio)")
    with col2:
        if not raw_mode:
            rag_threshold = st.slider("RAG relevance threshold", 0.0, 1.0, 0.25, 0.05,
                                     help="Lower = more aggressive RAG, 0.0 = always use RAG")
        else:
            rag_threshold = 0.0  # Ignored in raw mode
            st.caption("Raw mode: RAG threshold disabled")
    with col3:
        try:
            available_models = get_ollama_models()
            # Find current model index or default to 0
            current_model = config.OLLAMA_CHAT_MODEL
            model_index = 0
            if current_model in available_models:
                model_index = available_models.index(current_model)
            selected_model = st.selectbox("Model", available_models, index=model_index,
                                         help="Select Ollama model for chat")
        except Exception as e:
            selected_model = config.OLLAMA_CHAT_MODEL
            st.caption(f"Using default: {selected_model}")
    
    with st.sidebar:
        st.header("Session Context")
        current_focus = st.selectbox(
            "Current Focus",
            ["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"],
            index=0,
            help="What are you working on right now?"
        )
        project_tag = st.text_input(
            "Project Tag",
            value=st.session_state.get("project_tag", ""),
            placeholder="e.g. metacog-v2, obsidian-integration",
            help="Tag for this project/session"
        )
        # Store in session state
        st.session_state.current_focus = current_focus
        st.session_state.project_tag = project_tag
        
        st.markdown("---")
        st.header("Settings")
        top_k = st.slider("Top-K context chunks", min_value=1, max_value=10, value=rag_utils.DEFAULT_K)
        show_context = st.checkbox("Show retrieved context", value=False)
        st.markdown("**Chat model:**")
        st.code(selected_model, language="bash")
        st.markdown("**Embedding model:**")
        st.code(config.OLLAMA_EMBED_MODEL, language="bash")
        st.markdown("**Ollama API:**")
        st.code(config.OLLAMA_API_BASE, language="bash")
    
    question = st.chat_input("Ask a question about your documents...")
    
    if question:
        with st.spinner("Thinking..."):
            try:
                # Call updated answer_question with new parameters
                result = rag_utils.answer_question(
                    question, 
                    k=top_k,
                    raw_mode=raw_mode,
                    rag_threshold=rag_threshold,
                    model=selected_model
                )
                
                # Extract response components
                answer = result["response"]
                mode = result["mode"]
                max_relevance = result["max_relevance"]
                model_used = result["model"]
                sources_list = result.get("sources", [])
                context = result.get("context", "")
                
                # Format sources
                if sources_list:
                    sources = rag_utils.format_sources(sources_list)
                else:
                    sources = []
                
                # Log user question to ChatLogger
                if st.session_state.chat_logger:
                    try:
                        user_log_id = st.session_state.chat_logger.log_message(
                            session_id=st.session_state.session_id,
                            role="user",
                            content=question,
                            conversation_id=st.session_state.conversation_id
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log user message: {e}")
                        user_log_id = None
                else:
                    user_log_id = None
                
                # Log AI response to ChatLogger
                if st.session_state.chat_logger:
                    try:
                        ai_log_id = st.session_state.chat_logger.log_message(
                            session_id=st.session_state.session_id,
                            role="assistant",
                            content=answer,
                            mode=mode,
                            model=model_used,
                            max_relevance=max_relevance,
                            sources=sources_list,  # Store raw sources list
                            conversation_id=st.session_state.conversation_id
                        )
                    except Exception as e:
                        logger.warning(f"Failed to log AI message: {e}")
                        ai_log_id = None
                else:
                    ai_log_id = None
                
                # Store in chat history with metadata and log IDs
                st.session_state.chat_history.append({
                    "question": question,
                    "answer": answer,
                    "sources": sources,
                    "context": context,
                    "mode": mode,
                    "max_relevance": max_relevance,
                    "model": model_used,
                    "rag_threshold": rag_threshold,
                    "conversation_id": st.session_state.conversation_id,
                    "user_log_id": user_log_id,
                    "ai_log_id": ai_log_id
                })
                
                # Show warning if RAG was skipped
                if mode == "⚡ Auto-Fallback":
                    st.warning(f"⚠️ No relevant docs (max relevance {max_relevance:.3f} < threshold {rag_threshold:.2f}) → pure model mode")
                
            except Exception as e:
                error_msg = str(e)
                if "dimension" in error_msg.lower():
                    st.error(f"Embedding dimension mismatch: {error_msg}\n\n**Solution:** The ChromaDB collection was created with a different embedding model. Please delete the collection and re-ingest your documents, or ensure you're using the same embedding model for queries as was used during ingestion.")
                else:
                    st.error(f"Error answering question: {error_msg}")
                logger.error(f"Error in answer_question: {e}", exc_info=True)
    
    # Display chat history with badges and crystallize buttons
    for idx, entry in enumerate(reversed(st.session_state.chat_history)):
        # User message
        with st.chat_message("user"):
            st.markdown(entry['question'])
        
        # Assistant message
        with st.chat_message("assistant"):
            st.markdown(entry['answer'])
            
            # Mode badge and metadata
            mode = entry.get("mode", "🔍 RAG Mode")
            max_relevance = entry.get("max_relevance", 0.0)
            model_used = entry.get("model", "unknown")
            
            # Relevance emoji
            if max_relevance >= 0.7:
                rel_emoji = "🟢"
            elif max_relevance >= 0.4:
                rel_emoji = "🟡"
            else:
                rel_emoji = "🔴"
            
            st.caption(f"**{mode}** | Relevance: {max_relevance:.3f} {rel_emoji} | Model: `{model_used}`")
            
            # Show warning for auto-fallback
            if mode == "⚡ Auto-Fallback":
                threshold = entry.get("rag_threshold", 0.25)
                st.info(f"⚠️ RAG skipped (relevance {max_relevance:.3f} < threshold {threshold:.2f})")
            
            # Sources
            if entry.get("sources"):
                with st.expander("Sources"):
                    for src in entry["sources"]:
                        st.markdown(f"- {src}")
            
            # Context (if enabled)
            if show_context and entry.get("context"):
                with st.expander("Retrieved context"):
                    st.text(entry["context"])
            
            # Crystallize button for this turn
            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("💎 Crystallize", key=f"cryst_{len(st.session_state.chat_history) - idx - 1}", 
                            help="Export this turn as Markdown to Obsidian inbox"):
                    try:
                        metadata = {
                            "mode": mode,
                            "model": model_used,
                            "max_relevance": max_relevance,
                            "sources": entry.get("sources", []),
                            "context": entry.get("context", ""),
                            "rag_threshold": entry.get("rag_threshold", 0.25),
                            "conversation_id": entry.get("conversation_id", st.session_state.conversation_id)
                        }
                        
                        # Get user context from session state
                        user_focus = st.session_state.get("current_focus", "General")
                        project_tag = st.session_state.get("project_tag", "")
                        
                        filepath = crystallize_turn(
                            entry['question'], 
                            entry['answer'], 
                            metadata,
                            conversation_history=st.session_state.chat_history,
                            user_focus=user_focus,
                            project_tag=project_tag
                        )
                        
                        # Mark message as crystallized in ChatLogger
                        if st.session_state.chat_logger and entry.get("ai_log_id"):
                            try:
                                st.session_state.chat_logger.mark_crystallized(
                                    entry["ai_log_id"],
                                    filepath
                                )
                            except Exception as e:
                                logger.warning(f"Failed to mark message as crystallized: {e}")
                        
                        st.success(f"✅ Crystallized → `{filepath.split('/')[-1]}`\n\nReady for Obsidian ingestion!")
                    except Exception as e:
                        st.error(f"Failed to crystallize: {e}")
        
        st.markdown("---")

# Library Tab
with tabs[2]:
    st.header("Library")
    
    if backend_available:
        # View switcher
        view_mode = st.radio(
            "View Mode",
            ["Chunks View", "Archive View"],
            horizontal=True,
            key="library_view_mode"
        )
        
        if st.button("Refresh Library"):
            st.session_state.library_chunks_data = None
            st.session_state.library_archive_data = None
            st.session_state.library_tags_data = None
        
        if view_mode == "Chunks View":
            # Existing chunks view
            if "library_chunks_data" not in st.session_state:
                try:
                    st.session_state.library_chunks_data = get_chunks(limit=1000)
                except Exception as e:
                    logger.error(f"Error loading library chunks: {e}", exc_info=True)
                    st.session_state.library_chunks_data = {
                        "chunks": [],
                        "total": 0,
                        "sources": 0,
                        "error": f"Failed to load library data: {str(e)}"
                    }
            
            data = st.session_state.library_chunks_data
            
            # Ensure data is not None before checking for errors
            if data is None:
                data = {"chunks": [], "total": 0, "sources": 0, "error": "Failed to load library data"}
                st.session_state.library_chunks_data = data
            
            if "error" in data:
                error_msg = data['error']
                st.error(f"Error loading library: {error_msg}")
                
                # Provide helpful guidance for dimension mismatch
                if "dimension" in error_msg.lower() or "Collection" in error_msg:
                    st.info("💡 **Tip:** If you see dimension mismatch errors, you may need to delete the ChromaDB collection and re-ingest your documents. The collection path is in the error message above.")
            else:
                total_chunks = data.get("total", 0)
                sources = data.get("sources", 0)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Chunks", total_chunks)
                with col2:
                    st.metric("Source Documents", sources)
                
                if total_chunks == 0:
                    st.info("No chunks found. Ingest some documents first!")
                else:
                    # Group chunks by source for display
                    chunks_by_source = {}
                    for chunk in data.get("chunks", []):
                        source = chunk.get("source", "unknown")
                        if source not in chunks_by_source:
                            chunks_by_source[source] = []
                        chunks_by_source[source].append(chunk)
                    
                    # Display chunks grouped by source
                    for source, chunks in chunks_by_source.items():
                        filename = source.split("/")[-1] if "/" in source else source
                        with st.expander(f"📄 {filename} ({len(chunks)} chunks)"):
                            for chunk in chunks:
                                chunk_idx = chunk.get("chunk_index", 0)
                                text_preview = chunk.get("text_preview", "")
                                text_length = chunk.get("text_length", 0)
                                
                                st.markdown(f"**Chunk {chunk_idx}** ({text_length} chars)")
                                st.code(text_preview, language="markdown")
                                st.markdown("---")
        
        else:  # Archive View
            # Archive view with AI summaries and tags
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("Search archived files", key="archive_search", placeholder="Enter filename...")
            with col2:
                page_size = st.selectbox("Files per page", [10, 20, 50], index=1, key="archive_page_size")
            
            # Initialize session state
            if "library_archive_page" not in st.session_state:
                st.session_state.library_archive_page = 1
            
            # Get archived documents
            archive_data = get_archived_documents(
                page=st.session_state.library_archive_page,
                search=search_term if search_term else None,
                limit=page_size
            )
            
            if "error" in archive_data:
                st.error(f"Error loading archive: {archive_data['error']}")
            else:
                total_files = archive_data.get("total", 0)
                files = archive_data.get("files", [])
                pages = archive_data.get("pages", 1)
                
                st.metric("Archived Files", total_files)
                
                if total_files == 0:
                    st.info("No archived files found. Ingest some documents first!")
                else:
                    # Pagination controls
                    if pages > 1:
                        col1, col2, col3 = st.columns([1, 2, 1])
                        with col1:
                            if st.button("◀ Previous", disabled=st.session_state.library_archive_page <= 1):
                                st.session_state.library_archive_page -= 1
                                st.rerun()
                        with col2:
                            st.write(f"Page {st.session_state.library_archive_page} of {pages}")
                        with col3:
                            if st.button("Next ▶", disabled=st.session_state.library_archive_page >= pages):
                                st.session_state.library_archive_page += 1
                                st.rerun()
                    
                    # Display files
                    for file_info in files:
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"### 📄 {file_info['name']}")
                                
                                # File metadata
                                file_size_kb = file_info['size'] / 1024
                                modified_date = file_info.get('modified', '')[:10] if file_info.get('modified') else 'Unknown'
                                st.caption(f"Size: {file_size_kb:.1f} KB | Modified: {modified_date}")
                                
                                # AI Summary badge
                                if file_info.get('ai_summary'):
                                    st.info(f"**Summary:** {file_info['ai_summary']}")
                                
                                # AI Tags as chips
                                if file_info.get('ai_tags'):
                                    tag_cols = st.columns(min(len(file_info['ai_tags']), 5))
                                    for idx, tag in enumerate(file_info['ai_tags'][:5]):
                                        with tag_cols[idx % 5]:
                                            st.chip(tag)
                                
                                # Preview
                                if file_info.get('preview'):
                                    with st.expander("Preview"):
                                        st.code(file_info['preview'], language="markdown")
                            
                            with col2:
                                file_path = file_info['path']
                                
                                # Open in Cursor button
                                if st.button("📝 Open in Cursor", key=f"open_{file_info['name']}"):
                                    import webbrowser
                                    import os
                                    # Use cursor:// protocol or file://
                                    cursor_url = f"cursor://file/{os.path.abspath(file_path)}"
                                    try:
                                        webbrowser.open(cursor_url)
                                        st.success("Opening in Cursor...")
                                    except Exception as e:
                                        # Fallback: open file location
                                        webbrowser.open(f"file://{os.path.dirname(os.path.abspath(file_path))}")
                                        st.info(f"Opened file location. Error: {e}")
                                
                                # Re-ingest button
                                if st.button("🔄 Re-ingest", key=f"reingest_{file_info['name']}"):
                                    with st.spinner("Re-ingesting..."):
                                        result = ingest_file(file_path)
                                        if result.get("success"):
                                            st.success("Re-ingested successfully!")
                                            # Clear graph cache to trigger refresh
                                            if "graph_data" in st.session_state:
                                                st.session_state.graph_data = None
                                        else:
                                            st.error(f"Re-ingest failed: {result.get('message', 'Unknown error')}")
                            
                            st.divider()
    else:
        st.warning("Backend not available. Start the FastAPI backend to use the Library.")

# Ingest Tab
with tabs[3]:
    st.header("Ingest")
    
    if backend_available:
        st.subheader("Single File Ingestion (Ollama)")
        
        # Helper function to trigger ingestion with progress tracking
        def trigger_ingest(file_path: Path):
            """Trigger ingestion with progress feedback."""
            if "ingest_status" in st.session_state and st.session_state.ingest_status.get("stage") in ["loading", "embedding", "unloading"]:
                st.warning("Another ingestion in progress. Please wait.")
                return
            
            # Initialize status tracking
            st.session_state.ingest_status = {
                "stage": "loading",
                "model": config.OLLAMA_EMBED_MODEL,
                "file": file_path.name,
                "ram_before": psutil.Process().memory_info().rss
            }
            
            try:
                # Trigger ingestion via API
                result = ingest_file(str(file_path.resolve()))
                
                if result.get("success"):
                    # Get RAM after ingestion
                    ram_after = psutil.Process().memory_info().rss
                    ram_freed = st.session_state.ingest_status["ram_before"] - ram_after
                    
                    st.session_state.ingest_status = {
                        "stage": "done",
                        "file": file_path.name,
                        "ram_before": st.session_state.ingest_status["ram_before"],
                        "ram_after": ram_after,
                        "ram_freed": ram_freed
                    }
                    
                    # Clear graph cache to trigger refresh
                    if "graph_data" in st.session_state:
                        st.session_state.graph_data = None
                else:
                    st.session_state.ingest_status = {
                        "stage": "error",
                        "error": result.get("message", "Unknown error"),
                        "file": file_path.name
                    }
            except Exception as e:
                st.session_state.ingest_status = {
                    "stage": "error",
                    "error": str(e),
                    "file": file_path.name
                }
        
        # --- Native File Picker (Drag & Drop or Click) ---
        uploaded_file = st.file_uploader(
            "Select .md file to ingest",
            type=["md"],
            help="Click to browse or drag & drop a Markdown file from anywhere on your PC",
            label_visibility="visible"
        )
        
        # --- Handle uploaded file ---
        if uploaded_file is not None:
            inbox_path = Path(config.INBOX)
            inbox_path.mkdir(parents=True, exist_ok=True)
            
            save_path = inbox_path / uploaded_file.name
            
            # Handle duplicate filenames
            counter = 1
            while save_path.exists():
                name_parts = uploaded_file.name.rsplit(".", 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    new_name = f"{uploaded_file.name}_{counter}"
                save_path = inbox_path / new_name
                counter += 1
            
            # Save file to inbox
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ Saved: `{save_path.name}` → inbox/")
            
            # Show preview
            with st.expander(f"📄 Preview: {save_path.name}", expanded=True):
                try:
                    content = uploaded_file.getvalue().decode("utf-8", errors="ignore")
                    preview_length = 1500
                    if len(content) > preview_length:
                        st.code(content[:preview_length] + "\n\n... [truncated]", language="markdown")
                    else:
                        st.code(content, language="markdown")
                except Exception as e:
                    st.error(f"Could not preview file: {e}")
            
            # Show file metadata
            file_size = save_path.stat().st_size
            size_str = f"{file_size/1024:.1f} KB" if file_size < 1024*1024 else f"{file_size/(1024*1024):.1f} MB"
            st.caption(f"Size: {size_str} • Last modified: {time.strftime('%m/%d/%Y %I:%M %p', time.localtime(save_path.stat().st_mtime))}")
            
            # Ingest button
            if st.button(f"🚀 Ingest `{save_path.name}` Now", type="primary", use_container_width=True):
                trigger_ingest(save_path)
                st.rerun()
        
        st.markdown("---")
        
        # --- Browse Existing Files in Inbox ---
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown("#### Browse Existing Files in inbox/")
        with col2:
            if st.button("🔄 Refresh inbox", use_container_width=True):
                st.rerun()
        
        inbox_path = Path(config.INBOX)
        inbox_files = sorted(
            inbox_path.glob("*.md"),
            key=lambda x: x.stat().st_mtime,
            reverse=True
        ) if inbox_path.exists() else []
        
        if inbox_files:
            with st.expander(f"Found {len(inbox_files)} file(s) in inbox/", expanded=False):
                for file in inbox_files:
                    col1, col2, col3 = st.columns([4, 2, 1])
                    with col1:
                        st.markdown(f"**{file.name}**")
                    with col2:
                        size = file.stat().st_size
                        size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                        st.caption(f"{size_str} • {time.strftime('%m/%d %I:%M %p', time.localtime(file.stat().st_mtime))}")
                    with col3:
                        if st.button("Ingest", key=f"ingest_{file.name}", use_container_width=True):
                            result = trigger_ingest(file)
                            # Clear graph cache to trigger refresh
                            if "graph_data" in st.session_state:
                                st.session_state.graph_data = None
                            st.rerun()
        else:
            st.info("No .md files found in inbox/. Upload a file above or add files to the inbox directory.")
        
        st.markdown("---")
        
        # --- Progress Status Display ---
        if "ingest_status" in st.session_state:
            status = st.session_state.ingest_status
            
            if status["stage"] == "loading":
                st.warning(f"⏳ Loading model: `{status['model']}`...")
            elif status["stage"] == "embedding":
                st.info(f"🔄 Embedding chunks...")
            elif status["stage"] == "unloading":
                st.info("💾 Unloading model...")
            elif status["stage"] == "done":
                ram_freed = status.get("ram_freed", 0)
                ram_freed_mb = ram_freed / (1024 * 1024)
                st.success(f"✅ Ingested `{status['file']}`! Model unloaded. Freed ~{ram_freed_mb:.1f} MB RAM.")
                if st.button("Clear status", key="clear_status"):
                    del st.session_state.ingest_status
                    st.rerun()
            elif status["stage"] == "error":
                st.error(f"❌ Failed to ingest `{status.get('file', 'file')}`: {status.get('error', 'Unknown error')}")
                if st.button("Clear error", key="clear_error"):
                    del st.session_state.ingest_status
                    st.rerun()
        
        st.markdown("---")
        
        # --- Manual Path Input (Fallback) ---
        st.markdown("#### Manual File Path (Fallback)")
        file_path = st.text_input("File path to ingest (.md)", str(Path("knowledge/inbox").resolve() / "test.md"))
        
        if st.button("Embed Now (Load → Embed → Unload)", type="secondary"):
            if file_path:
                file_obj = Path(file_path)
                if file_obj.exists() and file_obj.suffix.lower() == ".md":
                    result = trigger_ingest(file_obj)
                    # Clear graph cache to trigger refresh
                    if "graph_data" in st.session_state:
                        st.session_state.graph_data = None
                    if result:
                        st.success("Ingestion complete! Graph will refresh automatically.")
                    st.rerun()
                else:
                    st.error("File does not exist or is not a .md file")
            else:
                st.error("Please provide a file path")
        
        st.markdown("---")
        
        st.subheader("Batch Folder Ingestion")
        folder = st.text_input("Folder to ingest", str(Path("knowledge/inbox").resolve()))
        fast = st.checkbox("Fast PDF mode", value=True)
        parallel = st.checkbox("Parallel processing", value=True)
        
        if st.button("Run Batch Ingestion"):
            log_placeholder = st.empty()
            log_text = ""
            
            for line in run_ingestion(folder, fast=fast, parallel=parallel):
                log_text += line + "\n"
                log_placeholder.text_area("Ingestion Logs", log_text, height=400)
            
            st.success("Ingestion complete!")
    else:
        st.warning("Backend not available. Start the FastAPI backend to use Ingestion.")

# Visualize Tab
with tabs[4]:
    st.header("Visualize")
    
    if backend_available:
        n_samples = st.slider("Number of samples", min_value=50, max_value=2000, value=500)
        
        if st.button("Generate UMAP Visualization"):
            with st.spinner("Computing UMAP coordinates..."):
                result = get_umap_coords(n=n_samples)
                
                # Ensure result is not None before checking for errors
                if result is None:
                    result = {"coords": [], "error": "Failed to compute UMAP coordinates"}
                
                if "error" in result:
                    st.error(f"Error: {result['error']}")
                else:
                    coords = result.get("coords", [])
                    if coords:
                        import pandas as pd
                        import plotly.express as px
                        
                        df = pd.DataFrame([
                            {"x": c["x"], "y": c["y"], "source": c.get("meta", {}).get("source", "unknown")}
                            for c in coords
                        ])
                        
                        fig = px.scatter(
                            df, x="x", y="y",
                            hover_data=["source"],
                            title="UMAP Visualization of Document Embeddings"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No coordinates returned")
    else:
        st.warning("Backend not available. Start the FastAPI backend to use Visualizations.")

# Graph Tab
with tabs[5]:
    st.header("Knowledge Graph")
    
    if backend_available:
        # Show last refresh time
        if "graph_last_refresh" not in st.session_state:
            st.session_state.graph_last_refresh = "Never"
        st.caption(f"Last refresh: {st.session_state.graph_last_refresh}")
        
        # Helper function to open file in Cursor
        def open_in_cursor(path: str):
            """Open file in Cursor IDE."""
            try:
                # Use the existing FastAPI endpoint
                import requests
                response = requests.post(
                    f"http://127.0.0.1:8000/open/cursor",
                    params={"path": path},
                    timeout=5
                )
                return response.json().get("success", False)
            except:
                # Fallback: try webbrowser
                try:
                    url = f"cursor://file/{os.path.abspath(path)}"
                    webbrowser.open(url)
                    return True
                except:
                    return False
        
        if "graph_data" not in st.session_state:
            st.session_state.graph_data = None
        
        col1, col2 = st.columns([1, 3])
        
        with col1:
            st.markdown("### Filters")
            
            # Get available tags from nodes
            all_tags = set()
            try:
                nodes_data = get_graph_nodes()
                for node in nodes_data.get("nodes", []):
                    if "tags" in node.get("metadata", {}):
                        tags_list = node["metadata"]["tags"]
                        if isinstance(tags_list, list):
                            all_tags.update(tags_list)
            except:
                pass
            
            tags = st.multiselect("Filter by Tags", sorted(all_tags))
            min_quality = st.slider("Min Quality", 0.0, 1.0, 0.5, 0.05)
            threshold = st.slider("Similarity Threshold", 0.5, 1.0, 0.75, 0.01)
            
            col_refresh, col_force = st.columns(2)
            with col_refresh:
                if st.button("🔄 Refresh Graph"):
                    st.session_state.graph_data = None
                    st.session_state.graph_last_refresh = time.strftime("%H:%M:%S")
                    st.rerun()
            with col_force:
                if st.button("⚡ Force Refresh", help="Clear cache and rebuild graph"):
                    st.session_state.graph_data = None
                    st.session_state.graph_last_refresh = None
                    st.session_state.graph_last_refresh = time.strftime("%H:%M:%S")
                    st.rerun()
        
        with col2:
            if st.session_state.graph_data is None:
                with st.spinner("Building graph..."):
                    try:
                        nodes_data = get_graph_nodes(tags=tags, min_quality=min_quality)
                        edges_data = get_graph_edges(threshold=threshold)
                        
                        # Ensure data is not None before checking for errors
                        if nodes_data is None:
                            nodes_data = {"nodes": [], "error": "Failed to load graph nodes"}
                        if edges_data is None:
                            edges_data = {"edges": [], "error": "Failed to load graph edges"}
                        
                        if "error" in nodes_data or "error" in edges_data:
                            st.error(f"Error loading graph: {nodes_data.get('error') or edges_data.get('error')}")
                        else:
                            st.session_state.graph_data = (
                                nodes_data.get("nodes", []),
                                edges_data.get("edges", [])
                            )
                    except Exception as e:
                        st.error(f"Error building graph: {e}")
                        st.session_state.graph_data = ([], [])
            
            nodes, edges = st.session_state.graph_data if st.session_state.graph_data else ([], [])
            
            if not nodes:
                st.info("No nodes found. Ingest some documents first to see the graph.")
            else:
                try:
                    from pyvis.network import Network
                    
                    net = Network(
                        height="700px",
                        width="100%",
                        bgcolor="#1e1e1e",
                        font_color="white",
                        select_menu=True,
                        filter_menu=True
                    )
                    
                    net.barnes_hut(
                        gravity=-8000,
                        central_gravity=0.3,
                        spring_length=200,
                        spring_strength=0.05,
                        damping=0.9
                    )
                    
                    # Add nodes
                    for node in nodes:
                        if node["type"] == "document":
                            color = "#00ff41"
                            size = 25
                            shape = "box"
                            
                            # Build enriched tooltip for document nodes
                            metadata = node.get("metadata", {})
                            tooltip_parts = [node["label"]]
                            if metadata.get("summary"):
                                tooltip_parts.append(f"\nSummary: {metadata['summary']}")
                            if metadata.get("tags"):
                                tags_str = ", ".join(metadata["tags"][:3]) if isinstance(metadata["tags"], list) else str(metadata["tags"])
                                tooltip_parts.append(f"\nTags: {tags_str}")
                            if metadata.get("quality_score"):
                                tooltip_parts.append(f"\nQuality: {metadata['quality_score']}/10")
                            title = "\n".join(tooltip_parts)
                        else:  # chunk
                            color = "#00aaff"
                            size = 15
                            shape = "dot"
                            
                            # Build enriched tooltip for chunk nodes
                            metadata = node.get("metadata", {})
                            tooltip_parts = [f"Chunk {metadata.get('chunk_index', 0)}"]
                            if metadata.get("text"):
                                text_preview = metadata["text"][:150] + "..." if len(metadata["text"]) > 150 else metadata["text"]
                                tooltip_parts.append(f"\n{text_preview}")
                            if metadata.get("tags"):
                                tags_str = ", ".join(metadata["tags"][:3]) if isinstance(metadata["tags"], list) else str(metadata["tags"])
                                tooltip_parts.append(f"\nTags: {tags_str}")
                            title = "\n".join(tooltip_parts)
                        
                        net.add_node(
                            node["id"],
                            label=node["label"],
                            title=title,
                            color=color,
                            size=size,
                            shape=shape
                        )
                    
                    # Add edges
                    for edge in edges:
                        net.add_edge(
                            edge["source"],
                            edge["target"],
                            value=edge["weight"] * 10,
                            title=edge["label"],
                            color="#888888"
                        )
                    
                    # Generate HTML
                    net.show("rag_graph.html")
                    
                    # Read and display HTML
                    with open("rag_graph.html", "r", encoding="utf-8") as f:
                        html = f.read()
                    
                    components.html(html, height=700, scrolling=True)
                    
                    # Open in Cursor button
                    st.markdown("---")
                    if st.button("📝 Open Selected in Cursor"):
                        # Note: Pyvis selection requires JavaScript interaction
                        # For now, we'll use a text input to select a node
                        st.info("💡 Click on a node in the graph, then use the node ID below to open it.")
                        
                        node_id = st.text_input("Node ID (from graph)", "")
                        if node_id:
                            # Find the node
                            selected_node = next((n for n in nodes if n["id"] == node_id), None)
                            if selected_node:
                                source_path = selected_node["metadata"].get("source")
                                if source_path and os.path.exists(source_path):
                                    if open_in_cursor(source_path):
                                        st.success(f"✅ Opened: {source_path}")
                                    else:
                                        st.error("Failed to open in Cursor")
                                else:
                                    st.error(f"File not found: {source_path}")
                            else:
                                st.error("Node not found")
                
                except ImportError:
                    st.error("Pyvis not installed. Run: pip install pyvis==0.3.2")
                except Exception as e:
                    st.error(f"Error rendering graph: {e}")
                    st.exception(e)
    else:
        st.warning("Backend not available. Start the FastAPI backend to use the Graph view.")

# Prompts Tab
with tabs[6]:
    st.header("Prompt Repository")
    st.info("Prompt repository functionality coming soon. Use the FastAPI backend directly for now.")

