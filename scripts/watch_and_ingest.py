"""
Watch and Ingest Pipeline
--------------------------
Monitors knowledge/inbox for new files, converts PDFs to Markdown,
classifies content semantically, and triggers ingestion automatically.

Features:
- Fast PDF conversion using PyMuPDF
- Semantic classification via LM Studio (local) or OpenAI (fallback)
- Automatic file routing to categorized subfolders
- Parallel processing for bulk operations
"""

import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Try PyMuPDF for fast PDF conversion
try:
    from pymupdf4llm import to_markdown as pymupdf_to_markdown

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Try watchdog for file monitoring
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False

# Try OpenAI client for classification
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Configuration
ROOT_DIR = Path(__file__).resolve().parent.parent
WATCH_DIR = ROOT_DIR / "knowledge" / "inbox"
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
PROCESSED_DIR = WATCH_DIR / "_processed"
ERROR_DIR = WATCH_DIR / "_error"
INGEST_SCRIPT = ROOT_DIR / "scripts" / "ingest.py"

# Ensure directories exist
WATCH_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
ERROR_DIR.mkdir(parents=True, exist_ok=True)

# Model configuration
USE_LMSTUDIO = bool(os.getenv("OPENAI_API_BASE", "").strip())
API_BASE = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")
API_KEY = os.getenv("OPENAI_API_KEY") or os.getenv("LMSTUDIO_API_KEY", "lm-studio")

# Categories for classification
CATEGORIES = ["hacking", "networking", "programming", "ai", "linux", "windows", "other"]

# Initialize OpenAI client if available
client = None
if OPENAI_AVAILABLE:
    try:
        client = OpenAI(base_url=API_BASE, api_key=API_KEY)
        # Quick health check for LM Studio
        if USE_LMSTUDIO:
            try:
                _ = client.models.list()
                print("[INFO] Using LM Studio local model for classification")
            except Exception:
                print("[WARN] LM Studio endpoint not available, falling back to OpenAI")
                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        else:
            print("[INFO] Using OpenAI cloud API for classification")
    except Exception as e:
        print(f"[WARN] Failed to initialize OpenAI client: {e}")
        client = None


def convert_pdf_to_markdown(pdf_path: Path) -> Optional[Path]:
    """Convert PDF to Markdown quickly using PyMuPDF."""
    if not PYMUPDF_AVAILABLE:
        print(f"[ERROR] PyMuPDF not available. Install with: pip install pymupdf pymupdf4llm")
        return None

    try:
        md_text = pymupdf_to_markdown(str(pdf_path))
        md_path = pdf_path.with_suffix(".md")
        md_path.write_text(md_text, encoding="utf-8")
        return md_path
    except Exception as e:
        print(f"[ERROR] Failed to convert {pdf_path.name}: {e}")
        return None


def categorize_text(text: str) -> str:
    """Categorize file content semantically into a folder label."""
    if not client:
        # Fallback to keyword-based classification
        return categorize_by_keywords(text)

    prompt = f"""
    Classify this document into one of the following categories:
    {CATEGORIES}.

    Only reply with the category name (single word).

    Document preview:
    {text[:1200]}
    """

    try:
        model_name = "mistral-7b-instruct-v0.2" if USE_LMSTUDIO else "gpt-3.5-turbo"
        response = client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            timeout=30,
        )
        label = response.choices[0].message.content.strip().lower()
        # Validate label
        for cat in CATEGORIES:
            if cat in label or label == cat:
                return cat
        return "other"
    except Exception as e:
        print(f"[WARN] LLM categorization failed: {e}, using keyword fallback")
        return categorize_by_keywords(text)


def categorize_by_keywords(text: str) -> str:
    """Lightweight keyword-based classification fallback."""
    text_lower = text.lower()
    keywords = {
        "hacking": ["exploit", "pentest", "nmap", "cybersecurity", "vulnerability", "malware"],
        "networking": ["tcp", "ip", "router", "switch", "protocol", "dns", "http"],
        "programming": ["python", "javascript", "code", "api", "function", "library", "syntax"],
        "ai": ["neural", "model", "gpt", "machine learning", "dataset", "training", "llm"],
        "linux": ["bash", "kernel", "ubuntu", "debian", "cli", "terminal", "unix"],
        "windows": ["powershell", "registry", "active directory", "windows", "cmd"],
    }
    for category, kw_list in keywords.items():
        if any(kw in text_lower for kw in kw_list):
            return category
    return "other"


def move_to_category(md_path: Path, category: str) -> Path:
    """Move converted markdown to categorized subfolder."""
    category_dir = KNOWLEDGE_DIR / category
    category_dir.mkdir(parents=True, exist_ok=True)
    dest = category_dir / md_path.name
    if dest.exists():
        # Add timestamp to avoid conflicts
        dest = category_dir / f"{md_path.stem}_{int(time.time())}{md_path.suffix}"
    shutil.move(str(md_path), str(dest))
    return dest


