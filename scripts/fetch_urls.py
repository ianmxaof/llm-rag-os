"""
Web-to-Markdown Fetcher for Powercore RAG
-----------------------------------------
Downloads web pages, converts them to markdown, and stores them in the knowledge directory.
"""

import argparse
import datetime
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify as md

ROOT_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"


def sanitize_filename(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.replace(".", "-")
    path = parsed.path.strip("/").replace("/", "-")
    if not path:
        path = "index"
    base = f"{host}-{path}"
    base = re.sub(r"[^a-zA-Z0-9_-]+", "-", base)
    base = re.sub(r"-{2,}", "-", base).strip("-")
    if not base:
        base = "document"
    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{base}-{timestamp}.md"


def fetch_url(url: str, timeout: int = 20) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/118.0.0.0 Safari/537.36"
        )
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    return response.text


def html_to_markdown(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "iframe"]):
        tag.decompose()
    cleaned_html = soup.prettify()
    markdown = md(cleaned_html, heading_style="ATX")
    return markdown


def save_markdown(content: str, url: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = sanitize_filename(url)
    out_path = out_dir / filename
    metadata = (
        f"---\n"
        f"source: {url}\n"
        f"fetched_at: {datetime.datetime.now().isoformat()}\n"
        f"tags: []\n"
        f"---\n\n"
    )
    out_path.write_text(metadata + content, encoding="utf-8")
    return out_path


def load_urls(args: argparse.Namespace) -> list[str]:
    urls = set(args.url or [])
    if args.input_file:
        file_path = Path(args.input_file)
        if not file_path.exists():
            raise FileNotFoundError(f"URL file not found: {file_path}")
        for line in file_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                urls.add(line)
    if not urls:
        raise ValueError("No URLs provided. Use --url or --input-file.")
    return sorted(urls)


def main():
    parser = argparse.ArgumentParser(
        description="Fetch URLs and convert them to markdown files for RAG ingestion."
    )
    parser.add_argument(
        "--url",
        action="append",
        help="URL to fetch. Repeat this option for multiple URLs.",
    )
    parser.add_argument(
        "--input-file",
        help="Path to a text file with one URL per line.",
    )
    parser.add_argument(
        "--out-dir",
        default=KNOWLEDGE_DIR,
        help=f"Output directory (default: {KNOWLEDGE_DIR})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=20,
        help="HTTP request timeout in seconds (default: 20).",
    )
    args = parser.parse_args()

    try:
        urls = load_urls(args)
    except (FileNotFoundError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        sys.exit(1)

    out_dir = Path(args.out_dir)
    successes = 0
    for url in urls:
        try:
            print(f"[INFO] Fetching {url}")
            html = fetch_url(url, timeout=args.timeout)
            markdown = html_to_markdown(html)
            out_path = save_markdown(markdown, url, out_dir)
            print(f"[OK] Saved to {out_path}")
            successes += 1
        except requests.RequestException as exc:
            print(f"[WARN] Failed to fetch {url}: {exc}")
        except Exception as exc:
            print(f"[WARN] Unexpected error for {url}: {exc}")

    print(f"[DONE] Converted {successes} of {len(urls)} URLs.")


if __name__ == "__main__":
    main()

