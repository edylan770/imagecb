"""Tests for tag normalization."""

from __future__ import annotations

from imagecb.caption.normalize import normalize_tag, normalize_tags


def test_normalize_tag_lowercase_and_plural():
    assert normalize_tag("Charts") == "chart"
    assert normalize_tag("  Revenue  ") == "revenue"


def test_normalize_tag_plural_exceptions():
    assert normalize_tag("sales") == "sales"
    assert normalize_tag("business") == "business"


def test_normalize_tags_synonym_map():
    vocab = {"sales", "chart", "dashboard"}
    result = normalize_tags(["Revenue", "charts", "ppt"], vocab)
    assert "sales" in result
    assert "chart" in result
    assert "powerpoint" in result


def test_normalize_tags_dedupes():
    vocab: set[str] = set()
    result = normalize_tags(["chart", "charts", "Chart"], vocab)
    assert result == ["chart"]
