#!/usr/bin/env python3
"""Regenerate the Dev-Chats contents list inside that folder's README.

Obsidian has no Dataview plugin in this vault, and a hand-written MOC would
rot as transcripts are exported. This rebuilds a dated wikilink list from
frontmatter / first heading / filename.

Usage (from llm-rag repo root):
  py scripts/regen_devchats_index.py
  py scripts/regen_devchats_index.py --dry-run
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.obsidian_metadata import extract_yaml_frontmatter

BEGIN_MARK = "<!-- BEGIN GENERATED DEV-CHATS INDEX -->"
END_MARK = "<!-- END GENERATED DEV-CHATS INDEX -->"
SKIP_NAMES = {"readme.md"}
HEAD_BYTES = 8192
_H1_RE = re.compile(r"(?m)^#\s+(.+)$")
_EXPORTED_ON_RE = re.compile(
    r"_Exported on\s+(\d{1,2})/(\d{1,2})/(\d{4})",
    re.IGNORECASE,
)
_STEM_DATE_RE = re.compile(r"(?:transcript|chat)[-_](\d{8})", re.IGNORECASE)
_CURSOR_STEM_DATE_RE = re.compile(r"^cursor-transcript-(\d{8})", re.IGNORECASE)
_CLAUDE_STEM_DATE_RE = re.compile(r"^claude-code-transcript-(\d{8})", re.IGNORECASE)


def default_chats_dir() -> Path:
    return _ROOT / "knowledge" / "notes" / "3-Resources" / "Dev-Chats"


def _read_head(path: Path, limit: int = HEAD_BYTES) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return fh.read(limit)


def _as_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def _date_from_stem(stem: str) -> date | None:
    for pattern in (_CLAUDE_STEM_DATE_RE, _CURSOR_STEM_DATE_RE, _STEM_DATE_RE):
        match = pattern.search(stem)
        if match:
            raw = match.group(1)
            try:
                return datetime.strptime(raw, "%Y%m%d").date()
            except ValueError:
                return None
    return None


def _date_from_exported_line(body: str) -> date | None:
    match = _EXPORTED_ON_RE.search(body)
    if not match:
        return None
    month, day, year = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _clean_title(raw: str) -> str:
    title = raw.strip().strip("#").strip()
    title = re.sub(r"[\[\]|]", " ", title)
    title = re.sub(r"\s+", " ", title).strip()
    if len(title) > 90:
        title = title[:87].rstrip() + "…"
    return title


def _title_from_body(body: str, stem: str) -> str:
    match = _H1_RE.search(body)
    if match:
        return _clean_title(match.group(1))
    return _clean_title(stem.replace("_", " ").replace("-", " "))


def _source_label(metadata: dict[str, Any], stem: str) -> str:
    source = str(metadata.get("source") or "").strip()
    if source:
        return source
    lowered = stem.lower()
    if lowered.startswith("claude-code-transcript"):
        return "claude-code"
    if lowered.startswith("cursor-transcript"):
        return "cursor-transcript"
    if lowered.startswith("cursor"):
        return "cursor"
    return "unknown"


def parse_chat(path: Path) -> dict[str, Any]:
    """Parse enough of one chat file to list it. Reads only the file head."""
    stem = path.stem
    head = _read_head(path)
    metadata, body = extract_yaml_frontmatter(head)
    when = (
        _as_date(metadata.get("exported_at"))
        or _as_date(metadata.get("created"))
        or _as_date(metadata.get("date"))
        or _date_from_stem(stem)
        or _date_from_exported_line(body)
        or datetime.fromtimestamp(path.stat().st_mtime).date()
    )
    title = _title_from_body(body, stem)
    if metadata.get("title"):
        title = _clean_title(str(metadata["title"]))
    return {
        "stem": stem,
        "title": title,
        "source": _source_label(metadata, stem),
        "date": when,
    }


def collect_entries(chats_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(chats_dir.glob("*.md")):
        if path.name.lower() in SKIP_NAMES:
            continue
        try:
            entries.append(parse_chat(path))
        except OSError:
            continue
    entries.sort(key=lambda row: (row["date"], row["stem"]), reverse=True)
    return entries


def render_index(entries: list[dict[str, Any]], *, generated_at: datetime | None = None) -> str:
    stamp = (generated_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    lines = [
        BEGIN_MARK,
        "",
        f"_Generated {stamp} · {len(entries)} chats. Rebuild: `py scripts/regen_devchats_index.py`_",
        "",
    ]
    current_day: date | None = None
    for row in entries:
        if row["date"] != current_day:
            if current_day is not None:
                lines.append("")
            current_day = row["date"]
            lines.append(f"## {current_day.isoformat()}")
            lines.append("")
        lines.append(f"- [[{row['stem']}|{row['title']}]] · {row['source']}")
    if entries:
        lines.append("")
    lines.append(END_MARK)
    return "\n".join(lines) + "\n"


def splice_readme(readme: str, generated: str) -> str:
    """Replace or append the generated block in README text."""
    start = readme.find(BEGIN_MARK)
    end = readme.find(END_MARK)
    block = generated.rstrip()
    if start != -1 and end != -1 and end >= start:
        end += len(END_MARK)
        return (readme[:start] + block + readme[end:]).rstrip() + "\n"
    return (readme.rstrip() + "\n\n" + block).rstrip() + "\n"


def write_index(chats_dir: Path, *, dry_run: bool = False) -> tuple[Path, int]:
    entries = collect_entries(chats_dir)
    generated = render_index(entries)
    readme_path = chats_dir / "README.md"
    existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else "# Dev-Chats\n"
    updated = splice_readme(existing, generated)
    if not dry_run:
        readme_path.write_text(updated, encoding="utf-8")
    return readme_path, len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate Dev-Chats README contents list")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Folder of chat markdown files (default: knowledge/notes/3-Resources/Dev-Chats)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print entry count; do not write")
    args = parser.parse_args()
    chats_dir = args.dir or default_chats_dir()
    if not chats_dir.is_dir():
        print(f"Dev-Chats folder not found: {chats_dir}", file=sys.stderr)
        return 1
    path, count = write_index(chats_dir, dry_run=args.dry_run)
    action = "would update" if args.dry_run else "updated"
    print(f"{action} {path} ({count} chats)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
