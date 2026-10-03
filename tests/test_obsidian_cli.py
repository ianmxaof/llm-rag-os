"""Second-brain pin for official Obsidian CLI + obsidian:// URIs."""

from pathlib import Path

from scripts.config import resolve_obsidian_vault_name, resolve_obsidian_vault_path
from scripts.obsidian_chunker import generate_obsidian_uri
from scripts.obsidian_cli import build_cli_argv, check_status


def test_second_brain_vault_is_knowledge_notes():
    vault = resolve_obsidian_vault_path()
    assert vault.as_posix().endswith("knowledge/notes")
    assert resolve_obsidian_vault_name() == "notes"
    assert vault.name == "notes"
    # Parent `knowledge` is a different registered vault — never the default.
    assert vault.parent.name == "knowledge"
    assert vault.parent.parent.name == "llm-rag"


def test_uri_includes_vault_name_and_relative_file():
    uri = generate_obsidian_uri("knowledge/notes/3-Resources/second-brain/current-beliefs.md", 0)
    assert uri.startswith("obsidian://open?vault=notes&file=")
    assert "current-beliefs.md" in uri
    assert "3-Resources" in uri


def test_uri_heading_block_still_appended():
    uri = generate_obsidian_uri("knowledge/notes/Manual/Test.md", 0, "# Introduction")
    assert "vault=notes" in uri
    assert "Test.md" in uri
    assert "block=^introduction" in uri


def test_build_cli_argv_prefixes_full_vault_path(tmp_path: Path):
    fake_bin = tmp_path / "Obsidian.com"
    fake_bin.write_text("", encoding="utf-8")
    vault = tmp_path / "knowledge" / "notes"
    vault.mkdir(parents=True)
    argv = build_cli_argv(["files"], vault=vault, binary=fake_bin)
    assert argv[0] == str(fake_bin)
    assert argv[1] == f"vault={vault.resolve()}"
    assert argv[2] == "files"


def test_build_cli_argv_keeps_explicit_vault(tmp_path: Path):
    fake_bin = tmp_path / "Obsidian.exe"
    fake_bin.write_text("", encoding="utf-8")
    argv = build_cli_argv(
        ["vault=other", "daily"],
        vault=tmp_path / "notes",
        binary=fake_bin,
    )
    assert argv[1] == "vault=other"
    assert argv[2] == "daily"


def test_check_status_points_at_second_brain():
    status = check_status()
    assert str(status["vault_path"]).replace("\\", "/").endswith("knowledge/notes")
    assert status["vault_name"] == "notes"
    assert "second-brain" in str(status["second_brain_marker"])
