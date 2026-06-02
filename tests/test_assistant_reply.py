"""Tests for template-based assistant replies."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import patch

import pytest

from imagecb.formatting.assistant_reply import (
    build_assistant_reply,
    format_assistant_message,
    provenance_from_record,
)
from imagecb.retrieval.query_parser import QuerySpec
from imagecb.retrieval.rerank import RankedResult
from imagecb.storage.metadata_db import ImageRecord


def _record(
    *,
    image_id: str = "id-1",
    source_file: str = "/docs/Q3_Review.pptx",
    source_type: str = "pptx",
    slide_index: int | None = 3,
    page_index: int | None = None,
    caption_short: str = "Bar chart of quarterly revenue",
    author: str | None = "Alice",
) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        content_hash=f"hash-{image_id}",
        image_path=f"data/images/{image_id}.png",
        source_file=source_file,
        source_type=source_type,
        source_modified_at=datetime(2024, 9, 15),
        source_created_at=None,
        author=author,
        slide_index=slide_index,
        page_index=page_index,
        slide_title=None,
        slide_notes=None,
        ocr_text=None,
        caption_short=caption_short,
        caption_detailed=None,
        objects_json=None,
        tags_json=None,
        scene=None,
        text_overlay_summary=None,
        created_at=datetime.utcnow(),
    )


def _ranked(record: ImageRecord, score: float = 0.9) -> RankedResult:
    from imagecb.retrieval.rerank import _format_provenance

    return RankedResult(
        image_id=record.image_id,
        score=score,
        record=record,
        provenance_line=_format_provenance(record),
    )


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value="/tmp/x.png")
def test_zero_results(_mock_resolve):
    msg = format_assistant_message([], None)
    assert "couldn't find" in msg.lower()
    assert "rephrasing" in msg.lower()


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value="/tmp/x.png")
def test_single_pptx_result(_mock_resolve):
    r = _ranked(_record())
    msg = format_assistant_message([r], None)
    assert "1 image" in msg.lower() or "1 images" not in msg.lower()
    assert "Q3_Review" in msg
    assert "Bar chart" in msg
    assert "Found 10" not in msg


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value="/tmp/x.png")
def test_multi_source_batch(_mock_resolve):
    results = [
        _ranked(_record(image_id="a", slide_index=3)),
        _ranked(_record(image_id="b", slide_index=7, caption_short="KPI dashboard")),
        _ranked(_record(image_id="c", slide_index=12, caption_short="Executive summary")),
        _ranked(
            _record(
                image_id="d",
                source_file="/docs/logo.png",
                source_type="image",
                slide_index=None,
                caption_short="Company logo",
            )
        ),
    ]
    msg = format_assistant_message(results, None)
    assert "4" in msg
    assert "Highlights" in msg
    assert "Slide 3" in msg
    assert "results panel" in msg.lower()


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value="/tmp/x.png")
def test_refinement_prefix(_mock_resolve):
    spec = QuerySpec(is_refinement=True)
    r = _ranked(_record())
    msg = format_assistant_message([r], spec)
    assert msg.startswith("Narrowed from your previous search")


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value=None)
def test_missing_file_footer(_mock_resolve):
    r = _ranked(_record())
    msg = format_assistant_message([r], None)
    assert "missing image files" in msg.lower()


def test_provenance_from_record():
    prov = provenance_from_record(_record())
    assert prov.source_name == "Q3_Review.pptx"
    assert prov.slide_index == 3
    assert prov.modified == "2024-09-15"
    assert prov.author == "Alice"
    assert "Slide 3" in prov.location_label()


@patch("imagecb.formatting.assistant_reply.resolve_image_file", return_value="/tmp/x.png")
def test_build_assistant_reply_cards(_mock_resolve):
    reply = build_assistant_reply([_ranked(_record(), score=0.87)])
    assert reply.message
    assert len(reply.results) == 1
    assert reply.results[0].image_url == "/api/images/id-1"
    assert reply.results[0].provenance.source_name == "Q3_Review.pptx"
    assert reply.results[0].match_percent == 94
