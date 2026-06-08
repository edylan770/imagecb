"""Tests for search lexicon and query expansion."""

from __future__ import annotations

from imagecb.caption.lexicon import (
    SearchLexicon,
    _build_synonym_groups,
    enrich_aliases_for_tags,
    expand_term,
    expand_text,
    load_seed_synonyms,
)
from imagecb.retrieval.query_build import dense_query_text
from imagecb.retrieval.query_expand import clear_acronym_cache, expand_query_spec, expand_query_text
from imagecb.retrieval.query_parser import QuerySpec


def _lexicon(corpus: set[str]) -> SearchLexicon:
    seed = load_seed_synonyms()
    groups = _build_synonym_groups(seed)
    term_to_group = {}
    for group in groups.values():
        for member in group:
            term_to_group[member] = group
    return SearchLexicon(
        corpus_terms=frozenset(corpus),
        seed_synonyms=seed,
        synonym_groups=groups,
        acronym_expansions=dict(seed),
        term_to_group=term_to_group,
    )


def test_bidirectional_sales_revenue():
    lex = _lexicon({"revenue", "dashboard"})
    matched = expand_term("sales", lex)
    assert "revenue" in matched


def test_bidirectional_revenue_sales():
    lex = _lexicon({"sales", "dashboard"})
    matched = expand_term("revenue", lex)
    assert "sales" in matched


def test_sdlc_acronym_expansion():
    lex = _lexicon({"software", "development", "diagram"})
    result = expand_text("sdlc diagram", lex)
    assert "sdlc" in result.acronym_expansions
    assert "software development life cycle" in result.acronym_expansions["sdlc"]


def test_non_acronym_token_expansion():
    lex = _lexicon({"revenue", "growth", "chart"})
    result = expand_text("sales growth chart", lex)
    assert "revenue" in result.all_terms


def test_enrich_aliases_for_tags():
    lex = _lexicon({"revenue", "sales"})
    aliases = enrich_aliases_for_tags(["sales"], lex)
    assert "revenue" in aliases


def test_expand_query_spec_adds_keywords():
    clear_acronym_cache()
    lex = _lexicon({"revenue", "dashboard"})
    spec = QuerySpec(semantic_query="sales dashboard", raw_text="sales dashboard")
    spec = expand_query_spec(spec, use_llm=False, lexicon=lex)
    assert "revenue" in spec.expanded_keywords


def test_dense_query_text_includes_expanded():
    spec = QuerySpec(
        semantic_query="sales dashboard",
        expanded_keywords=["revenue"],
    )
    text = dense_query_text(spec)
    assert "sales" in text
    assert "revenue" in text


def test_expand_query_text_no_duplicate_original():
    lex = _lexicon({"sales"})
    result = expand_text("sales", lex)
    assert "sales" not in result.all_terms or result.all_terms.count("sales") <= 1
