"""Corpus Desk — digests, backlog, chunk inspector, digest↔source graph.

AnythingLLM/Docs feel without Obsidian. Ledger + vault files are source of truth.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]+)?\]\]")
BACKTICK_PATH_RE = re.compile(r"`([^`]+\.md)`")
HEADING_RE = re.compile(r"(?m)^(#{1,6})\s+(.+)$")


@dataclass
class DigestItem:
    path: Path
    title: str
    created: Optional[str]
    source: Optional[str]
    summary: Optional[str]
    kind: str  # digest | thread-digest | thinktank | crystallize | other
    mtime: float
    links: List[str] = field(default_factory=list)


@dataclass
class BacklogRow:
    path: Path
    rel: str
    status: str  # embedded | stale | never
    content_hash: str
    ledger_hash: Optional[str]
    chunk_count: int
    last_ingested: Optional[str]
    size: int
    mtime: float


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_frontmatter(text: str) -> Tuple[Dict[str, Any], str]:
    """Minimal YAML-ish frontmatter → dict + body (no PyYAML required)."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    meta: Dict[str, Any] = {}
    for line in m.group(1).splitlines():
        if ":" not in line or line.strip().startswith("#"):
            continue
        key, _, raw = line.partition(":")
        key = key.strip()
        val = raw.strip().strip("'\"")
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            meta[key] = [
                x.strip().strip("'\"") for x in inner.split(",") if x.strip()
            ] if inner else []
        else:
            meta[key] = val
    body = text[m.end() :]
    return meta, body


def extract_links(text: str) -> List[str]:
    links: List[str] = []
    for m in WIKILINK_RE.finditer(text):
        links.append(m.group(1).strip())
    for m in BACKTICK_PATH_RE.finditer(text):
        links.append(m.group(1).strip().replace("\\", "/"))
    # de-dupe preserve order
    seen = set()
    out = []
    for x in links:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def heading_chunks(body: str, min_size: int = 80) -> List[Dict[str, Any]]:
    """Soft display chunks by markdown headings (not the live Lance splitter)."""
    if not body.strip():
        return []
    parts: List[Tuple[str, str]] = []
    matches = list(HEADING_RE.finditer(body))
    if not matches:
        return [
            {
                "index": 0,
                "heading": "(body)",
                "text": body.strip(),
                "hash": hashlib.sha256(body.encode("utf-8")).hexdigest()[:12],
            }
        ]
    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        title = m.group(2).strip()
        block = body[start:end].strip()
        if len(block) < min_size and i + 1 < len(matches):
            continue
        parts.append((title, block))
    out = []
    for i, (title, block) in enumerate(parts):
        out.append(
            {
                "index": i,
                "heading": title,
                "text": block,
                "hash": hashlib.sha256(block.encode("utf-8")).hexdigest()[:12],
            }
        )
    return out


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_ledger_map(ledger_path: Path) -> Dict[str, Dict[str, Any]]:
    """Map absolute + forward-slash paths → ledger row."""
    out: Dict[str, Dict[str, Any]] = {}
    if not ledger_path.exists():
        return out
    try:
        con = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
        try:
            rows = con.execute(
                "SELECT file_path, last_hash, last_ingested_ts, chunk_count "
                "FROM ingestion_ledger"
            ).fetchall()
        finally:
            con.close()
    except sqlite3.Error:
        return out
    for file_path, last_hash, ts, chunks in rows:
        row = {
            "file_path": file_path,
            "last_hash": last_hash,
            "last_ingested_ts": ts,
            "chunk_count": int(chunks or 0),
        }
        p = Path(file_path)
        keys = {str(file_path), str(p).replace("\\", "/")}
        try:
            keys.add(str(p.resolve()))
            keys.add(str(p.resolve()).replace("\\", "/"))
        except OSError:
            pass
        for k in keys:
            out[k] = row
    return out


