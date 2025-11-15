"""
Split a ChatGPT HTML export into individual markdown files.

Usage:
    python scripts/process_chatgpt_html.py --input chat.html --output knowledge/chatgpt
"""

import argparse
import datetime
import hashlib
from pathlib import Path

from bs4 import BeautifulSoup

FRONT_MATTER = """---
title: "{title}"
exported_at: "{timestamp}"
source_file: "{source}"
hash: "{hash}"
---

{content}
"""


def sanitize_filename(name: str) -> str:
    safe = "".join(c if c.isalnum() or c in " -_." else "_" for c in name)
    safe = safe.strip().replace(" ", "_")
    return safe or "conversation"


def extract_conversations(html_path: Path):
    soup = BeautifulSoup(html_path.read_text(encoding="utf-8"), "html.parser")
    conversations = []

    conversation_divs = soup.find_all("div", class_="conversation")
    for convo_div in conversation_divs:
        title_el = convo_div.find("h4")
        title = title_el.get_text(strip=True) if title_el else "Untitled Conversation"
        parts = []
        for msg in convo_div.find_all("div", class_="message"):
            author = msg.find_previous("div", class_="author")
            role = (author.get_text(strip=True) if author else "User").upper()
            body = msg.get_text("\n", strip=True)
            if body:
                parts.append(f"{role}\n{body}")
        conversations.append((title, "\n\n".join(parts)))
    return conversations


def safe_json_loads(raw_text: str):
    import json
    import string
    import demjson3

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    hex_chars = set(string.hexdigits)
    builder: list[str] = []
    i = 0
    length = len(raw_text)

    while i < length:
        ch = raw_text[i]
        if ch != "\\":
            builder.append(ch)
            i += 1
            continue

        next_index = i + 1
        if next_index >= length:
            builder.append("\\\\")
            i += 1
            continue

        nxt = raw_text[next_index]
        if nxt == "u":
            hex_part = raw_text[next_index + 1 : next_index + 5]
            if len(hex_part) == 4 and all(c in hex_chars for c in hex_part):
                builder.append("\\")
                builder.append("u")
                builder.append(hex_part)
                i += 5
                continue
            builder.append("\\\\")
            i += 1
            continue

        if nxt in "\"\\/bfnrt":
            builder.append("\\")
            builder.append(nxt)
            i += 2
            continue

        builder.append("\\\\")
        i += 1

    sanitized = "".join(builder)
    try:
        return json.loads(sanitized)
    except json.JSONDecodeError:
        # Fall back to tolerant decoder (handles bare backslashes, etc.)
        return demjson3.decode(sanitized)


def main():
    parser = argparse.ArgumentParser(description="Split ChatGPT HTML export.")
    parser.add_argument("--input", required=True, help="Path to chat.html export")
    parser.add_argument("--output", required=True, help="Destination folder for markdown files")
    args = parser.parse_args()

    html_path = Path(args.input)
    out_dir = Path(args.output)
    timestamp = datetime.datetime.now().isoformat()

    # Extract conversation data either via HTML or embedded JSON fallback
    conversations = extract_conversations(html_path)

    if not conversations:
        import json
        import re

        html_text = html_path.read_text(encoding="utf-8")
        match = re.search(r"var jsonData = (\[.*?\]);", html_text, re.S)
        if not match:
            raise RuntimeError("No conversations found in HTML export.")
        raw_json = match.group(1)
        data = safe_json_loads(raw_json)

        conversations = []
        for convo in data:
            title = convo.get("title") or "Untitled Conversation"
            mapping = convo.get("mapping", {})
            # Gather messages in creation order
            nodes = [
                node
                for node in mapping.values()
                if isinstance(node, dict) and node.get("message")
            ]
            nodes.sort(key=lambda n: n.get("message", {}).get("create_time", 0))
            parts = []
            for node in nodes:
                role = node["message"].get("author", {}).get("role", "user")
                content = node["message"].get("content", {})
                if content.get("content_type") == "text":
                    text_parts = content.get("parts", [])
                    text = "\n".join(text_parts)
                else:
                    text = ""
                if text:
                    parts.append(f"{role.upper()}\n{text}")
            conversations.append((title, "\n\n".join(parts)))

    if not conversations:
        raise RuntimeError("No conversations found in HTML export.")

    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, (title, content) in enumerate(conversations, start=1):
        file_hash = hashlib.md5(content.encode("utf-8")).hexdigest()
        filename = f"{idx:03d}_{sanitize_filename(title)}.md"
        out_path = out_dir / filename
        out_path.write_text(
            FRONT_MATTER.format(
                title=title.replace('"', "'"),
                timestamp=timestamp,
                source=html_path.name,
                hash=file_hash,
                content=content,
            ),
            encoding="utf-8",
        )
        print(f"Saved {out_path}")


if __name__ == "__main__":
    main()

