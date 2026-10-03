#!/usr/bin/env python3
"""One-shot Obsidian bulk ingest into LanceDB (no watchdog).

Usage:
  py scripts/obsidian_bulk_ingest.py
  py scripts/obsidian_bulk_ingest.py --paths 0-Inbox Manual Auto
  py scripts/obsidian_bulk_ingest.py --paths 3-Resources/Dev-Chats --memory-safe
  py scripts/obsidian_bulk_ingest.py --dry-run
"""

from __future__ import annotations

import argparse
import gc
import logging
import os
import sys
from contextlib import contextmanager
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.config import (
    EMBEDDING_BATCH_SIZE,
    MAX_INGEST_BODY_CHARS,
    MEMORY_SAFE_EMBED_BATCH,
    MEMORY_SAFE_MAX_CHUNKS,
    OBSIDIAN_EXCLUDE_DIRS,
    OBSIDIAN_WATCH_DIRS,
    config,
)
from scripts.obsidian_rag_ingester import ObsidianIngester

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VAULT_ROOT = Path(config.ROOT) / "knowledge" / "notes"
MEMORY_SAFE_BATCH_SIZE = MEMORY_SAFE_EMBED_BATCH
LOCK_PATH = Path(config.ROOT) / "data" / ".obsidian_bulk_ingest.lock"


@contextmanager
def ingest_lock():
    """Ensure only one bulk ingest runs at a time (prevents RAM stacking)."""
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_PATH.exists():
        try:
            stale = LOCK_PATH.read_text(encoding="utf-8").strip()
            pid = int(stale.split()[0])
            os.kill(pid, 0)
            raise RuntimeError(
                f"Another bulk ingest is already running (pid {pid}). "
                f"Stop it before starting a new one."
            )
        except (ProcessLookupError, ValueError, PermissionError, OSError):
            logger.warning("Removing stale ingest lock: %s", LOCK_PATH)
            LOCK_PATH.unlink(missing_ok=True)

    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        os.write(fd, f"{os.getpid()} bulk_ingest\n".encode("utf-8"))
    finally:
        os.close(fd)

    try:
        yield
    finally:
        LOCK_PATH.unlink(missing_ok=True)


def _excluded(file_path: Path) -> bool:
    parts = set(file_path.parts)
    for exclude in OBSIDIAN_EXCLUDE_DIRS:
        token = exclude.strip("/").replace("\\", "/")
        if token in parts or any(p.startswith("_secrets") for p in parts):
            return True
    if "_secrets_pulled" in str(file_path):
        return True
    return False


def _resolve_watch_paths(names: list[str] | None) -> list[Path]:
    if not names:
        return [Path(config.ROOT) / d for d in OBSIDIAN_WATCH_DIRS]
    out: list[Path] = []
    for name in names:
        p = VAULT_ROOT / name if not Path(name).is_absolute() else Path(name)
        if p.exists():
            out.append(p)
        else:
            logger.warning("Skip missing path: %s", p)
    return out


def collect_md_files(watch_paths: list[Path], *, recursive: bool = True) -> list[Path]:
    files: list[Path] = []
    for base in watch_paths:
        if base.is_file():
            if base.suffix.lower() == ".md" and not _excluded(base):
                files.append(base)
            continue
        if not base.is_dir():
            continue
        iterator = base.rglob("*.md") if recursive else base.glob("*.md")
        for fp in iterator:
            if _excluded(fp):
                continue
            files.append(fp)
    return sorted(set(files))