def trigger_ingestion(file_path: Optional[Path] = None):
    """Trigger the ingestion script to update the vector store."""
    try:
        cmd = ["python", str(INGEST_SCRIPT), "--no-reset", "--fast", "--parallel"]
        if file_path:
            cmd.extend(["--src", str(file_path.parent)])
        result = subprocess.run(
            cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=3600
        )
        if result.returncode == 0:
            print("[INFO] Ingestion completed successfully")
        else:
            print(f"[WARN] Ingestion had issues: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("[WARN] Ingestion timed out (this is normal for large batches)")
    except Exception as e:
        print(f"[ERROR] Failed to trigger ingestion: {e}")


def process_file(file_path: Path, auto_ingest: bool = True):
    """Process a single file: convert → categorize → move → ingest."""
    print(f"\n[PROCESSING] {file_path.name}")

    # Convert PDF to Markdown if needed
    md_path = file_path
    if file_path.suffix.lower() == ".pdf":
        print("  -> Converting PDF to Markdown...")
        md_path = convert_pdf_to_markdown(file_path)
        if not md_path:
            shutil.move(str(file_path), str(ERROR_DIR / file_path.name))
            return
        print(f"  [OK] Converted to {md_path.name}")

    # Read text for classification
    try:
        text_sample = md_path.read_text(encoding="utf-8", errors="ignore")[:2000]
    except Exception as e:
        print(f"  [WARN] Could not read file: {e}")
        shutil.move(str(file_path), str(ERROR_DIR / file_path.name))
        return

    # Classify content
    print("  -> Classifying content...")
    category = categorize_text(text_sample)
    print(f"  [CATEGORY] {category}")

    # Move to category folder
    categorized_path = move_to_category(md_path, category)
    print(f"  [OK] Moved to: {categorized_path.relative_to(ROOT_DIR)}")

    # Move original PDF to processed folder
    if file_path.suffix.lower() == ".pdf" and file_path.exists():
        shutil.move(str(file_path), str(PROCESSED_DIR / file_path.name))

    # Trigger ingestion
    if auto_ingest:
        print("  [INGEST] Triggering ingestion...")
        trigger_ingestion(categorized_path)


class WatchHandler(FileSystemEventHandler):
    """File system event handler for watching new files."""

    def __init__(self, auto_ingest: bool = True):
        self.auto_ingest = auto_ingest
        self.processed_files = set()

    def on_created(self, event):
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        # Avoid processing the same file twice
        if file_path in self.processed_files:
            return

        # Wait for file to finish copying
        time.sleep(2)

        # Check if file still exists and is readable
        if not file_path.exists():
            return

        # Only process supported file types
        if file_path.suffix.lower() not in [".pdf", ".md", ".txt"]:
            return

        self.processed_files.add(file_path)
        process_file(file_path, auto_ingest=self.auto_ingest)


def watch_folder(auto_ingest: bool = True, poll_interval: int = 10):
    """Watch folder for new files (polling mode if watchdog unavailable)."""
    if WATCHDOG_AVAILABLE:
        print(f"[WATCH] Watching {WATCH_DIR} for new files (using watchdog)...")
        event_handler = WatchHandler(auto_ingest=auto_ingest)
        observer = Observer()
        observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    else:
        # Fallback to polling mode
        print(f"[WATCH] Polling {WATCH_DIR} for new files (install watchdog for better performance)...")
        processed = set()
        while True:
            for file_path in WATCH_DIR.glob("*"):
                if file_path.is_file() and file_path not in processed:
                    if file_path.suffix.lower() in [".pdf", ".md", ".txt"]:
                        processed.add(file_path)
                        process_file(file_path, auto_ingest=auto_ingest)
            time.sleep(poll_interval)


def process_existing_files(auto_ingest: bool = False):
    """Process any existing files in the inbox folder."""
    # Get files with known extensions
    existing_files = list(WATCH_DIR.glob("*.pdf")) + list(WATCH_DIR.glob("*.md")) + list(WATCH_DIR.glob("*.txt"))
    # Also include files without extensions (treat as text)
    for file_path in WATCH_DIR.iterdir():
        if file_path.is_file() and not file_path.suffix and file_path.name not in ["_processed", "_error"]:
            if file_path not in existing_files:
                existing_files.append(file_path)
    
    if not existing_files:
        print("[INFO] No files found to process")
        return

    print(f"[INFO] Found {len(existing_files)} existing files to process")
    for file_path in existing_files:
        if file_path.parent.name in ["_processed", "_error"]:
            continue
        process_file(file_path, auto_ingest=auto_ingest)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Watch inbox folder and auto-process files")
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Do not automatically trigger ingestion after processing files",
    )
    parser.add_argument(
        "--process-existing",
        action="store_true",
        help="Process any existing files in inbox before starting watch mode",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Polling interval in seconds (when watchdog unavailable)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Process existing files and exit (do not start watch mode)",
    )
    args = parser.parse_args()

    auto_ingest = not args.no_ingest

    if not PYMUPDF_AVAILABLE:
        print("[WARN] PyMuPDF not available. PDF conversion will be skipped.")
        print("       Install with: pip install pymupdf pymupdf4llm")

    if args.process_existing or args.once:
        process_existing_files(auto_ingest=auto_ingest)

    if args.once:
        print("[INFO] Processing complete. Exiting.")
        exit(0)

    watch_folder(auto_ingest=auto_ingest, poll_interval=args.poll_interval)

