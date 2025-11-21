"""
RAG Ingestion Script for Powercore Personal LLM
------------------------------------------------
Converts local data sources to markdown (using Unstructured when available),
embeds with BAAI/bge-small-en-v1.5, and stores vectors in Chroma.

Supports --fast mode using PyMuPDF for faster PDF processing and --parallel
for concurrent document processing.
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

# Import centralized configuration and preprocessing
from scripts.config import config
from scripts.preprocess import chunk_text as preprocess_chunk_text

# Try PyMuPDF for fast PDF processing
try:
    import fitz  # PyMuPDF
    from pymupdf4llm import to_markdown as pymupdf_to_markdown

    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

# Try Unstructured for rich document formats
try:
    from unstructured.partition.auto import partition

    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

FRONT_MATTER_PATTERN = re.compile(r"^---\s*(.*?)\s*---\s*(.*)$", re.DOTALL)

# Use centralized config
ROOT_DIR = config.ROOT
CONFIG_PATH = config.CONFIG_PATH
KNOWLEDGE_DIR = config.KNOWLEDGE_DIR
VECTOR_DIR = config.VECTOR_DIR
MODEL_NAME = config.EMBED_MODEL
SUPPORTED_EXTS = config.SUPPORTED_EXTS

# Obsidian system-folder skipping helper (added by Obsidian+RAG integration)
SKIP_FOLDERS = {".obsidian", "_attachments", "_dashboard"}

def should_skip(name: str) -> bool:
    """
    Return True for folders the ingestion walker should skip.
    - Explicitly skip known Obsidian system folders
    - Skip any folder starting with '_' except '_templates'
    """
    if name in SKIP_FOLDERS:
        return True
    if name.startswith("_") and name != "_templates":
        return True
    return False


def load_sources(extra_sources: Iterable[Path | str] | None = None) -> List[Path]:
    sources: List[Path] = []
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            for entry in data.get("directories", []):
                path = Path(entry.get("path", "")).expanduser()
                read_only = entry.get("read_only", False)
                if not path.exists():
                    print(f"[WARN] Configured path does not exist: {path}")
                    continue
                if read_only:
                    print(f"[INFO] Skipping read-only path: {path}")
                    continue
                sources.append(path)
        except Exception as exc:
            print(f"[WARN] Failed to load source config: {exc}")

    if extra_sources:
        for src in extra_sources:
            path = Path(src).expanduser()
            if path.exists():
                sources.append(path)
            else:
                print(f"[WARN] Extra source missing: {path}")

    if not sources:
        sources.append(KNOWLEDGE_DIR)
    return sources


def safe_relative_path(root: Path, target: Path) -> str:
    try:
        return str(target.relative_to(root))
    except ValueError:
        return str(target)


# Use preprocessing module for chunking
def chunk_text(text: str, chunk_size: int = None, chunk_overlap: int = None) -> List[str]:
    """Chunk text using centralized preprocessing module."""
    return preprocess_chunk_text(
        text,
        chunk_size=chunk_size or config.CHUNK_SIZE,
        chunk_overlap=chunk_overlap or config.CHUNK_OVERLAP
    )


def parse_front_matter(content: str) -> tuple[Optional[Dict[str, str]], str]:
    match = FRONT_MATTER_PATTERN.match(content)
    if not match:
        return None, content
    raw_meta, body = match.groups()
    metadata: Dict[str, str] = {}
    for line in raw_meta.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            metadata[key.strip()] = value.strip().strip('"')
    return metadata, body


def normalize_to_markdown(src_path: Path, out_dir: Path, use_fast: bool = False) -> Path | None:
    """
    Convert a source file to markdown format.
    
    Args:
        src_path: Source file path
        out_dir: Output directory for markdown file
        use_fast: If True, use PyMuPDF for PDFs (faster but less layout-aware)
    
    Returns:
        Path to created markdown file, or None if conversion failed
    """
    ext = src_path.suffix.lower()
    text = ""

    if ext in {".txt", ".md"}:
        text = src_path.read_text(encoding="utf-8", errors="ignore")
    elif ext == ".pdf":
        # Fast mode: use PyMuPDF if available
        if use_fast and PYMUPDF_AVAILABLE:
            try:
                text = pymupdf_to_markdown(str(src_path))
            except Exception as exc:
                print(f"[WARN] PyMuPDF failed on {src_path}: {exc}")
                # Fallback to Unstructured if available
                if UNSTRUCTURED_AVAILABLE:
                    try:
                        elements = partition(filename=str(src_path))
                        text = "\n\n".join(
                            element.text.strip()
                            for element in elements
                            if getattr(element, "text", "").strip()
                        )
                    except Exception as exc2:
                        print(f"[WARN] Unstructured fallback also failed: {exc2}")
                        return None
                else:
                    return None
        elif UNSTRUCTURED_AVAILABLE:
            try:
                elements = partition(filename=str(src_path))
                text = "\n\n".join(
                    element.text.strip()
                    for element in elements
                    if getattr(element, "text", "").strip()
                )
            except Exception as exc:
                print(f"[WARN] Unstructured failed on {src_path}: {exc}")
                return None
        else:
            print(f"[WARN] PDF support requires unstructured or pymupdf: {src_path}")
            return None
    elif UNSTRUCTURED_AVAILABLE:
        try:
            elements = partition(filename=str(src_path))
            text = "\n\n".join(
                element.text.strip()
                for element in elements
                if getattr(element, "text", "").strip()
            )
        except Exception as exc:
            print(f"[WARN] Unstructured failed on {src_path}: {exc}")
            return None
    else:
        print(f"[WARN] Unsupported file type (install unstructured): {src_path}")
        return None

    if not text.strip():
        print(f"[WARN] No extractable text for {src_path}")
        return None

    rel_path = src_path.stem + ".md"
    out_path = out_dir / rel_path
    out_dir.mkdir(parents=True, exist_ok=True)

    metadata = (
        f"---\n"
        f"source: {src_path}\n"
        f"date: {datetime.datetime.now().isoformat()}\n"
        f"tags: []\n"
        f"---\n\n"
    )
    out_path.write_text(metadata + text, encoding="utf-8")
    return out_path


def _normalize_single_file(
    path: Path, src: Path, use_fast: bool
) -> Tuple[Path, Optional[Path], Optional[Exception]]:
    """Normalize a single file, returning (source_path, output_path, error)."""
    try:
        # Route all normalized markdown into the Obsidian vault Auto folder
        auto_dir = KNOWLEDGE_DIR / "notes" / "Auto"
        auto_dir.mkdir(parents=True, exist_ok=True)
        out_path = normalize_to_markdown(path, auto_dir, use_fast=use_fast)
        return path, out_path, None
    except Exception as exc:
        return path, None, exc


def ingest_sources(
    sources: List[Path], reset_store: bool = True, use_fast: bool = False, parallel: bool = False
):
    """
    Ingest sources into the knowledge base.
    
    Args:
        sources: List of source directories to process
        reset_store: If True, wipe the vector store before ingesting
        use_fast: If True, use PyMuPDF for faster PDF processing
        parallel: If True, process files concurrently using ThreadPoolExecutor
    """
    start_time = time.time()
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all files to process
    files_to_process: List[Tuple[Path, Path]] = []  # (file_path, source_root)
    for src in sources:
        if not src.exists():
            print(f"[WARN] Skipping missing source: {src}")
            continue
        print(f"[INFO] Scanning source: {src}")
        for path in src.rglob("*"):
            if not path.is_file():
                continue
            if path.suffix.lower() not in SUPPORTED_EXTS:
                continue
            # Skip files in Obsidian system folders
            path_parts = path.parts
            if any(should_skip(part) for part in path_parts):
                continue
            files_to_process.append((path, src))

    total_files = len(files_to_process)
    print(f"[INFO] Found {total_files} files to process")

    # Process files (parallel or sequential)
    if parallel and total_files > 1:
        max_workers = min(os.cpu_count() or 4, total_files)
        print(f"[INFO] Processing {total_files} files in parallel (max_workers={max_workers})")
        processed = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(_normalize_single_file, path, src, use_fast): (path, src)
                for path, src in files_to_process
            }
            for future in as_completed(futures):
                path, src = futures[future]
                try:
                    _, out_path, error = future.result()
                    if error:
                        print(f"[WARN] Failed to normalize {path}: {error}")
                        failed += 1
                    elif out_path:
                        processed += 1
                        if processed % 10 == 0:
                            print(f"[INFO] Processed {processed}/{total_files} files...")
                except Exception as exc:
                    print(f"[WARN] Exception processing {path}: {exc}")
                    failed += 1
        print(f"[INFO] Normalization complete: {processed} succeeded, {failed} failed")
    else:
        # Sequential processing
        processed = 0
        failed = 0
        for path, src in files_to_process:
            try:
                _, out_path, error = _normalize_single_file(path, src, use_fast)
                if error:
                    print(f"[WARN] Failed to normalize {path}: {error}")
                    failed += 1
                elif out_path:
                    processed += 1
                    if processed % 10 == 0:
                        print(f"[INFO] Processed {processed}/{total_files} files...")
            except Exception as exc:
                print(f"[WARN] Exception processing {path}: {exc}")
                failed += 1
        print(f"[INFO] Normalization complete: {processed} succeeded, {failed} failed")

    if reset_store and VECTOR_DIR.exists():
        shutil.rmtree(VECTOR_DIR)
    VECTOR_DIR.mkdir(parents=True, exist_ok=True)

    print("[INFO] Loading embedding model (this may take 10-30s on first run)...")
    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME, normalize_embeddings=True
    )
    print("[INFO] Model loaded successfully")
    chroma_client = chromadb.PersistentClient(path=str(VECTOR_DIR))
    collection = chroma_client.get_or_create_collection(
        name=config.COLLECTION_NAME, embedding_function=embedding_function
    )
    try:
        collection.delete()
    except Exception:
        pass

    documents: List[str] = []
    metadatas: List[dict] = []
    ids: List[str] = []

    # Collect all markdown files first for progress tracking
    md_files = sorted(KNOWLEDGE_DIR.rglob("*.md"))
    total_files = len(md_files)
    print(f"[INFO] Scanning {total_files} markdown files...")

    for file_idx, md_file in enumerate(md_files):
        if file_idx % 10 == 0 or file_idx == total_files - 1:
            print(f"[INFO] Processing file {file_idx+1}/{total_files}: {md_file.name}")
        try:
            raw_text = md_file.read_text(encoding="utf-8")
            fm, text = parse_front_matter(raw_text)
            base_meta = {
                "source": str(md_file),
                "title": fm.get("title") if fm else None,
                "exported_at": fm.get("exported_at") if fm else None,
                "hash": fm.get("hash") if fm else None,
            }
        except Exception as exc:
            print(f"[WARN] Failed to read {md_file}: {exc}")
            continue

        for idx, chunk in enumerate(chunk_text(text)):
            documents.append(chunk)
            meta = base_meta.copy()
            meta["chunk"] = idx
            metadatas.append({k: v for k, v in meta.items() if v})
            ids.append(hashlib.md5(f"{md_file}-{idx}".encode("utf-8")).hexdigest())
            
            # Progress indicator for chunking
            if len(documents) % 100 == 0:
                print(f"[INFO] Chunked {len(documents)} text segments so far...")

    if not documents:
        print("[WARN] No markdown documents found for embedding.")
        return

    print(f"[INFO] Embedding {len(documents)} chunks into vector database...")
    collection.add(documents=documents, metadatas=metadatas, ids=ids)
    elapsed = time.time() - start_time
    print(f"[INFO] Embedded {len(documents)} chunks with {MODEL_NAME}.")
    print(f"[INFO] Ingestion complete in {elapsed:.1f}s. Chroma DB updated.")


def watch_mode(
    sources: List[Path], interval: int = 3600, use_fast: bool = False, parallel: bool = False
):
    print(f"Watching sources every {interval}s...")
    ingest_sources(sources, reset_store=True, use_fast=use_fast, parallel=parallel)
    while True:
        time.sleep(interval)
        ingest_sources(sources, reset_store=False, use_fast=use_fast, parallel=parallel)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Powercore LLM RAG Ingestor")
    parser.add_argument(
        "--src",
        action="append",
        help="Additional source folder to ingest (can be repeated).",
    )
    parser.add_argument("--watch", action="store_true", help="Enable continuous watch mode")
    parser.add_argument("--interval", type=int, default=3600, help="Watch interval in seconds")
    parser.add_argument(
        "--no-reset",
        action="store_true",
        help="Do not wipe the vector store directory before ingesting.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Use PyMuPDF for faster PDF processing (requires pymupdf and pymupdf4llm)",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Process files concurrently using multiple threads (faster for large batches)",
    )
    args = parser.parse_args()

    if args.fast and not PYMUPDF_AVAILABLE:
        print(
            "[WARN] --fast mode requested but PyMuPDF not available. "
            "Install with: pip install pymupdf pymupdf4llm"
        )
        print("[INFO] Continuing with standard Unstructured processing...")

    source_paths = load_sources(args.src)

    if args.watch:
        watch_mode(
            source_paths, args.interval, use_fast=args.fast, parallel=args.parallel
        )
    else:
        ingest_sources(
            source_paths, reset_store=not args.no_reset, use_fast=args.fast, parallel=args.parallel
        )

