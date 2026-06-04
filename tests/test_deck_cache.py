"""Tests for deck disk cache."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from pathlib import Path

from imagecb.deck.cache import (
    get_deck_manifest,
    get_slide_llm_cache,
    put_deck_manifest,
    put_slide_llm_cache,
    request_fingerprint,
    search_fingerprint,
)
from imagecb.deck.llm import SlideLLMOutput


@pytest.fixture
def deck_cache_dir(tmp_path, monkeypatch):
    cache = tmp_path / "deck_cache"
    fake_settings = Mock()
    fake_settings.deck_cache_enabled = True
    fake_settings.deck_cache_dir = cache
    monkeypatch.setattr("imagecb.deck.cache.SETTINGS", fake_settings)

    def slide_path(content_hash: str) -> Path:
        return cache / "slides" / f"{content_hash}.json"

    def deck_path(deck_hash: str) -> Path:
        return cache / "decks" / f"{deck_hash}.json"

    monkeypatch.setattr("imagecb.deck.cache._slide_cache_path", slide_path)
    monkeypatch.setattr("imagecb.deck.cache._deck_cache_path", deck_path)
    return cache


def test_slide_llm_cache_roundtrip(deck_cache_dir):
    out = SlideLLMOutput(
        slide_index=3,
        status="image_needed",
        description="Office teamwork photo",
    )
    put_slide_llm_cache("abc123", 3, out)
    cached = get_slide_llm_cache("abc123")
    assert cached is not None
    assert cached.status == "image_needed"
    assert cached.description == "Office teamwork photo"


def test_deck_manifest_roundtrip(deck_cache_dir):
    put_deck_manifest(
        "deck1",
        "demo.pptx",
        ["h1", "h2"],
        [{"slide_index": 1, "status": "image_needed"}],
    )
    m = get_deck_manifest("deck1")
    assert m is not None
    assert m.filename == "demo.pptx"
    assert len(m.slide_hashes) == 2


def test_search_fingerprint_includes_corpus(monkeypatch):
    monkeypatch.setattr(
        "imagecb.deck.cache.corpus_fingerprint",
        lambda: "corpfp",
    )
    fp1 = search_fingerprint("query", top_k=10, min_match_percent=0)
    fp2 = search_fingerprint("query", top_k=5, min_match_percent=0)
    assert fp1 != fp2


def test_request_fingerprint_includes_corpus_and_params(monkeypatch):
    monkeypatch.setattr(
        "imagecb.deck.cache.corpus_fingerprint",
        lambda: "corpfp",
    )
    fp1 = request_fingerprint(top_k=10, min_match_percent=0)
    fp2 = request_fingerprint(top_k=5, min_match_percent=0)
    fp3 = request_fingerprint(top_k=10, min_match_percent=50)
    assert fp1 != fp2
    assert fp1 != fp3


def test_deck_manifest_stores_request_fingerprint(deck_cache_dir):
    put_deck_manifest(
        "deck1",
        "demo.pptx",
        ["h1"],
        [{"slide_index": 1}],
        request_fingerprint="reqfp",
    )
    m = get_deck_manifest("deck1")
    assert m is not None
    assert m.request_fingerprint == "reqfp"
