"""Tests for Lance → rag_utils retrieval bridge."""

from unittest.mock import MagicMock, patch

import pytest


class _FakeSeries:
    """Minimal Series stand-in for _row_to_metadata tests."""

    def __init__(self, data):
        self._data = data

    @property
    def index(self):
        return self._data.keys()

    def get(self, key, default=None):
        return self._data.get(key, default)


def test_should_use_lance_auto_when_populated():
    from src.rag_utils import _should_use_lance_backend

    with patch("src.obsidian_lance_retrieval.lance_obsidian_available", return_value=True):
        with patch("src.rag_utils.RAG_VECTOR_BACKEND", "auto"):
            assert _should_use_lance_backend() is True


def test_should_use_lance_respects_chroma_override():
    from src.rag_utils import _should_use_lance_backend

    with patch("src.obsidian_lance_retrieval.lance_obsidian_available", return_value=True):
        with patch("src.rag_utils.RAG_VECTOR_BACKEND", "chroma"):
            assert _should_use_lance_backend() is False


def test_row_to_metadata_maps_source_file():
    from src.obsidian_lance_retrieval import _row_to_metadata

    row = _FakeSeries(
        {
            "text": "hello",
            "source_file": r"C:\vault\notes\foo.md",
            "chunk_index": "2",
            "title": "Foo Note",
        }
    )
    meta = _row_to_metadata(row, "curated")
    assert meta["source"] == r"C:\vault\notes\foo.md"
    assert meta["title"] == "Foo Note"
    assert meta["chunk"] == "2"
    assert meta["trust_level"] == "curated"


def test_retrieve_obsidian_context_merges_and_ranks():
    fake_vector = [0.1] * 384
    embedder = MagicMock()
    embedder.query_embed.return_value = iter([fake_vector])
    embedder.embed.return_value = iter([fake_vector])

    hits_curated = [
        {"text": "curated chunk", "metadata": {"source": "/a.md", "title": "A", "trust_level": "curated"}, "distance": 0.2}
    ]
    hits_raw = [
        {"text": "raw chunk", "metadata": {"source": "/b.md", "title": "B", "trust_level": "raw"}, "distance": 0.5}
    ]

    def fake_search(table, query_vector, limit, trust_level, curated_boost):
        return hits_curated if trust_level == "curated" else hits_raw

    with patch("src.obsidian_lance_retrieval.lancedb.connect", return_value=MagicMock()):
        with patch("src.obsidian_lance_retrieval._get_embedder", return_value=embedder):
            with patch("src.obsidian_lance_retrieval.USE_RERANKER", False):
                with patch("src.obsidian_lance_retrieval.LANCE_DB_PATH") as mock_path:
                    mock_path.exists.return_value = True
                    with patch("src.obsidian_lance_retrieval._search_table", side_effect=fake_search):
                        with patch("src.obsidian_lance_retrieval._search_table_fts", return_value=[]):
                            from src.obsidian_lance_retrieval import retrieve_obsidian_context

                            formatted, metas, docs, distances = retrieve_obsidian_context(
                                "test query", k=2, hybrid=False
                            )

    assert len(docs) == 2
    assert docs[0] == "curated chunk"
    assert metas[0]["trust_level"] == "curated"
    assert "curated chunk" in formatted
    assert len(distances) == 2


def test_reciprocal_rank_fusion_prefers_agreement():
    from src.obsidian_lance_retrieval import reciprocal_rank_fusion

    a = {"text": "shared", "metadata": {"source": "a.md", "chunk": "0"}, "distance": 0.4}
    b = {"text": "only-dense", "metadata": {"source": "b.md", "chunk": "0"}, "distance": 0.1}
    c = {"text": "only-lex", "metadata": {"source": "c.md", "chunk": "0"}, "distance": 0.2}
    fused = reciprocal_rank_fusion([[b, a], [c, a]])
    assert fused[0]["text"] == "shared"


def test_neural_rerank_orders_by_score():
    from src.obsidian_lance_retrieval import _neural_rerank

    hits = [
        {"text": "wrong", "metadata": {"source": "a.md"}, "distance": 0.1},
        {"text": "right", "metadata": {"source": "b.md"}, "distance": 0.9},
    ]
    encoder = MagicMock()
    encoder.rerank.return_value = iter([0.05, 0.91])
    with patch("src.obsidian_lance_retrieval.USE_RERANKER", True):
        with patch("src.obsidian_lance_retrieval._get_reranker", return_value=encoder):
            ranked = _neural_rerank(hits, "test query")
    assert ranked[0]["text"] == "right"
    assert ranked[0]["rerank_score"] == pytest.approx(0.91)


def test_retrieve_context_uses_lance_when_auto(monkeypatch):
    from src import rag_utils

    lance_result = ("lance ctx", [{"source": "x.md"}], ["chunk text"], [0.3])

    monkeypatch.setattr(rag_utils, "RAG_VECTOR_BACKEND", "auto")
    monkeypatch.setattr(rag_utils, "_should_use_lance_backend", lambda: True)

    with patch("src.obsidian_lance_retrieval.retrieve_obsidian_context", return_value=lance_result):
        out = rag_utils.retrieve_context("hello", k=3)

    assert out == lance_result
