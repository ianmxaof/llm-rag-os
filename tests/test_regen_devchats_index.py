"""Dev-Chats README index: parse frontmatter / splice generated block (no vault I/O)."""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from scripts.regen_devchats_index import (
    BEGIN_MARK,
    END_MARK,
    collect_entries,
    parse_chat,
    render_index,
    splice_readme,
    write_index,
)


def test_parse_chat_prefers_exported_at_and_h1(tmp_path: Path):
    path = tmp_path / "claude-code-transcript-20260905-abc_telegram.md"
    path.write_text(
        "---\n"
        "type: dev-chat\n"
        "source: claude-code-transcript\n"
        "exported_at: 2026-09-05T04:56:07Z\n"
        "---\n\n"
        "# what does the telegram mcp server do\n\n"
        "body\n",
        encoding="utf-8",
    )
    row = parse_chat(path)
    assert row["date"] == date(2026, 9, 5)
    assert row["title"] == "what does the telegram mcp server do"
    assert row["source"] == "claude-code-transcript"
    assert row["stem"] == path.stem


def test_parse_chat_falls_back_to_exported_on_line(tmp_path: Path):
    path = tmp_path / "cursor_album_selection.md"
    path.write_text(
        "# Album selection randomization\n"
        "_Exported on 9/4/2026 at 01:43:17 PDT from Cursor_\n\n"
        "body\n",
        encoding="utf-8",
    )
    row = parse_chat(path)
    assert row["date"] == date(2026, 9, 4)
    assert row["title"] == "Album selection randomization"
    assert row["source"] == "cursor"


def test_collect_skips_readme_and_sorts_newest_first(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Dev-Chats\n", encoding="utf-8")
    older = tmp_path / "cursor-transcript-20260830-old_topic.md"
    newer = tmp_path / "claude-code-transcript-20260905-new_topic.md"
    older.write_text("# old topic\n", encoding="utf-8")
    newer.write_text("# new topic\n", encoding="utf-8")
    entries = collect_entries(tmp_path)
    assert [row["stem"] for row in entries] == [newer.stem, older.stem]


def test_splice_readme_survives_backslash_in_generated_title():
    existing = "# Dev-Chats\n\n" + BEGIN_MARK + "\nold\n" + END_MARK + "\n"
    generated = render_index(
        [
            {
                "stem": "chat-path",
                "title": r"Repo at C:\Powercore-repo-main",
                "source": "cursor",
                "date": date(2026, 9, 5),
            }
        ],
        generated_at=datetime(2026, 9, 5, 12, 0),
    )
    out = splice_readme(existing, generated)
    assert r"C:\Powercore-repo-main" in out
    assert out.count(BEGIN_MARK) == 1


def test_splice_readme_replaces_existing_block():
    existing = "# Dev-Chats\n\nkeep me\n\n" + BEGIN_MARK + "\nold\n" + END_MARK + "\n"
    generated = render_index(
        [{"stem": "chat-a", "title": "Hello", "source": "cursor", "date": date(2026, 9, 5)}],
        generated_at=datetime(2026, 9, 5, 12, 0),
    )
    out = splice_readme(existing, generated)
    assert "keep me" in out
    assert "[[chat-a|Hello]]" in out
    assert out.count(BEGIN_MARK) == 1
    assert out.count(END_MARK) == 1
    assert "old" not in out


def test_write_index_appends_when_markers_missing(tmp_path: Path):
    (tmp_path / "README.md").write_text("# Dev-Chats\n\nPrefer crystallize.\n", encoding="utf-8")
    chat = tmp_path / "claude-code-transcript-20260905-x.md"
    chat.write_text("# topic one\n", encoding="utf-8")
    path, count = write_index(tmp_path)
    assert path == tmp_path / "README.md"
    assert count == 1
    text = path.read_text(encoding="utf-8")
    assert "Prefer crystallize." in text
    assert "[[%s|topic one]]" % chat.stem in text