def _iter_watch_md(repo: Path, watch_dirs: Iterable[str], exclude_dirs: Iterable[str]) -> List[Path]:
    exclude = tuple(e.replace("\\", "/").rstrip("/") for e in exclude_dirs)
    files: List[Path] = []
    for rel in watch_dirs:
        root = repo / rel.replace("\\", "/").rstrip("/")
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".md":
            files.append(root)
            continue
        for p in root.rglob("*.md"):
            try:
                s = str(p.relative_to(repo)).replace("\\", "/")
            except ValueError:
                s = str(p).replace("\\", "/")
            if any(f"/{ex}/" in f"/{s}/" or s.startswith(f"{ex}/") for ex in exclude):
                continue
            files.append(p)
    # unique
    seen = set()
    uniq = []
    for p in files:
        key = str(p.resolve()) if p.exists() else str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def classify_status(
    path: Path, ledger: Dict[str, Dict[str, Any]]
) -> Tuple[str, str, Optional[Dict[str, Any]]]:
    content_hash = sha256_file(path) if path.is_file() else ""
    keys = [str(path), str(path).replace("\\", "/")]
    try:
        keys.extend(
            [str(path.resolve()), str(path.resolve()).replace("\\", "/")]
        )
    except OSError:
        pass
    row = None
    for k in keys:
        if k in ledger:
            row = ledger[k]
            break
    if row is None:
        return "never", content_hash, None
    if row["last_hash"] == content_hash:
        return "embedded", content_hash, row
    return "stale", content_hash, row


def build_backlog(
    *,
    repo: Path,
    ledger_path: Path,
    watch_dirs: List[str],
    exclude_dirs: List[str],
    status_filter: Optional[str] = None,
    limit: int = 200,
) -> List[BacklogRow]:
    ledger = load_ledger_map(ledger_path)
    rows: List[BacklogRow] = []
    for path in _iter_watch_md(repo, watch_dirs, exclude_dirs):
        try:
            st, chash, row = classify_status(path, ledger)
        except OSError:
            continue
        if status_filter and status_filter != "all" and st != status_filter:
            continue
        try:
            rel = str(path.relative_to(repo)).replace("\\", "/")
        except ValueError:
            rel = str(path).replace("\\", "/")
        stat = path.stat()
        rows.append(
            BacklogRow(
                path=path,
                rel=rel,
                status=st,
                content_hash=chash,
                ledger_hash=row["last_hash"] if row else None,
                chunk_count=row["chunk_count"] if row else 0,
                last_ingested=row["last_ingested_ts"] if row else None,
                size=stat.st_size,
                mtime=stat.st_mtime,
            )
        )
    rows.sort(key=lambda r: r.mtime, reverse=True)
    return rows[:limit]


def _digest_kind(name: str) -> str:
    n = name.lower()
    if n.startswith("digest-"):
        return "digest"
    if n.startswith("thread-digest"):
        return "thread-digest"
    if "thinktank" in n:
        return "thinktank"
    if n.endswith("_crystallized.md") or "crystalliz" in n:
        return "crystallize"
    return "other"


def list_digests(vault: Path, inbox: Path, limit: int = 80) -> List[DigestItem]:
    candidates: List[Path] = []
    inbox0 = vault / "0-Inbox"
    if inbox0.exists():
        candidates.extend(inbox0.glob("digest-*.md"))
        candidates.extend(inbox0.glob("thread-digest-*.md"))
    if inbox.exists():
        candidates.extend(inbox.glob("*thinktank*.md"))
        candidates.extend(inbox.glob("*_crystallized.md"))
        candidates.extend(inbox.glob("thinktank-corpus-*.md"))
    items: List[DigestItem] = []
    seen = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen or not path.is_file():
            continue
        seen.add(key)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        meta, body = parse_frontmatter(text)
        title = meta.get("summary") or path.stem.replace("-", " ")
        # first H1 if no summary
        h1 = re.search(r"(?m)^#\s+(.+)$", body)
        if h1 and not meta.get("summary"):
            title = h1.group(1).strip()
        items.append(
            DigestItem(
                path=path,
                title=str(title)[:160],
                created=meta.get("created"),
                source=meta.get("source"),
                summary=meta.get("summary"),
                kind=_digest_kind(path.name),
                mtime=path.stat().st_mtime,
                links=extract_links(text),
            )
        )
    items.sort(key=lambda d: d.mtime, reverse=True)
    return items[:limit]


