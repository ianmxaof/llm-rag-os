import os
import sys
import time
import logging
import shutil
import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

import streamlit as st
import streamlit.components.v1 as components
import webbrowser
import requests

logger = logging.getLogger(__name__)


# === ERROR HANDLING WRAPPER ===
def safe_execute(func: Callable, fallback_value: Any, error_message: str) -> Any:
    """Execute function with error handling"""
    try:
        return func()
    except Exception as e:
        logger.error(f"{error_message}: {e}")
        st.error(f"⚠️ {error_message}")
        return fallback_value

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

# Import v2.0 utilities
from src.app.utils.rag_engine import get_rag_context, get_rag_context_cached, _compute_context_hash, adjust_chunk_relevance, get_performance_stats
from src.app.utils.obsidian_bridge import get_related_notes, inject_note_context, crystallize_to_vault, open_in_obsidian, detect_vault_changes
from src.app.utils.memory_store import get_memory_streams, load_conversation_by_id, store_conversation, mark_crystallized, search_conversations
from typing import Callable, Any

# === FUNCTION DEFINITIONS (must be before sidebar) ===
# === ATOMIC STATE UPDATE FUNCTION ===
def update_conversation_state(new_message: Optional[Dict] = None):
    """Atomic state update after message - prevents race conditions"""
    # Store message if provided
    if new_message:
        st.session_state.chat_history.append(new_message)
    
    # Batch compute related data ONCE
    if st.session_state.chat_history:
        context = " ".join([
            m.get('question', m.get('content', '')) 
            for m in st.session_state.chat_history[-3:]
        ])
        
        # Update all state together atomically
        st.session_state.update({
            'related_notes': safe_execute(
                lambda: get_related_notes(context, top_k=5),
                fallback_value=[],
                error_message="Could not update related notes"
            ),
            'current_thread': {
                'id': st.session_state.conversation_id,
                'title': (
                    st.session_state.chat_history[0].get('question', 'New Thread')[:50]
                    if st.session_state.chat_history
                    else 'New Thread'
                ),
                'message_count': len(st.session_state.chat_history)
            },
            'rag_context': safe_execute(
                lambda: get_rag_context(
                    st.session_state.chat_history[-1].get('question', ''),
                    k=st.session_state.settings.get('top_k', 8),
                    settings=st.session_state.settings
                ) if st.session_state.chat_history else [],
                fallback_value=[],
                error_message="Could not update RAG context"
            )
        })
        
        # Update memory streams (less frequently - every 5 messages)
        if len(st.session_state.chat_history) % 5 == 0:
            st.session_state.memory_streams = safe_execute(
                lambda: get_memory_streams(),
                fallback_value=[],
                error_message="Could not update memory streams"
            )
        
        # Store conversation to persistent memory store
        safe_execute(
            lambda: store_conversation(
                conversation_id=st.session_state.conversation_id,
                messages=st.session_state.chat_history,
                title=st.session_state.current_thread.get('title'),
                tags=st.session_state.get('current_tags', []),
                metadata={
                    'related_notes': [n['source'] for n in st.session_state.get('related_notes', [])]
                }
            ),
            fallback_value=False,
            error_message="Could not store conversation"
        )

# === LOAD CONVERSATION FUNCTION ===
def load_conversation(conversation_id: str):
    """Restore a previous conversation from memory store"""
    try:
        conversation = load_conversation_by_id(conversation_id)
        if conversation:
            st.session_state.conversation_id = conversation_id
            st.session_state.chat_history = conversation.get('messages', [])
            st.session_state.current_thread = {
                'id': conversation_id,
                'title': conversation.get('title', 'Restored Thread'),
                'message_count': len(conversation.get('messages', []))
            }
            update_conversation_state(None)
            st.success(f"✅ Loaded: {conversation.get('title', 'Conversation')}")
            st.rerun()
        else:
            st.error("Conversation not found")
    except Exception as e:
        st.error(f"Failed to load conversation: {e}")

# === ATTENTION FLOW VISUALIZATION ===
def render_attention_map():
    """Visualize which notes are being used most in the current session"""
    try:
        # Track note access in session state
        if 'note_access_tracking' not in st.session_state:
            st.session_state.note_access_tracking = {}
        
        # Update tracking from current RAG context and related notes
        rag_context = st.session_state.get('rag_context', [])
        if rag_context:
            for chunk in rag_context:
                source = chunk.get('source', 'unknown')
                if source != 'unknown':
                    if source not in st.session_state.note_access_tracking:
                        st.session_state.note_access_tracking[source] = {
                            'count': 0,
                            'last_accessed': None
                        }
                    st.session_state.note_access_tracking[source]['count'] += 1
                    st.session_state.note_access_tracking[source]['last_accessed'] = time.time()
        
        related_notes = st.session_state.get('related_notes', [])
        if related_notes:
            for note in related_notes:
                source = note.get('source', 'unknown')
                if source != 'unknown':
                    if source not in st.session_state.note_access_tracking:
                        st.session_state.note_access_tracking[source] = {
                            'count': 0,
                            'last_accessed': None
                        }
                    st.session_state.note_access_tracking[source]['count'] += 1
                    st.session_state.note_access_tracking[source]['last_accessed'] = time.time()
        
        # Show visualization if we have tracked notes
        if st.session_state.note_access_tracking:
            with st.expander("🧠 Knowledge Attention Map", expanded=False):
                # Sort by access count
                sorted_notes = sorted(
                    st.session_state.note_access_tracking.items(),
                    key=lambda x: x[1]['count'],
                    reverse=True
                )[:10]  # Top 10
                
                if sorted_notes:
                    try:
                        import plotly.graph_objects as go
                        
                        notes = [Path(n[0]).stem for n in sorted_notes]
                        counts = [n[1]['count'] for n in sorted_notes]
                        
                        fig = go.Figure(data=[go.Bar(
                            x=notes,
                            y=counts,
                            marker=dict(
                                color=counts,
                                colorscale='Viridis',
                                showscale=True
                            )
                        )])
                        
                        fig.update_layout(
                            title="Most Referenced Notes This Session",
                            xaxis_title="Note",
                            yaxis_title="Times Referenced",
                            height=300,
                            template='plotly_dark'
                        )
                        
                        st.plotly_chart(fig, use_container_width=True)
                    except ImportError:
                        # Fallback to simple text list if Plotly not available
                        st.caption("Most Referenced Notes:")
                        for note_path, stats in sorted_notes[:5]:
                            note_name = Path(note_path).stem
                            st.markdown(f"- **{note_name}**: {stats['count']} references")
                    except Exception as e:
                        logger.error(f"Error rendering attention map: {e}")
                        st.caption("Could not render attention map")
    
    except Exception as e:
        logger.error(f"Error in render_attention_map: {e}")
        # Fail silently

