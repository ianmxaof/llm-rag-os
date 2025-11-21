"""
Unified Elite Prompt Ingester
------------------------------
Automated ingester for elite prompts from frontier AI repos and developer feeds.
Supports GitHub API polling, Hugging Face polling, and GitHub webhook real-time events.

Features:
- Robust: backoff retries, rate limit handling, signature verification (optional secret)
- Idempotent, semantic dedupe, Ollama scoring
- Versioning support (immutable history)

Run modes:
  python scripts/prompt_ingester.py --poll          # Scheduled cron
  python scripts/prompt_ingester.py --webhook       # Real-time server
"""

import argparse
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add parent directory to path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import pyarrow as pa
import requests
from scripts.config import (
    LANCE_DB_PATH,
    OBSIDIAN_EMBED_MODEL,
    PROMPTS_CURATED_COLLECTION,
    PROMPT_MIN_SCORE,
    ENABLE_HYBRID_SEARCH,
    OLLAMA_API_BASE,
    OLLAMA_CHAT_MODEL,
)

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    print("ERROR: lancedb is required. Install with: pip install lancedb")
    sys.exit(1)

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    print("ERROR: fastembed is required. Install with: pip install fastembed")
    sys.exit(1)

try:
    import backoff
    BACKOFF_AVAILABLE = True
except ImportError:
    print("WARNING: backoff not available. Install with: pip install backoff")
    BACKOFF_AVAILABLE = False

try:
    from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
    from pydantic import BaseModel
    import uvicorn
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False
    print("WARNING: FastAPI not available. Webhook mode disabled. Install with: pip install fastapi uvicorn")


# GitHub repos to monitor
GITHUB_REPOS = [
    "hegelai/prompttools",
    "langchain-ai/langsmith",
    "microsoft/promptflow",
    "stanfordnlp/dspy",
    "infiniflow/ragflow",
    "SciPhi-AI/AutoRAG",
    "langgenius/dify",
]

# Hugging Face repos to monitor
HF_REPOS = [
    "cognitivecomputations/dolphin",
    "ehartford/Wizard-Vicuna-30B-Uncensored",
    "lmsys/vicuna-13b-v1.5",
    "NousResearch/Hermes-2-Pro-Mistral-7B",
    "mlabonne/NeuralHermes-2.5-Mistral-7B",
    "teknium/OpenHermes-2.5",
]

# API configuration
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
HF_TOKEN = os.getenv("HUGGINGFACE_TOKEN")
WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET")

HEADERS_GH = {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "PromptIngester/2.0"
}
if GITHUB_TOKEN:
    HEADERS_GH["Authorization"] = f"token {GITHUB_TOKEN}"

HEADERS_HF = {
    "User-Agent": "PromptIngester/2.0"
}
if HF_TOKEN:
    HEADERS_HF["Authorization"] = f"Bearer {HF_TOKEN}"

# State file
STATE_FILE = Path(ROOT_DIR) / "data" / "prompt_ingester_state.json"
STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

if STATE_FILE.exists():
    with open(STATE_FILE, "r") as f:
        state = json.load(f)
    last_poll = datetime.fromisoformat(state.get("last_poll", "2025-01-01T00:00:00"))
    processed_hashes = set(state.get("processed", []))
else:
    last_poll = datetime(2025, 1, 1)
    state = {"last_poll": last_poll.isoformat(), "processed": []}
    processed_hashes = set()


def extract_and_score_prompt(title: str, body: str, link: str, author: str = "Unknown") -> Optional[Tuple[str, float, str]]:
    """
    Use Ollama to detect/extract prompt from entry, score it (0-10).
    Returns (prompt_text, score, category) or None.
    """
    full_text = f"{title}\n{body or ''}"[:3000]  # Truncate for tokens
    
    extract_prompt = f"""Analyze this entry from a frontier AI repo (GitHub or Hugging Face).
Extract if it contains a high-value prompt (system/user prompt for reasoning/coding/agents/redteam).

Entry: {full_text}

If yes, output ONLY:
PROMPT_START
{{exact prompt text}}
PROMPT_END
CATEGORY: {{one word category}}
SCORE: {{score}}/10

If no prompt, output: NO_PROMPT"""
    
    try:
        import httpx
        ollama_url = OLLAMA_API_BASE.replace("/api", "") + "/api/generate"
        response = httpx.post(
            ollama_url,
            json={
                "model": OLLAMA_CHAT_MODEL,
                "prompt": extract_prompt,
                "stream": False,
            },
            timeout=120,
        )
        
        if response.status_code != 200:
            return None
        
        output = response.json().get("response", "").strip()
        
        if "NO_PROMPT" in output:
            return None
        
        if "PROMPT_START" in output and "PROMPT_END" in output:
            prompt_text = output.split("PROMPT_START")[1].split("PROMPT_END")[0].strip()
            lines = output.split("\n")
            category = next((l.split(": ")[1] for l in lines if "CATEGORY:" in l), "general").strip()
            score_str = next((l.split(": ")[1] for l in lines if "SCORE:" in l), "0").strip()
            score = float(score_str.split("/")[0])
            
            if score > PROMPT_MIN_SCORE:
                return prompt_text, score, category
    except Exception as e:
        print(f"[WARN] Prompt extraction failed: {e}")
    
    return None