def digests_touching_hash_or_name(
    digests: List[DigestItem], *, name: str, content_hash: str
) -> List[DigestItem]:
    """Heuristic lineage: digest mentions filename or short hash."""
    needle_name = name.lower()
    short = content_hash[:12].lower() if content_hash else ""
    hits = []
    for d in digests:
        try:
            text = d.path.read_text(encoding="utf-8", errors="replace").lower()
        except OSError:
            continue
        if needle_name and needle_name in text:
            hits.append(d)
            continue
        if short and short in text:
            hits.append(d)
            continue
        for link in d.links:
            if needle_name in link.lower() or Path(link).name.lower() == needle_name:
                hits.append(d)
                break
    return hits


def graph_edges_from_digests(digests: List[DigestItem], max_edges: int = 200) -> List[Tuple[str, str, str]]:
    """(digest_stem, target, kind) edges for a first-pass graph."""
    edges: List[Tuple[str, str, str]] = []
    for d in digests:
        src = d.path.stem
        for link in d.links:
            edges.append((src, link, d.kind))
            if len(edges) >= max_edges:
                return edges
    return edges


def make_chunk_id(source_file: str, chunk_index: Any) -> str:
    """Stable Lance chunk id (schema has no dedicated chunk_id column)."""
    name = Path(str(source_file)).name
    return f"{name}#c{chunk_index}"


def _path_match_keys(path: Path) -> List[str]:
    keys = [
        str(path),
        str(path).replace("\\", "/"),
        path.name,
    ]
    try:
        keys.extend(
            [
                str(path.resolve()),
                str(path.resolve()).replace("\\", "/"),
            ]
        )
    except OSError:
        pass
    return keys


def query_lance_chunks_for_source(
    lance_path: Path,
    source: Path,
    *,
    limit: int = 80,
) -> List[Dict[str, Any]]:
    """Load non-deleted Lance rows for a source file (curated + raw)."""
    if not lance_path.exists():
        return []
    try:
        import lancedb
    except ImportError:
        return []

    needles = {k.lower() for k in _path_match_keys(source)}
    name = source.name.lower()
    out: List[Dict[str, Any]] = []
    try:
        db = lancedb.connect(str(lance_path))
        names: List[str] = []
        try:
            listed = db.list_tables()
            names = list(getattr(listed, "tables", None) or [])
            if not names and isinstance(listed, dict):
                names = list(listed.get("tables") or [])
        except Exception:
            names = []
        if not names:
            try:
                names = list(db.table_names())
            except Exception:
                names = ["obsidian_curated", "obsidian_raw"]
        for tname in names:
            if "obsidian" not in str(tname).lower():
                continue
            try:
                tbl = db.open_table(tname)
                # Full table read is OK for filtered local inspect (curated ~3k rows).
                df = tbl.to_pandas()
                if "deleted" in df.columns:
                    df = df[df["deleted"].astype(str).str.lower() != "true"]
                col = "source_file" if "source_file" in df.columns else (
                    "source" if "source" in df.columns else None
                )
                if col is None:
                    continue
                df = df[
                    df[col]
                    .astype(str)
                    .str.lower()
                    .str.contains(re.escape(name), na=False, regex=True)
                ]
                df = df.head(limit)
            except Exception:
                continue
            if df is None or df.empty:
                continue
            for _, row in df.iterrows():
                sf = str(row.get("source_file") or row.get("source") or "")
                sf_l = sf.lower().replace("\\", "/")
                if name not in sf_l and not any(n.replace("\\", "/") in sf_l for n in needles if "/" in n or "\\" in n):
                    # still accept name match already filtered
                    if name not in Path(sf).name.lower():
                        continue
                idx = str(row.get("chunk_index", "0"))
                text = str(row.get("text") or "")
                text_hash = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
                out.append(
                    {
                        "chunk_id": make_chunk_id(sf or source.name, idx),
                        "chunk_index": idx,
                        "section": str(row.get("section") or ""),
                        "source_file": sf,
                        "trust_level": str(row.get("trust_level") or ""),
                        "obsidian_uri": str(row.get("obsidian_uri") or ""),
                        "collection": str(tname),
                        "text": text,
                        "text_hash": text_hash,
                        "text_hash_short": text_hash[:12],
                        "preview": text[:240],
                    }
                )
                if len(out) >= limit:
                    return out
    except Exception:
        return out
    # Prefer curated then raw; stable by chunk_index
    out.sort(key=lambda c: (0 if "curated" in c["collection"] else 1, int(c["chunk_index"] or 0)))
    return out


