"""Watch-dir contract: high-signal vault folders for Python crews, not plugins."""

from scripts.config import (
    OBSIDIAN_EXCLUDE_DIRS,
    OBSIDIAN_RECURSIVE,
    OBSIDIAN_WATCH_DIRS,
    resolve_obsidian_vault_name,
    resolve_obsidian_vault_path,
)


def test_watch_dirs_cover_para_high_signal():
    joined = " ".join(OBSIDIAN_WATCH_DIRS)
    for token in (
        "1-Projects/",
        "2-Areas/",
        "3-Resources/second-brain/",
        "knowledge/inbox/",
        "TBCC/",
    ):
        assert token in joined, token


def test_watch_dirs_do_not_include_plugin_caches_or_dumps():
    joined = " ".join(OBSIDIAN_WATCH_DIRS)
    for token in (".smart-env", "Copilot/", "Eni-main", "8-22-26"):
        assert token not in joined, token


def test_exclude_plugin_caches_and_dump_folders():
    joined = " ".join(OBSIDIAN_EXCLUDE_DIRS)
    for token in (".smart-env/", ".copilot/", "Copilot/", "Eni-main/", "8-22-26 DOC DUMP/"):
        assert token in joined, token


def test_recursive_watch_is_on_for_project_trees():
    assert OBSIDIAN_RECURSIVE is True


def test_default_vault_is_second_brain_notes_not_parent_knowledge():
    vault = resolve_obsidian_vault_path()
    assert vault.name == "notes"
    assert resolve_obsidian_vault_name() == "notes"
    assert vault.parent.name == "knowledge"
