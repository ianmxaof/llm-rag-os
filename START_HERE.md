# Local RAG Kit — Powercore

Buyer entry for the store zip. Keep the deep engineer README as `README.md` in repo; packers should place this file at the zip root as `START_HERE.md`.

Your notes stay on your machine. This pack is the local-first RAG stack: embeddings, vault ingest, prompt store hooks, and a FastAPI backend.

## What you get

- `backend/` — API service
- `config/` — starter config templates
- `docker/` — optional container path
- `eval/` — evaluation helpers
- `requirements.txt` — Python deps
- Longer engineer notes live in `README.md`

## Quick start (Windows)

1. Install **Python 3.11+** and **Ollama**.
2. From the extracted folder:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

3. Copy sample env under `config/` to a local `.env`.
4. `ollama pull nomic-embed-text` and a chat model (e.g. `mistral`).
5. Follow **Running the System** in `README.md`.

Product: https://powercore.app