# === CONVERSATION BRANCHING ===
def create_branch(branch_point: int):
    """Create a new conversation branch from a specific message point"""
    try:
        if branch_point < 0 or branch_point >= len(st.session_state.chat_history):
            st.error("Invalid branch point")
            return
        
        # Create new conversation from branch point
        new_thread_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Copy messages up to branch point
        branched_messages = st.session_state.chat_history[:branch_point + 1].copy()
        
        # Save as new thread
        safe_execute(
            lambda: store_conversation(
                conversation_id=new_thread_id,
                messages=branched_messages,
                title=f"Branch from: {branched_messages[0].get('question', 'Untitled')[:50]}",
                tags=['branch'],
                metadata={
                    'parent_thread': st.session_state.conversation_id,
                    'branch_point': branch_point,
                    'original_thread': st.session_state.conversation_id
                }
            ),
            fallback_value=False,
            error_message="Could not create branch"
        )
        
        # Switch to new thread
        st.session_state.conversation_id = new_thread_id
        st.session_state.chat_history = branched_messages
        
        # Update thread info
        st.session_state.current_thread = {
            'id': new_thread_id,
            'title': f"Branch from: {branched_messages[0].get('question', 'Untitled')[:50]}",
            'message_count': len(branched_messages)
        }
        
        st.success(f"✓ Branched conversation at message {branch_point}")
        st.rerun()
    
    except Exception as e:
        logger.error(f"Error creating branch: {e}")
        st.error(f"Failed to create branch: {e}")

def render_branch_points():
    """Allow branching at any message point"""
    chat_history = st.session_state.get("chat_history", [])
    if not chat_history:
        return
    
    with st.expander("🔀 Conversation Branches", expanded=False):
        st.caption("Fork conversation at any point")
        
        # Show last 5 messages as branch points
        for idx in range(len(chat_history) - 1, max(-1, len(chat_history) - 6), -1):
            entry = chat_history[idx]
            if entry.get('question'):
                question_preview = entry['question'][:40] + "..." if len(entry['question']) > 40 else entry['question']
                
                if st.button(
                    f"Branch from msg {idx}",
                    key=f"branch_{idx}",
                    use_container_width=True,
                    help=question_preview
                ):
                    create_branch(idx)

# === SEMANTIC PROMPT DISCOVERY ===
def suggest_prompts_for_context():
    """AI-powered prompt suggestions based on conversation context"""
    try:
        chat_history = st.session_state.get("chat_history", [])
        if not chat_history:
            return
        
        # Get recent conversation context
        recent_messages = " ".join([
            m.get('question', m.get('content', '')) 
            for m in chat_history[-3:]
        ])
        
        if not recent_messages:
            return
        
        # Embed conversation context
        from src.rag_utils import embed_texts
        import numpy as np
        
        conv_embedding = embed_texts([recent_messages])[0]
        
        # Define prompt library with descriptions
        prompt_library = [
            {
                'name': 'Analyze and synthesize',
                'description': 'Break down complex topics and synthesize insights',
                'text': 'Analyze and synthesize the key points from the context, identifying patterns and connections.'
            },
            {
                'name': 'Extract key insights',
                'description': 'Pull out the most important takeaways',
                'text': 'Extract the key insights and actionable items from the context.'
            },
            {
                'name': 'Compare and contrast',
                'description': 'Find similarities and differences',
                'text': 'Compare and contrast the different perspectives or approaches mentioned in the context.'
            },
            {
                'name': 'Crystallize conversation',
                'description': 'Save valuable insights to Obsidian',
                'text': 'Crystallize the most valuable insights from this conversation into a structured note.'
            },
            {
                'name': 'Critical path analysis',
                'description': 'Find highest-leverage actions',
                'text': 'Identify the critical path and highest-leverage actions from the context.'
            },
            {
                'name': 'Generate questions',
                'description': 'Create probing questions to explore deeper',
                'text': 'Generate thoughtful questions that would help explore the context more deeply.'
            }
        ]
        
        # Embed all prompts
        prompt_texts = [p['text'] for p in prompt_library]
        prompt_embeddings = embed_texts(prompt_texts)
        
        # Calculate cosine similarities
        conv_vec = np.array(conv_embedding)
        similarities = []
        
        for idx, prompt_vec in enumerate(prompt_embeddings):
            prompt_array = np.array(prompt_vec)
            # Cosine similarity
            dot_product = np.dot(conv_vec, prompt_array)
            norm_conv = np.linalg.norm(conv_vec)
            norm_prompt = np.linalg.norm(prompt_array)
            
            if norm_conv > 0 and norm_prompt > 0:
                similarity = dot_product / (norm_conv * norm_prompt)
            else:
                similarity = 0.0
            
            similarities.append((prompt_library[idx], similarity))
        
        # Sort by similarity and get top 3
        similarities.sort(key=lambda x: x[1], reverse=True)
        top_prompts = similarities[:3]
        
        # Show suggestions if relevance > 0.6
        if top_prompts and top_prompts[0][1] > 0.6:
            st.caption("💡 Suggested Prompts")
            for prompt_data, score in top_prompts:
                if score > 0.6:
                    if st.button(
                        f"▶ {prompt_data['name']} ({score:.0%})",
                        key=f"suggest_{prompt_data['name']}",
                        use_container_width=True,
                        help=prompt_data['description']
                    ):
                        # Execute the suggested prompt
                        st.session_state.prompt_template = prompt_data['text']
                        st.rerun()
    
    except Exception as e:
        logger.error(f"Error in semantic prompt discovery: {e}")
        # Fail silently - don't show error to user

