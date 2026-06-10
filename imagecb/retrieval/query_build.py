"""Shared query text and refinement heuristics for hybrid retrieval."""

from __future__ import annotations

from typing import List, Tuple

from imagecb.caption.lexicon import load_seed_synonyms, normalize_tag, tokenize_text
from imagecb.config import SETTINGS
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


def query_token_count(spec: QuerySpec) -> int:
    """Approximate query length in tokens for retrieval tuning."""
    text = (spec.semantic_query or spec.raw_text or "").strip()
    return len(tokenize_text(text)) + len(spec.must_have_keywords)


def is_short_query(spec: QuerySpec) -> bool:
    return query_token_count(spec) <= SETTINGS.short_query_max_tokens


def _is_strict_acronym_token(token: str) -> bool:
    """True for short consonant-heavy tokens (sdlc, kpi), not content words in seed map."""
    import re

    from imagecb.caption.lexicon import _ACRONYM_RE

    t = normalize_tag(token)
    if not t or " " in t or len(t) < 2 or len(t) > 6:
        return False
    if re.search(r"[aeiou]", t):
        return False
    return bool(_ACRONYM_RE.match(t))


def _seed_expansions_for_spec(spec: QuerySpec) -> List[str]:
    """Acronym-only seed-map expansions for short queries."""
    if not is_short_query(spec) or spec.must_have_keywords:
        return []

    seed = load_seed_synonyms()
    text = (spec.semantic_query or spec.raw_text or "").strip()
    tokens = tokenize_text(text)
    out: List[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not _is_strict_acronym_token(token):
            continue
        norm = normalize_tag(token)
        phrase = seed.get(norm) or seed.get(token.lower())
        if not phrase:
            continue
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            out.append(phrase)
    return out


def dense_query_text(spec: QuerySpec) -> str:
    """Text used for dense embedding and sparse BM25 (semantic + must-have only)."""
    parts: List[str] = []
    semantic = (spec.semantic_query or spec.raw_text or "").strip()
    if semantic:
        parts.append(semantic)
    parts.extend(k for k in spec.must_have_keywords if k)
    parts.extend(_seed_expansions_for_spec(spec))
    return _dedupe_join(parts)


def rerank_query_text(spec: QuerySpec, fallback: str = "") -> str:
    """Text passed to the cross-encoder reranker."""
    text = dense_query_text(spec)
    if text:
        return text
    return (fallback or "").strip()


def resolve_rerank_top_n(spec: QuerySpec) -> int:
    if is_short_query(spec):
        return SETTINGS.short_query_rerank_top_n
    return SETTINGS.rerank_top_n


def resolve_retrieval_top_k(spec: QuerySpec) -> Tuple[int, int]:
    if is_short_query(spec):
        k = SETTINGS.short_query_retrieval_top_k
        return k, k
    return SETTINGS.dense_top_k, SETTINGS.sparse_top_k


def should_restrict_to_previous(spec: QuerySpec, user_text: str, pool_size: int) -> bool:
    """Whether to limit search to the previous turn's candidate pool."""
    if pool_size <= 0:
        return False
    return spec.is_refinement
