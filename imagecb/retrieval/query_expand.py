"""Query-time synonym and acronym expansion against the search lexicon."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from imagecb.caption.lexicon import (
    ExpandedQuery,
    SearchLexicon,
    add_acronym_expansion,
    add_acronym_negative,
    build_search_lexicon,
    expand_text,
    is_llm_acronym_candidate,
    normalize_tag,
    reset_acronym_file_cache,
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


def _unknown_acronym_tokens(text: str, raw_text: str, lexicon: SearchLexicon) -> List[str]:
    """Return strict LLM acronym candidates without a static expansion."""
    unknown: List[str] = []
    for token in tokenize_text(text):
        if not is_llm_acronym_candidate(token, raw_text, lexicon=lexicon):
            continue
        norm = normalize_tag(token)
        if norm:
            unknown.append(norm)
    return unknown


def _merge_expanded_keywords(expanded: ExpandedQuery) -> List[str]:
    """Union corpus-aligned synonym terms with full acronym expansion phrases."""
    seen: set[str] = set()
    out: List[str] = []
    for term in expanded.all_terms:
        key = term.lower()
        if key not in seen:
            seen.add(key)
            out.append(term)
    for phrase in expanded.acronym_expansions.values():
        phrase = (phrase or "").strip()
        if not phrase:
            continue
        key = phrase.lower()
        if key not in seen:
            seen.add(key)
            out.append(phrase)
    return out


def _expand_acronym_via_llm(token: str, lexicon: SearchLexicon) -> Optional[str]:
    """LLM fallback for unrecognized acronyms; cached per process and on disk."""
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

    expansion = (expansion or "").strip().lower()
    if expansion:
        _acronym_llm_cache[norm] = expansion
        lexicon.acronym_expansions[norm] = expansion
        add_acronym_expansion(norm, expansion)
    else:
        add_acronym_negative(norm)
    return expansion or None


def expand_query_text(
    text: str,
    lexicon: Optional[SearchLexicon] = None,
    *,
    use_llm: bool = True,
    raw_text: str = "",
) -> ExpandedQuery:
    """Run full expansion pipeline on raw query text."""
    if lexicon is None:
        lexicon = build_search_lexicon()

    source_text = raw_text or text
    if use_llm:
        for token in _unknown_acronym_tokens(text, source_text, lexicon):
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

    raw = (spec.raw_text or spec.semantic_query or combined).strip()
    expanded = expand_query_text(combined, lexicon, use_llm=use_llm, raw_text=raw)
    spec.expanded_keywords = _merge_expanded_keywords(expanded)
    return spec


def clear_acronym_cache() -> None:
    """Clear in-process and file-backed acronym caches (for tests)."""
    _acronym_llm_cache.clear()
    reset_acronym_file_cache()
