"""Tests for LLM suggestion generation and cache."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest

from imagecb.suggestions import generate as gen_mod
from imagecb.suggestions.corpus_summary import CorpusContext, SourceFileStat
from imagecb.suggestions.generate import (
    ONBOARDING_SUGGESTIONS,
    generate_suggestions,
    normalize_recent_titles,
    _coerce_suggestions_json,
)


@pytest.fixture(autouse=True)
def clear_cache():
    gen_mod._cache.clear()
    yield
    gen_mod._cache.clear()


def test_coerce_suggestions_json_from_object():
    raw = '{"suggestions": ["Find charts", "Logos only"]}'
    assert _coerce_suggestions_json(raw) == ["Find charts", "Logos only"]


def test_coerce_suggestions_json_strips_fences():
    raw = '```json\n{"suggestions": ["A", "B"]}\n```'
    assert _coerce_suggestions_json(raw) == ["A", "B"]


def test_normalize_recent_titles_dedupes_and_skips_new_chat():
    titles = ["New chat", "Charts", "charts", "  ", "Logos"]
    assert normalize_recent_titles(titles) == ("Charts", "Logos")


def test_empty_corpus_returns_onboarding_without_llm():
    ctx = CorpusContext(indexed_count=0, fingerprint="empty")
    with patch.object(gen_mod, "get_suggestion_llm") as mock_llm:
        result = generate_suggestions([], limit=4, ctx=ctx)
    mock_llm.assert_not_called()
    assert result.suggestions == ONBOARDING_SUGGESTIONS[:4]
    assert result.cached is False


def test_llm_success_populates_suggestions():
    ctx = CorpusContext(
        indexed_count=10,
        source_files=(SourceFileStat(name="deck.pptx", source_type="pptx", count=5),),
        fingerprint="abc123",
    )
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"suggestions": ["A", "B", "C", "D"]}'
    with patch.object(gen_mod, "get_suggestion_llm", return_value=mock_llm):
        r1 = generate_suggestions(["Past search"], limit=4, ctx=ctx)
    assert r1.suggestions == ["A", "B", "C", "D"]
    assert r1.cached is False
    mock_llm.generate.assert_called_once()


def test_cache_hit_on_second_call():
    ctx = CorpusContext(indexed_count=5, fingerprint="fp1")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"suggestions": ["One", "Two", "Three", "Four"]}'
    with patch.object(gen_mod, "get_suggestion_llm", return_value=mock_llm):
        r1 = generate_suggestions([], limit=4, ctx=ctx)
        r2 = generate_suggestions([], limit=4, ctx=ctx)
    assert r1.cached is False
    assert r2.cached is True
    assert r2.suggestions == r1.suggestions
    mock_llm.generate.assert_called_once()


def test_llm_failure_uses_fallback():
    ctx = CorpusContext(indexed_count=3, fingerprint="fp2")
    mock_llm = MagicMock()
    mock_llm.generate.side_effect = RuntimeError("bedrock down")
    with patch.object(gen_mod, "get_suggestion_llm", return_value=mock_llm):
        result = generate_suggestions([], limit=4, ctx=ctx)
    assert len(result.suggestions) == 4
    assert result.cached is False


def test_cache_expires_after_ttl():
    ctx = CorpusContext(indexed_count=2, fingerprint="fp3")
    mock_llm = MagicMock()
    mock_llm.generate.return_value = '{"suggestions": ["X", "Y", "Z", "W"]}'
    titles = gen_mod.normalize_recent_titles([])
    key = gen_mod._cache_key(ctx, titles)
    with patch.object(gen_mod, "get_suggestion_llm", return_value=mock_llm):
        generate_suggestions([], limit=4, ctx=ctx)
        gen_mod._cache[key] = (time.monotonic() - 10_000, ["X", "Y", "Z", "W"])
        generate_suggestions([], limit=4, ctx=ctx)
    assert mock_llm.generate.call_count == 2
