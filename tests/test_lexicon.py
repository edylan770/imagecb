"""Tests for search lexicon and query expansion."""

from __future__ import annotations

from imagecb.caption.lexicon import (
    SearchLexicon,
    _build_synonym_groups,
    enrich_aliases_for_tags,
    enrich_recommended_cases,
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


def test_expand_query_spec_keywords_still_excluded_from_dense():
    clear_acronym_cache()
    lex = _lexicon({"revenue", "dashboard"})
    spec = expand_query_spec(
        QuerySpec(semantic_query="sales dashboard", raw_text="sales dashboard"),
        use_llm=False,
        lexicon=lex,
    )
    dense = dense_query_text(spec)
    assert "revenue" in spec.expanded_keywords
    assert "revenue" not in dense


def test_non_acronym_token_expansion():
    lex = _lexicon({"revenue", "growth", "chart"})
    result = expand_text("sales growth chart", lex)
    assert "revenue" in result.all_terms


def test_enrich_aliases_for_tags():
    lex = _lexicon({"revenue", "sales"})
    aliases = enrich_aliases_for_tags(["sales"], lex)
    assert "revenue" in aliases


def test_enrich_recommended_cases_strips_boilerplate_not_vlm_cases():
    lex = _lexicon({"sales", "revenue"})
    existing = [
        "quarterly sales chart",
        "sales chart",
        "sales diagram",
        "sales performance",
        "revenue by region",
    ]
    out = enrich_recommended_cases(
        ["sales"],
        "performance",
        existing_cases=existing,
        lexicon=lex,
    )
    assert "quarterly sales chart" in out
    assert "revenue by region" in out
    assert "sales chart" not in out
    assert "sales diagram" not in out
    assert "sales performance" not in out
    assert enrich_recommended_cases(["sales"], "performance", lexicon=lex) == []


def test_enrich_recommended_cases_strips_bare_format_when_asset_type_set():
    lex = _lexicon({"cloud", "diagram"})
    out = enrich_recommended_cases(
        ["cloud"],
        "systems",
        existing_cases=["diagram", "cloud systems diagram"],
        lexicon=lex,
        asset_type="diagram",
    )
    assert "diagram" not in out
    assert "cloud systems diagram" in out


def test_expand_query_spec_adds_keywords():
    clear_acronym_cache()
    lex = _lexicon({"revenue", "dashboard"})
    spec = QuerySpec(semantic_query="sales dashboard", raw_text="sales dashboard")
    spec = expand_query_spec(spec, use_llm=False, lexicon=lex)
    assert "revenue" in spec.expanded_keywords


def test_dense_query_text_excludes_expanded():
    spec = QuerySpec(
        semantic_query="sales dashboard",
        expanded_keywords=["revenue"],
    )
    text = dense_query_text(spec)
    assert "sales" in text
    assert "revenue" not in text


def test_expand_query_text_no_duplicate_original():
    lex = _lexicon({"sales"})
    result = expand_text("sales", lex)
    assert "sales" not in result.all_terms or result.all_terms.count("sales") <= 1


def test_service_tag_does_not_gain_sdlc_alias():
    lex = _lexicon({"service", "military", "software", "sdlc"})
    aliases = enrich_aliases_for_tags(["service"], lex)
    assert "sdlc" not in aliases
    assert "development" not in aliases
    assert "cycle" not in aliases


def test_sdlc_tag_gets_expansion_phrase():
    lex = _lexicon({"sdlc", "software"})
    aliases = enrich_aliases_for_tags(["sdlc"], lex)
    assert "software development life cycle" in aliases
    assert "sdlc: software development life cycle" in aliases


def test_ceo_cfo_cto_groups_do_not_cross_contaminate():
    seed = load_seed_synonyms()
    groups = _build_synonym_groups(seed)
    term_to_group = {}
    for group in groups.values():
        for member in group:
            term_to_group[member] = group

    ceo_group = term_to_group.get("ceo", frozenset())
    cfo_group = term_to_group.get("cfo", frozenset())
    cto_group = term_to_group.get("cto", frozenset())
    assert "cfo" not in ceo_group or ceo_group == cfo_group
    assert "cto" not in ceo_group or ceo_group == cto_group
    assert "ceo" not in cfo_group or cfo_group == ceo_group
    assert "technology" not in cfo_group
    assert "financial" not in cto_group


def test_saas_and_sdlc_synonym_groups_are_isolated():
    seed = load_seed_synonyms()
    groups = _build_synonym_groups(seed)
    term_to_group = {}
    for group in groups.values():
        for member in group:
            term_to_group[member] = group
    saas_group = term_to_group.get("saas", frozenset())
    sdlc_group = term_to_group.get("sdlc", frozenset())
    assert "sdlc" not in saas_group
    assert "saas" not in sdlc_group
    assert "service" not in sdlc_group
