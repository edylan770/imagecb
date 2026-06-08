"""Tests for query expansion pipeline."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from imagecb.caption.lexicon import SearchLexicon, _build_synonym_groups, load_seed_synonyms
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


def test_expand_query_spec_without_llm():
    clear_acronym_cache()
    lex = _lexicon({"revenue"})
    spec = expand_query_spec(
        QuerySpec(semantic_query="sales chart", raw_text="sales chart"),
        use_llm=False,
        lexicon=lex,
    )
    assert "revenue" in spec.expanded_keywords


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_llm_acronym_fallback(mock_get_llm):
    clear_acronym_cache()
    mock_llm = MagicMock()
    mock_llm.expand_acronym.return_value = "unknown business term"
    mock_get_llm.return_value = mock_llm

    lex = _lexicon({"business", "term"})
    lex.acronym_expansions.pop("xyz", None)

    result = expand_query_text("xyz chart", lex, use_llm=True)
    mock_llm.expand_acronym.assert_called_once()
    assert mock_llm.expand_acronym.call_args[0][0] == "xyz"


def test_known_acronym_skips_llm():
    clear_acronym_cache()
    lex = _lexicon({"software", "development"})
    with patch("imagecb.retrieval.query_expand.get_query_llm") as mock_get_llm:
        expand_query_text("sdlc", lex, use_llm=True)
        mock_get_llm.assert_not_called()
