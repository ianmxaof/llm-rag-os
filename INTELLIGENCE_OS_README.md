# Intelligence OS Integration Guide

This guide covers the Frontier AI Intelligence OS integration - a minimal, laptop-friendly pipeline that automatically curates and ingests high-signal content from GitHub, RSS feeds, arXiv, and Reddit.

## Quick Start (Path A - 5 minutes)

### 1. Setup Minimal Docker Stack

```bash
# Run setup script
./scripts/setup_intelligence_os.sh  # Linux/macOS
# OR
.\scripts\setup_intelligence_os.ps1  # Windows

# Edit .env.intelligence and add your API keys
# Then start services
docker compose -f docker/intelligence-minimal.yml up -d
```

### 2. Link Output to Existing System

```bash
# Link output folder to your inbox
ln -s "$(pwd)/intelligence-data/out" "knowledge/inbox/intelligence-feed"  # Linux/macOS
# OR (Windows PowerShell)
New-Item -ItemType SymbolicLink -Path "knowledge/inbox/intelligence-feed" -Target "$(pwd)/intelligence-data/out"
```

### 3. Import N8N Workflow

1. Open http://localhost:5678
2. Login with admin / changeme (change password immediately)
3. Import the workflow JSON (provided separately)
4. Add credentials: Anthropic API key, GitHub token
5. Activate workflow

**Result**: 3-15 high-signal notes per day (only permanence ≥8/10) appear in your inbox.

## Native Integration (Path B - This Weekend)

### Setup Sources

```python
# Create sources via API or directly in database
from backend.models import Source, SessionLocal

db = SessionLocal()

# GitHub source
github_source = Source(
    source_type="github",
    name="Frontier AI Engineers",
    config={
        "repos": ["anthropics/anthropic", "openai/openai", "xai-org/grok"],
        "users": ["samaltman", "dario-amodei"],
    },
    enabled=True,
)
db.add(github_source)

# RSS source
rss_source = Source(
    source_type="rss",
    name="AI Blogs",
    config={
        "feeds": [
            "https://www.anthropic.com/index.xml",
            "https://openai.com/blog/rss.xml",
        ],
    },
    enabled=True,
)
db.add(rss_source)

db.commit()
```

### Run Pipeline

```bash
# Initialize database tables
python scripts/intelligence_pipeline.py --init-db

# Run pipeline (processes last 24 hours)
python scripts/intelligence_pipeline.py --since-hours 24

# Or run continuously (every 15 minutes)
# Add to cron or use scheduler service
```

### API Endpoints

- `GET /sources/` - List all sources
- `POST /sources/` - Create new source
- `POST /sources/{id}/collect` - Manually trigger collection
- `GET /refinement/` - List refined documents
- `GET /queue/stats` - Queue statistics
- `GET /alerts/` - Secret scan alerts

## Configuration

### Environment Variables

Add to `.env.intelligence`:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional
GITHUB_TOKENS=ghp_...
N8N_PASSWORD=changeme
TRUFFLEHOG_ENABLED=false
SECRET_ALERT_WEBHOOK=https://...
```

### Source Configuration

Sources are stored in the database. Use the API or Streamlit UI to manage them.

## Resource Usage

- **Path A (Docker)**: 3-4 GB idle, ~7 GB peak
- **Path B (Native)**: 6-12 GB idle (API refinement), 22-28 GB (local LLM)
- **Storage**: ~300 KB/day (3-15 notes/day), <150 MB/year

## Control & Safety

### Instant Kill Switches

1. **N8N UI**: Click "Pause" → everything freezes
2. **Docker**: `docker compose -f docker/intelligence-minimal.yml pause`
3. **Symlink**: Delete symlink → no more files land in inbox
4. **Workflow**: Deactivate in N8N → stops processing

### Monitoring

- **N8N UI** (http://localhost:5678): See what flows through, what gets SKIPped
- **File system**: Monitor `intelligence-data/out/` folder
- **Streamlit**: New "Intelligence Feed" tab (coming in Phase 3)

## Integration with Existing System

### No Changes Required

- Existing RAG pipeline (`scripts/ingest.py`) continues working unchanged
- Streamlit UI remains untouched
- ChromaDB and SQLite databases unaffected
- Obsidian vault structure unchanged

### How It Works

1. **Collection**: Sources are polled every 15-60 minutes
2. **Refinement**: LLM curator SKIPs 95-98% of items (only permanence ≥8/10 survives)
3. **Secret Scanning**: Optional TruffleHog scanning for security
4. **Ingestion**: Refined items are queued and can be ingested via existing pipeline

## Troubleshooting

### No items appearing

- Check N8N workflow is activated
- Verify API keys are correct
- Check logs: `docker compose -f docker/intelligence-minimal.yml logs`

### Too many/few items

- Adjust permanence threshold in refinement prompt (default: ≥8/10)
- Modify curator prompt to be more/less strict

### High RAM usage

- Use API-based refinement (Claude) instead of local Ollama
- Reduce collection frequency
- Lower permanence threshold to filter more aggressively

## Next Steps

1. **Tonight**: Deploy Path A, get immediate data
2. **This Weekend**: Implement Path B using Path A's data as seed
3. **Next Week**: Add Streamlit UI tab for monitoring
4. **Future**: Add more sources, customize refinement prompts

