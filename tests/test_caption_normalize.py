"""Tests for tag normalization."""

from __future__ import annotations

from imagecb.caption.lexicon import SearchLexicon, normalize_tag
from imagecb.caption.normalize import normalize_tag as normalize_tag_reexport
from imagecb.caption.normalize import normalize_tags


def test_normalize_tag_lowercase_and_plural():
    assert normalize_tag("Charts") == "chart"
    assert normalize_tag("  Revenue  ") == "revenue"


def test_normalize_tag_plural_exceptions():
    assert normalize_tag("sales") == "sales"
    assert normalize_tag("business") == "business"


def test_normalize_tags_synonym_map():
    vocab = {"sales", "chart", "dashboard"}
    result = normalize_tags(["Revenue", "charts", "ppt"], vocab, lexicon=_empty_lexicon())
    assert "sales" in result
    assert "chart" in result
    assert "powerpoint" in result


def test_normalize_tags_dedupes():
    vocab: set[str] = set()
    result = normalize_tags(["chart", "charts", "Chart"], vocab, lexicon=_empty_lexicon())
    assert result == ["chart"]


def test_normalize_tags_lexicon_resolves_to_corpus_vocab():
    """sales and revenue share a synonym group; prefer corpus term."""
    lexicon = SearchLexicon(
        corpus_terms=frozenset({"revenue", "chart"}),
        seed_synonyms={"revenue": "sales", "sale": "sales"},
        synonym_groups={
            "sales": frozenset({"sales", "revenue", "sale"}),
        },
        acronym_expansions={},
        term_to_group={
            "sales": frozenset({"sales", "revenue", "sale"}),
            "revenue": frozenset({"sales", "revenue", "sale"}),
            "sale": frozenset({"sales", "revenue", "sale"}),
        },
    )
    vocab = {"revenue", "chart"}
    result = normalize_tags(["sales", "charts"], vocab, lexicon=lexicon)
    assert result == ["revenue", "chart"]


def test_normalize_tag_reexport_matches_lexicon():
    assert normalize_tag_reexport is normalize_tag


def _empty_lexicon() -> SearchLexicon:
    return SearchLexicon(
        corpus_terms=frozenset(),
        seed_synonyms={},
        synonym_groups={},
        acronym_expansions={},
        term_to_group={},
    )

