"""Tests for query expansion pipeline."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from imagecb.caption.lexicon import (
    AcronymCache,
    SearchLexicon,
    _build_synonym_groups,
    is_llm_acronym_candidate,
    load_seed_synonyms,
    reset_acronym_file_cache,
)
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


@pytest.fixture
def isolated_acronym_cache(tmp_path, monkeypatch):
    """Point acronym cache at a temp file for file-backed tests."""
    path = tmp_path / "acronym_cache.json"
    mock_settings = MagicMock()
    mock_settings.acronym_cache_path = path
    monkeypatch.setattr("imagecb.caption.lexicon.SETTINGS", mock_settings)
    clear_acronym_cache()
    yield path
    clear_acronym_cache()


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
def test_llm_acronym_fallback(mock_get_llm, isolated_acronym_cache):
    clear_acronym_cache()
    mock_llm = MagicMock()
    mock_llm.expand_acronym.return_value = "unknown business term"
    mock_get_llm.return_value = mock_llm

    lex = _lexicon({"business", "term"})
    lex.acronym_expansions.pop("xyz", None)

    result = expand_query_text("xyz chart", lex, use_llm=True, raw_text="xyz chart")
    mock_llm.expand_acronym.assert_called_once()
    assert mock_llm.expand_acronym.call_args[0][0] == "xyz"
    assert "unknown business term" in result.acronym_expansions.get("xyz", "")


def test_known_acronym_skips_llm():
    clear_acronym_cache()
    lex = _lexicon({"software", "development"})
    with patch("imagecb.retrieval.query_expand.get_query_llm") as mock_get_llm:
        expand_query_text("sdlc", lex, use_llm=True, raw_text="sdlc")
        mock_get_llm.assert_not_called()


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_denylist_skips_llm(mock_get_llm):
    clear_acronym_cache()
    lex = _lexicon({"chart"})
    expand_query_text("sys chart", lex, use_llm=True, raw_text="sys chart")
    mock_get_llm.assert_not_called()
    assert not is_llm_acronym_candidate("sys", "sys chart", lexicon=lex)


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_negative_cache_skips_llm(mock_get_llm, isolated_acronym_cache):
    isolated_acronym_cache.write_text(
        json.dumps({"expansions": {}, "negative": ["xyz"]}),
        encoding="utf-8",
    )
    reset_acronym_file_cache()

    lex = _lexicon({"chart"})
    lex.acronym_expansions.pop("xyz", None)
    expand_query_text("xyz chart", lex, use_llm=True, raw_text="xyz chart")
    mock_get_llm.assert_not_called()


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_persistent_cache_skips_llm(mock_get_llm, isolated_acronym_cache):
    isolated_acronym_cache.write_text(
        json.dumps({"expansions": {"xyz": "unknown business term"}, "negative": []}),
        encoding="utf-8",
    )
    reset_acronym_file_cache()

    lex = _lexicon({"business", "term"})
    lex.acronym_expansions["xyz"] = "unknown business term"
    expand_query_text("xyz chart", lex, use_llm=True, raw_text="xyz chart")
    mock_get_llm.assert_not_called()
    assert "unknown business term" in expand_query_text(
        "xyz chart", lex, use_llm=False, raw_text="xyz chart"
    ).acronym_expansions.get("xyz", "")


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_uppercase_acronym_triggers_llm(mock_get_llm, isolated_acronym_cache):
    clear_acronym_cache()
    mock_llm = MagicMock()
    mock_llm.expand_acronym.return_value = "national aeronautics and space administration"
    mock_get_llm.return_value = mock_llm

    lex = _lexicon({"launch"})
    lex.acronym_expansions.pop("nasa", None)

    expand_query_text("NASA launch", lex, use_llm=True, raw_text="NASA launch")
    mock_llm.expand_acronym.assert_called_once()
    assert mock_llm.expand_acronym.call_args[0][0] == "nasa"


@patch("imagecb.retrieval.query_expand.get_query_llm")
def test_llm_empty_response_adds_negative_cache(mock_get_llm, isolated_acronym_cache):
    mock_llm = MagicMock()
    mock_llm.expand_acronym.return_value = ""
    mock_get_llm.return_value = mock_llm

    lex = _lexicon({"chart"})
    lex.acronym_expansions.pop("xyz", None)
    expand_query_text("xyz chart", lex, use_llm=True, raw_text="xyz chart")

    data = json.loads(isolated_acronym_cache.read_text(encoding="utf-8"))
    assert "xyz" in data["negative"]
