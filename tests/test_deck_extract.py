"""Tests for deck slide text extraction."""

from __future__ import annotations

from imagecb.deck.extract import (
    deck_hash,
    normalize_text_for_hash,
    slide_content_hash,
)


def test_slide_content_hash_stable():
    h1 = slide_content_hash("Title", "Body text", "Notes")
    h2 = slide_content_hash("Title", "Body text", "Notes")
    assert h1 == h2
    assert len(h1) == 64


def test_slide_content_hash_changes_with_body():
    h1 = slide_content_hash("Title", "A", None)
    h2 = slide_content_hash("Title", "B", None)
    assert h1 != h2


def test_deck_hash_order_matters():
    a = slide_content_hash("T", "a", None)
    b = slide_content_hash("T", "b", None)
    assert deck_hash([a, b]) != deck_hash([b, a])


def test_normalize_text_for_hash():
    assert normalize_text_for_hash("  hello \n\n\n world  ") == "hello\n\nworld"
