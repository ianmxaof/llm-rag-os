"""Corpus Desk helpers: frontmatter, hashes, backlog status."""
from pathlib import Path

from src.app.corpus_desk import (
    classify_status,
    extract_links,
    heading_chunks,
    parse_frontmatter,
    graph_edges_from_digests,
    make_chunk_id,
    match_heading_to_lance,
    build_dense_graph,
    DigestItem,
)


SAMPLE = """---
type: evening-digest
created: 2026-10-26T03:00:02Z
source: tbcc-evening-digest
summary: Evening digest — test
tags:
  - tbcc
  - digest
---

# Evening digest

See `3-Resources/second-brain/DECISIONS.md` and [[current-beliefs]].

## Briefing

- Review something.
"""


def test_parse_frontmatter_and_links():
    meta, body = parse_frontmatter(SAMPLE)
    assert meta["type"] == "evening-digest"
    assert "Evening digest" in body
    links = extract_links(SAMPLE)
    assert any("DECISIONS.md" in x for x in links)
    assert any("current-beliefs" in x for x in links)


def test_heading_chunks_have_hashes():
    _, body = parse_frontmatter(SAMPLE)
    chunks = heading_chunks(body)
    assert len(chunks) >= 1
    assert all(len(c["hash"]) == 12 for c in chunks)


def test_classify_never_vs_embedded(tmp_path: Path):
    f = tmp_path / "note.md"
    f.write_text("# hi\n", encoding="utf-8")
    st, chash, row = classify_status(f, {})
    assert st == "never"
    assert len(chash) == 64
    assert row is None
    ledger = {
        str(f.resolve()): {
            "last_hash": chash,
            "last_ingested_ts": "2026-01-01",
            "chunk_count": 2,
        }
    }
    # also key by str(f)
    ledger[str(f)] = ledger[str(f.resolve())]
    st2, _, row2 = classify_status(f, ledger)
    assert st2 == "embedded"
    assert row2["chunk_count"] == 2


def test_graph_edges_from_digest_item(tmp_path: Path):
    p = tmp_path / "digest-x.md"
    p.write_text(SAMPLE, encoding="utf-8")
    d = DigestItem(
        path=p,
        title="t",
        created=None,
        source=None,
        summary=None,
        kind="digest",
        mtime=0,
        links=extract_links(SAMPLE),
    )
    edges = graph_edges_from_digests([d])
    assert edges
    assert edges[0][0] == "digest-x"


def test_make_chunk_id():
    assert make_chunk_id(r"C:\vault\note.md", 3) == "note.md#c3"


def test_match_heading_to_lance():
    headings = [{"index": 0, "heading": "Briefing", "text": "x", "hash": "abc"}]
    lance = [
        {
            "chunk_id": "note.md#c0",
            "chunk_index": "0",
            "section": "## Briefing",
            "text_hash_short": "deadbeefcafe",
            "obsidian_uri": "obsidian://open?file=note.md",
            "collection": "obsidian_curated",
        }
    ]
    joined = match_heading_to_lance(headings, lance)
    assert joined[0]["lance_chunk_id"] == "note.md#c0"
    assert joined[0]["lance_text_hash"] == "deadbeefcafe"


def test_build_dense_graph_nodes():
    p = Path("digest-x.md")
    d = DigestItem(
        path=p,
        title="Evening",
        created=None,
        source=None,
        summary=None,
        kind="digest",
        mtime=0,
        links=["DECISIONS.md", "[[current-beliefs]]"],
    )
    # extract_links style plain names
    d.links = ["DECISIONS.md", "current-beliefs"]
    g = build_dense_graph([d], lance_path=None)
    types = {n["type"] for n in g["nodes"]}
    assert "digest" in types
    assert "source" in types
    assert g["stats"]["edges"] >= 1
