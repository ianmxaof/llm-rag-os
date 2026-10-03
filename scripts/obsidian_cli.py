"""Pin the official Obsidian CLI to the second-brain vault.

Live vault: llm-rag/knowledge/notes (PARA + 3-Resources/second-brain).
A second registered vault exists at llm-rag/knowledge (the parent folder).
CLI commands without vault= follow cwd or the currently open vault — so this
wrapper always passes vault=<absolute notes path> first.

Windows stdout needs Obsidian.com beside Obsidian.exe (installer 1.12.7+).
In-app updates do not add that redirector.

Examples:
  py -3.13 scripts/obsidian_cli.py --check
  py -3.13 scripts/obsidian_cli.py files
  py -3.13 scripts/obsidian_cli.py search query="current-beliefs"
  py -3.13 scripts/obsidian_cli.py read path="3-Resources/second-brain/current-beliefs.md"
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Sequence

_LLM_RAG_ROOT = Path(__file__).resolve().parent.parent
if str(_LLM_RAG_ROOT) not in sys.path:
    sys.path.insert(0, str(_LLM_RAG_ROOT))

from scripts.config import resolve_obsidian_vault_name, resolve_obsidian_vault_path

DEFAULT_INSTALL_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Obsidian"


def find_obsidian_executable() -> Path:
    install = DEFAULT_INSTALL_DIR
    redirector = install / "Obsidian.com"
    exe = install / "Obsidian.exe"
    if redirector.is_file():
        return redirector
    on_path = shutil.which("obsidian")
    if on_path:
        return Path(on_path)
    if exe.is_file():
        return exe
    raise FileNotFoundError(
        "Obsidian CLI not found. Register it in Settings → General → Command line interface, "
        "or install to %LOCALAPPDATA%\\Programs\\Obsidian"
    )


def windows_redirector_missing() -> bool:
    return os.name == "nt" and not (DEFAULT_INSTALL_DIR / "Obsidian.com").is_file()


def build_cli_argv(
    user_args: Sequence[str],
    *,
    vault: Path | None = None,
    binary: Path | None = None,
) -> list[str]:
    vault_path = (vault or resolve_obsidian_vault_path()).resolve()
    exe = binary or find_obsidian_executable()
    args = [str(a) for a in user_args]
    if args and args[0].lower().startswith("vault="):
        return [str(exe), *args]
    return [str(exe), f"vault={vault_path}", *args]


def check_status() -> dict[str, object]:
    vault = resolve_obsidian_vault_path()
    try:
        binary = find_obsidian_executable()
        binary_error = None
    except FileNotFoundError as exc:
        binary = None
        binary_error = str(exc)
    return {
        "vault_path": str(vault),
        "vault_name": resolve_obsidian_vault_name(),
        "vault_exists": vault.is_dir(),
        "binary": str(binary) if binary else None,
        "binary_error": binary_error,
        "windows_redirector_missing": windows_redirector_missing(),
        "second_brain_marker": str(vault / "3-Resources" / "second-brain"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="obsidian_cli",
        description="Official Obsidian CLI, always pinned to the second-brain vault (knowledge/notes).",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Print vault/binary status and exit (does not launch Obsidian).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the argv that would be executed, then exit.",
    )
    parser.add_argument(
        "obsidian_args",
        nargs=argparse.REMAINDER,
        help="Arguments forwarded to obsidian after vault=<second-brain path>.",
    )
    args = parser.parse_args(argv)

    forwarded = list(args.obsidian_args)
    if forwarded and forwarded[0] == "--":
        forwarded = forwarded[1:]

    if args.check or not forwarded:
        status = check_status()
        print(f"vault_name\t{status['vault_name']}")
        print(f"vault_path\t{status['vault_path']}")
        print(f"vault_exists\t{status['vault_exists']}")
        print(f"binary\t{status['binary'] or status['binary_error']}")
        print(f"windows_redirector_missing\t{status['windows_redirector_missing']}")
        if status["windows_redirector_missing"]:
            print(
                "note\tWindows installer is too old for CLI stdout. "
                "Redownload from https://obsidian.md/download (1.12.7+) so Obsidian.com sits next to Obsidian.exe. "
                "PATH registration alone is not enough."
            )
        print("pin\tAlways pass vault=<vault_path> as the first CLI argument.")
        print(
            "warn\tDo not run CLI from llm-rag/knowledge — that parent folder is a different vault."
        )
        if not forwarded:
            return 0 if status["vault_exists"] and status["binary"] else 2

    try:
        cmd = build_cli_argv(forwarded)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.dry_run:
        print(" ".join(cmd))
        return 0

    proc = subprocess.run(cmd, check=False)
    return int(proc.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
