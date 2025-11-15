"""
GitHub Content Fetcher for Powercore RAG
---------------------------------------
Downloads files from GitHub repositories using the GitHub API and stores them locally.
"""

import argparse
import base64
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import requests

ROOT_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
GITHUB_API_BASE = "https://api.github.com"


def parse_repo_spec(spec: str) -> tuple[str, str, str]:
    """
    Accepts formats:
      - owner/repo/path/to/file.md
      - https://github.com/owner/repo/blob/branch/path/to/file.md
      - https://raw.githubusercontent.com/owner/repo/branch/path/to/file.md
    Returns (owner, repo, path). Branch resolution handled separately.
    """
    if spec.startswith("http://") or spec.startswith("https://"):
        parsed = urlparse(spec)
        parts = parsed.path.strip("/").split("/")
        if "raw.githubusercontent.com" in parsed.netloc.lower():
            if len(parts) < 4:
                raise ValueError(f"Invalid raw GitHub URL: {spec}")
            owner, repo, branch = parts[0], parts[1], parts[2]
            path = "/".join(parts[3:])
            return owner, repo, path, branch
        if "github.com" in parsed.netloc.lower():
            if len(parts) < 5:
                raise ValueError(f"Invalid GitHub blob URL: {spec}")
            owner, repo, fmt, branch = parts[0], parts[1], parts[2], parts[3]
            if fmt not in {"blob", "raw", "tree"}:
                raise ValueError(f"Unsupported GitHub URL format: {spec}")
            path = "/".join(parts[4:])
            return owner, repo, path, branch
        raise ValueError(f"Unsupported GitHub URL: {spec}")

    # Assume owner/repo/path format (branch optional via CLI)
    parts = spec.split("/")
    if len(parts) < 3:
        raise ValueError(f"Invalid repo specification: {spec}")
    owner, repo = parts[0], parts[1]
    path = "/".join(parts[2:])
    return owner, repo, path, None


def build_contents_url(owner: str, repo: str, path: str, ref: Optional[str]) -> str:
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{path}"
    if ref:
        url += f"?ref={ref}"
    return url


def fetch_github_file(owner: str, repo: str, path: str, ref: Optional[str], token: Optional[str]) -> dict:
    url = build_contents_url(owner, repo, path, ref)
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, headers=headers, timeout=20)
    if response.status_code == 404:
        raise FileNotFoundError(f"File not found: {owner}/{repo}/{path} (ref={ref})")
    response.raise_for_status()
    return response.json()


def decode_content(item: dict) -> str:
    if item.get("encoding") == "base64" and "content" in item:
        return base64.b64decode(item["content"]).decode("utf-8", errors="ignore")
    if "download_url" in item and item["download_url"]:
        download = requests.get(item["download_url"], timeout=20)
        download.raise_for_status()
        download.encoding = "utf-8"
        return download.text
    raise ValueError("Unable to decode GitHub file content.")


def sanitize_filename(owner: str, repo: str, path: str) -> str:
    parts = [owner, repo] + path.split("/")
    safe_parts = []
    for part in parts:
        safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in part)
        safe = safe.strip("-")
        if safe:
            safe_parts.append(safe)
    filename = "__".join(safe_parts)
    return filename or "github_file"


def save_file(content: str, owner: str, repo: str, path: str, ref: Optional[str], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    basename = sanitize_filename(owner, repo, path)
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    ext = Path(path).suffix or ".md"
    out_path = out_dir / f"{basename}-{timestamp}{ext}"
    metadata = {
        "source": f"{owner}/{repo}/{path}",
        "ref": ref or "default",
        "fetched_at": datetime.datetime.now().isoformat(),
    }
    payload = f"---\n{json.dumps(metadata, indent=2)}\n---\n\n{content}"
    out_path.write_text(payload, encoding="utf-8")
    return out_path


def load_specs(args: argparse.Namespace) -> list[tuple[str, str, str, Optional[str]]]:
    specs: set[tuple[str, str, str, Optional[str]]] = set()
    if args.spec:
        for spec in args.spec:
            owner, repo, path, url_branch = parse_repo_spec(spec)
            branch = url_branch or args.ref
            specs.add((owner, repo, path, branch))
    if args.input_file:
        file_path = Path(args.input_file)
        if not file_path.exists():
            raise FileNotFoundError(f"Spec file not found: {file_path}")
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            owner, repo, path, url_branch = parse_repo_spec(line)
            branch = url_branch or args.ref
            specs.add((owner, repo, path, branch))
    if not specs:
        raise ValueError("No GitHub specs provided. Use --spec or --input-file.")
    return sorted(specs)


def main():
    parser = argparse.ArgumentParser(description="Fetch GitHub file contents for RAG ingestion.")
    parser.add_argument(
        "--spec",
        action="append",
        help="GitHub file spec (owner/repo/path) or GitHub URL. Repeat for multiple.",
    )
    parser.add_argument(
        "--input-file",
        help="Text file with one spec per line (same formats as --spec).",
    )
    parser.add_argument(
        "--ref",
        help="Branch or tag. Used when not supplied in the spec/URL.",
    )
    parser.add_argument(
        "--out-dir",
        default=KNOWLEDGE_DIR,
        help=f"Output directory (default: {KNOWLEDGE_DIR})",
    )
    parser.add_argument(
        "--token",
        help="GitHub personal access token. Defaults to GITHUB_TOKEN env variable.",
    )
    args = parser.parse_args()

    try:
        specs = load_specs(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    token = args.token or os.getenv("GITHUB_TOKEN")
    out_dir = Path(args.out_dir)
    successes = 0

    for owner, repo, path, ref in specs:
        ident = f"{owner}/{repo}/{path}"
        try:
            print(f"[INFO] Fetching {ident} (ref={ref or 'default'})")
            item = fetch_github_file(owner, repo, path, ref, token)
            content = decode_content(item)
            out_path = save_file(content, owner, repo, path, ref, out_dir)
            print(f"[OK] Saved to {out_path}")
            successes += 1
        except FileNotFoundError as exc:
            print(f"[WARN] {exc}")
        except requests.HTTPError as exc:
            print(f"[WARN] GitHub API error for {ident}: {exc}")
        except Exception as exc:
            print(f"[WARN] Unexpected error for {ident}: {exc}")

    print(f"[DONE] Retrieved {successes} of {len(specs)} files.")


if __name__ == "__main__":
    main()