def _sources_already_in_lance(ingester: ObsidianIngester) -> set[str]:
    """Resolved source_file paths already present (non-deleted) in the current Lance DB."""
    sources: set[str] = set()
    for table in (ingester.curated_table, ingester.raw_table, getattr(ingester, "prompts_table", None)):
        if table is None:
            continue
        try:
            arrow = table.to_arrow()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read Lance table for resume set: %s", exc)
            continue
        names = set(arrow.column_names)
        if "source_file" not in names:
            continue
        col = arrow.column("source_file")
        deleted = arrow.column("deleted") if "deleted" in names else None
        for i in range(len(col)):
            raw = col[i].as_py()
            if not raw:
                continue
            if deleted is not None and str(deleted[i].as_py()).lower() == "true":
                continue
            try:
                sources.add(str(Path(raw).resolve()))
            except OSError:
                sources.add(str(raw))
    return sources


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk ingest Obsidian notes to LanceDB")
    parser.add_argument(
        "--paths",
        nargs="*",
        help="Vault-relative folders (default: OBSIDIAN_WATCH_DIRS)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List files only")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass ledger hash skip (still skips files already in this Lance DB unless --force-all)",
    )
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Re-embed every file even if already present in the current Lance DB",
    )
    parser.add_argument("--no-recursive", action="store_true", help="Top-level .md only")
    parser.add_argument(
        "--max-file-mb",
        type=float,
        default=float(os.getenv("MAX_INGEST_FILE_MB", "1.5")),
        help="Skip markdown files larger than this many MB (default 1.5; giant chat dumps)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max files to process this run (0=all; ledger skips unchanged)",
    )
    parser.add_argument(
        "--embed-batch-size",
        type=int,
        default=0,
        help=f"Chunks per embed batch (default: {EMBEDDING_BATCH_SIZE}; memory-safe: {MEMORY_SAFE_BATCH_SIZE})",
    )
    parser.add_argument(
        "--memory-safe",
        action="store_true",
        help=(
            f"Low-RAM mode: batch={MEMORY_SAFE_BATCH_SIZE}, "
            f"max {MEMORY_SAFE_MAX_CHUNKS} chunks/file, "
            f"body cap {MAX_INGEST_BODY_CHARS} chars"
        ),
    )
    args = parser.parse_args()

    watch_paths = _resolve_watch_paths(args.paths)
    if not watch_paths:
        logger.error("No watch paths found")
        return 1

    files = collect_md_files(watch_paths, recursive=not args.no_recursive)
    if args.limit and args.limit > 0:
        files = files[: args.limit]
    logger.info("Found %d markdown files under %s", len(files), [str(p) for p in watch_paths])

    if args.dry_run:
        for fp in files[:50]:
            print(fp.relative_to(VAULT_ROOT))
        if len(files) > 50:
            print(f"... +{len(files) - 50} more")
        return 0

    batch_size = args.embed_batch_size
    max_chunks = None
    max_body = None
    if args.memory_safe:
        batch_size = batch_size or MEMORY_SAFE_BATCH_SIZE
        max_chunks = MEMORY_SAFE_MAX_CHUNKS
        max_body = MAX_INGEST_BODY_CHARS
    elif not batch_size:
        batch_size = EMBEDDING_BATCH_SIZE

    force = bool(args.force or args.force_all)
    max_file_bytes = max(0.0, float(args.max_file_mb)) * 1024 * 1024

    try:
        with ingest_lock():
            logger.info(
                "Embed batch=%d memory_safe=%s max_chunks=%s max_body=%s force=%s force_all=%s max_file_mb=%s",
                batch_size,
                args.memory_safe,
                max_chunks,
                max_body,
                force,
                args.force_all,
                args.max_file_mb,
            )
            ingester = ObsidianIngester(
                embed_batch_size=batch_size,
                max_chunks_per_note=max_chunks,
                max_body_chars=max_body,
            )
            already_in_index: set[str] = set()
            if force and not args.force_all:
                already_in_index = _sources_already_in_lance(ingester)
                logger.info("Resume: %d source paths already in this Lance DB", len(already_in_index))

            ok = skip = err = 0
            total = len(files)
            for i, fp in enumerate(files, start=1):
                size = fp.stat().st_size if fp.exists() else 0
                logger.info(
                    "Processing %d/%d (%.1f KB): %s",
                    i,
                    total,
                    size / 1024.0,
                    fp.name,
                )
                if max_file_bytes and size > max_file_bytes:
                    skip += 1
                    logger.warning(
                        "Skipping oversized %s (%.2f MB > %.2f MB cap)",
                        fp.name,
                        size / (1024 * 1024),
                        args.max_file_mb,
                    )
                    continue
                resolved = str(fp.resolve())
                if resolved in already_in_index:
                    skip += 1
                    logger.info("Skipping %s (already in Lance index)", fp.name)
                    continue
                try:
                    result = ingester.process_note(fp, force=force)
                    status = (result or {}).get("status", "unknown")
                    if status in {"skipped", "unchanged"}:
                        skip += 1
                    elif status == "error":
                        err += 1
                        logger.warning("%s: %s", fp.name, result.get("error"))
                    else:
                        ok += 1
                        already_in_index.add(resolved)
                except Exception as exc:  # noqa: BLE001
                    err += 1
                    logger.exception("Failed %s: %s", fp, exc)
                gc.collect()

            logger.info("Done: processed=%d skipped=%d errors=%d", ok, skip, err)
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 1

    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