# === PROMPT CHAIN EXECUTOR ===
def render_prompt_chain_executor():
    """UI component for executing prompt chains"""
    try:
        from src.app.utils.prompt_chains import PromptChain, execute_chain
        
        chain_executor = PromptChain()
        
        # List available chains
        chains = chain_executor.list_chains()
        
        if not chains:
            st.caption("No chains found. Create chains in prompts/chains/")
            return
        
        st.caption("⛓️ Prompt Chains")
        
        # Select chain
        selected_chain = st.selectbox(
            "Select Chain",
            chains,
            key="prompt_chain_selector",
            label_visibility="collapsed"
        )
        
        if selected_chain:
            # Load chain config
            chain_config = chain_executor.load_chain(selected_chain)
            
            if chain_config:
                st.caption(chain_config.get('description', ''))
                st.caption(f"Steps: {len(chain_config.get('steps', []))}")
                
                if st.button("▶ Execute Chain", key="execute_prompt_chain", use_container_width=True):
                    # Get initial input (last few messages or user input)
                    chat_history = st.session_state.get("chat_history", [])
                    if chat_history:
                        initial_input = " ".join([
                            m.get('question', m.get('content', '')) 
                            for m in chat_history[-3:]
                        ])
                    else:
                        initial_input = "No conversation context available"
                    
                    # Create LLM function wrapper
                    def llm_function(prompt: str, temperature: float, rag_k: int) -> str:
                        """Wrapper to call existing LLM function"""
                        try:
                            from src import rag_utils
                            selected_model = st.session_state.get("selected_model", config.OLLAMA_CHAT_MODEL)
                            
                            result = rag_utils.answer_question(
                                question=prompt,
                                k=rag_k,
                                raw_mode=False,
                                rag_threshold=0.25,
                                model=selected_model
                            )
                            
                            return result.get('response', '')
                        except Exception as e:
                            logger.error(f"LLM call failed in prompt chain: {e}")
                            raise
                    
                    # Execute with debug callbacks
                    execution_container = st.container()
                    
                    with execution_container:
                        st.markdown("### Execution Log")
                        
                        step_placeholders = {}
                        
                        def debug_callback(step_result):
                            """Update UI for each step"""
                            step_num = step_result['step_number']
                            
                            if step_num not in step_placeholders:
                                step_placeholders[step_num] = st.expander(
                                    f"Step {step_result['step_number']}: {step_result['description']}",
                                    expanded=True
                                )
                            
                            with step_placeholders[step_num]:
                                st.caption("Input:")
                                st.code(step_result['input'][:200] + '...' if len(step_result['input']) > 200 else step_result['input'])
                                
                                if step_result['success']:
                                    st.caption("Output:")
                                    st.markdown(step_result['output'])
                                    st.success("✓ Step completed")
                                else:
                                    st.error(f"❌ {step_result['error']}")
                        
                        # Execute chain
                        result = execute_chain(
                            chain_config=chain_config,
                            initial_input=initial_input,
                            llm_function=llm_function,
                            debug_callback=debug_callback
                        )
                        
                        if result['success']:
                            st.markdown("### Final Output")
                            st.markdown(result['final_output'])
                            st.balloons()
                            
                            # Optionally add to conversation
                            if st.button("Add to Conversation", key="add_chain_result"):
                                if "chat_history" not in st.session_state:
                                    st.session_state.chat_history = []
                                st.session_state.chat_history.append({
                                    'question': f"[Chain: {selected_chain}]",
                                    'answer': result['final_output'],
                                    'sources': [],
                                    'context': '',
                                    'mode': '⛓️ Prompt Chain',
                                    'max_relevance': 1.0,
                                    'model': 'chain',
                                    'rag_threshold': 0.0,
                                    'conversation_id': st.session_state.get("conversation_id", "")
                                })
                                st.rerun()
                        else:
                            st.error(f"Chain failed: {result['error']}")
    
    except Exception as e:
        logger.error(f"Error rendering prompt chain executor: {e}")
        st.caption(f"Error: {e}")

