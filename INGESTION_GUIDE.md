# Ingestion Guide

This guide covers the enhanced ingestion pipeline with fast PDF processing and automated file watching.

## Quick Start

### Standard Ingestion

```bash
# Basic ingestion (uses Unstructured for PDFs)
python scripts/ingest.py

# Fast mode (uses PyMuPDF - 5-10x faster for PDFs)
python scripts/ingest.py --fast

# Parallel processing (uses multiple CPU cores)
python scripts/ingest.py --parallel

# Combine both optimizations
python scripts/ingest.py --fast --parallel

# Target specific source directory
python scripts/ingest.py --src knowledge/hacking

# Incremental update (don't reset vector store)
python scripts/ingest.py --no-reset --fast --parallel
```

### PowerShell Wrapper

```powershell
# Basic ingestion
.\scripts\run_ingest.ps1

# Fast mode with parallel processing
.\scripts\run_ingest.ps1 -Fast -Parallel

# Incremental update of specific source
.\scripts\run_ingest.ps1 -NoReset -Fast -Parallel -ExtraSource "knowledge/hacking"
```

## Automated File Watching

The `watch_and_ingest.py` script monitors `knowledge/inbox/` for new files and automatically:
1. Converts PDFs to Markdown (using PyMuPDF)
2. Classifies content semantically (using LM Studio or OpenAI)
3. Routes files to appropriate subfolders (`hacking`, `programming`, `ai`, etc.)
4. Triggers ingestion to update the vector store

### Setup

1. Create the inbox folder:
   ```bash
   mkdir knowledge/inbox
   ```

2. Ensure LM Studio is running (or set `OPENAI_API_KEY` in `.env`)

3. Start the watcher:
   ```bash
   python scripts/watch_and_ingest.py
   ```

### Usage

```bash
# Start watching (auto-ingests after processing files)
python scripts/watch_and_ingest.py

# Process existing files in inbox first
python scripts/watch_and_ingest.py --process-existing

# Watch without auto-ingestion (manual control)
python scripts/watch_and_ingest.py --no-ingest

# Adjust polling interval (when watchdog unavailable)
python scripts/watch_and_ingest.py --poll-interval 5
```

### Workflow

1. Drop PDFs, Markdown, or text files into `knowledge/inbox/`
2. The watcher detects new files and processes them
3. Files are converted (if PDF), classified, and moved to category folders
4. Ingestion runs automatically to update ChromaDB
5. Processed PDFs are moved to `knowledge/inbox/_processed/`
6. Errors are logged to `knowledge/inbox/_error/`

## Performance Tips

### Fast Mode (`--fast`)

- Uses PyMuPDF instead of Unstructured for PDFs
- **5-10x faster** for text-based PDFs
- Less layout-aware (may lose some formatting)
- Recommended for bulk ingestion of ebooks/articles

**Installation:**
```bash
pip install pymupdf pymupdf4llm
```

### Parallel Processing (`--parallel`)

- Processes multiple files concurrently
- Uses all available CPU cores
- **2-4x speedup** on multi-core systems
- Best for large batches (50+ files)

### Combined Optimization

For maximum speed on large PDF collections:
```bash
python scripts/ingest.py --fast --parallel --src knowledge/hacking
```

Expected performance on ThinkPad i5 (4 cores):
- Standard: ~120 minutes for 100 PDFs (1 GB)
- Fast + Parallel: ~20-30 minutes for same batch

## Dependencies

### Required
- `unstructured[all]` - Rich document format support
- `sentence-transformers` - Embedding generation
- `chromadb` - Vector database

### Optional (for fast mode)
- `pymupdf` - Fast PDF extraction
- `pymupdf4llm` - PDF to Markdown conversion

### Optional (for file watching)
- `watchdog` - File system monitoring (falls back to polling if unavailable)
- `openai` - Semantic classification (or use LM Studio)

Install all optional dependencies:
```bash
pip install pymupdf pymupdf4llm watchdog
```

## Environment Variables

Add to `.env`:

```env
# For semantic classification in watch_and_ingest.py
OPENAI_API_KEY=sk-...                    # OpenAI API key (fallback)
OPENAI_API_BASE=http://localhost:1234/v1  # LM Studio endpoint (optional)
LMSTUDIO_API_KEY=lm-studio              # LM Studio API key (optional)

# For ingestion
EMBED_MODEL_NAME=BAAI/bge-small-en-v1.5  # Embedding model
RAG_TOP_K=3                              # Retrieval top-k
```

## Troubleshooting

### PyMuPDF not available
If `--fast` mode fails:
```bash
pip install pymupdf pymupdf4llm
```

### Watchdog not available
The watcher falls back to polling mode (checks every 10 seconds). Install for better performance:
```bash
pip install watchdog
```

### Classification fails
If semantic classification fails, the watcher uses keyword-based fallback. Ensure:
- LM Studio is running (if using local model)
- `OPENAI_API_KEY` is set (if using OpenAI)
- Network connectivity (if using OpenAI cloud)

### Ingestion timeout
For very large batches, ingestion may take time. The watcher has a 1-hour timeout. For manual runs, you can cancel and resume with `--no-reset`.

## File Organization

Recommended structure:
```
knowledge/
├── inbox/              # Drop new files here
│   ├── _processed/    # Processed PDFs
│   └── _error/        # Failed conversions
├── hacking/           # Security/hacking content
├── programming/       # Code/development content
├── ai/                # AI/ML content
├── networking/        # Network/IT content
├── linux/             # Linux/system content
├── windows/           # Windows-specific content
└── other/             # Uncategorized content
```

