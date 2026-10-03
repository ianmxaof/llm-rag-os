"""
Obsidian LanceDB retrieval for Streamlit / rag_utils.
Uses the same fastembed model and collections as obsidian_rag_ingester.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    import lancedb

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False

try:
    from fastembed import TextEmbedding

    FASTEMBED_AVAILABLE = True
except ImportError:
    FASTEMBED_AVAILABLE = False

try:
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    FASTEMBED_RERANK_AVAILABLE = True
except ImportError:
    TextCrossEncoder = None  # type: ignore[misc, assignment]
    FASTEMBED_RERANK_AVAILABLE = False

from scripts.config import (
    LANCE_DB_PATH,
    OBSIDIAN_CURATED_COLLECTION,
    OBSIDIAN_EMBED_MODEL,
    OBSIDIAN_EMBED_MULTILINGUAL,
    OBSIDIAN_RAW_COLLECTION,
    RERANKER_MODEL,
    USE_RERANKER,
)

_RESERVED_COLUMNS = frozenset({"vector", "text", "_distance", "_score"})


@lru_cache(maxsize=1)
def _embedder_model_name() -> str:
    name = OBSIDIAN_EMBED_MODEL
    if OBSIDIAN_EMBED_MULTILINGUAL and ":multilingual" not in name:
        return f"{name}:multilingual"
    return name


@lru_cache(maxsize=1)
def _get_embedder() -> TextEmbedding:
    if not FASTEMBED_AVAILABLE:
        raise ImportError("fastembed is required for Lance retrieval. pip install fastembed")
    threads = max(1, int(os.getenv("EMBEDDING_THREADS", "1")))
    return TextEmbedding(model_name=_embedder_model_name(), threads=threads)


@lru_cache(maxsize=1)
def _get_reranker():
    if not FASTEMBED_RERANK_AVAILABLE or TextCrossEncoder is None:
        raise ImportError("fastembed cross-encoder rerank is not available")
    return TextCrossEncoder(model_name=RERANKER_MODEL)


def _to_float_list(vector) -> List[float]:
    if hasattr(vector, "tolist"):
        return list(vector.tolist())
    return list(vector)


def _query_vector(embedder: TextEmbedding, question: str) -> List[float]:
    """Use query_embed when the model has a query prefix (nomic, bge)."""
    query_embed = getattr(embedder, "query_embed", None)
    if callable(query_embed):
        raw = list(query_embed([question]))[0]
    else:
        raw = list(embedder.embed([question]))[0]
    return _to_float_list(raw)


def _rerank_score(item) -> float:
    if hasattr(item, "score"):
        return float(item.score)
    if isinstance(item, (tuple, list)) and len(item) >= 2:
        return float(item[-1])
    return float(item)


def _neural_rerank(hits: List[dict], question: str) -> List[dict]:
    """Cross-encoder rerank. Fail-soft: return the fused order if the model cannot load."""
    if not USE_RERANKER or not hits:
        return list(hits)
    try:
        encoder = _get_reranker()
        documents = [str(h.get("text") or "") for h in hits]
        raw_scores = list(encoder.rerank(question, documents))
    except Exception as exc:
        logger.warning("Neural rerank skipped: %s", exc)
        return list(hits)

    scored: List[Tuple[float, dict]] = []
    for hit, item in zip(hits, raw_scores):
        score = _rerank_score(item)
        row = dict(hit)
        row["rerank_score"] = score
        row["distance"] = 1.0 / (1.0 + max(score, 0.0))
        scored.append((score, row))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [row for _, row in scored]


def lance_obsidian_available() -> bool:
    """True when LanceDB exists and at least one Obsidian table has rows."""
    if not LANCEDB_AVAILABLE or not LANCE_DB_PATH.exists():
        return False
    try:
        db = lancedb.connect(str(LANCE_DB_PATH))
        for name in (OBSIDIAN_CURATED_COLLECTION, OBSIDIAN_RAW_COLLECTION):
            try:
                table = db.open_table(name)
                if table.count_rows() > 0:
                    return True
            except Exception:
                continue
        return False
    except Exception as exc:
        logger.debug("Lance availability check failed: %s", exc)
        return False


def _row_to_metadata(row: Any, trust_level: str) -> Dict[str, str]:
    """Flatten a Lance row into the metadata dict rag_utils expects."""
    meta: Dict[str, str] = {"trust_level": trust_level}
    if hasattr(row, "index"):
        series = row
        for key in series.index:
            if key in _RESERVED_COLUMNS:
                continue
            val = series.get(key)
            if val is None or val == "":
                continue
            meta[str(key)] = str(val)
    else:
        for key, val in dict(row).items():
            if key in _RESERVED_COLUMNS or val is None or val == "":
                continue
            meta[str(key)] = str(val)

    source = meta.get("source_file") or meta.get("source") or "unknown"
    meta["source"] = source
    if "title" not in meta:
        meta["title"] = Path(source).stem.replace("_", " ")
    if "chunk" not in meta and "chunk_index" in meta:
        meta["chunk"] = meta["chunk_index"]
    return meta


def _distance_to_similarity(distance: float) -> float:
    """Map Lance vector distance to Chroma-style similarity in [0, 1]."""
    if distance <= 1.0:
        return max(0.0, 1.0 - float(distance))
    # L2-style distances: squash with a soft scale
    return max(0.0, 1.0 / (1.0 + float(distance)))


def _hit_key(hit: dict) -> str:
    meta = hit.get("metadata") or {}
    source = str(meta.get("source") or meta.get("source_file") or "")
    chunk = str(meta.get("chunk") or meta.get("chunk_index") or "")
    text = str(hit.get("text") or "")[:80]
    return f"{source}::{chunk}::{hash(text)}"


def _tokenize_query(question: str) -> List[str]:
    import re

    tokens = re.findall(r"[a-zA-Z0-9_]{3,}", (question or "").lower())
    # Drop ultra-common filler that blows up keyword ranks on vault prose.
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "your",
        "have",
        "will",
        "are",
        "was",
        "were",
        "been",
        "being",
        "about",
        "project",
        "notes",
    }
    return [t for t in tokens if t not in stop][:24]


def _lexical_score(text: str, tokens: List[str]) -> float:
    """BM25-lite: term frequency with length normalization (no IDF corpus needed)."""
    if not tokens or not text:
        return 0.0
    low = text.lower()
    words = low.split()
    doc_len = max(len(words), 1)
    score = 0.0
    for tok in tokens:
        tf = low.count(tok)
        if tf <= 0:
            continue
        # k1=1.2, b=0.75, avgdl≈200 tokens for chunked vault notes
        score += (tf * 2.2) / (tf + 1.2 * (0.25 + 0.75 * doc_len / 200.0))
    return score


def reciprocal_rank_fusion(
    ranked_lists: List[List[dict]],
    *,
    k: int = 60,
) -> List[dict]:
    """Fuse multiple ranked hit lists via Reciprocal Rank Fusion."""
    scores: Dict[str, float] = {}
    best: Dict[str, dict] = {}
    for ranked in ranked_lists:
        for rank, hit in enumerate(ranked):
            key = _hit_key(hit)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            prev = best.get(key)
            if prev is None or float(hit.get("distance", 1.0)) < float(prev.get("distance", 1.0)):
                best[key] = hit
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out: List[dict] = []
    for key, rrf in ordered:
        hit = dict(best[key])
        hit["rrf_score"] = rrf
        # Lower distance = better for callers that sort on distance.
        hit["distance"] = 1.0 / (1.0 + rrf)
        out.append(hit)
    return out


def _search_table(table, query_vector: List[float], limit: int, trust_level: str, curated_boost: float):
    hits = []
    try:
        results = table.search(query_vector).limit(limit).to_pandas()
    except Exception as exc:
        logger.warning("Lance search failed on %s: %s", trust_level, exc)
        return hits

    if results is None or results.empty:
        return hits

    if "deleted" in results.columns:
        results = results[results["deleted"] != "true"]

    for _, row in results.iterrows():
        text = row.get("text", "")
        if not text or not str(text).strip():
            continue
        raw_distance = row.get("_distance")
        if raw_distance is None:
            raw_distance = row.get("_score", 1.0)
        distance = float(raw_distance)
        if trust_level == "curated":
            distance *= curated_boost
        hits.append(
            {
                "text": str(text),
                "metadata": _row_to_metadata(row, trust_level),
                "distance": distance,
            }
        )
    return hits


def _search_table_fts(table, question: str, limit: int, trust_level: str, curated_boost: float):
    """Optional Tantivy FTS when an index exists on the table."""
    hits = []
    try:
        results = table.search(question, query_type="fts").limit(limit).to_pandas()
    except Exception as exc:
        logger.debug("Lance FTS unavailable on %s: %s", trust_level, exc)
        return hits

    if results is None or results.empty:
        return hits
    if "deleted" in results.columns:
        results = results[results["deleted"] != "true"]

    for _, row in results.iterrows():
        text = row.get("text", "")
        if not text or not str(text).strip():
            continue
        # FTS often exposes _score (higher better); map to distance-like.
        raw_score = row.get("_score")
        if raw_score is not None:
            distance = 1.0 / (1.0 + float(raw_score))
        else:
            distance = 0.5
        if trust_level == "curated":
            distance *= curated_boost
        hits.append(
            {
                "text": str(text),
                "metadata": _row_to_metadata(row, trust_level),
                "distance": distance,
            }
        )
    return hits


def _format_hits(top: List[dict]) -> Tuple[str, List[Dict], List[str], List[float]]:
    documents = [h["text"] for h in top]
    metadatas = [h["metadata"] for h in top]
    distances = [float(h["distance"]) for h in top]

    parts: List[str] = []
    for idx, (doc, meta) in enumerate(zip(documents, metadatas), start=1):
        title = meta.get("title") or "Untitled"
        source = meta.get("source") or "unknown"
        chunk = meta.get("chunk", meta.get("chunk_index", idx - 1))
        parts.append(f"[{idx}] {title} (chunk {chunk})\nSource: {source}\n{doc}")
    formatted = "\n\n".join(parts)
    return formatted, metadatas, documents, distances


def _collect_dense_hits(
    db,
    query_vector: List[float],
    *,
    per_table_limit: int,
    curated_boost: float,
) -> List[dict]:
    all_hits: List[dict] = []
    for collection, trust in (
        (OBSIDIAN_CURATED_COLLECTION, "curated"),
        (OBSIDIAN_RAW_COLLECTION, "raw"),
    ):
        try:
            table = db.open_table(collection)
            if table.count_rows() == 0:
                continue
            boost = curated_boost if trust == "curated" else 1.0
            all_hits.extend(_search_table(table, query_vector, per_table_limit, trust, boost))
        except Exception as exc:
            logger.debug("Skipping collection %s: %s", collection, exc)
    all_hits.sort(key=lambda h: h["distance"])
    return all_hits


def _collect_fts_hits(
    db,
    question: str,
    *,
    per_table_limit: int,
    curated_boost: float,
) -> List[dict]:
    all_hits: List[dict] = []
    for collection, trust in (
        (OBSIDIAN_CURATED_COLLECTION, "curated"),
        (OBSIDIAN_RAW_COLLECTION, "raw"),
    ):
        try:
            table = db.open_table(collection)
            if table.count_rows() == 0:
                continue
            boost = curated_boost if trust == "curated" else 1.0
            all_hits.extend(_search_table_fts(table, question, per_table_limit, trust, boost))
        except Exception as exc:
            logger.debug("Skipping FTS collection %s: %s", collection, exc)
    all_hits.sort(key=lambda h: h["distance"])
    return all_hits


def _lexical_rerank(hits: List[dict], question: str) -> List[dict]:
    tokens = _tokenize_query(question)
    if not tokens or not hits:
        return list(hits)
    scored: List[Tuple[float, dict]] = []
    for hit in hits:
        lex = _lexical_score(str(hit.get("text") or ""), tokens)
        # Blend: keep vector distance influence so pure keyword spam doesn't dominate.
        distance = float(hit.get("distance") or 1.0)
        combined = lex / (1.0 + distance)
        scored.append((combined, hit))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    out: List[dict] = []
    for combined, hit in scored:
        row = dict(hit)
        row["lexical_score"] = combined
        # Invert so callers can still sort ascending by distance.
        row["distance"] = 1.0 / (1.0 + combined) if combined > 0 else float(hit.get("distance") or 1.0)
        out.append(row)
    return out


def retrieve_obsidian_context(
    question: str,
    k: int = 3,
    *,
    curated_boost: float = 0.85,
    hybrid: bool = True,
) -> Tuple[str, List[Dict], List[str], List[float]]:
    """
    Retrieve from obsidian_curated + obsidian_raw (curated ranked first).

    When hybrid=True (default): dense ANN + lexical re-rank (+ optional FTS),
    fused with Reciprocal Rank Fusion, then a cross-encoder rerank.
    Falls back to dense-only when needed. Neural rerank is fail-soft.

    Returns the same tuple shape as rag_utils.retrieve_context.
    """
    if not LANCEDB_AVAILABLE:
        raise ImportError("lancedb is required. pip install lancedb pyarrow")

    if not LANCE_DB_PATH.exists():
        raise FileNotFoundError(f"LanceDB path missing: {LANCE_DB_PATH}")

    db = lancedb.connect(str(LANCE_DB_PATH))
    embedder = _get_embedder()
    query_vector = _query_vector(embedder, question)

    per_table_limit = max(k * 4, k)
    dense = _collect_dense_hits(
        db, query_vector, per_table_limit=per_table_limit, curated_boost=curated_boost
    )

    if not dense:
        return "", [], [], []

    if hybrid:
        candidate_pool = dense[: max(k * 6, 12)]
        lexical = _lexical_rerank(candidate_pool, question)
        fts = _collect_fts_hits(
            db, question, per_table_limit=per_table_limit, curated_boost=curated_boost
        )
        lists: List[List[dict]] = [dense, lexical]
        if fts:
            lists.append(fts)
        fused = reciprocal_rank_fusion(lists)
        pool = fused or dense
    else:
        pool = dense

    pool = pool[: max(k * 6, 12)]
    ranked = _neural_rerank(pool, question)
    return _format_hits(ranked[:k])
