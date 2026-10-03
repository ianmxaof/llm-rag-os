from pathlib import Path
import re
import datetime as dt

sidecar = Path(r"C:\Powercore-repo-main\llm-rag\_sidecar_out_of_vault")
lib = Path(r"C:\Powercore-repo-main\llm-rag\knowledge\notes\3-Resources\library")
today = dt.date.today().isoformat()

SKIP_TOP = {
    "opencode",
    "Eni-main",
    "MarkText",
    "_locked_eni_remnant",
    "copilot-index",
    "smart-env",
    "agents",
    "claude",
    "claudian",
    "copilot-20260912-173624",
}

ROUTES = {
    "8-22-26 DOC DUMP": "01-telegram-exports",
    "root-loose-20260912-173624": "00-intake",
    "Abliterated, Heretic Model LLM Turns": "02-chat-exports",
    "Userscripts-heavy-20260912-173624": "05-userscripts-reference",
    "Copilot": "03-dev-sessions",
}


def slug(name: str) -> str:
    s = re.sub(r"[^\w\-]+", "-", name, flags=re.UNICODE).strip("-").lower()
    return s[:80] or "note"


def has_frontmatter(text: str) -> bool:
    return text.startswith("---\n") or text.startswith("---\r\n")


def wrap(text: str, *, source: str, shelf: str, title: str) -> str:
    safe_title = title.replace('"', "'")[:120]
    if has_frontmatter(text):
        return (
            f"<!-- library-import from sidecar/{source} shelf={shelf} on {today} -->\n"
            + text
        )
    return (
        f"---\n"
        f'title: "{safe_title}"\n'
        f"type: library-import\n"
        f"created: {today}\n"
        f"source: sidecar/{source}\n"
        f"shelf: {shelf}\n"
        f"tags:\n"
        f"  - second-brain\n"
        f"  - library-import\n"
        f"  - needs-review\n"
        f"---\n\n"
        f"# {safe_title}\n\n"
        f"_Imported from sidecar `{source}` on {today}. Review, then remove `needs-review`._\n\n"
        f"---\n\n"
        f"{text.lstrip()}"
    )


copied = 0
skipped = 0
for top in sorted(sidecar.iterdir()):
    if not top.is_dir() or top.name in SKIP_TOP:
        continue
    shelf = ROUTES.get(top.name)
    if not shelf:
        print(f"unrouted dir: {top.name}")
        continue
    dest_dir = lib / shelf
    dest_dir.mkdir(parents=True, exist_ok=True)
    for md in top.rglob("*.md"):
        if md.name.lower() == "readme.md" and md.parent == top:
            continue
        rel = md.relative_to(top)
        out_name = slug(str(rel.with_suffix("")).replace("\\", "-").replace("/", "-")) + ".md"
        out = dest_dir / out_name
        if out.exists():
            out = dest_dir / f"{out.stem}-{copied}.md"
        try:
            text = md.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            print("read fail", md, e)
            skipped += 1
            continue
        if len(text) > 800_000:
            print("skip huge", md, len(text))
            skipped += 1
            continue
        out.write_text(
            wrap(text, source=top.name, shelf=shelf, title=md.stem[:120]),
            encoding="utf-8",
        )
        copied += 1

print(f"copied={copied} skipped={skipped}")
for shelf in sorted(p.name for p in lib.iterdir() if p.is_dir()):
    n = len(list((lib / shelf).glob("*.md")))
    print(f"  {shelf}: {n}")