def ingest_prompt(
    prompt_text: str,
    author: str,
    source: str,
    category: str,
    score: float,
    platform: str,
    db: lancedb.LanceDB,
    table: lancedb.Table,
    embedder: TextEmbedding
) -> int:
    """
    Ingest a prompt into LanceDB with versioning support.
    Returns 1 if inserted, 0 if skipped.
    """
    entry_hash = hashlib.sha256((prompt_text + source).encode()).hexdigest()
    if entry_hash in processed_hashes:
        return 0
    
    # Semantic dedupe
    try:
        query_vector = embedder.embed_documents([prompt_text])[0]
        similar = table.search(query_vector).limit(1).to_list()
        if similar and similar[0].get("_distance", 1.0) < 0.05:
            print(f"Skipping similar prompt")
            processed_hashes.add(entry_hash)
            return 0
    except Exception:
        pass
    
    # Embed
    vector = embedder.embed_documents([prompt_text])[0]
    
    # Check if ID exists (for versioning)
    base_id = f"{platform}_{entry_hash[:8]}"
    try:
        existing = table.search(base_id).where(f"id LIKE '{base_id}_%'").limit(1).to_list()
        if existing:
            # Get latest version
            latest = max(existing, key=lambda x: x.get("version", 1))
            version = latest.get("version", 1) + 1
            previous_id = latest.get("id")
        else:
            version = 1
            previous_id = None
    except Exception:
        version = 1
        previous_id = None
    
    new_id = f"{base_id}_v{version}_{datetime.now().strftime('%Y%m%d')}"
    
    # Insert
    prompt_data = {
        "id": new_id,
        "prompt_text": prompt_text,
        "author": author,
        "source": source,
        "category": category,
        "score": float(score),
        "uses": 0,
        "version": version,
        "previous_id": previous_id,
        "last_used_at": None,
        "vector": vector,
        "fulltext": prompt_text,
    }
    
    try:
        table.add([prompt_data])
        processed_hashes.add(entry_hash)
        print(f"Ingested [{platform}] {new_id} (score: {score:.1f}, v{version}) – {source}")
        return 1
    except Exception as e:
        print(f"[ERROR] Failed to insert prompt: {e}")
        return 0


def poll_github_repo(repo: str, db: lancedb.LanceDB, table: lancedb.Table, embedder: TextEmbedding) -> int:
    """Poll GitHub repo for new prompts."""
    inserted = 0
    
    for endpoint in ["/commits", "/pulls", "/issues"]:
        url = f"https://api.github.com/repos/{repo}{endpoint}"
        params = {"since": last_poll.isoformat(), "per_page": 30}
        
        try:
            # Retry logic with backoff
            max_retries = 6
            for attempt in range(max_retries):
                try:
                    response = requests.get(url, headers=HEADERS_GH, params=params, timeout=15)
                    
                    if response.status_code == 429:  # Rate limit
                        retry_after = int(response.headers.get("Retry-After", 60))
                        print(f"Rate limited. Sleeping {retry_after} seconds.")
                        time.sleep(retry_after)
                        if attempt < max_retries - 1:
                            continue
                    
                    response.raise_for_status()
                    break
                except requests.exceptions.RequestException as e:
                    if attempt == max_retries - 1:
                        raise
                    wait_time = 2 ** attempt  # Exponential backoff
                    time.sleep(wait_time)
            data = response.json()
            
            if not isinstance(data, list):
                data = [data]
            
            for entry in data:
                title = entry.get("title") or entry.get("commit", {}).get("message", "")[:200]
                body = entry.get("body") or entry.get("commit", {}).get("message", "") or ""
                link = entry.get("html_url") or entry.get("url", "")
                author = entry.get("user", {}).get("login") or entry.get("commit", {}).get("author", {}).get("name", "Unknown")
                
                result = extract_and_score_prompt(title, body, link, author)
                if result:
                    prompt_text, score, category = result
                    inserted += ingest_prompt(prompt_text, author, link, category, score, "github", db, table, embedder)
        except Exception as e:
            print(f"GitHub poll error {repo}{endpoint}: {e}")
    
    return inserted


