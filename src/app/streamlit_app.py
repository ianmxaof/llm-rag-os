import os
import sys
import time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import webbrowser

# Add parent directory to path so we can import from src
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src import rag_utils
from src.api_client import (
    check_backend_available, get_llm_status, start_lm_studio, stop_lm_studio,
    get_ollama_status, list_documents, get_document, update_document_metadata, 
    run_ingestion, ingest_file, get_umap_coords, get_corpus_stats,
    get_graph_nodes, get_graph_edges
)

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
    st.caption("Query your local knowledge base. Make sure the Mistral server (LM Studio / llama.cpp) is running.")
    
    with st.sidebar:
        st.header("Settings")
        top_k = st.slider("Top-K context chunks", min_value=1, max_value=10, value=rag_utils.DEFAULT_K)
        show_context = st.checkbox("Show retrieved context", value=False)
        st.markdown("**Model endpoint:**")
        st.code(os.getenv("LOCAL_MODEL_URL", "http://127.0.0.1:1234/v1/chat/completions"), language="bash")
        st.markdown("**Embedding model:**")
        st.code(rag_utils.EMBED_MODEL_NAME, language="bash")
    
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    
    question = st.chat_input("Ask a question about your documents...")
    
    if question:
        with st.spinner("Thinking..."):
            answer, metas, context = rag_utils.answer_question(question, k=top_k)
            sources = rag_utils.format_sources(metas)
        st.session_state.chat_history.append(
            {"question": question, "answer": answer, "sources": sources, "context": context}
        )
    
    for entry in reversed(st.session_state.chat_history):
        st.markdown(f"**You:** {entry['question']}")
        st.markdown(f"**Assistant:** {entry['answer']}")
        if entry["sources"]:
            st.markdown("**Sources:**")
            for src in entry["sources"]:
                st.markdown(f"- {src}")
        if show_context:
            with st.expander("Retrieved context"):
                st.text(entry["context"])
        st.markdown("---")

# Library Tab
with tabs[2]:
    st.header("Library")
    
    if backend_available:
        if st.button("Refresh Library"):
            st.session_state.library_data = list_documents(limit=100)
        
        if "library_data" not in st.session_state:
            st.session_state.library_data = list_documents(limit=100)
        
        data = st.session_state.library_data
        
        if "error" in data:
            st.error(f"Error loading library: {data['error']}")
        else:
            st.metric("Total Documents", data.get("total", 0))
            
            for item in data.get("items", []):
                with st.expander(f"{item.get('source_path', 'Unknown')} (v{item.get('ingest_version', 1)})"):
                    st.write(f"**Status:** {item.get('status', 'unknown')}")
                    st.write(f"**Tags:** {', '.join(item.get('tags', []))}")
                    st.write(f"**Notes:** {item.get('notes', '')}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"View Details", key=f"view_{item['id']}"):
                            st.session_state.selected_doc_id = item['id']
                    with col2:
                        if st.button(f"Open in Cursor", key=f"open_{item['id']}"):
                            # TODO: Implement open in Cursor
                            st.info("Open in Cursor functionality coming soon")
    else:
        st.warning("Backend not available. Start the FastAPI backend to use the Library.")

# Ingest Tab
with tabs[3]:
    st.header("Ingest")
    
    if backend_available:
        st.subheader("Single File Ingestion (Ollama)")
        
        # File Browser Section
        st.markdown("#### Browse Local Files")
        default_dir = str(Path("knowledge/inbox").resolve())
        
        if "current_dir" not in st.session_state:
            st.session_state.current_dir = default_dir
        if "show_browser" not in st.session_state:
            st.session_state.show_browser = False
        
        col_browse, col_close = st.columns([3, 1])
        with col_browse:
            if st.button("📁 Browse Files", key="browse_btn"):
                st.session_state.show_browser = True
                st.session_state.current_dir = default_dir
                st.rerun()
        
        if st.session_state.show_browser:
            st.markdown("---")
            col_dir, col_go, col_close_btn = st.columns([4, 1, 1])
            with col_dir:
                new_dir = st.text_input("Directory:", value=st.session_state.current_dir, key="dir_input")
            with col_go:
                if st.button("Go"):
                    if os.path.isdir(new_dir):
                        st.session_state.current_dir = new_dir
                        st.rerun()
            with col_close_btn:
                if st.button("Close"):
                    st.session_state.show_browser = False
                    st.rerun()
            
            if os.path.isdir(st.session_state.current_dir):
                st.markdown(f"**Contents of:** `{st.session_state.current_dir}`")
                try:
                    items = sorted(os.listdir(st.session_state.current_dir))
                    inbox_path = Path("knowledge/inbox").resolve()
                    current_path = Path(st.session_state.current_dir).resolve()
                    
                    for item in items:
                        item_path = os.path.join(st.session_state.current_dir, item)
                        try:
                            if os.path.isfile(item_path) and item.endswith(".md"):
                                col_file, col_copy = st.columns([3, 1])
                                with col_file:
                                    # Check if file is already in inbox
                                    item_resolved = Path(item_path).resolve()
                                    if item_resolved.parent == inbox_path:
                                        st.text(f"📄 {item} (already in inbox)")
                                    else:
                                        st.text(f"📄 {item}")
                                with col_copy:
                                    # Don't show copy button if already in inbox
                                    if item_resolved.parent != inbox_path:
                                        if st.button(f"Copy → inbox", key=f"copy_{item_path}"):
                                            try:
                                                target = inbox_path / item
                                                target.parent.mkdir(parents=True, exist_ok=True)
                                                
                                                # Handle duplicate filenames
                                                counter = 1
                                                while target.exists():
                                                    name_parts = item.rsplit(".", 1)
                                                    if len(name_parts) == 2:
                                                        new_name = f"{name_parts[0]}_{counter}.{name_parts[1]}"
                                                    else:
                                                        new_name = f"{item}_{counter}"
                                                    target = inbox_path / new_name
                                                    counter += 1
                                                
                                                shutil.copy2(item_path, str(target))
                                                st.success(f"✅ Copied to inbox: {target.name}")
                                                st.rerun()
                                            except PermissionError as pe:
                                                st.error(f"Permission denied: {pe}")
                                            except Exception as e:
                                                st.error(f"Error copying file: {e}")
                            elif os.path.isdir(item_path):
                                if st.button(f"📁 {item}/", key=f"dir_{item_path}"):
                                    st.session_state.current_dir = item_path
                                    st.rerun()
                        except PermissionError:
                            # Skip files/dirs we can't access
                            continue
                except PermissionError as pe:
                    st.error(f"Permission denied accessing directory: {pe}")
                except Exception as e:
                    st.error(f"Error listing directory: {e}")
            st.markdown("---")
        
        # Manual Path Input + Embed
        st.markdown("#### Manual File Path")
        file_path = st.text_input("File path to ingest (.md)", str(Path("knowledge/inbox").resolve() / "test.md"))
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Embed Now (Load → Embed → Unload)", type="primary"):
                if file_path:
                    file_obj = Path(file_path)
                    if file_obj.exists() and file_obj.suffix.lower() == ".md":
                        with st.spinner("Loading model, embedding, unloading..."):
                            result = ingest_file(str(file_obj.resolve()))
                            if result.get("success"):
                                st.success(f"✅ Done! {result.get('message', '')} Model unloaded. RAM freed.")
                            else:
                                st.error(f"❌ Error: {result.get('message', 'Unknown error')}")
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
                        else:  # chunk
                            color = "#00aaff"
                            size = 15
                            shape = "dot"
                        
                        title = node["metadata"].get("text", node["label"])
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

