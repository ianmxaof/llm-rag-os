# LLM RAG OS - Local RAG Operating System

A private, local RAG (Retrieval-Augmented Generation) system powered by Ollama. Build your own knowledge base with automatic model management, document refinement, and corpus visualization.

## Features

- **Ollama Integration**: Clean, programmatic model loading/unloading (no GUI hacks)
- **Auto-Unload**: Models automatically unload after embedding to free RAM
- **Fast Ingestion**: Batch and single-file ingestion with Ollama embeddings
- **Streamlit GUI**: Beautiful web interface for managing your RAG pipeline
- **FastAPI Backend**: RESTful API for programmatic control
- **ChromaDB**: Vector store for semantic search
- **Docker Support**: Containerized deployment ready
- **CI/CD**: GitHub Actions for automated testing

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) installed and running
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/llm-rag-os.git
   cd llm-rag-os
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Install and start Ollama**
   ```bash
   # Windows
   winget install ollama
   
   # macOS
   brew install ollama
   
   # Linux
   curl -fsSL https://ollama.com/install.sh | sh
   
   # Start Ollama service
   ollama serve
   ```

4. **Pull required models**
   ```bash
   ollama pull nomic-embed-text           # For embeddings
   ollama pull mistral:7b-instruct-q5_K_M # For chat (optional)
   ```

5. **Start the backend**
   ```bash
   # Windows
   scripts\run_backend.bat
   
   # Linux/macOS
   ./scripts/run_backend.sh
   
   # Or manually
   uvicorn backend.app:app --reload
   ```

6. **Start the Streamlit GUI** (in a new terminal)
   ```bash
   streamlit run src/app/streamlit_app.py
   ```

7. **Open your browser**
   - Streamlit: http://localhost:8501
   - FastAPI docs: http://localhost:8000/docs

## Usage

### Single File Ingestion

1. Place a `.md` file in `knowledge/inbox/`
2. Open Streamlit → Ingest tab
3. Click "Embed Now (Load → Embed → Unload)"
4. Model loads, embeds, and unloads automatically

### Batch Ingestion

1. Place files in `knowledge/inbox/`
2. Use the batch ingestion feature in Streamlit
3. Or run via API:
   ```bash
   curl -X POST "http://localhost:8000/ingest/run?path=knowledge/inbox&fast=true&parallel=true"
   ```

### API Usage

```python
import requests

# Check Ollama status
response = requests.get("http://localhost:8000/ollama/status")
print(response.json())

# Ingest a file
response = requests.post(
    "http://localhost:8000/ingest/file",
    json={"path": "knowledge/inbox/myfile.md"}
)
print(response.json())

# Query your knowledge base
response = requests.get("http://localhost:8000/library/list")
print(response.json())
```

## Docker Deployment

### Build and run with Docker Compose

```bash
docker-compose up --build
```

This will:
- Start Ollama service
- Start FastAPI backend (port 8000)
- Start Streamlit GUI (port 8501)

### Build Docker image manually

```bash
docker build -t rag-os:v0.1 .
docker run -p 8000:8000 -p 8501:8501 -p 11434:11434 rag-os:v0.1
```

## Project Structure

```
llm-rag-os/
├── backend/              # FastAPI backend
│   ├── controllers/     # API route handlers
│   │   ├── ollama.py   # Ollama integration
│   │   ├── ingest.py   # Ingestion endpoints
│   │   └── ...
│   ├── models.py        # Database models
│   └── app.py          # FastAPI app
├── scripts/             # Utility scripts
│   ├── embed_worker.py  # Background embedding worker
│   ├── preprocess.py    # Text preprocessing
│   └── config.py       # Configuration
├── src/                 # Client utilities
│   ├── api_client.py   # FastAPI client
│   └── rag_utils.py    # RAG utilities
├── tests/              # Test suite
│   └── smoke_test.py   # Smoke tests
├── knowledge/          # Knowledge base (gitignored)
│   ├── inbox/          # Drop files here
│   ├── processed/      # Processed files
│   └── archived/      # Archived files
├── chroma/             # Vector store (gitignored)
├── src/
│   ├── app/
│   │   └── streamlit_app.py  # Streamlit GUI
│   └── ...                   # Other source modules
├── Dockerfile          # Docker configuration
├── docker-compose.yml  # Docker Compose config
└── requirements.txt    # Python dependencies
```

## Configuration

Environment variables (optional, defaults provided):

```bash
# Ollama settings
OLLAMA_API_BASE=http://localhost:11434/api
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=mistral:7b-instruct-q5_K_M

# Embedding settings
EMBED_MODEL_NAME=BAAI/bge-small-en-v1.5
CHUNK_SIZE=1500
CHUNK_OVERLAP=200

# Vector store
COLLECTION_NAME=llm_docs
```

## Development

### Running Tests

```bash
# Run smoke tests
python tests/smoke_test.py

# Or with pytest
pytest tests/
```

### CI/CD

GitHub Actions automatically runs smoke tests on version tags:

```bash
git tag -a v0.1 -m "First release"
git push origin v0.1
```

## API Documentation

Once the backend is running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Key Endpoints

- `GET /health` - Health check
- `GET /ollama/status` - Ollama service status
- `POST /ollama/embed` - Embed texts
- `POST /ingest/file` - Ingest single file
- `POST /ingest/run` - Run batch ingestion
- `GET /library/list` - List documents
- `GET /visualize/umap` - Get UMAP coordinates

## Troubleshooting

### Ollama not responding

```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Restart Ollama
ollama serve
```

### Model not found

```bash
# Pull the required model
ollama pull nomic-embed-text
```

### Port already in use

Change ports in:
- `scripts/run_backend.bat` / `scripts/run_backend.sh` (FastAPI)
- `src/app/streamlit_app.py` (Streamlit)

## Roadmap

- [x] Ollama integration with auto-unload
- [x] Single-file ingestion
- [x] Docker support
- [x] CI/CD pipeline
- [ ] Graph visualization (Obsidian-style)
- [ ] Plugin system
- [ ] Refine loop with versioning
- [ ] Obsidian sync

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [Ollama](https://ollama.com) for local LLM inference
- [ChromaDB](https://www.trychroma.com/) for vector storage
- [FastAPI](https://fastapi.tiangolo.com/) for the API framework
- [Streamlit](https://streamlit.io/) for the GUI

## Version

**v0.1** - Initial release with Ollama integration

---

**Built with ❤️ for local, private AI**