def _filename_index(roots: List[Path]) -> Dict[str, Path]:
    """Map lowercase filename → first Path found (for graph Lance joins)."""
    idx: Dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.suffix.lower() == ".md":
            idx.setdefault(root.name.lower(), root)
            continue
        try:
            for p in root.rglob("*.md"):
                idx.setdefault(p.name.lower(), p)
        except OSError:
            continue
    return idx


def build_dense_graph(
    digests: List[DigestItem],
    *,
    lance_path: Optional[Path] = None,
    path_index: Optional[Dict[str, Path]] = None,
    max_digest_nodes: int = 40,
    max_source_nodes: int = 50,
    max_chunk_nodes: int = 100,
) -> Dict[str, Any]:
    """Research-desk-scope graph: digests → sources → Lance chunks."""
    nodes: Dict[str, Dict[str, Any]] = {}
    edges: List[Dict[str, Any]] = []

    def add_node(nid: str, label: str, ntype: str, **extra: Any) -> None:
        if nid not in nodes:
            nodes[nid] = {"id": nid, "label": label[:48], "type": ntype, **extra}

    digest_slice = digests[:max_digest_nodes]
    source_refs: Dict[str, str] = {}  # display key → node id
    source_count = 0

    for d in digest_slice:
        did = f"digest:{d.path.stem}"
        add_node(did, d.title or d.path.stem, "digest", kind=d.kind)
        for link in d.links:
            key = Path(link).name if ("/" in link or "\\" in link) else link
            sid = f"source:{key}"
            if source_count >= max_source_nodes and sid not in nodes:
                continue
            if sid not in nodes:
                source_count += 1
            add_node(sid, key, "source")
            source_refs[key.lower()] = sid
            edges.append({"source": did, "target": sid, "rel": d.kind, "weight": 1.0})

    # Attach Lance chunks for linked sources (by filename)
    chunk_count = 0
    idx = path_index or {}
    if lance_path and lance_path.exists() and source_refs:
        for key, sid in list(source_refs.items()):
            if chunk_count >= max_chunk_nodes:
                break
            guess = idx.get(Path(key).name.lower()) or idx.get(key.lower())
            if guess is None:
                continue
            for ch in query_lance_chunks_for_source(lance_path, guess, limit=8):
                cid = f"chunk:{ch['chunk_id']}"
                if cid in nodes:
                    continue
                if chunk_count >= max_chunk_nodes:
                    break
                label = ch["section"] or ch["chunk_id"]
                add_node(
                    cid,
                    label,
                    "chunk",
                    chunk_id=ch["chunk_id"],
                    text_hash_short=ch["text_hash_short"],
                )
                edges.append(
                    {
                        "source": sid,
                        "target": cid,
                        "rel": "lance",
                        "weight": 0.6,
                    }
                )
                chunk_count += 1

    return {
        "nodes": list(nodes.values()),
        "edges": edges,
        "stats": {
            "digests": sum(1 for n in nodes.values() if n["type"] == "digest"),
            "sources": sum(1 for n in nodes.values() if n["type"] == "source"),
            "chunks": sum(1 for n in nodes.values() if n["type"] == "chunk"),
            "edges": len(edges),
        },
    }


