import os
from pathlib import Path

import streamlit as st

from src import rag_utils
from src.api_client import (
    check_backend_available, get_llm_status, start_lm_studio, stop_lm_studio,
    get_ollama_status, list_documents, get_document, update_document_metadata, 
    run_ingestion, ingest_file, get_umap_coords, get_corpus_stats
)

st.set_page_config(page_title="Powercore RAG Control Panel", layout="wide")

st.title("🔍 Powercore RAG Control Panel")
st.caption("Local RAG pipeline with Ollama integration")

# Check backend availability
backend_available = check_backend_available()
if not backend_available:
    st.warning("⚠️ FastAPI backend is not running. Start it with: `python -m backend.app` or `run_backend.bat`")

# Create tabs
tabs = st.tabs(["Dashboard", "Chat", "Library", "Ingest", "Visualize", "Prompts"])

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

# Prompts Tab
with tabs[5]:
    st.header("Prompt Repository")
    st.info("Prompt repository functionality coming soon. Use the FastAPI backend directly for now.")

