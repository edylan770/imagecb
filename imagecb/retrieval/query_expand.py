"""Query-time synonym and acronym expansion against the search lexicon."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from imagecb.caption.lexicon import (
    ExpandedQuery,
    SearchLexicon,
    build_search_lexicon,
    expand_text,
    is_acronym_like,
    normalize_tag,
    tokenize_text,
)
from imagecb.models.llm import get_query_llm
from imagecb.retrieval.query_parser import QuerySpec

logger = logging.getLogger(__name__)

_acronym_llm_cache: Dict[str, str] = {}


def _collect_query_text(spec: QuerySpec) -> str:
    parts: List[str] = []
    semantic = (spec.semantic_query or spec.raw_text or "").strip()
    if semantic:
        parts.append(semantic)
    parts.extend(k for k in spec.must_have_keywords if k)
    return " ".join(parts).strip()


def _unknown_acronym_tokens(text: str, lexicon: SearchLexicon) -> List[str]:
    """Return acronym-like tokens without a static expansion."""
    unknown: List[str] = []
    for token in tokenize_text(text):
        if not is_acronym_like(token):
            continue
        norm = normalize_tag(token)
        if norm and not lexicon.expand_acronym_static(norm):
            unknown.append(norm)
    return unknown


def _expand_acronym_via_llm(token: str, lexicon: SearchLexicon) -> Optional[str]:
    """LLM fallback for unrecognized acronyms; cached per process."""
    norm = normalize_tag(token)
    if not norm:
        return None
    if norm in _acronym_llm_cache:
        return _acronym_llm_cache[norm]

    vocab_hint = sorted(lexicon.corpus_terms)[:50]
    try:
        expansion = get_query_llm().expand_acronym(norm, vocab_hint)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Acronym LLM expansion failed for %r: %s", norm, exc)
        return None

    if expansion:
        _acronym_llm_cache[norm] = expansion
        lexicon.acronym_expansions[norm] = expansion
    return expansion or None


def expand_query_text(
    text: str,
    lexicon: Optional[SearchLexicon] = None,
    *,
    use_llm: bool = True,
) -> ExpandedQuery:
    """Run full expansion pipeline on raw query text."""
    if lexicon is None:
        lexicon = build_search_lexicon()

    if use_llm:
        for token in _unknown_acronym_tokens(text, lexicon):
            _expand_acronym_via_llm(token, lexicon)

    return expand_text(text, lexicon)


def expand_query_spec(
    spec: QuerySpec,
    *,
    use_llm: bool = True,
    lexicon: Optional[SearchLexicon] = None,
) -> QuerySpec:
    """Expand semantic query and must-have keywords via lexicon pipeline."""
    if lexicon is None:
        lexicon = build_search_lexicon()

    combined = _collect_query_text(spec)
    if not combined:
        spec.expanded_keywords = []
        return spec

    expanded = expand_query_text(combined, lexicon, use_llm=use_llm)
    spec.expanded_keywords = expanded.all_terms
    return spec


def clear_acronym_cache() -> None:
    """Clear in-process LLM acronym cache (for tests)."""
    _acronym_llm_cache.clear()