def render_pyvis_corpus_graph(graph: Dict[str, Any]) -> None:
    """Interactive pyvis network with PowerCore Chrome colors."""
    import streamlit as st
    import streamlit.components.v1 as components

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    if not nodes:
        st.info("No graph nodes yet.")
        return
    try:
        from pyvis.network import Network
    except ImportError:
        st.warning("Install pyvis for the interactive graph: `pip install pyvis==0.3.2`")
        st.dataframe(
            [{"from": e["source"], "to": e["target"], "rel": e.get("rel")} for e in edges[:120]],
            use_container_width=True,
            hide_index=True,
        )
        return

    colors = {
        "digest": "#a78bfa",  # violet suite
        "source": "#22d3ee",  # cyan focus
        "chunk": "#71717a",  # subtle
    }
    net = Network(
        height="640px",
        width="100%",
        bgcolor="#0a0a0b",
        font_color="#f4f4f5",
        directed=True,
    )
    net.barnes_hut(
        gravity=-12000,
        central_gravity=0.25,
        spring_length=140,
        spring_strength=0.04,
        damping=0.9,
    )
    for n in nodes:
        ntype = n.get("type", "source")
        size = {"digest": 28, "source": 18, "chunk": 10}.get(ntype, 14)
        shape = {"digest": "box", "source": "dot", "chunk": "diamond"}.get(ntype, "dot")
        title = n.get("chunk_id") or n.get("kind") or ntype
        if n.get("text_hash_short"):
            title = f"{title} · {n['text_hash_short']}"
        net.add_node(
            n["id"],
            label=n.get("label", n["id"]),
            color=colors.get(ntype, "#a1a1aa"),
            size=size,
            shape=shape,
            title=str(title),
        )
    for e in edges:
        net.add_edge(
            e["source"],
            e["target"],
            value=float(e.get("weight", 1)) * 8,
            color="#3d3d46",
            title=e.get("rel", ""),
        )
    out = _repo_root() / "data" / "corpus_desk_graph.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(str(out))
    html = out.read_text(encoding="utf-8")
    components.html(html, height=660, scrolling=True)


