"""Shared query text and refinement heuristics for hybrid retrieval."""

from __future__ import annotations

from typing import List

from imagecb.retrieval.query_parser import QuerySpec


def _dedupe_join(parts: List[str]) -> str:
    seen: set[str] = set()
    out: List[str] = []
    for p in parts:
        p = (p or "").strip()
        if not p:
            continue
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return " ".join(out).strip()


def dense_query_text(spec: QuerySpec) -> str:
    """Text used for dense embedding and sparse BM25 (semantic + must-have + expanded)."""
    parts: List[str] = []
    semantic = (spec.semantic_query or spec.raw_text or "").strip()
    if semantic:
        parts.append(semantic)
    parts.extend(k for k in spec.must_have_keywords if k)
    parts.extend(k for k in spec.expanded_keywords if k)
    return _dedupe_join(parts)


def rerank_query_text(spec: QuerySpec, fallback: str = "") -> str:
    """Text passed to the cross-encoder reranker."""
    text = dense_query_text(spec)
    if text:
        return text
    return (fallback or "").strip()


def should_restrict_to_previous(spec: QuerySpec, user_text: str, pool_size: int) -> bool:
    """Whether to limit search to the previous turn's candidate pool."""
    if pool_size <= 0:
        return False
    return spec.is_refinement
