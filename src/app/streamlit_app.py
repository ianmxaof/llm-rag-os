import os
import sys
import time
import logging
import shutil
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
import streamlit.components.v1 as components
import webbrowser
import requests

logger = logging.getLogger(__name__)

# API base URL for backend requests
API_BASE = "http://127.0.0.1:8000"

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import rag_utils
from src.api_client import (
    check_backend_available, get_llm_status, start_lm_studio, stop_lm_studio,
    get_ollama_status, get_ollama_models, list_documents, get_chunks, get_document, update_document_metadata, 
    run_ingestion, ingest_file, get_umap_coords, get_corpus_stats,
    get_graph_nodes, get_graph_edges, get_archived_documents, get_tags, get_files_by_tag,
    get_ingestion_status
)
from src.crystallize import crystallize_turn, crystallize_conversation
from scripts.chat_logger import ChatLogger
from scripts.config import config
import psutil

# Remove Streamlit timeout limits for long-running ingestion tasks
os.environ.setdefault("STREAMLIT_SERVER_MAX_REQUEST_SIZE", "0")
os.environ.setdefault("STREAMLIT_SERVER_MAX_MESSAGE_SIZE", "0")

# Page config - Phase 1: Single-page layout
st.set_page_config(
    page_title="Powercore Mind",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# === THIS LINE IS MAGIC — DO NOT DELETE === 
# Forces Streamlit to enable native sidebar even if we hide everything
_ = st.sidebar  # This single line activates the native sidebar system

# === HIDDEN JS ENGINE — DO NOT DELETE ===
# All JavaScript moved here to prevent visible debug blocks
components.html("""
<script>
(function() {
    // Copy to clipboard function (used by message actions)
    window.copyToClipboard = function(text) {
        navigator.clipboard.writeText(text).then(function() {
            // Silent copy
        }).catch(function(err) {
            console.error('Failed to copy: ', err);
        });
    };
    
    // Crystallize and canvas handlers (use URL params)
    window.triggerCrystallize = function(idx) {
        const url = new URL(window.location);
        url.searchParams.set('crystallize', idx);
        window.location.href = url.toString();
    };
    
    window.triggerCanvas = function(idx) {
        const url = new URL(window.location);
        url.searchParams.set('canvas', idx);
        window.location.href = url.toString();
    };
    
    // Keyboard shortcuts
    document.addEventListener('keydown', function(e) {
        // Cmd+K or Ctrl+K to focus input
        if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
            e.preventDefault();
            const inputs = document.querySelectorAll('input[type="text"], textarea');
            if (inputs.length > 0) {
                inputs[inputs.length - 1].focus();
            }
        }
        
        // Esc to clear input
        if (e.key === 'Escape') {
            const inputs = document.querySelectorAll('input[type="text"], textarea');
            inputs.forEach(input => {
                if (input.value) {
                    input.value = '';
                }
            });
        }
        
        // Cmd+/ or Ctrl+/ to show shortcuts
        if ((e.metaKey || e.ctrlKey) && e.key === '/') {
            e.preventDefault();
            alert('Keyboard Shortcuts:\\n\\nCmd/Ctrl+K: Focus input\\nEsc: Clear input\\nCmd/Ctrl+/: Show this help');
        }
    });
})();
</script>
""", height=0, width=0)

# Phase 6 & 7: Custom CSS for header, messages, and mobile responsiveness
st.markdown("""
<style>
    /* Fixed header bar */
    .fixed-header {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 60px;
        background: #1e1e1e;
        border-bottom: 1px solid #333;
        z-index: 999;
        display: flex;
        align-items: center;
        padding: 0 20px;
    }
    
    /* Main content area with header offset */
    .main-content {
        margin-top: 60px;
        height: calc(100vh - 60px);
        display: flex;
        flex-direction: column;
    }
    
    /* Chat container - scrollable */
    .chat-container {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        padding-bottom: 100px; /* Space for fixed input */
    }
    
    /* Message bubbles - Phase 2 styling */
    .message-bubble {
        margin: 7px 0;
        padding: 12px 16px;
        border-radius: 12px;
        max-width: 80%;
        position: relative;
        word-wrap: break-word;
    }
    
    /* Message divider - Grok style */
    .message-divider {
        border-top: 1px solid #2d2d2d;
        margin: 8px 0;
    }
    
    .message-user {
        background: #0066cc;
        color: white;
        margin-left: auto;
        margin-right: 0;
        text-align: right;
    }
    
    .message-assistant {
        background: #2d2d2d;
        color: #e0e0e0;
        margin-left: 0;
        margin-right: auto;
    }
    
    /* Floating icon buttons - Grok style */
    .message-actions {
        position: absolute;
        bottom: 8px;
        right: 8px;
        display: flex;
        gap: 8px;
        opacity: 0;
        transition: opacity 0.2s;
    }
    
    .message-bubble:hover .message-actions {
        opacity: 1;
    }
    
    .action-icon {
        font-size: 28px;
        cursor: pointer;
        background: none;
        border: none;
        padding: 0;
        margin: 0;
        transition: transform 0.2s;
        line-height: 1;
    }
    
    .action-icon:hover {
        transform: scale(1.1);
    }
    
    .action-icon[title]:hover::after {
        content: attr(title);
        position: absolute;
        bottom: 100%;
        right: 0;
        background: #1e1e1e;
        color: #e0e0e0;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
        margin-bottom: 4px;
    }
    
    /* Fixed input area - Phase 7 */
    .fixed-input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #1e1e1e;
        border-top: 1px solid #333;
        padding: 15px 20px;
        z-index: 998;
    }
    
    /* Context pill - Phase 1 */
    .context-pill {
        display: inline-block;
        background: #333;
        color: #aaa;
        padding: 4px 12px;
        border-radius: 12px;
        font-size: 12px;
        margin-top: 8px;
    }
    
    /* Thinking animation - Phase 5 */
    @keyframes bounce {
        0%, 80%, 100% { transform: translateY(0); }
        40% { transform: translateY(-10px); }
    }
    
    .thinking-dots span {
        display: inline-block;
        animation: bounce 1.4s infinite;
    }
    
    .thinking-dots span:nth-child(2) {
        animation-delay: 0.2s;
    }
    
    .thinking-dots span:nth-child(3) {
        animation-delay: 0.4s;
    }
    
    /* Mobile responsive - Phase 7 */
    @media (max-width: 768px) {
        .message-bubble {
            max-width: 95%;
        }
        
        .fixed-header {
            padding: 0 10px;
        }
    }
    
    /* Hide Streamlit default elements */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
    header { visibility: hidden; }
    
    /* Remove loading animations */
    .stSpinner > div {
        animation: none !important;
    }
    
    /* Header logo smaller */
    .header-logo {
        font-size: 18px;
        font-weight: 600;
        margin: 0;
        padding: 0;
    }
    
    /* Perfect Grok input icons */
    button[data-testid*="upload_trigger"],
    button[data-testid*="quick_crystal"],
    button[data-testid*="quick_copy"] {
        background: none !important;
        border: none !important;
        color: #aaa !important;
        font-size: 20px !important;
        padding: 8px 12px !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
        box-shadow: none !important;
    }
    
    button[data-testid*="upload_trigger"]:hover,
    button[data-testid*="quick_crystal"]:hover,
    button[data-testid*="quick_copy"]:hover {
        background: #333 !important;
        color: white !important;
    }
    
    /* Remove Streamlit's default input border glow */
    div[data-baseweb="input"] {
        border-radius: 16px !important;
    }
    
    /* Ensure input bar icons are properly aligned */
    div[data-testid="column"]:has(button[data-testid*="upload_trigger"]),
    div[data-testid="column"]:has(button[data-testid*="quick_crystal"]),
    div[data-testid="column"]:has(button[data-testid*="quick_copy"]) {
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = False
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
if "project_tag" not in st.session_state:
    st.session_state.project_tag = ""
if "current_focus" not in st.session_state:
    st.session_state.current_focus = "General"
if "raw_mode" not in st.session_state:
    st.session_state.raw_mode = False
if "rag_threshold" not in st.session_state:
    st.session_state.rag_threshold = 0.25
if "top_k" not in st.session_state:
    st.session_state.top_k = rag_utils.DEFAULT_K
if "show_context" not in st.session_state:
    st.session_state.show_context = False

# Initialize ChatLogger
if "chat_logger" not in st.session_state:
    try:
        st.session_state.chat_logger = ChatLogger()
    except Exception as e:
        logger.warning(f"Failed to initialize ChatLogger: {e}")
        st.session_state.chat_logger = None

# Check backend availability
try:
    backend_available = check_backend_available()
except Exception as e:
    logger.warning(f"Failed to check backend availability: {e}")
    backend_available = False

# Cached functions
@st.cache_data(ttl=30)
def get_corpus_stats_safe():
    try:
        r = requests.get(f"{API_BASE}/visualize/stats", timeout=4)
        r.raise_for_status()
        data = r.json()
        return {"total_chunks": data.get("total_chunks", 0), "error": None}
    except Exception as e:
        logger.warning(f"Corpus stats failed: {e}")
        return {"total_chunks": None, "error": str(e)}

@st.cache_data(ttl=15)
def get_ollama_status_safe():
    try:
        r = requests.get("http://localhost:11434/api/tags", timeout=3)
        r.raise_for_status()
        return {"available": True, "error": None}
    except Exception as e:
        return {"available": False, "error": str(e)[:100]}

# Phase 1 & 6: Fixed Header Bar
def render_header():
    """Render fixed top header bar with logo, controls, and menu."""
    # Hamburger in top-left, reorder columns (removed col5 for New Chat button)
    col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
    
    with col1:
        # Custom beautiful hamburger button
        if st.button("☰", key="hamburger", use_container_width=True):
            # This is the ONLY correct way in modern Streamlit
            st.session_state.sidebar_open = not st.session_state.get("sidebar_open", False)
            st.rerun()
    
    with col2:
        # Logo - smaller and left-aligned (Issue 5)
        st.markdown('<div class="header-logo">🧠 Powercore Mind</div>', unsafe_allow_html=True)
    
    with col3:
        # Project tag input
        project_tag = st.text_input(
            "Project Tag",
            value=st.session_state.project_tag,
            placeholder="e.g. metacog-v2",
            key="header_project_tag",
            label_visibility="collapsed"
        )
        st.session_state.project_tag = project_tag
    
    with col4:
        # Model selector
        try:
            available_models = get_ollama_models()
            current_model = config.OLLAMA_CHAT_MODEL
            model_index = 0
            if current_model in available_models:
                model_index = available_models.index(current_model)
            selected_model = st.selectbox(
                "Model",
                available_models,
                index=model_index,
                key="header_model_selector",
                label_visibility="collapsed"
            )
            st.session_state.selected_model = selected_model
        except Exception as e:
            st.session_state.selected_model = config.OLLAMA_CHAT_MODEL
    

# Phase 1: Collapsible Sidebar
def render_sidebar():
    """Render collapsible sidebar with navigation links."""
    # Conditionally render sidebar based on state
    if st.session_state.get("sidebar_open", False):
        with st.sidebar:
            st.markdown("## Navigation")
            
            # Close button
            if st.button("Close ×", key="close_sidebar"):
                st.session_state.sidebar_open = False
                st.rerun()
            
            # New Chat button - moved from header
            if st.button("🆕 New Chat", key="new_chat_sidebar", use_container_width=True, type="primary"):
                st.session_state.chat_history = []
                st.session_state.conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
                st.rerun()
            
            st.markdown("---")
        
        pages = {
            "Chat": "chat",
            "Library": "library",
            "Ingest": "ingest",
            "Visualize": "visualize",
            "Graph": "graph",
            "Settings": "settings",
            "Prompts": "prompts"
        }
        
        for page_name, page_key in pages.items():
            if st.button(page_name, key=f"nav_{page_key}", use_container_width=True):
                st.session_state.current_page = page_key
                st.rerun()
        
        st.markdown("---")
        
        # Session Context
        st.header("Session Context")
        current_focus = st.selectbox(
            "Current Focus",
            ["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"],
            index=["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"].index(
                st.session_state.current_focus
            ) if st.session_state.current_focus in ["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"] else 0,
            help="What are you working on right now?"
        )
        st.session_state.current_focus = current_focus
        
        st.markdown("---")
        st.header("Settings")
        top_k = st.slider("Top-K context chunks", min_value=1, max_value=10, value=st.session_state.top_k)
        st.session_state.top_k = top_k
        show_context = st.checkbox("Show retrieved context", value=st.session_state.show_context)
        st.session_state.show_context = show_context
        
        st.markdown("---")
        st.subheader("Obsidian Sync")
        
        auto_ingest_obsidian = st.checkbox(
            "Auto-ingest Obsidian notes",
            value=st.session_state.get("auto_ingest_obsidian", True),
            help="Automatically ingest new/modified notes from knowledge/notes/ folder"
        )
        st.session_state.auto_ingest_obsidian = auto_ingest_obsidian
        
        col1, col2 = st.columns(2)
        with col1:
            try:
                watcher_status_response = requests.get(f"{API_BASE}/ingest/watch/status", timeout=2)
                if watcher_status_response.status_code == 200:
                    watcher_status = watcher_status_response.json().get("notes_watcher", "unknown")
                    if watcher_status == "running":
                        st.success("✅ Running")
                    else:
                        st.warning(f"⚠️ {watcher_status}")
                else:
                    st.info("Unknown")
            except Exception:
                st.info("Unknown")
        
        with col2:
            col_start, col_stop = st.columns(2)
            with col_start:
                if st.button("▶", key="start_notes_watcher"):
                    try:
                        response = requests.post(f"{API_BASE}/ingest/watch/notes/start", timeout=5)
                        if response.status_code == 200:
                            st.success("Started")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col_stop:
                if st.button("⏹", key="stop_notes_watcher"):
                    try:
                        response = requests.post(f"{API_BASE}/ingest/watch/notes/stop", timeout=5)
                        if response.status_code == 200:
                            st.success("Stopped")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        st.markdown("---")
        if st.button("Ingest all existing Obsidian notes (one-time)", type="primary", key="ingest_all_obsidian"):
            with st.spinner("Ingesting your entire vault..."):
                try:
                    response = requests.post(f"{API_BASE}/ingest/watch/notes/ingest-all", timeout=300)
                    if response.status_code == 200:
                        result = response.json()
                        count = result.get("count", 0)
                        st.success(f"Done! {count} notes added.")
                        st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

# Issue 3: Render floating action icons for messages
def render_message_actions(message_id: str, entry: dict, idx: int):
    """Render 3 floating action icons (Copy, Crystallize, Canvas) in bottom-right."""
    # Escape text for JavaScript (for data attribute)
    answer_text = entry.get('answer', '')
    escaped_answer = answer_text.replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$').replace('"', '&quot;').replace("'", "&#39;").replace('\n', '\\n').replace('\r', '\\r')
    
    actions_html = f"""
    <div class="message-actions">
        <button class="action-icon" title="Copy" onclick="window.copyToClipboard(`{escaped_answer}`)">📋</button>
        <button class="action-icon" title="Crystallize into note" onclick="window.triggerCrystallize({idx})" style="color: #60a5fa;">◆</button>
        <button class="action-icon" title="Send to Canvas" onclick="window.triggerCanvas({idx})" style="color: #a78bfa;">↗</button>
    </div>
    """
    return actions_html

# Phase 3: OCR helper for images
def extract_text_from_image(image_bytes):
    """Extract text from image using OCR."""
    try:
        import easyocr
        reader = easyocr.Reader(['en'])
        result = reader.readtext(image_bytes)
        text = ' '.join([item[1] for item in result])
        return text
    except ImportError:
        try:
            import pytesseract
            from PIL import Image
            import io
            image = Image.open(io.BytesIO(image_bytes))
            text = pytesseract.image_to_string(image)
            return text
        except ImportError:
            logger.warning("Neither easyocr nor pytesseract available for OCR")
            return None
    except Exception as e:
        logger.error(f"OCR failed: {e}")
        return None

# Phase 4: Canvas utilities
canvas_dir = Path("knowledge/canvas")
canvas_dir.mkdir(parents=True, exist_ok=True)

def add_to_canvas(canvas_name: str, title: str, content: str, chat_session_id: str = None):
    """Add a card to an Obsidian canvas file."""
    canvas_path = canvas_dir / f"{canvas_name}.canvas"
    
    # Load existing canvas or create new
    if canvas_path.exists():
        with open(canvas_path, 'r', encoding='utf-8') as f:
            canvas_data = json.load(f)
    else:
        canvas_data = {"nodes": [], "edges": []}
    
    # Calculate position (offset from last node)
    last_x = 0
    last_y = 0
    if canvas_data["nodes"]:
        last_x = max(node.get("x", 0) for node in canvas_data["nodes"])
        last_y = max(node.get("y", 0) for node in canvas_data["nodes"])
    
    # Create new node
    node_id = str(uuid.uuid4())
    new_node = {
        "id": node_id,
        "type": "text",
        "x": last_x + 450,
        "y": last_y + 50 if last_y > 0 else 0,
        "width": 400,
        "height": 300,
        "text": f"# {title}\n\n{content}"
    }
    
    if chat_session_id:
        new_node["text"] += f"\n\n---\n\n*Backlink to chat session: {chat_session_id}*"
    
    canvas_data["nodes"].append(new_node)
    
    # Save canvas
    with open(canvas_path, 'w', encoding='utf-8') as f:
        json.dump(canvas_data, f, indent=2)
    
    return str(canvas_path)

# Phase 5: Thinking animation component
def render_thinking_animation():
    """Render thinking animation with bouncing dots."""
    return """
    <div class="thinking-dots" style="color: #aaa; font-size: 14px; padding: 10px;">
        Thinking<span>.</span><span>.</span><span>.</span>
    </div>
    """

# Render header
render_header()

# Render sidebar
render_sidebar()

# Main content area
if st.session_state.current_page == "chat":
    # Phase 1: Chat interface as default
    
    # Chat container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # Mode controls (moved from old chat tab)
    col1, col2 = st.columns([1, 3])
    with col1:
        raw_mode = st.checkbox("☠️ Uncensored Raw Mode", value=st.session_state.raw_mode, 
                              help="Bypass RAG entirely — pure uncensored model chat")
        st.session_state.raw_mode = raw_mode
    with col2:
        if not raw_mode:
            rag_threshold = st.slider("RAG relevance threshold", 0.0, 1.0, st.session_state.rag_threshold, 0.05,
                                     help="Lower = more aggressive RAG, 0.0 = always use RAG")
            st.session_state.rag_threshold = rag_threshold
        else:
            rag_threshold = 0.0
            st.caption("Raw mode: RAG threshold disabled")
    
    # Crystallize entire conversation button
    if st.session_state.chat_history:
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("💎 Crystallize Entire Conversation", type="primary", use_container_width=True):
                try:
                    filepath = crystallize_conversation(st.session_state.chat_history)
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
                    st.success(f"✅ Conversation crystallized → `{filepath}`")
                except Exception as e:
                    st.error(f"Failed to crystallize conversation: {e}")
        st.markdown("---")
    
    # === PERFECT GROK INPUT BAR ===
    # Initialize session state for file uploader
    if "show_file_uploader" not in st.session_state:
        st.session_state.show_file_uploader = False
    
    cols = st.columns([0.5, 8, 0.5])
    with cols[1]:
        left, middle, right = st.columns([1.2, 10, 1])
        
        with left:
            # Paperclip (upload) button
            if st.button("📎", key="upload_trigger", help="Attach file or screenshot", use_container_width=True, type="secondary"):
                st.session_state.show_file_uploader = True
                st.rerun()
        
        with middle:
            question = st.chat_input(
                placeholder="Ask your second brain…",
                key="main_chat_input"
            )
        
        with right:
            col_crystal, col_copy = st.columns([1, 1])
            with col_crystal:
                # Diamond (crystallize) button
                if st.button("◆", key="quick_crystal", help="Crystallize last response", use_container_width=True, type="secondary"):
                    if st.session_state.chat_history:
                        # Get last assistant message
                        last_entry = None
                        for entry in reversed(st.session_state.chat_history):
                            if entry.get("answer"):
                                last_entry = entry
                                break
                        
                        if last_entry:
                            try:
                                metadata = {
                                    "mode": last_entry.get("mode", "🔍 RAG Mode"),
                                    "model": last_entry.get("model", "unknown"),
                                    "max_relevance": last_entry.get("max_relevance", 0.0),
                                    "sources": last_entry.get("sources", []),
                                    "context": last_entry.get("context", ""),
                                    "rag_threshold": last_entry.get("rag_threshold", 0.25),
                                    "conversation_id": last_entry.get("conversation_id", st.session_state.conversation_id)
                                }
                                
                                filepath = crystallize_turn(
                                    last_entry['question'],
                                    last_entry['answer'],
                                    metadata,
                                    conversation_history=st.session_state.chat_history,
                                    user_focus=st.session_state.current_focus,
                                    project_tag=st.session_state.project_tag
                                )
                                
                                if st.session_state.chat_logger and last_entry.get("ai_log_id"):
                                    try:
                                        st.session_state.chat_logger.mark_crystallized(
                                            last_entry["ai_log_id"],
                                            filepath
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to mark message as crystallized: {e}")
                                
                                st.toast(f"Crystallized → `{filepath.split('/')[-1]}`", icon="✅")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Failed to crystallize: {e}")
            
            with col_copy:
                # Copy button
                if st.button("📋", key="quick_copy", help="Copy last response", use_container_width=True, type="secondary"):
                    if st.session_state.chat_history:
                        # Get last assistant message
                        last_entry = None
                        for entry in reversed(st.session_state.chat_history):
                            if entry.get("answer"):
                                last_entry = entry
                                break
                        
                        if last_entry:
                            answer_text = last_entry.get("answer", "")
                            # Copy to clipboard via hidden JavaScript component
                            components.html(f"""
                            <script>
                            navigator.clipboard.writeText({repr(answer_text)}).then(function() {{
                                // Silent copy
                            }}).catch(function(err) {{
                                console.error('Failed to copy: ', err);
                            }});
                            </script>
                            """, height=0, width=0)
                            st.toast("Copied to clipboard", icon="✅")
    
    # Hidden actual file uploader (triggered by paperclip)
    if st.session_state.show_file_uploader:
        uploaded = st.file_uploader(
            "Upload file",
            key="hidden_uploader",
            label_visibility="visible",
            accept_multiple_files=False,
            type=["md", "pdf", "txt", "png", "jpg", "jpeg"]
        )
        if uploaded:
            # Process file using existing ingest logic
            inbox_path = Path(config.INBOX)
            inbox_path.mkdir(parents=True, exist_ok=True)
            save_path = inbox_path / uploaded.name
            
            # Handle duplicates
            counter = 1
            while save_path.exists():
                name_parts = uploaded.name.rsplit(".", 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    new_name = f"{uploaded.name}_{counter}"
                save_path = inbox_path / new_name
                counter += 1
            
            # Save file
            with open(save_path, "wb") as f:
                f.write(uploaded.getbuffer())
            
            # Handle images with OCR
            if uploaded.name.lower().endswith(('.png', '.jpg', '.jpeg')):
                image_text = extract_text_from_image(uploaded.getbuffer())
                if image_text:
                    # Save OCR text as markdown
                    ocr_path = save_path.with_suffix('.md')
                    with open(ocr_path, 'w', encoding='utf-8') as f:
                        f.write(f"# OCR Text from {uploaded.name}\n\n{image_text}")
                    save_path = ocr_path
            
            # Ingest file
            try:
                result = ingest_file(str(save_path.resolve()))
                if result.get("success"):
                    st.toast(f"Ingesting {uploaded.name}… added to your brain", icon="✅")
                    # Add system message
                    st.session_state.chat_history.append({
                        "question": f"Attached: {uploaded.name}",
                        "answer": f"File ingested and available for retrieval.",
                        "sources": [],
                        "context": "",
                        "mode": "📎 File Attachment",
                        "max_relevance": 1.0,
                        "model": "system",
                        "rag_threshold": 0.0,
                        "conversation_id": st.session_state.conversation_id,
                        "user_log_id": None,
                        "ai_log_id": None
                    })
                    st.session_state.show_file_uploader = False
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to ingest {uploaded.name}: {e}")
                st.session_state.show_file_uploader = False
    
    if question:
        # Phase 5: Show thinking animation
        thinking_placeholder = st.empty()
        thinking_placeholder.markdown(render_thinking_animation(), unsafe_allow_html=True)
        
        try:
            # Get selected model
            selected_model = st.session_state.get("selected_model", config.OLLAMA_CHAT_MODEL)
            
            # Call answer_question
            result = rag_utils.answer_question(
                question, 
                k=st.session_state.top_k,
                raw_mode=st.session_state.raw_mode,
                rag_threshold=st.session_state.rag_threshold,
                model=selected_model
            )
            
            # Clear thinking animation
            thinking_placeholder.empty()
            
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
            
            # Log to ChatLogger
            user_log_id = None
            ai_log_id = None
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
                
                try:
                    ai_log_id = st.session_state.chat_logger.log_message(
                        session_id=st.session_state.session_id,
                        role="assistant",
                        content=answer,
                        mode=mode,
                        model=model_used,
                        max_relevance=max_relevance,
                        sources=sources_list,
                        conversation_id=st.session_state.conversation_id
                    )
                except Exception as e:
                    logger.warning(f"Failed to log AI message: {e}")
            
            # Store in chat history
            st.session_state.chat_history.append({
                "question": question,
                "answer": answer,
                "sources": sources,
                "context": context,
                "mode": mode,
                "max_relevance": max_relevance,
                "model": model_used,
                "rag_threshold": st.session_state.rag_threshold,
                "conversation_id": st.session_state.conversation_id,
                "user_log_id": user_log_id,
                "ai_log_id": ai_log_id
            })
            
            st.rerun()
            
        except Exception as e:
            thinking_placeholder.empty()
            error_msg = str(e)
            if "dimension" in error_msg.lower():
                st.error(f"Embedding dimension mismatch: {error_msg}")
            else:
                st.error(f"Error answering question: {error_msg}")
            logger.error(f"Error in answer_question: {e}", exc_info=True)
    
    # Phase 1 & 2: Display chat history with custom styling
    for idx, entry in enumerate(reversed(st.session_state.chat_history)):
        # User message - Phase 2: right-aligned blue
        message_id_user = f"user_{len(st.session_state.chat_history) - idx - 1}"
        escaped_question = entry['question'].replace('\\', '\\\\').replace('`', '\\`').replace('$', '\\$').replace('"', '&quot;').replace("'", "&#39;").replace(chr(10), '\\n').replace(chr(13), '\\r')
        user_html = f"""
        <div class="message-bubble message-user">
            {entry['question'].replace(chr(10), '<br>')}
            <div class="message-actions">
                <button class="action-icon" title="Copy" onclick="window.copyToClipboard(`{escaped_question}`)">📋</button>
            </div>
        </div>
        """
        st.markdown(user_html, unsafe_allow_html=True)
        
        # Assistant message - Phase 2: left-aligned dark gray
        message_id_assistant = f"assistant_{len(st.session_state.chat_history) - idx - 1}"
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
        
        # Issue 2: Remove debug code block, Issue 3: Add floating icons
        assistant_html = f"""
        <div class="message-bubble message-assistant">
            {entry['answer'].replace(chr(10), '<br>')}
            {render_message_actions(message_id_assistant, entry, len(st.session_state.chat_history) - idx - 1)}
        </div>
        """
        st.markdown(assistant_html, unsafe_allow_html=True)
        
        # Issue 5: Add faint divider between messages
        st.markdown('<div class="message-divider"></div>', unsafe_allow_html=True)
        
        # Sources expander
        if entry.get("sources"):
            with st.expander("Sources"):
                for src in entry["sources"]:
                    st.markdown(f"- {src}")
        
        # Context expander
        if st.session_state.show_context and entry.get("context"):
            with st.expander("Retrieved context"):
                st.text(entry["context"])
        
        # Phase 1: Context pill
        if entry.get("sources"):
            num_chunks = len(entry.get("sources", []))
            # Extract source names from formatted sources
            source_names = []
            for src in entry.get("sources", [])[:3]:
                if isinstance(src, str):
                    source_names.append(src.split("/")[-1] if "/" in src else src)
                elif isinstance(src, dict):
                    source_names.append(src.get("source", "unknown").split("/")[-1])
            tags_str = ", ".join(source_names) if source_names else "N/A"
            st.markdown(f'<div class="context-pill">Context: {num_chunks} chunks • {tags_str}</div>', unsafe_allow_html=True)
        
        # Issue 3: Handle icon clicks via URL parameters
        entry_idx = len(st.session_state.chat_history) - idx - 1
        
        # Check URL params for actions
        query_params = st.query_params
        if query_params.get("crystallize") == str(entry_idx):
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
                
                filepath = crystallize_turn(
                    entry['question'], 
                    entry['answer'], 
                    metadata,
                    conversation_history=st.session_state.chat_history,
                    user_focus=st.session_state.current_focus,
                    project_tag=st.session_state.project_tag
                )
                
                if st.session_state.chat_logger and entry.get("ai_log_id"):
                    try:
                        st.session_state.chat_logger.mark_crystallized(
                            entry["ai_log_id"],
                            filepath
                        )
                    except Exception as e:
                        logger.warning(f"Failed to mark message as crystallized: {e}")
                
                st.toast(f"Crystallized → `{filepath.split('/')[-1]}`", icon="✅")
                # Clear URL param
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to crystallize: {e}")
                st.query_params.clear()
        
        # Check URL params for canvas action
        if query_params.get("canvas") == str(entry_idx):
            try:
                canvas_name = "Powercore Mind 2025"
                title = entry['question'][:50] if entry.get('question') else "Chat Entry"
                content = f"**Q:** {entry.get('question', '')}\n\n**A:** {entry.get('answer', '')}"
                canvas_path = add_to_canvas(
                    canvas_name,
                    title,
                    content,
                    st.session_state.conversation_id
                )
                st.toast(f"Added to Canvas → open in Obsidian", icon="✅")
                # Clear URL param
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Failed to add to canvas: {e}")
                st.query_params.clear()
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Phase 7: Fixed input area (handled by st.chat_input above, but we add styling)
    st.markdown('<div class="fixed-input-area"></div>', unsafe_allow_html=True)

elif st.session_state.current_page == "library":
    # Library page (old Library tab content)
    st.header("Library")
    if backend_available:
        view_mode = st.radio("View Mode", ["Chunks View", "Archive View"], horizontal=True, key="library_view_mode")
        if st.button("Refresh Library"):
            st.session_state.library_chunks_data = None
            st.session_state.library_archive_data = None
        
        if view_mode == "Chunks View":
            if "library_chunks_data" not in st.session_state:
                try:
                    st.session_state.library_chunks_data = get_chunks(limit=1000)
                except Exception as e:
                    logger.error(f"Error loading library chunks: {e}", exc_info=True)
                    st.session_state.library_chunks_data = {"chunks": [], "total": 0, "sources": 0, "error": str(e)}
            
            data = st.session_state.library_chunks_data
            if "error" in data:
                st.error(f"Error loading library: {data['error']}")
            else:
                total_chunks = data.get("total", 0)
                sources = data.get("sources", 0)
                st.metric("Total Chunks", total_chunks)
                st.metric("Source Documents", sources)
                
                if total_chunks == 0:
                    st.info("No chunks found. Ingest some documents first!")
                else:
                    chunks_by_source = {}
                    for chunk in data.get("chunks", []):
                        source = chunk.get("source", "unknown")
                        if source not in chunks_by_source:
                            chunks_by_source[source] = []
                        chunks_by_source[source].append(chunk)
                    
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
            col1, col2 = st.columns([3, 1])
            with col1:
                search_term = st.text_input("Search archived files", key="archive_search", placeholder="Enter filename...")
            with col2:
                page_size = st.selectbox("Files per page", [10, 20, 50], index=1, key="archive_page_size")
            
            if "library_archive_page" not in st.session_state:
                st.session_state.library_archive_page = 1
            
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
                    st.info("No archived files found.")
                else:
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
                    
                    for file_info in files:
                        with st.container():
                            col1, col2 = st.columns([4, 1])
                            with col1:
                                st.markdown(f"### 📄 {file_info['name']}")
                                file_size_kb = file_info['size'] / 1024
                                modified_date = file_info.get('modified', '')[:10] if file_info.get('modified') else 'Unknown'
                                st.caption(f"Size: {file_size_kb:.1f} KB | Modified: {modified_date}")
                                if file_info.get('ai_summary'):
                                    st.info(f"**Summary:** {file_info['ai_summary']}")
                                if file_info.get('ai_tags'):
                                    tag_cols = st.columns(min(len(file_info['ai_tags']), 5))
                                    for idx, tag in enumerate(file_info['ai_tags'][:5]):
                                        with tag_cols[idx % 5]:
                                            st.chip(tag)
                                if file_info.get('preview'):
                                    with st.expander("Preview"):
                                        st.code(file_info['preview'], language="markdown")
                            with col2:
                                file_path = file_info['path']
                                if st.button("📝 Open", key=f"open_{file_info['name']}"):
                                    cursor_url = f"cursor://file/{os.path.abspath(file_path)}"
                                    try:
                                        webbrowser.open(cursor_url)
                                        st.success("Opening...")
                                    except Exception as e:
                                        webbrowser.open(f"file://{os.path.dirname(os.path.abspath(file_path))}")
                                if st.button("🔄 Re-ingest", key=f"reingest_{file_info['name']}"):
                                    with st.spinner("Re-ingesting..."):
                                        result = ingest_file(file_path)
                                        if result.get("success"):
                                            st.success("Re-ingested!")
                                        else:
                                            st.error(f"Failed: {result.get('message', 'Unknown error')}")
                            st.divider()
    else:
        st.warning("Backend not available.")

elif st.session_state.current_page == "ingest":
    # Ingest page (old Ingest tab content - simplified)
    st.header("Ingest")
    if backend_available:
        uploaded_file = st.file_uploader("Select .md file to ingest", type=["md"])
        if uploaded_file is not None:
            inbox_path = Path(config.INBOX)
            inbox_path.mkdir(parents=True, exist_ok=True)
            save_path = inbox_path / uploaded_file.name
            
            counter = 1
            while save_path.exists():
                name_parts = uploaded_file.name.rsplit(".", 1)
                if len(name_parts) == 2:
                    new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                else:
                    new_name = f"{uploaded_file.name}_{counter}"
                save_path = inbox_path / new_name
                counter += 1
            
            with open(save_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            st.success(f"✅ Saved: `{save_path.name}` → inbox/")
            
            if st.button(f"🚀 Ingest `{save_path.name}` Now", type="primary"):
                result = ingest_file(str(save_path.resolve()))
                if result.get("success"):
                    st.success(f"✅ Ingested: `{save_path.name}`")
                else:
                    st.error(f"Failed: {result.get('message', 'Unknown error')}")
    else:
        st.warning("Backend not available.")

elif st.session_state.current_page == "visualize":
    # Visualize page (old Visualize tab content)
    st.header("Visualize")
    if backend_available:
        n_samples = st.slider("Number of samples", min_value=50, max_value=2000, value=500)
        if st.button("Generate UMAP Visualization"):
            with st.spinner("Computing UMAP coordinates..."):
                result = get_umap_coords(n=n_samples)
                if result and "error" not in result:
                    coords = result.get("coords", [])
                    if coords:
                        import pandas as pd
                        import plotly.express as px
                        df = pd.DataFrame([
                            {"x": c["x"], "y": c["y"], "source": c.get("meta", {}).get("source", "unknown")}
                            for c in coords
                        ])
                        fig = px.scatter(df, x="x", y="y", hover_data=["source"], title="UMAP Visualization")
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No coordinates returned")
                else:
                    st.error(f"Error: {result.get('error', 'Unknown error')}")
    else:
        st.warning("Backend not available.")

elif st.session_state.current_page == "graph":
    # Graph page (old Graph tab content - simplified)
    st.header("Knowledge Graph")
    if backend_available:
        if "graph_data" not in st.session_state:
            st.session_state.graph_data = None
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.markdown("### Filters")
            tags = st.multiselect("Filter by Tags", [])
            min_quality = st.slider("Min Quality", 0.0, 1.0, 0.5, 0.05)
            threshold = st.slider("Similarity Threshold", 0.5, 1.0, 0.75, 0.01)
            if st.button("🔄 Refresh Graph"):
                st.session_state.graph_data = None
                st.rerun()
        
        with col2:
            if st.session_state.graph_data is None:
                with st.spinner("Building graph..."):
                    try:
                        nodes_data = get_graph_nodes(tags=tags, min_quality=min_quality)
                        edges_data = get_graph_edges(threshold=threshold)
                        if nodes_data and "error" not in nodes_data and edges_data and "error" not in edges_data:
                            st.session_state.graph_data = (
                                nodes_data.get("nodes", []),
                                edges_data.get("edges", [])
                            )
                        else:
                            st.error("Error loading graph data")
                            st.session_state.graph_data = ([], [])
                    except Exception as e:
                        st.error(f"Error building graph: {e}")
                        st.session_state.graph_data = ([], [])
            
            nodes, edges = st.session_state.graph_data if st.session_state.graph_data else ([], [])
            if not nodes:
                st.info("No nodes found. Ingest some documents first!")
            else:
                try:
                    from pyvis.network import Network
                    net = Network(height="700px", width="100%", bgcolor="#1e1e1e", font_color="white")
                    net.barnes_hut(gravity=-8000, central_gravity=0.3, spring_length=200, spring_strength=0.05, damping=0.9)
                    
                    for node in nodes:
                        color = "#00ff41" if node["type"] == "document" else "#00aaff"
                        size = 25 if node["type"] == "document" else 15
                        shape = "box" if node["type"] == "document" else "dot"
                        net.add_node(node["id"], label=node["label"], color=color, size=size, shape=shape)
                    
                    for edge in edges:
                        net.add_edge(edge["source"], edge["target"], value=edge["weight"] * 10, color="#888888")
                    
                    net.show("rag_graph.html")
                    with open("rag_graph.html", "r", encoding="utf-8") as f:
                        html = f.read()
                    components.html(html, height=700, scrolling=True)
                except ImportError:
                    st.error("Pyvis not installed. Run: pip install pyvis==0.3.2")
                except Exception as e:
                    st.error(f"Error rendering graph: {e}")
    else:
        st.warning("Backend not available.")

elif st.session_state.current_page == "settings":
    # Settings page (consolidated from sidebar)
    st.header("Settings")
    st.subheader("Chat Settings")
    top_k = st.slider("Top-K context chunks", min_value=1, max_value=10, value=st.session_state.top_k)
    st.session_state.top_k = top_k
    show_context = st.checkbox("Show retrieved context", value=st.session_state.show_context)
    st.session_state.show_context = show_context
    
    st.subheader("Model Settings")
    st.code(f"Chat model: {st.session_state.get('selected_model', config.OLLAMA_CHAT_MODEL)}")
    st.code(f"Embedding model: {config.OLLAMA_EMBED_MODEL}")
    st.code(f"Ollama API: {config.OLLAMA_API_BASE}")

elif st.session_state.current_page == "prompts":
    # Prompts page (old Prompts tab)
    st.header("Prompt Repository")
    st.info("Prompt repository functionality coming soon. Use the FastAPI backend directly for now.")

# Keyboard shortcuts JavaScript moved to hidden component at top
