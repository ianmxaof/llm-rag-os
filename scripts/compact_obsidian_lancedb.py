#!/usr/bin/env python3
"""Compact the nomic Obsidian LanceDB and drop leftover versions.

The live vectors stay. Uncompacted _transactions are what ballooned this
folder to multiple GB for ~12k chunks.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import timedelta
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.config import LANCE_DB_PATH  # noqa: E402


def _dir_mb(path: Path) -> float:
    if not path.exists():
        return 0.0
    total = 0
    for fp in path.rglob("*"):
        if fp.is_file():
            total += fp.stat().st_size
    return total / (1024 * 1024)


def compact_table(table) -> str:
    optimize = getattr(table, "optimize", None)
    if callable(optimize):
        optimize(cleanup_older_than=timedelta(seconds=0))
        return "optimize(cleanup_older_than=0)"
    compact = getattr(table, "compact_files", None)
    if callable(compact):
        compact()
        cleanup = getattr(table, "cleanup_old_versions", None)
        if callable(cleanup):
            cleanup(older_than=timedelta(seconds=0))
        return "compact_files+cleanup_old_versions"
    raise RuntimeError("This LanceDB build has no optimize/compact_files API")


def main() -> int:
    parser = argparse.ArgumentParser(description="Compact nomic Obsidian LanceDB")
    parser.add_argument(
        "--delete-legacy-bge",
        action="store_true",
        help="Delete unused 384-d data/lancedb_obsidian (not nomicq)",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import lancedb

    print(f"nomicq path: {LANCE_DB_PATH}")
    print(f"nomicq size before: {_dir_mb(LANCE_DB_PATH):.1f} MB")
    if args.dry_run:
        return 0

    db = lancedb.connect(str(LANCE_DB_PATH))
    listed = db.list_tables()
    names = list(getattr(listed, "tables", None) or [])
    if not names and hasattr(db, "table_names"):
        names = list(db.table_names())
    for name in names:
        if not isinstance(name, str):
            raise TypeError(f"unexpected table name {name!r}")
        table = db.open_table(name)
        rows = table.count_rows() if hasattr(table, "count_rows") else "?"
        method = compact_table(table)
        print(f"  {name}: rows={rows} compacted via {method}")

    print(f"nomicq size after: {_dir_mb(LANCE_DB_PATH):.1f} MB")

    legacy = _ROOT / "data" / "lancedb_obsidian"
    if args.delete_legacy_bge and legacy.exists():
        print(f"deleting unused bge index {legacy} ({_dir_mb(legacy):.1f} MB)")
        shutil.rmtree(legacy)
        print("legacy bge index gone")
    elif args.delete_legacy_bge:
        print(f"legacy bge index already absent: {legacy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
