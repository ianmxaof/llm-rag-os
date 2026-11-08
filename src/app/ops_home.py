"""Ops home — second-brain status + Deepen/Fade for DECISIONS.md.

Streamlit landing page so Obsidian is optional. Keeps vault PARA files as source of truth.
"""
from __future__ import annotations

import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

DECISIONS_REL = Path("3-Resources") / "second-brain" / "DECISIONS.md"
BELIEFS_REL = Path("3-Resources") / "second-brain" / "current-beliefs.md"
SECTION_NAMES = ("Deepen", "Fade", "Open")
OPEN_BULLET_RE = re.compile(
    r"^- \*\*(.+?)\*\*(?:\s*[—-]\s*(.*))?$",
    re.MULTILINE,
)
BRIEFING_PATH_RE = re.compile(r"`([^`]+)`")
BRIEFING_BULLET_RE = re.compile(
    r"^[-*]\s+(?:[🔴🟡⚪⚫•]\s+)?\*\*(Review|Optional|Done|Ignore)\*\*\s*[—-]\s*(.+)$",
    re.IGNORECASE,
)
RECALL_ROW_RE = re.compile(
    r"^\|\s*([123])\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|\s*(.*?)\s*\|?\s*$"
)


def decisions_path(vault: Path) -> Path:
    return vault / DECISIONS_REL


def beliefs_path(vault: Path) -> Path:
    return vault / BELIEFS_REL


def digest_path(vault: Path, day: Optional[datetime] = None) -> Path:
    day = day or datetime.now(timezone.utc)
    return vault / "0-Inbox" / f"digest-{day.strftime('%Y-%m-%d')}.md"


