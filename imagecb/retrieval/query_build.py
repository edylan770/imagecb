"""Shared query text and refinement heuristics for hybrid retrieval."""

from __future__ import annotations

from typing import List

from imagecb.retrieval.query_parser import QuerySpec


def dense_query_text(spec: QuerySpec) -> str:
    """Text used for dense embedding and sparse BM25 (semantic + must-have)."""
    parts: List[str] = []
    semantic = (spec.semantic_query or spec.raw_text or "").strip()
    if semantic:
        parts.append(semantic)
    parts.extend(k for k in spec.must_have_keywords if k)
    return " ".join(parts).strip()


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