def match_heading_to_lance(
    heading_chunks_list: List[Dict[str, Any]],
    lance_chunks: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Attach best Lance chunk_id onto display heading chunks via section / index."""
    by_section = {}
    for lc in lance_chunks:
        sec = (lc.get("section") or "").lstrip("#").strip().lower()
        if sec:
            by_section[sec] = lc
        by_section[str(lc.get("chunk_index"))] = lc
    enriched = []
    for hc in heading_chunks_list:
        h = hc["heading"].lstrip("#").strip().lower()
        hit = by_section.get(h) or by_section.get(str(hc["index"]))
        row = dict(hc)
        if hit:
            row["lance_chunk_id"] = hit["chunk_id"]
            row["lance_text_hash"] = hit["text_hash_short"]
            row["lance_uri"] = hit.get("obsidian_uri") or ""
            row["lance_collection"] = hit.get("collection") or ""
        enriched.append(row)
    return enriched


def inspect_document(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta, body = parse_frontmatter(text)
    content_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    return {
        "path": path,
        "meta": meta,
        "body": body,
        "content_hash": content_hash,
        "short_hash": content_hash[:12],
        "chunks": heading_chunks(body),
        "links": extract_links(text),
    }


def render_corpus_desk(
    *,
    vault: Path,
    inbox: Path,
    ledger_path: Path,
    watch_dirs: List[str],
    exclude_dirs: List[str],
    lance_path: Optional[Path] = None,
    go_to_page=None,
) -> None:
    import streamlit as st

    repo = _repo_root()
    st.markdown(
        '<div class="pc-ops-kicker">PowerCore · Suite</div>'
        "<h3 style='margin:0 0 4px 0;font-family:var(--pc-font-ui);"
        "color:var(--pc-fg);'>Corpus Desk</h3>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Digests, backlog, Lance chunk IDs, and a denser digest→source→chunk graph. "
        "Obsidian optional."
    )

    digests = list_digests(vault, inbox)
    tab_d, tab_b, tab_c, tab_g = st.tabs(
        ["Digests", "Backlog", "Inspector", "Graph"]
    )

    with tab_d:
        if not digests:
            st.info("No digests / thinktank drops found under 0-Inbox or knowledge/inbox.")
        else:
            st.caption(f"{len(digests)} reports (newest first)")
            for i, d in enumerate(digests):
                when = d.created or datetime.fromtimestamp(
                    d.mtime, tz=timezone.utc
                ).strftime("%Y-%m-%d %H:%M UTC")
                with st.expander(f"[{d.kind}] {d.title}", expanded=i == 0):
                    st.markdown(
                        f"<div class='pc-ops-panel'>"
                        f"<div class='pc-ops-kicker'>{when}</div>"
                        f"<code>{d.path.name}</code><br>"
                        f"source: {d.source or '—'} · links: {len(d.links)}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )
                    if d.links:
                        st.caption("Linked targets")
                        st.write(", ".join(f"`{x}`" for x in d.links[:20]))
                    if st.button("Open in Inspector", key=f"cd_dig_insp_{i}"):
                        st.session_state.corpus_inspect_path = str(d.path)
                        st.rerun()
                    preview = d.path.read_text(encoding="utf-8", errors="replace")[
                        :2500
                    ]
                    st.code(preview, language="markdown")

    with tab_b:
        filt = st.selectbox(
            "Status",
            ["all", "never", "stale", "embedded"],
            key="cd_backlog_filter",
        )
        limit = st.slider("Show up to", 50, 500, 150, 50, key="cd_backlog_limit")
        with st.spinner("Scanning watch dirs vs ledger…"):
            rows = build_backlog(
                repo=repo,
                ledger_path=ledger_path,
                watch_dirs=watch_dirs,
                exclude_dirs=exclude_dirs,
                status_filter=None if filt == "all" else filt,
                limit=limit,
            )
        counts = {"embedded": 0, "stale": 0, "never": 0}
        # cheap recount on filtered set only — also show filter result size
        for r in rows:
            counts[r.status] = counts.get(r.status, 0) + 1
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Listed", len(rows))
        c2.metric("Embedded", counts.get("embedded", 0))
        c3.metric("Stale", counts.get("stale", 0))
        c4.metric("Never", counts.get("never", 0))
        st.caption("Status vs ingestion_ledger SHA256 (watch dirs only).")
        for i, r in enumerate(rows):
            badge = {"embedded": "🟢", "stale": "🟡", "never": "⚪"}.get(r.status, "?")
            label = f"{badge} {r.status} · {r.rel} · `{r.content_hash[:12]}`"
            with st.expander(label, expanded=False):
                st.write(
                    f"chunks in ledger: **{r.chunk_count}** · "
                    f"last ingest: {r.last_ingested or '—'} · "
                    f"size: {r.size} B"
                )
                if r.ledger_hash and r.ledger_hash != r.content_hash:
                    st.warning(
                        f"Ledger hash `{r.ledger_hash[:12]}` ≠ file `{r.content_hash[:12]}`"
                    )
                if st.button("Inspect", key=f"cd_bl_insp_{i}"):
                    st.session_state.corpus_inspect_path = str(r.path)
                    st.rerun()

    with tab_c:
        default_path = st.session_state.get("corpus_inspect_path", "")
        path_str = st.text_input(
            "File path (absolute or under repo)",
            value=default_path,
            key="cd_inspect_path",
        )
        pick = st.file_uploader(
            "Or drop a .md to preview (does not ingest)",
            type=["md"],
            key="cd_inspect_upload",
        )
        target: Optional[Path] = None
        if pick is not None:
            # ephemeral preview only
            tmp = repo / "data" / ".corpus_desk_preview.md"
            tmp.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_bytes(pick.getvalue())
            target = tmp
        elif path_str.strip():
            p = Path(path_str.strip())
            if not p.is_file():
                alt = repo / path_str.strip()
                if alt.is_file():
                    p = alt
            target = p if p.is_file() else None

        if target is None:
            st.info("Pick a digest/backlog row or paste a path.")
        else:
            doc = inspect_document(target)
            lance_chunks: List[Dict[str, Any]] = []
            if lance_path:
                with st.spinner("Joining Lance chunk IDs…"):
                    lance_chunks = query_lance_chunks_for_source(
                        lance_path, target, limit=80
                    )
            display_chunks = match_heading_to_lance(doc["chunks"], lance_chunks)
            related = digests_touching_hash_or_name(
                digests, name=target.name, content_hash=doc["content_hash"]
            )
            st.markdown(
                f"<div class='pc-ops-panel'>"
                f"<div class='pc-ops-kicker'>Content hash</div>"
                f"<code>{doc['content_hash']}</code><br>"
                f"short: <code>{doc['short_hash']}</code> · "
                f"heading chunks: {len(doc['chunks'])} · "
                f"Lance rows: {len(lance_chunks)}"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.subheader("Frontmatter")
            if doc["meta"]:
                for k, v in doc["meta"].items():
                    st.markdown(f"**{k}:** `{v}`")
            else:
                st.caption("No frontmatter")
            if related:
                st.subheader("Related digests / reports")
                for d in related[:8]:
                    st.markdown(f"- [{d.kind}] **{d.title}** (`{d.path.name}`)")
            else:
                st.caption("No digest mentions this filename/hash yet.")

            st.subheader("Lance index (joined)")
            if not lance_chunks:
                st.caption(
                    "No Lance rows for this file (never embedded, soft-deleted, or path mismatch)."
                )
            else:
                st.dataframe(
                    [
                        {
                            "chunk_id": c["chunk_id"],
                            "idx": c["chunk_index"],
                            "section": c["section"][:60],
                            "text_hash": c["text_hash_short"],
                            "trust": c["trust_level"],
                            "collection": c["collection"],
                        }
                        for c in lance_chunks
                    ],
                    use_container_width=True,
                    hide_index=True,
                )

            st.subheader("Chunks (heading ↔ Lance)")
            for ch in display_chunks:
                lance_bit = (
                    f" · Lance `{ch['lance_chunk_id']}` · `{ch.get('lance_text_hash')}`"
                    if ch.get("lance_chunk_id")
                    else " · (no Lance join)"
                )
                with st.expander(
                    f"#{ch['index']} {ch['heading']} · `{ch['hash']}`{lance_bit}",
                    expanded=ch["index"] == 0,
                ):
                    if ch.get("lance_uri"):
                        st.caption(ch["lance_uri"])
                    st.code(ch["text"][:4000], language="markdown")

    with tab_g:
        include_chunks = st.checkbox(
            "Attach Lance chunks for linked sources",
            value=True,
            key="cd_graph_lance",
        )
        max_d = st.slider("Max digest nodes", 10, 80, 35, key="cd_graph_max_d")
        with st.spinner("Building dense graph…"):
            path_idx = _filename_index(
                [
                    vault / "0-Inbox",
                    vault / "3-Resources" / "second-brain",
                    inbox,
                    vault / "1-Projects",
                    vault / "TBCC",
                ]
            )
            graph = build_dense_graph(
                digests,
                lance_path=lance_path if include_chunks else None,
                path_index=path_idx,
                max_digest_nodes=max_d,
            )
        stats = graph.get("stats") or {}
        st.caption(
            f"digests={stats.get('digests', 0)} · sources={stats.get('sources', 0)} · "
            f"chunks={stats.get('chunks', 0)} · edges={stats.get('edges', 0)} "
            "(PowerCore Chrome pyvis — research-desk scope)"
        )
        render_pyvis_corpus_graph(graph)
        with st.expander("Edge table", expanded=False):
            st.dataframe(
                [
                    {
                        "from": e["source"],
                        "to": e["target"],
                        "rel": e.get("rel"),
                    }
                    for e in (graph.get("edges") or [])[:150]
                ],
                use_container_width=True,
                hide_index=True,
            )
        if go_to_page and st.button("Open Knowledge Base", key="cd_to_kb"):
            go_to_page("knowledge_base")
