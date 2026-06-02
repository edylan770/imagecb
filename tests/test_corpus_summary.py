"""Tests for corpus summary aggregation."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from imagecb.suggestions.corpus_summary import (
    _summarize_records,
    build_corpus_context,
    context_to_prompt_text,
)


def _record(
    *,
    source_file: str = "/data/deck.pptx",
    source_type: str = "pptx",
    author: str = "Alice",
    caption_short: str = "A bar chart",
    modified: datetime | None = None,
):
    return SimpleNamespace(
        source_file=source_file,
        source_type=source_type,
        author=author,
        caption_short=caption_short,
        source_modified_at=modified or datetime(2024, 6, 1),
    )


def test_summarize_records_aggregates_sources_and_authors():
    records = [
        _record(source_file="/a/Q3.pptx", author="Alice"),
        _record(source_file="/a/Q3.pptx", author="Alice"),
        _record(source_file="/b/report.pdf", source_type="pdf", author="Bob"),
    ]
    ctx = _summarize_records(records)
    assert ctx.indexed_count == 3
    assert ctx.source_files[0].name == "Q3.pptx"
    assert ctx.source_files[0].count == 2
    assert "Alice" in ctx.authors
    assert ctx.fingerprint


def test_fingerprint_stable_for_same_data():
    records = [_record(), _record(source_file="/b/x.pdf", source_type="pdf")]
    a = _summarize_records(records)
    b = _summarize_records(records)
    assert a.fingerprint == b.fingerprint


def test_empty_records_zero_count():
    ctx = _summarize_records([])
    assert ctx.indexed_count == 0
    assert ctx.fingerprint


def test_context_to_prompt_text_includes_sources():
    ctx = _summarize_records([_record(source_file="/data/deck.pptx")])
    text = context_to_prompt_text(ctx)
    assert "deck.pptx" in text
    assert "Indexed images: 1" in text


@patch("imagecb.suggestions.corpus_summary.metadata_db.get_all_records")
def test_build_corpus_context_calls_db(mock_get):
    mock_get.return_value = [_record()]
    ctx = build_corpus_context()
    assert ctx.indexed_count == 1
    mock_get.assert_called_once()