# Phase 1: Collapsible Sidebar - Claude/Grok Style
def render_sidebar_content():
    """Render sidebar expanders and additional content."""
    # === V2.0 NEW EXPANDERS ===
    
    # 0. Attention Flow Visualization
    render_attention_map()
    
    # 1. Active Context Expander
    with st.expander("🎯 Active Context", expanded=True):
        current_thread = st.session_state.get("current_thread")
        if current_thread:
            st.markdown(f"""
            <div style="background: rgba(124, 58, 237, 0.15); border-left: 3px solid #7c3aed; padding: 12px; border-radius: 8px; margin-bottom: 12px;">
                <strong>{current_thread.get('title', 'Untitled Thread')}</strong><br>
                <small style="color: rgba(255,255,255,0.5);">
                    {current_thread.get('message_count', 0)} messages
                </small>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.caption("No active thread. Start a new thought!")
        
        # Related Obsidian notes
        chat_history = st.session_state.get("chat_history", [])
        related = safe_execute(
            lambda: get_related_notes(
                " ".join([
                    m.get('question', m.get('content', '')) 
                    for m in chat_history[-3:]
                ])
                if chat_history else "",
                top_k=5
            ),
            fallback_value=[],
            error_message="Could not load related notes"
        )
        
        if related:
            st.caption("🔗 Connected Notes")
            for note in related[:3]:
                score_class = "relevance-high" if note['score'] >= 0.7 else ("relevance-medium" if note['score'] >= 0.4 else "relevance-low")
                
                with st.expander(f"📄 {note['title']} ({note['score']:.0%})", expanded=False):
                    # Show preview
                    note_content = safe_execute(
                        lambda: inject_note_context(note['source']),
                        fallback_value=None,
                        error_message="Could not load note"
                    )
                    
                    if note_content:
                        preview = note_content[:300] + "..." if len(note_content) > 300 else note_content
                        st.caption("Preview:")
                        st.markdown(preview)
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("💉 Inject", key=f"inject_{note['id']}", use_container_width=True):
                                # Add to conversation context
                                injected_msg = {
                                    'role': 'system',
                                    'content': f"[Context injected from {note['title']}]\n\n{note_content}",
                                    'metadata': {'type': 'injected_context', 'source': note['source']}
                                }
                                # Store in session state for next message
                                if 'injected_contexts' not in st.session_state:
                                    st.session_state.injected_contexts = []
                                st.session_state.injected_contexts.append(injected_msg)
                                st.success(f"✓ Injected {note['title']}")
                                st.rerun()
                        
                        with col2:
                            if st.button("🔗 Open", key=f"open_{note['id']}", use_container_width=True):
                                open_in_obsidian(note['source'])
                                st.info("Opening in Obsidian...")
                        
                        with col3:
                            if st.button("📋 Copy", key=f"copy_{note['id']}", use_container_width=True):
                                st.code(note_content, language="markdown")
                    else:
                        st.caption("Note content not available")
    
    # 2. Knowledge Base Expander
    with st.expander("📚 Knowledge Base", expanded=False):
        tab1, tab2, tab3 = st.tabs(["Vault", "Documents", "Graph"])
        
        with tab1:
            st.caption("Obsidian Vault Browser")
            vault_path = Path("./knowledge/notes")
            if vault_path.exists():
                folders = safe_execute(
                    lambda: [d.name for d in vault_path.iterdir() if d.is_dir() and not d.name.startswith('.')],
                    fallback_value=[],
                    error_message="Could not list vault folders"
                )
                for folder in folders[:5]:
                    if st.checkbox(f"📁 {folder}", value=False):
                        st.markdown(f"- 📄 {folder} notes")
            else:
                st.caption("Vault not found")
        
        with tab2:
            st.caption("Ingested Documents")
            docs_result = safe_execute(
                lambda: list_documents(),
                fallback_value={"items": [], "total": 0},
                error_message="Could not load documents"
            )
            # Handle both dict response and list response
            if isinstance(docs_result, dict):
                docs_list = docs_result.get("items", [])
            elif isinstance(docs_result, list):
                docs_list = docs_result
            else:
                docs_list = []
            
            if docs_list:
                st.markdown("**Recent:**")
                for doc in docs_list[:5]:
                    # Handle both dict and string formats
                    if isinstance(doc, dict):
                        doc_name = doc.get('source_path', doc.get('name', 'Unknown'))
                    else:
                        doc_name = str(doc)
                    st.markdown(f"- {doc_name}")
            else:
                st.caption("No documents ingested yet")
            
            if st.button("➕ Ingest New Document", use_container_width=True):
                st.info("Use the paperclip icon in the chat input to ingest files")
        
        with tab3:
            st.markdown("""
            <div style="background: rgba(15, 15, 15, 0.8); border: 1px solid rgba(255, 255, 255, 0.05); border-radius: 8px; padding: 12px; margin: 8px 0; min-height: 120px; display: flex; align-items: center; justify-content: center; color: rgba(255, 255, 255, 0.4); font-size: 0.85rem;">
                🌐 Graph View<br>
                <small>Click to expand full graph</small>
            </div>
            """, unsafe_allow_html=True)
    
    # 2.5. Conversation Branching
    render_branch_points()
    
    # 3. Memory Streams Expander
    with st.expander("💭 Memory Streams", expanded=False):
        streams = safe_execute(
            lambda: get_memory_streams(),
            fallback_value=[],
            error_message="Could not load memory streams"
        )
        
        # Group by category
        today = [s for s in streams if s.get('category') == 'today']
        week = [s for s in streams if s.get('category') == 'week']
        
        if today:
            st.caption("Today")
            for stream in today:
                st.markdown(f"""
                <div style="padding: 8px 12px; border-radius: 8px; margin: 4px 0; cursor: pointer; background: rgba(30, 30, 30, 0.4); border-left: 2px solid #00ff88;">
                    <strong>{stream['title']}</strong><br>
                    <small style="color: rgba(255,255,255,0.5);">
                        {stream.get('message_count', 0)} messages
                    </small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Load", key=f"load_{stream['id']}", use_container_width=True):
                    load_conversation(stream['id'])
        
        if week:
            st.caption("This Week")
            for stream in week:
                st.markdown(f"""
                <div style="padding: 8px 12px; border-radius: 8px; margin: 4px 0; cursor: pointer; background: rgba(30, 30, 30, 0.4);">
                    <strong>{stream['title']}</strong><br>
                    <small style="color: rgba(255,255,255,0.5);">
                        {stream.get('message_count', 0)} messages
                    </small>
                </div>
                """, unsafe_allow_html=True)
                if st.button("Load", key=f"load_{stream['id']}", use_container_width=True):
                    load_conversation(stream['id'])
    
    # 4. System Settings Expander (enhanced)
    with st.expander("⚙️ System", expanded=False):
        st.caption("Interaction Preferences")
        
        # Ensure settings exists
        if "settings" not in st.session_state:
            st.session_state.settings = {}
        
        auto_crystallize = st.toggle(
            "Auto-Crystallize Insights",
            value=st.session_state.settings.get('auto_crystallize', False),
            key="auto_crystallize_toggle",
            help="Automatically save valuable insights to Obsidian"
        )
        st.session_state.settings['auto_crystallize'] = auto_crystallize
        
        uncensored_mode = st.toggle(
            "Uncensored Raw Mode",
            value=st.session_state.settings.get('uncensored_mode', False),
            key="uncensored_mode_toggle",
            help="Disable content filters (use responsibly)"
        )
        st.session_state.settings['uncensored_mode'] = uncensored_mode
        st.session_state.raw_mode = uncensored_mode
        
        # Advanced RAG tuning
        st.markdown("---")
        manual_tuning = st.checkbox(
            "Manual RAG Tuning",
            value=st.session_state.settings.get('manual_rag_tuning', False),
            help="Override automatic RAG parameter optimization"
        )
        st.session_state.settings['manual_rag_tuning'] = manual_tuning
        
        if manual_tuning:
            st.caption("⚠️ System auto-tunes these. Override only if needed.")
            top_k_slider = st.slider(
                "Context Chunks (Top-K)",
                min_value=1,
                max_value=20,
                value=st.session_state.settings.get('top_k', 8),
                key="top_k_slider",
                help="Number of context chunks to retrieve"
            )
            st.session_state.settings['top_k'] = top_k_slider
            st.session_state.top_k = top_k_slider
            
            relevance_slider = st.slider(
                "Relevance Threshold",
                min_value=0.0,
                max_value=1.0,
                value=st.session_state.settings.get('relevance_threshold', 0.25),
                step=0.05,
                key="relevance_slider",
                help="Minimum similarity score for retrieval"
            )
            st.session_state.settings['relevance_threshold'] = relevance_slider
            st.session_state.rag_threshold = relevance_slider
    
    # 5. Prompts Library Expander
    with st.expander("📝 Prompts Library", expanded=False):
        st.caption("Quick Templates")
        # TODO: Query prompts from API if available
        prompts = [
            "Analyze and synthesize...",
            "Extract key insights from...",
            "Compare and contrast...",
            "Crystallize this conversation"
        ]
        
        for prompt in prompts:
            if st.button(prompt, key=f"prompt_{prompt[:10]}", use_container_width=True):
                st.session_state.prompt_template = prompt
                st.rerun()
        
        st.markdown("---")
        
        # Semantic Prompt Discovery
        suggest_prompts_for_context()
        
        st.markdown("---")
        
        # Prompt Chain Executor
        render_prompt_chain_executor()
    
    # 6. Session Context & Obsidian Sync (integrated into System Settings)
    with st.expander("🔧 Session & Sync", expanded=False):
        # Session Context
        st.caption("Current Focus")
        current_focus_value = st.session_state.get("current_focus", "General")
        current_focus = st.selectbox(
            "What are you working on?",
            ["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"],
            index=["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"].index(
                current_focus_value
            ) if current_focus_value in ["Researching", "Building", "Reflecting", "Planning", "Debugging", "General"] else 0,
            key="sidebar_current_focus",
            help="What are you working on right now?"
        )
        st.session_state.current_focus = current_focus
        
        st.markdown("---")
        
        # Basic Settings
        st.caption("Display Preferences")
        show_context = st.checkbox("Show retrieved context", value=st.session_state.get("show_context", False), key="sidebar_show_context")
        st.session_state.show_context = show_context
        
        st.markdown("---")
        
        # Obsidian Sync
        st.caption("Obsidian Integration")
        auto_ingest_obsidian = st.checkbox(
            "Auto-ingest Obsidian notes",
            value=st.session_state.get("auto_ingest_obsidian", True),
            key="sidebar_auto_ingest",
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
                if st.button("▶", key="sidebar_start_watcher"):
                    try:
                        response = requests.post(f"{API_BASE}/ingest/watch/notes/start", timeout=5)
                        if response.status_code == 200:
                            st.success("Started")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
            with col_stop:
                if st.button("⏹", key="sidebar_stop_watcher"):
                    try:
                        response = requests.post(f"{API_BASE}/ingest/watch/notes/stop", timeout=5)
                        if response.status_code == 200:
                            st.success("Stopped")
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        st.markdown("---")
        if st.button("Ingest all existing Obsidian notes (one-time)", type="primary", key="sidebar_ingest_all"):
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

# Remove Streamlit timeout limits for long-running ingestion tasks
os.environ.setdefault("STREAMLIT_SERVER_MAX_REQUEST_SIZE", "0")
os.environ.setdefault("STREAMLIT_SERVER_MAX_MESSAGE_SIZE", "0")

# Page config - Claude/Grok Design Language
st.set_page_config(
    page_title="Powercore Mind",
    layout="centered",
    initial_sidebar_state="expanded"
)

# === SIDEBAR MUST BE RENDERED IMMEDIATELY AFTER set_page_config ===
# In Streamlit v1.38+ with layout="centered", ANY st. command before sidebar kills it
with st.sidebar:
    # New Chat button - small pill shape
    if st.button("🆕 New Chat", key="new_chat_sidebar", type="primary"):
        st.session_state.chat_history = []
        st.session_state.conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        st.rerun()
    
    st.markdown("---")
    
    pages = {
        "Chat": "chat",
        "Cognitive IDE": "cognitive_ide",
        "Library": "library",
        "Ingest": "ingest",
        "Visualize": "visualize",
        "Graph": "graph",
        "Settings": "settings",
        "Prompts": "prompts"
    }
    
    current_page = st.session_state.get("current_page", "chat")
    for page_name, page_key in pages.items():
        # Highlight active page with purple accent
        button_type = "primary" if page_key == current_page else "secondary"
        if st.button(page_name, key=f"nav_{page_key}", use_container_width=True, type=button_type):
            st.session_state.current_page = page_key
            st.rerun()
    
    # Floating chevron button on sidebar right edge (when expanded)
    if not st.session_state.get("sidebar_collapsed", False):
        st.markdown("""
        <div class="sidebar-chevron" onclick="toggleSidebarCollapse()">⟨</div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Render the rest of sidebar content (expanders, etc.)
    render_sidebar_content()

# === NOW inject global CSS and JavaScript AFTER sidebar ===
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
    
    // Toggle Streamlit's native sidebar - BULLETPROOF VERSION
    window.toggleSidebar = function() {
        // Use Streamlit's official collapsedControl selector
        const toggleBtn = document.querySelector('[data-testid="collapsedControl"]');
        if (toggleBtn) {
            toggleBtn.click();
            return true;
        }
        // Fallback to header button if collapsedControl not found
        const header = document.querySelector('header[data-testid="stHeader"]');
        if (header) {
            const toggleButton = header.querySelector('button');
            if (toggleButton) {
                toggleButton.click();
                return true;
            }
        }
        return false;
    };
    
    // Chevron button handlers for sidebar toggle - Enhanced with class management
    window.toggleSidebarCollapse = function() {
        const toggleBtn = document.querySelector('[data-testid="collapsedControl"]');
        if (toggleBtn) {
            document.body.classList.add('sidebar-collapsed');
            const sidebar = document.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                sidebar.classList.add('collapsed');
            }
            toggleBtn.click();
        }
    };
    
    window.toggleSidebarExpand = function() {
        const toggleBtn = document.querySelector('[data-testid="collapsedControl"]');
        if (toggleBtn) {
            document.body.classList.remove('sidebar-collapsed');
            const sidebar = document.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                sidebar.classList.remove('collapsed');
            }
            toggleBtn.click();
        }
    };
    
    // Sync sidebar state on page load - ensure sidebar is expanded by default
    function syncSidebarState() {
        // Wait for Streamlit to render sidebar
        setTimeout(function() {
            const sidebar = document.querySelector('section[data-testid="stSidebar"]');
            if (sidebar) {
                const isExpanded = sidebar.getAttribute('aria-expanded') === 'true';
                // If sidebar is collapsed, expand it (respect initial_sidebar_state="expanded")
                if (!isExpanded) {
                    // Check for collapsed control button (visible when sidebar is collapsed)
                    const collapsedControl = document.querySelector('[data-testid="collapsedControl"]');
                    if (collapsedControl && collapsedControl.offsetParent !== null) {
                        // Sidebar is collapsed - expand it
                        collapsedControl.click();
                    }
                }
            }
        }, 300); // Give Streamlit time to render
    }
    
    // Run sync on page load - multiple attempts to ensure it works
    function runSync() {
        syncSidebarState();
        // Also try after a longer delay in case Streamlit is slow
        setTimeout(syncSidebarState, 1000);
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', runSync);
    } else {
        runSync();
    }
    
    // Also sync after Streamlit reruns
    window.addEventListener('load', runSync);
    
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

# Initialize session state - MUST be after sidebar
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = f"conv_{int(time.time())}_{uuid.uuid4().hex[:8]}"
# Sidebar state - default to open/expanded
if "sidebar_open" not in st.session_state:
    st.session_state.sidebar_open = True   # ← This single line reveals v2.0 forever
if "sidebar_collapsed" not in st.session_state:
    st.session_state.sidebar_collapsed = False
if "sidebar_width" not in st.session_state:
    st.session_state.sidebar_width = 280

# Ensure sidebar is expanded on initial load
# Streamlit's initial_sidebar_state="expanded" handles this, but we sync our state
if st.session_state.sidebar_open and not st.session_state.sidebar_collapsed:
    # Sidebar should be open - this is handled by initial_sidebar_state
    pass
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

# Initialize v2.0 state variables
if "related_notes" not in st.session_state:
    st.session_state.related_notes = []
if "current_thread" not in st.session_state:
    st.session_state.current_thread = None
if "memory_streams" not in st.session_state:
    st.session_state.memory_streams = []
if "rag_context" not in st.session_state:
    st.session_state.rag_context = []
if "settings" not in st.session_state:
    st.session_state.settings = {
        'top_k': st.session_state.get('top_k', 3),
        'relevance_threshold': st.session_state.get('rag_threshold', 0.25),
        'auto_crystallize': False,
        'uncensored_mode': st.session_state.get('raw_mode', False),
        'auto_ingest_obsidian': st.session_state.get('auto_ingest_obsidian', True),
        'manual_rag_tuning': False
    }

# Initialize ChatLogger
if "chat_logger" not in st.session_state:
    try:
        st.session_state.chat_logger = ChatLogger()
    except Exception as e:
        logger.warning(f"Failed to initialize ChatLogger: {e}")
        st.session_state.chat_logger = None

# Claude/Grok Design Language CSS - Consolidated and moved after sidebar
st.markdown("""
<style>
    /* FORCE SIDEBAR TO EXIST */
    section[data-testid="stSidebar"] {
        min-width: 280px !important;
        width: 280px !important;
        flex-shrink: 0 !important;
        transition: all 0.35s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    
    /* Main container - centered with max-width 1200px */
    .main-container {
        max-width: 1200px;
        margin: 0 auto;
        padding: 0 100px;
    }
    
    /* Reduce top void - tighter spacing */
    .main .block-container {
        padding-top: 1rem !important;
        padding-bottom: 1rem !important;
    }
    
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
    
    /* Chat container - scrollable, centered */
    .chat-container {
        flex: 1;
        overflow-y: auto;
        padding: 20px;
        padding-bottom: 100px;
        max-width: 1200px;
        margin: 0 auto;
        width: 100%;
    }
    
    /* Chevron buttons for sidebar control - Purple obelisk style */
    .sidebar-chevron {
        position: fixed;
        top: 50%;
        right: 8px;
        transform: translateY(-50%);
        background: rgba(138, 43, 226, 0.9);
        color: white;
        width: 32px;
        height: 64px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        cursor: pointer;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    .main-chevron {
        position: fixed;
        left: 16px;
        top: 50%;
        transform: translateY(-50%);
        background: rgba(138, 43, 226, 0.9);
        color: white;
        width: 32px;
        height: 64px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        cursor: pointer;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    /* Visual density adjustments - tighter spacing throughout */
    .main-container .stButton > button {
        padding: 6px 16px !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        min-height: 36px !important;
    }
    
    .main-container input[type="text"],
    .main-container textarea {
        padding: 8px 12px !important;
        font-size: 14px !important;
        border-radius: 8px !important;
    }
    
    .main-container .stSelectbox > div > div {
        padding: 6px 12px !important;
        font-size: 13px !important;
    }
    
    /* Cards and panels - inset premium feel */
    .main-container [data-testid="stCard"] {
        padding: 16px !important;
        border-radius: 12px !important;
        margin: 8px 0 !important;
    }
    
    /* Reduce spacing in columns */
    .main-container [data-testid="column"] {
        padding: 0 8px !important;
    }
    
    /* Tighter headings */
    .main-container h1 {
        font-size: 2rem !important;
        margin: 1rem 0 0.5rem 0 !important;
    }
    
    .main-container h2 {
        font-size: 1.5rem !important;
        margin: 0.75rem 0 0.4rem 0 !important;
    }
    
    .main-container h3 {
        font-size: 1.25rem !important;
        margin: 0.5rem 0 0.3rem 0 !important;
    }
    
    /* Ensure inputs respect side padding */
    .main-container .stTextInput,
    .main-container .stTextArea,
    .main-container .stSelectbox {
        max-width: 100% !important;
    }
    
    /* Message bubbles - Denser Claude/Grok style */
    .message-bubble {
        margin: 4px 0;
        padding: 10px 14px;
        border-radius: 12px;
        max-width: 80%;
        position: relative;
        word-wrap: break-word;
        line-height: 1.5;
    }
    
    /* Message divider - tighter spacing */
    .message-divider {
        border-top: 1px solid #2d2d2d;
        margin: 4px 0;
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
    
    /* TRUE 2030 GLASSMORPHISM — NOTHING CAN STOP THIS */
    div[data-testid="stExpander"] {
        background: rgba(26, 26, 26, 0.85) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 16px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4) !important;
        margin: 12px 0 !important;
        padding: 8px !important;
    }
    
    /* Expander content area */
    div[data-testid="stExpander"] > div {
        background: transparent !important;
    }
    
    /* Expander label */
    div[data-testid="stExpander"] > div > label {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 15px !important;
    }
    
    /* Sidebar - Denser Claude/Grok style */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0a0a0a 0%, #111 100%) !important;
    }
    
    /* Sidebar content area - tighter spacing */
    section[data-testid="stSidebar"] > div {
        background: transparent !important;
        padding: 12px 8px !important;
    }
    
    /* Sidebar buttons - smaller, denser */
    section[data-testid="stSidebar"] button {
        padding: 6px 12px !important;
        margin: 2px 0 !important;
        font-size: 13px !important;
        border-radius: 6px !important;
        min-height: 32px !important;
        line-height: 1.4 !important;
    }
    
    /* Active sidebar item highlight - purple accent */
    section[data-testid="stSidebar"] button[kind="secondary"]:has-text,
    section[data-testid="stSidebar"] button:active {
        background: rgba(124, 58, 237, 0.2) !important;
        border-left: 2px solid #7c3aed !important;
    }
    
    /* New Chat button - small pill shape */
    section[data-testid="stSidebar"] button[kind="primary"] {
        background: rgba(124, 58, 237, 0.3) !important;
        border: 1px solid rgba(124, 58, 237, 0.5) !important;
        border-radius: 20px !important;
        padding: 6px 16px !important;
        font-size: 12px !important;
        width: auto !important;
        max-width: fit-content !important;
        margin: 8px auto !important;
    }
    
    /* Sidebar text - smaller, crisper */
    section[data-testid="stSidebar"] h1,
    section[data-testid="stSidebar"] h2,
    section[data-testid="stSidebar"] h3 {
        font-size: 14px !important;
        margin: 8px 0 4px 0 !important;
        padding: 0 !important;
    }
    
    /* Sidebar expanders - tighter */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        margin: 4px 0 !important;
    }
    
    /* Sidebar captions - smaller */
    section[data-testid="stSidebar"] .stCaption {
        font-size: 11px !important;
        margin: 2px 0 !important;
    }
    
    /* Relevance badge styles */
    .relevance-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        margin-left: 8px;
    }
    
    .relevance-high {
        background: rgba(0, 255, 136, 0.2);
        color: #00ff88;
    }
    
    .relevance-medium {
        background: rgba(255, 184, 0, 0.2);
        color: #ffb800;
    }
    
    .relevance-low {
        background: rgba(255, 68, 68, 0.2);
        color: #ff4444;
    }
    
    /* Note link styles */
    .note-link {
        color: #7c3aed !important;
        text-decoration: none;
        border-bottom: 1px dashed rgba(124, 58, 237, 0.5);
        padding: 2px 4px;
        border-radius: 4px;
        display: inline-block;
        margin: 2px;
        font-size: 0.9rem;
    }
    
    .note-link:hover {
        background: rgba(124, 58, 237, 0.1);
        border-bottom: 1px solid #7c3aed;
    }
    
    /* RAG chunk styles */
    .rag-chunk {
        background: rgba(30, 30, 30, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 10px;
        margin: 8px 0;
    }
    
    .rag-chunk:hover {
        border-color: rgba(124, 58, 237, 0.3);
        transform: translateX(2px);
    }
    
    /* Memory item styles */
    .memory-item {
        padding: 8px 12px;
        border-radius: 8px;
        margin: 4px 0;
        cursor: pointer;
        background: rgba(30, 30, 30, 0.4);
    }
    
    .memory-item:hover {
        background: rgba(124, 58, 237, 0.1);
        border-left: 2px solid #7c3aed;
        padding-left: 10px;
    }
    
    .memory-item.today {
        border-left: 2px solid #00ff88;
    }
</style>
""", unsafe_allow_html=True)

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
    # Removed hamburger - using chevron buttons instead
    col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
    
    with col1:
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
        
        # INVENT LAW button
        if st.button("⚡ INVENT LAW", type="primary", key="invent_law_button", use_container_width=True):
            st.session_state.show_invent_law = True
            st.rerun()
    
    # INVENT LAW UI (shown when button clicked)
    if st.session_state.get("show_invent_law", False):
        with st.expander("⚡ Invent New Law of Thought", expanded=True):
            goal = st.text_input(
                "What cognitive process should now exist?",
                placeholder="e.g. Detect hidden contradictions across decades",
                key="invent_law_goal"
            )
            
            if goal and st.button("Enact New Law of Thought", key="generate_law"):
                try:
                    from src import rag_utils
                    selected_model = st.session_state.get("selected_model", config.OLLAMA_CHAT_MODEL)
                    
                    generation_prompt = f"""
Goal: {goal}

Create a new process chain in valid YAML format.

Requirements:
- Name in SCREAMING_SNAKE_CASE
- 4-6 ruthless steps
- Each step has: description, prompt, temperature, rag_k
- No fluff. No explanation. Just the YAML.

Format:
name: CHAIN_NAME
description: Brief description
version: 1.0
settings:
  default_temperature: 0.2
  default_rag_k: 12
steps:
  - description: "Step description"
    prompt: "Step prompt with {{context}} placeholder"
    temperature: 0.2
    rag_k: 10
metadata:
  created: 2025-01-15
  author: powercore
  tags: [cognitive-process]
"""
                    
                    with st.spinner("Generating new law of thought..."):
                        result = rag_utils.answer_question(
                            question=generation_prompt,
                            k=8,
                            raw_mode=False,
                            rag_threshold=0.25,
                            model=selected_model
                        )
                        
                        new_chain_yaml = result.get('response', '')
                        
                        # Display generated chain
                        st.markdown("### Generated Chain:")
                        st.code(new_chain_yaml, language="yaml")
                        
                        # Extract chain name
                        import re
                        name_match = re.search(r"name:\s*(\w+)", new_chain_yaml)
                        if name_match:
                            chain_name = name_match.group(1)
                            
                            # Save button
                            if st.button("🧠 Make This Law Real", key="save_law"):
                                chains_dir = Path("prompts/chains")
                                chains_dir.mkdir(parents=True, exist_ok=True)
                                
                                chain_path = chains_dir / f"{chain_name}.yaml"
                                chain_path.write_text(new_chain_yaml, encoding='utf-8')
                                
                                st.success(f"⚡ {chain_name} is now eternal law")
                                st.session_state.show_invent_law = False
                                st.rerun()
                        else:
                            st.warning("Could not extract chain name from generated YAML")
                
                except Exception as e:
                    st.error(f"Error generating law: {e}")
                    logger.error(f"Error in INVENT LAW: {e}")
            
            # Close button
            if st.button("Cancel", key="cancel_invent_law"):
                st.session_state.show_invent_law = False
                st.rerun()
    

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

def crystallize_with_canvas_integration(conversation_history: List[Dict] = None, entry: Dict = None):
    """
    Complete crystallization: Obsidian note + Canvas node + Memory marking
    
    Args:
        conversation_history: Full conversation history (for entire conversation)
        entry: Single message entry (for single turn)
    
    Returns:
        Tuple of (note_path, connection_count)
    """
    import json
    import os
    from pathlib import Path
    from datetime import datetime
    
    try:
        # Determine if this is a full conversation or single turn
        if conversation_history:
            # Full conversation crystallization
            title = st.session_state.current_thread.get('title', 'Untitled Conversation')
            insights = "\n\n".join([
                f"**Q:** {m.get('question', '')}\n**A:** {m.get('answer', '')}"
                for m in conversation_history
            ])
            context_messages = conversation_history[-5:]
        elif entry:
            # Single turn crystallization
            title = entry.get('question', 'Untitled')[:50]
            insights = f"**Q:** {entry.get('question', '')}\n\n**A:** {entry.get('answer', '')}"
            context_messages = [entry]
        else:
            st.error("No conversation data provided")
            return None, 0
        
        # 1. Get related notes for linking
        context = " ".join([
            m.get('question', m.get('content', '')) 
            for m in context_messages
        ])
        related = safe_execute(
            lambda: get_related_notes(context, top_k=10),
            fallback_value=[],
            error_message="Could not get related notes"
        )
        related_sources = [n['source'] for n in related]
        
        # 2. Crystallize to Obsidian vault
        note_path = safe_execute(
            lambda: crystallize_to_vault(
                title=title,
                content=insights,
                tags=['crystallized', 'powercore'],
                linked_notes=related_sources,
                metadata={'conversation_id': st.session_state.conversation_id}
            ),
            fallback_value=None,
            error_message="Could not crystallize to vault"
        )
        
        if not note_path:
            return None, 0
        
        # 3. Update canvas.json
        vault_path = Path(os.getenv('OBSIDIAN_VAULT_PATH', './knowledge/notes'))
        canvas_path = vault_path / 'canvas.json'
        
        try:
            if canvas_path.exists():
                canvas_data = json.loads(canvas_path.read_text(encoding='utf-8'))
            else:
                canvas_data = {'nodes': [], 'edges': []}
            
            # Find related nodes already in canvas
            related_node_ids = []
            for node in canvas_data.get('nodes', []):
                node_file = str(node.get('file', ''))
                if any(src in node_file for src in related_sources):
                    related_node_ids.append(node['id'])
            
            # Calculate position (cluster near related nodes)
            if related_node_ids:
                related_nodes = [n for n in canvas_data['nodes'] if n['id'] in related_node_ids]
                if related_nodes:
                    avg_x = sum(n.get('x', 0) for n in related_nodes) / len(related_nodes)
                    avg_y = sum(n.get('y', 0) for n in related_nodes) / len(related_nodes)
                    new_x = avg_x + 50
                    new_y = avg_y + 50
                else:
                    new_x, new_y = 0, 0
            else:
                new_x, new_y = 0, 0
            
            # Create new node
            new_node_id = f"node_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            rel_note_path = note_path.relative_to(vault_path)
            new_node = {
                'id': new_node_id,
                'type': 'file',
                'file': str(rel_note_path).replace('\\', '/'),
                'x': int(new_x),
                'y': int(new_y),
                'width': 400,
                'height': 300,
                'color': '5'
            }
            
            canvas_data['nodes'].append(new_node)
            
            # Create edges to related nodes (limit 5)
            for related_id in related_node_ids[:5]:
                edge_id = f"edge_{new_node_id}_{related_id}"
                canvas_data['edges'].append({
                    'id': edge_id,
                    'fromNode': new_node_id,
                    'toNode': related_id,
                    'color': '5',
                    'label': 'crystallized from'
                })
            
            # Save canvas
            canvas_path.write_text(json.dumps(canvas_data, indent=2), encoding='utf-8')
            connection_count = len(related_node_ids)
            
        except Exception as e:
            logger.warning(f"Could not update canvas: {e}")
            connection_count = 0
        
        # 4. Mark in memory store
        safe_execute(
            lambda: mark_crystallized(st.session_state.conversation_id, str(note_path)),
            fallback_value=False,
            error_message="Could not mark as crystallized"
        )
        
        return note_path, connection_count
    
    except Exception as e:
        logger.error(f"Error in crystallize_with_canvas_integration: {e}")
        return None, 0

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

# === RAG TRANSPARENCY COMPONENT ===
def render_rag_transparency():
    """Show RAG context being used with feedback mechanism"""
    if not st.session_state.show_context:
        return
    
    if not st.session_state.chat_history:
        return
    
    last_entry = st.session_state.chat_history[-1]
    query = last_entry.get('question', '')
    sources = last_entry.get('sources', [])
    
    if not query or not sources:
        return
    
    # Use cached RAG context retrieval
    try:
        context_hash = _compute_context_hash(st.session_state.chat_history, st.session_state.settings)
        chunks = safe_execute(
            lambda: get_rag_context_cached(
                context_hash, 
                query, 
                st.session_state.settings.get('top_k', 8),
                st.session_state.settings
            ),
            fallback_value=[],
            error_message="Could not load RAG context"
        )
    except Exception as e:
        logger.error(f"Error in render_rag_transparency: {e}")
        chunks = []
    
    # If no chunks from cache, use sources from last entry
    if not chunks and sources:
        chunks = []
        for idx, source in enumerate(sources[:5]):
            chunks.append({
                'id': f"chunk_{idx}",
                'source': source.get('source', 'unknown') if isinstance(source, dict) else str(source),
                'score': source.get('score', 0.5) if isinstance(source, dict) else 0.5,
                'preview': source.get('preview', '') if isinstance(source, dict) else '',
                'content': source.get('content', '') if isinstance(source, dict) else ''
            })
    
    if not chunks:
        return
    
    with st.expander(f"🧬 Active Context ({len(chunks)} chunks)", expanded=False):
        st.caption("The system is using these knowledge fragments:")
        
        for chunk in chunks:
            score = chunk.get('score', 0.5)
            score_class = "relevance-high" if score >= 0.7 else ("relevance-medium" if score >= 0.4 else "relevance-low")
            
            st.markdown(f"""
            <div class="rag-chunk">
                <div>
                    <strong>{chunk.get('source', 'unknown')}</strong>
                    <span class="relevance-badge {score_class}">
                        {score:.0%}
                    </span>
                </div>
                <p style="color: rgba(255,255,255,0.7); font-size: 0.9rem; margin-top: 8px;">
                    {chunk.get('preview', chunk.get('content', '')[:150])}
                </p>
            </div>
            """, unsafe_allow_html=True)
            
            # Feedback buttons
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("↑ Boost", key=f"boost_{chunk['id']}", help="Increase relevance"):
                    success = adjust_chunk_relevance(
                        chunk_id=chunk['id'], 
                        source=chunk.get('source', ''),
                        adjustment=0.1,
                        conversation_id=st.session_state.conversation_id,
                        query=query
                    )
                    if success:
                        st.success("✓ Boosted!")
                        st.rerun()
            with col2:
                if st.button("↓ Lower", key=f"lower_{chunk['id']}", help="Decrease relevance"):
                    success = adjust_chunk_relevance(
                        chunk_id=chunk['id'], 
                        source=chunk.get('source', ''),
                        adjustment=-0.1,
                        conversation_id=st.session_state.conversation_id,
                        query=query
                    )
                    if success:
                        st.info("✓ Lowered!")
                        st.rerun()

# NOW open the main container - AFTER sidebar is fully rendered
st.markdown('<div class="main-container">', unsafe_allow_html=True)

# When sidebar is collapsed, show expand chevron in main area
if st.session_state.get("sidebar_collapsed", False):
    st.markdown("""
    <div class="main-chevron" onclick="toggleSidebarExpand()">⟩</div>
    """, unsafe_allow_html=True)

# Render header (after sidebar and container setup)
render_header()

if st.session_state.current_page == "chat":
    # Phase 1: Chat interface as default
    
    # Chat container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    
    # RAG Transparency Component (Phase 3)
    safe_execute(
        lambda: render_rag_transparency(),
        fallback_value=None,
        error_message="Could not render RAG transparency"
    )
    
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
                    # Use new canvas-integrated crystallization
                    note_path, connection_count = crystallize_with_canvas_integration(
                        conversation_history=st.session_state.chat_history
                    )
                    
                    if note_path:
                        # Also call original crystallize for backward compatibility
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
                        
                        success_msg = f"✅ Conversation crystallized → `{note_path.name}`"
                        if connection_count > 0:
                            success_msg += f"\n✓ Added to canvas with {connection_count} connections"
                        st.success(success_msg)
                    else:
                        st.error("Failed to crystallize conversation")
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
                                
                                # Use canvas-integrated crystallization
                                note_path, connection_count = crystallize_with_canvas_integration(
                                    entry=last_entry
                                )
                                
                                # Also call original for backward compatibility
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
                                
                                toast_msg = f"Crystallized → `{filepath.split('/')[-1]}`"
                                if note_path and connection_count > 0:
                                    toast_msg += f" (+ {connection_count} canvas connections)"
                                st.toast(toast_msg, icon="✅")
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
                    # Add system message using atomic state update
                    system_message = {
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
                    }
                    update_conversation_state(system_message)
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
            new_message_entry = {
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
            }
            
            # Use atomic state update (Phase 5)
            update_conversation_state(new_message_entry)
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
                
                # Use canvas-integrated crystallization
                note_path, connection_count = crystallize_with_canvas_integration(
                    entry=entry
                )
                
                # Also call original for backward compatibility
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
                
                toast_msg = f"Crystallized → `{filepath.split('/')[-1]}`"
                if note_path and connection_count > 0:
                    toast_msg += f" (+ {connection_count} canvas connections)"
                st.toast(toast_msg, icon="✅")
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

elif st.session_state.current_page == "cognitive_ide":
    # Cognitive IDE - Visual Chain Editor
    try:
        from src.components.chain_editor import render_chain_editor
        render_chain_editor()
    except Exception as e:
        logger.error(f"Error rendering Cognitive IDE: {e}")
        st.error(f"Failed to load Cognitive IDE: {e}")
        st.info("Make sure all dependencies are installed: pip install pyyaml")

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

# Close main container div
st.markdown('</div>', unsafe_allow_html=True)

# Keyboard shortcuts JavaScript moved to hidden component at top