def poll_hf_repo(repo_id: str, db: lancedb.LanceDB, table: lancedb.Table, embedder: TextEmbedding) -> int:
    """Poll Hugging Face repo for new prompts."""
    inserted = 0
    
    # Poll recent commits
    commits_url = f"https://huggingface.co/api/models/{repo_id}/commits"
    try:
        response = requests.get(commits_url, headers=HEADERS_HF, timeout=15)
        if response.status_code == 200:
            commits = response.json()[:20]
            for commit in commits:
                commit_date = datetime.fromisoformat(commit["date"].replace("Z", "+00:00"))
                if commit_date <= last_poll:
                    continue
                
                title = commit["title"]
                body = "\n".join(commit.get("files", []))
                link = f"https://huggingface.co/{repo_id}/commit/{commit['id']}"
                author = commit["author"]["name"]
                
                result = extract_and_score_prompt(title, body, link, author)
                if result:
                    prompt_text, score, category = result
                    inserted += ingest_prompt(prompt_text, author, link, category, score, "hf", db, table, embedder)
    except Exception as e:
        print(f"HF commits poll error {repo_id}: {e}")
    
    return inserted


# Webhook server (if FastAPI available)
if FASTAPI_AVAILABLE:
    app = FastAPI(title="GitHub Prompt Webhook")
    
    class WebhookPayload(BaseModel):
        action: Optional[str] = None
        repository: Optional[dict] = None
        issue: Optional[dict] = None
        pull_request: Optional[dict] = None
        comment: Optional[dict] = None
        commits: Optional[List[dict]] = None
    
    @app.post("/webhook")
    async def github_webhook(request: Request, background_tasks: BackgroundTasks):
        """Handle GitHub webhook events."""
        if WEBHOOK_SECRET:
            signature = request.headers.get("X-Hub-Signature-256")
            if not signature:
                raise HTTPException(status_code=403, detail="No signature")
            body = await request.body()
            mac = hmac.new(WEBHOOK_SECRET.encode(), body, hashlib.sha256)
            if not hmac.compare_digest(mac.hexdigest(), signature.split("=")[1]):
                raise HTTPException(status_code=403, detail="Invalid signature")
        
        payload = await request.json()
        event = request.headers.get("X-GitHub-Event", "unknown")
        
        background_tasks.add_task(process_webhook_payload, payload, event)
        return {"status": "received"}
    
    def process_webhook_payload(payload: dict, event: str):
        """Process webhook payload in background."""
        # Initialize components
        db = lancedb.connect(str(LANCE_DB_PATH))
        table = db.open_table(PROMPTS_CURATED_COLLECTION)
        embedder = TextEmbedding(model_name=OBSIDIAN_EMBED_MODEL)
        
        inserted = 0
        repo = payload.get("repository", {}).get("full_name", "Unknown")
        
        if event == "push":
            for commit in payload.get("commits", []):
                result = extract_and_score_prompt(
                    commit["message"], "", commit["url"], commit["author"]["name"]
                )
                if result:
                    prompt_text, score, category = result
                    inserted += ingest_prompt(
                        prompt_text, commit["author"]["name"], commit["url"],
                        category, score, "github", db, table, embedder
                    )
        elif event in ["issues", "issue_comment"]:
            issue = payload.get("issue", {}) or payload.get("comment", {})
            result = extract_and_score_prompt(
                issue.get("title", ""), issue.get("body", ""),
                issue.get("html_url", ""), payload.get("sender", {}).get("login", "")
            )
            if result:
                prompt_text, score, category = result
                inserted += ingest_prompt(
                    prompt_text, payload.get("sender", {}).get("login", ""),
                    issue.get("html_url", ""), category, score, "github", db, table, embedder
                )
        elif event == "pull_request":
            pr = payload.get("pull_request", {})
            result = extract_and_score_prompt(
                pr.get("title", ""), pr.get("body", ""),
                pr.get("html_url", ""), pr.get("user", {}).get("login", "")
            )
            if result:
                prompt_text, score, category = result
                inserted += ingest_prompt(
                    prompt_text, pr.get("user", {}).get("login", ""),
                    pr.get("html_url", ""), category, score, "github", db, table, embedder
                )
        
        if inserted > 0:
            print(f"Webhook ingested {inserted} prompts from {repo}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll", action="store_true", help="Run polling once")
    parser.add_argument("--webhook", action="store_true", help="Start webhook server")
    args = parser.parse_args()
    
    if args.webhook and FASTAPI_AVAILABLE:
        print("Starting GitHub webhook server on http://0.0.0.0:3000/webhook")
        uvicorn.run(app, host="0.0.0.0", port=3000)
    
    elif args.poll or True:  # Default to poll
        # Initialize components
        db = lancedb.connect(str(LANCE_DB_PATH))
        table = db.open_table(PROMPTS_CURATED_COLLECTION)
        embedder = TextEmbedding(model_name=OBSIDIAN_EMBED_MODEL)
        
        inserted_total = 0
        
        for repo in GITHUB_REPOS:
            inserted_total += poll_github_repo(repo, db, table, embedder)
        
        for repo in HF_REPOS:
            inserted_total += poll_hf_repo(repo, db, table, embedder)
        
        # Save state
        state["last_poll"] = datetime.now().isoformat()
        state["processed"] = list(processed_hashes)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        
        print(f"Poll complete – {inserted_total} new elite prompts ingested.")