def _mtime_iso(path: Path) -> Optional[str]:
    if not path.exists():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _age_hours(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 3600.0


def newest_mtime_under(root: Path, limit: int = 5000) -> Optional[float]:
    """Best-effort newest mtime under a tree (capped walk)."""
    if not root.exists():
        return None
    newest: Optional[float] = None
    n = 0
    try:
        for p in root.rglob("*"):
            if not p.is_file():
                continue
            try:
                m = p.stat().st_mtime
            except OSError:
                continue
            if newest is None or m > newest:
                newest = m
            n += 1
            if n >= limit:
                break
    except OSError:
        return newest
    return newest


def ledger_row_count(ledger_path: Path) -> Optional[int]:
    if not ledger_path.exists():
        return None
    try:
        con = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
        try:
            cur = con.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [r[0] for r in cur.fetchall()]
            if not tables:
                return 0
            # Prefer common ledger table names
            for preferred in ("ingestion_ledger", "files", "file_ledger", "ledger"):
                if preferred in tables:
                    return con.execute(f"SELECT COUNT(*) FROM {preferred}").fetchone()[0]
            # Fallback: largest table
            best = 0
            for t in tables:
                try:
                    c = con.execute(f"SELECT COUNT(*) FROM [{t}]").fetchone()[0]
                    best = max(best, int(c))
                except sqlite3.Error:
                    continue
            return best
        finally:
            con.close()
    except sqlite3.Error:
        return None


def parse_decisions_sections(text: str) -> Dict[str, List[str]]:
    """Split DECISIONS.md into Deepen / Fade / Open bullet lists (raw lines)."""
    sections: Dict[str, List[str]] = {s: [] for s in SECTION_NAMES}
    current: Optional[str] = None
    for line in text.splitlines():
        heading = re.match(r"^##\s+(Deepen|Fade|Open)\s*$", line.strip())
        if heading:
            current = heading.group(1)
            continue
        if current and line.strip().startswith("- "):
            sections[current].append(line.rstrip())
    return sections


def open_belief_titles(sections: Dict[str, List[str]]) -> List[Tuple[str, str]]:
    """Return (title, full_bullet_line) for Open section."""
    out: List[Tuple[str, str]] = []
    for line in sections.get("Open", []):
        m = OPEN_BULLET_RE.match(line.strip())
        if m:
            out.append((m.group(1).strip(), line))
        else:
            # keep unparsed bullets moveable by full line
            out.append((line.lstrip("- ").strip()[:80], line))
    return out


def move_open_to(
    text: str,
    title: str,
    target: str,
) -> str:
    """Move an Open bullet whose bold title matches into Deepen or Fade."""
    if target not in ("Deepen", "Fade"):
        raise ValueError("target must be Deepen or Fade")
    sections = parse_decisions_sections(text)
    open_items = open_belief_titles(sections)
    match_line: Optional[str] = None
    for t, line in open_items:
        if t == title:
            match_line = line
            break
    if match_line is None:
        raise KeyError(f"Open belief not found: {title}")

    # Clean Open boilerplate for Deepen/Fade destination
    cleaned = re.sub(
        r"\s*[—-]\s*still open\..*$",
        "",
        match_line,
        flags=re.IGNORECASE,
    ).rstrip()
    if not cleaned.endswith("."):
        # keep as bullet with short note
        pass
    dest_line = cleaned

    # Rebuild file from original, preserving frontmatter + intro
    lines = text.splitlines(keepends=True)
    out: List[str] = []
    current: Optional[str] = None
    inserted = {s: False for s in SECTION_NAMES}
    # Rebuild section contents
    new_sections = {s: list(sections[s]) for s in SECTION_NAMES}
    new_sections["Open"] = [ln for ln in new_sections["Open"] if ln != match_line]
    # Avoid dup in target
    new_sections[target] = [ln for ln in new_sections[target] if title not in ln]
    new_sections[target].append(dest_line)

    # Write: copy until first ## Deepen, then emit sections in order
    preamble: List[str] = []
    hit_sections = False
    for line in lines:
        if re.match(r"^##\s+(Deepen|Fade|Open)\s*$", line.strip()):
            hit_sections = True
            break
        preamble.append(line)

    out.extend(preamble)
    if not hit_sections and preamble and not preamble[-1].endswith("\n"):
        out.append("\n")

    for name in SECTION_NAMES:
        out.append(f"## {name}\n")
        out.append("\n")
        bullets = new_sections[name]
        if not bullets:
            out.append("_None yet._\n")
        else:
            for b in bullets:
                out.append(b if b.endswith("\n") else b + "\n")
        out.append("\n")

    tail = extract_tail_after_open(text)
    if tail:
        out.append(tail if tail.endswith("\n") else tail + "\n")

    # Refresh updated frontmatter timestamp if present
    body = "".join(out)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = re.sub(
        r"(?m)^updated:\s*.*$",
        f"updated: {now}",
        body,
        count=1,
    )
    return body


def apply_decision_move(vault: Path, title: str, target: str) -> Path:
    path = decisions_path(vault)
    text = path.read_text(encoding="utf-8")
    updated = move_open_to(text, title, target)
    path.write_text(updated, encoding="utf-8")
    return path


def extract_tail_after_open(text: str) -> str:
    """Keep ## Recall evals when rebuilding Deepen/Fade/Open."""
    m = re.search(r"(?ms)^##\s+Recall evals\s*\n.*", text)
    return (m.group(0).rstrip() + "\n") if m else ""


def parse_digest_briefing_actions(text: str) -> List[Dict[str, Any]]:
    """Pull actionable Briefing rows with vault path + chat seed."""
    if not text:
        return []
    in_brief = False
    actions: List[Dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_brief = stripped.lower().startswith("## briefing")
            continue
        if not in_brief:
            continue
        m = BRIEFING_BULLET_RE.match(stripped)
        if not m:
            continue
        label = m.group(1).strip()
        body = m.group(2).strip()
        if label.lower() in ("done", "ignore"):
            continue
        paths = BRIEFING_PATH_RE.findall(body)
        path = ""
        for p in paths:
            if p.endswith(".md") or "second-brain" in p or "0-Inbox" in p or "inbox" in p.lower():
                path = p.replace("\\", "/")
                break
        if not path and paths:
            path = paths[0].replace("\\", "/")
        short = re.sub(r"\s*→\s*`[^`]+`\s*$", "", body).strip()
        if len(short) > 90:
            short = short[:87] + "…"
        chat = short
        if "«" in body:
            titles = re.findall(r"«([^»]+)»", body)
            if titles:
                chat = f"What should I do next on: {titles[0]}?"
        elif path:
            chat = f"Summarize and suggest one next step for `{path}`."
        actions.append(
            {
                "label": label,
                "summary": short,
                "path": path,
                "chat_prompt": chat,
            }
        )
        if len(actions) >= 5:
            break
    return actions


def parse_recall_evals(text: str) -> List[Dict[str, str]]:
    """Rows from ## Recall evals table (slots 1–3)."""
    rows: List[Dict[str, str]] = []
    in_sec = False
    for line in (text or "").splitlines():
        if re.match(r"^##\s+Recall evals\s*$", line.strip()):
            in_sec = True
            continue
        if in_sec and line.strip().startswith("## "):
            break
        if not in_sec:
            continue
        m = RECALL_ROW_RE.match(line.strip())
        if not m or m.group(1) not in ("1", "2", "3"):
            continue
        rows.append(
            {
                "n": m.group(1),
                "question": m.group(2).strip(),
                "pass": m.group(3).strip(),
                "notes": m.group(4).strip(),
                "when": m.group(5).strip(),
            }
        )
    while len(rows) < 3:
        n = str(len(rows) + 1)
        rows.append({"n": n, "question": "", "pass": "", "notes": "", "when": ""})
    return rows[:3]


def write_recall_evals(vault: Path, rows: List[Dict[str, str]]) -> Path:
    """Rewrite ## Recall evals table in DECISIONS.md; create section if missing."""
    path = decisions_path(vault)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    table_lines = [
        "## Recall evals",
        "",
        "Log three operator questions after Chat retrieval. Pass = right chunk in top hits.",
        "_RAG ready_ when **3/3** pass with a one-line note (not vibes).",
        "",
        "| # | Question | Pass? | Notes | When (UTC) |",
        "|---|----------|-------|-------|------------|",
    ]
    for i, row in enumerate(rows[:3], start=1):
        q = (row.get("question") or "").replace("|", "/")
        p = (row.get("pass") or "").replace("|", "/")
        n = (row.get("notes") or "").replace("|", "/")
        w = (row.get("when") or "").replace("|", "/")
        table_lines.append(f"| {i} | {q} | {p} | {n} | {w} |")
    table_lines.append("")
    block = "\n".join(table_lines)

    if re.search(r"(?m)^##\s+Recall evals\s*$", text):
        text = re.sub(
            r"(?ms)^##\s+Recall evals\s*\n.*?(?=^##\s+\w|\Z)",
            block,
            text,
        )
    else:
        text = text.rstrip() + "\n\n" + block
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    text = re.sub(r"(?m)^updated:\s*.*$", f"updated: {now}", text, count=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    return path


def collect_ops_status(
    *,
    api_base: str,
    vault: Path,
    lance_path: Path,
    ledger_path: Path,
) -> Dict[str, Any]:
    backend_ok = False
    watcher = "unknown"
    try:
        r = requests.get(f"{api_base}/health", timeout=2)
        backend_ok = r.status_code == 200
    except requests.RequestException:
        backend_ok = False

    if backend_ok:
        try:
            wr = requests.get(f"{api_base}/ingest/watch/status", timeout=2)
            if wr.status_code == 200:
                watcher = wr.json().get("notes_watcher", "unknown")
        except requests.RequestException:
            watcher = "unreachable"

    lance_newest = newest_mtime_under(lance_path)
    lance_age_h = (
        (time.time() - lance_newest) / 3600.0 if lance_newest is not None else None
    )
    lance_iso = (
        datetime.fromtimestamp(lance_newest, tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
        if lance_newest
        else None
    )

    dig = digest_path(vault)
    dec = decisions_path(vault)
    sections: Dict[str, List[str]] = {s: [] for s in SECTION_NAMES}
    if dec.exists():
        sections = parse_decisions_sections(dec.read_text(encoding="utf-8"))

    return {
        "backend_ok": backend_ok,
        "watcher": watcher,
        "lance_exists": lance_path.exists(),
        "lance_last": lance_iso,
        "lance_age_hours": lance_age_h,
        "ledger_exists": ledger_path.exists(),
        "ledger_rows": ledger_row_count(ledger_path),
        "ledger_mtime": _mtime_iso(ledger_path),
        "digest_today": dig.exists(),
        "digest_path": str(dig) if dig.exists() else None,
        "digest_mtime": _mtime_iso(dig) if dig.exists() else None,
        "decisions_mtime": _mtime_iso(dec),
        "open_beliefs": open_belief_titles(sections),
        "deepen_count": len(sections.get("Deepen", [])),
        "fade_count": len(sections.get("Fade", [])),
        "open_count": len(sections.get("Open", [])),
    }


def render_ops_home(
    *,
    api_base: str,
    vault: Path,
    lance_path: Path,
    ledger_path: Path,
    go_to_page,
) -> None:
    """Streamlit Ops landing. Import streamlit only at call time (keeps tests light)."""
    import streamlit as st

    st.markdown(
        '<div class="pc-ops-kicker">PowerCore · Suite</div>'
        "<h3 style='margin:0 0 4px 0;font-family:var(--pc-font-ui);"
        "color:var(--pc-fg);'>Ops — Second Brain</h3>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Near-black PowerCore Chrome. Obsidian optional. "
        "Quiet start — no focus-stealing consoles. Pairs with research desk / powercore.app."
    )

    status = collect_ops_status(
        api_base=api_base,
        vault=vault,
        lance_path=lance_path,
        ledger_path=ledger_path,
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Backend", "up" if status["backend_ok"] else "down")
    with c2:
        st.metric("Notes watcher", str(status["watcher"]))
    with c3:
        rows = status["ledger_rows"]
        st.metric("Ledger rows", rows if rows is not None else "—")
    with c4:
        age = status["lance_age_hours"]
        if age is None:
            st.metric("Lance age", "missing")
        elif age < 24:
            st.metric("Lance age", f"{age:.1f}h")
        else:
            st.metric("Lance age", f"{age/24:.1f}d")

    st.markdown("---")
    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Index**")
        st.write(
            f"- Lance path: `{'exists' if status['lance_exists'] else 'missing'}`  \n"
            f"- Last Lance write: {status['lance_last'] or '—'}  \n"
            f"- Ledger mtime: {status['ledger_mtime'] or '—'}"
        )
        if status["backend_ok"]:
            b1, b2 = st.columns(2)
            with b1:
                if st.button("▶ Start watcher", key="ops_start_watcher"):
                    try:
                        r = requests.post(
                            f"{api_base}/ingest/watch/notes/start", timeout=5
                        )
                        st.toast(r.json().get("message", r.text) if r.ok else r.text)
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(str(e))
            with b2:
                if st.button("⏹ Stop watcher", key="ops_stop_watcher"):
                    try:
                        r = requests.post(
                            f"{api_base}/ingest/watch/notes/stop", timeout=5
                        )
                        st.toast(r.json().get("message", r.text) if r.ok else r.text)
                        st.rerun()
                    except requests.RequestException as e:
                        st.error(str(e))
        else:
            st.warning("Backend down — start with `scripts/start_rag_os.ps1` (quiet).")

    with right:
        st.markdown("**Today**")
        if status["digest_today"]:
            st.success(f"Digest present ({status['digest_mtime']})")
        else:
            st.info("No digest for today yet.")
        st.write(
            f"Open beliefs: **{status['open_count']}** · "
            f"Deepen: **{status['deepen_count']}** · "
            f"Fade: **{status['fade_count']}**"
        )
        nav1, nav2, nav3 = st.columns(3)
        with nav1:
            if st.button("Open Chat", key="ops_to_chat", use_container_width=True):
                go_to_page("chat")
        with nav2:
            if st.button("Corpus Desk", key="ops_to_corpus", use_container_width=True):
                go_to_page("corpus")
        with nav3:
            if st.button("Open Graph", key="ops_to_graph", use_container_width=True):
                go_to_page("corpus")

    # —— Do this next (from today's digest briefing) ——
    st.markdown("---")
    st.markdown("#### Do this next")
    dig = digest_path(vault)
    actions: List[Dict[str, Any]] = []
    if dig.exists():
        try:
            actions = parse_digest_briefing_actions(
                dig.read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            actions = []
    if not actions:
        st.caption("No briefing actions yet — wait for tonight’s digest or refresh after evening digest.")
    else:
        st.caption("One click → Corpus Inspector (path) or Chat (seeded question).")
        for i, act in enumerate(actions):
            cols = st.columns([5, 1, 1])
            with cols[0]:
                st.markdown(f"**{act['label']}** — {act['summary']}")
            with cols[1]:
                if act.get("path") and st.button(
                    "Inspector", key=f"ops_next_insp_{i}", use_container_width=True
                ):
                    rel = str(act["path"]).lstrip("/")
                    full = vault / rel
                    st.session_state.corpus_inspect_path = (
                        str(full) if full.exists() else str(full)
                    )
                    go_to_page("corpus")
            with cols[2]:
                if st.button("Chat", key=f"ops_next_chat_{i}", use_container_width=True):
                    st.session_state.ops_chat_seed = act.get("chat_prompt") or act["summary"]
                    if act.get("path"):
                        st.session_state.corpus_inspect_path = str(vault / str(act["path"]).lstrip("/"))
                    go_to_page("chat")

    # —— Recall evals (prove RAG ready) ——
    st.markdown("---")
    st.markdown("#### Recall evals — prove RAG ready")
    st.caption(
        "Three known-fact Chat queries. Log pass/fail in DECISIONS.md. "
        "3/3 pass = ready (not vibes)."
    )
    dec_text = ""
    if decisions_path(vault).exists():
        try:
            dec_text = decisions_path(vault).read_text(encoding="utf-8", errors="replace")
        except OSError:
            dec_text = ""
    recall_rows = parse_recall_evals(dec_text)
    passed = sum(1 for r in recall_rows if r.get("pass", "").lower() in ("yes", "y", "pass", "✓", "true"))
    st.write(f"Score: **{passed}/3**")
    updated_rows: List[Dict[str, str]] = []
    for i, row in enumerate(recall_rows):
        with st.expander(f"Eval {row['n']}", expanded=not bool(row.get("pass"))):
            q = st.text_input(
                "Question",
                value=row.get("question") or "",
                key=f"ops_recall_q_{i}",
            )
            pcol, ncol = st.columns(2)
            with pcol:
                pass_val = st.selectbox(
                    "Pass?",
                    options=["", "yes", "no"],
                    index=["", "yes", "no"].index(row.get("pass") or "")
                    if (row.get("pass") or "") in ("", "yes", "no")
                    else 0,
                    key=f"ops_recall_p_{i}",
                )
            with ncol:
                notes = st.text_input(
                    "Notes",
                    value=row.get("notes") or "",
                    key=f"ops_recall_n_{i}",
                )
            when = row.get("when") or ""
            if pass_val and not when:
                when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
            updated_rows.append(
                {
                    "n": row["n"],
                    "question": q,
                    "pass": pass_val,
                    "notes": notes,
                    "when": when if pass_val else row.get("when") or "",
                }
            )
            if q and st.button("Ask in Chat", key=f"ops_recall_ask_{i}"):
                st.session_state.ops_chat_seed = q
                go_to_page("chat")
    if st.button("Save recall evals → DECISIONS.md", key="ops_save_recall"):
        try:
            write_recall_evals(vault, updated_rows)
            st.success("Recall evals saved.")
            st.rerun()
        except Exception as e:
            st.error(str(e))

    st.markdown("---")
    st.markdown("#### Open beliefs — Deepen / Fade")
    st.caption(
        "Moves the bullet in `3-Resources/second-brain/DECISIONS.md`. "
        "Dream-merge keeps Deepen/Fade and refreshes Open."
    )

    opens = status["open_beliefs"]
    if not opens:
        st.info("No open beliefs — Open section empty or DECISIONS.md missing.")
        return

    for i, (title, _line) in enumerate(opens):
        row = st.container()
        with row:
            tcol, dcol, fcol = st.columns([5, 1, 1])
            with tcol:
                st.markdown(f"**{title}**")
            with dcol:
                if st.button("↑ Deepen", key=f"ops_deepen_{i}", help="Work this idea"):
                    try:
                        apply_decision_move(vault, title, "Deepen")
                        st.success(f"Deepened: {title}")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with fcol:
                if st.button("↓ Fade", key=f"ops_fade_{i}", help="Stop proposing"):
                    try:
                        apply_decision_move(vault, title, "Fade")
                        st.info(f"Faded: {title}")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
