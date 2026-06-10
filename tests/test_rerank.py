"""Tests for rerank score filtering."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

from imagecb.retrieval.hybrid import Candidate
from imagecb.retrieval.rerank import RankedResult, _candidate_text, rerank
from imagecb.storage.metadata_db import serialize_list
from imagecb.storage.metadata_db import ImageRecord


def _record(image_id: str) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        content_hash=f"hash-{image_id}",
        image_path=f"data/images/{image_id}.png",
        source_file="/docs/test.pptx",
        source_type="pptx",
        source_modified_at=datetime(2024, 9, 15),
        source_created_at=None,
        author=None,
        slide_index=1,
        page_index=None,
        slide_title=None,
        slide_notes=None,
        ocr_text=None,
        caption_short="Test caption",
        caption_detailed=None,
        objects_json=None,
        tags_json=None,
        scene=None,
        text_overlay_summary=None,
        created_at=datetime.utcnow(),
    )


@patch("imagecb.retrieval.rerank.get_reranker")
@patch("imagecb.retrieval.rerank.metadata_db.get_records")
def test_rerank_filters_by_min_score(mock_get_records, mock_get_reranker):
    records = [_record("a"), _record("b"), _record("c")]
    mock_get_records.return_value = records
    mock_get_reranker.return_value.score.return_value = [0.95, 0.72, 0.88]

    candidates = [
        Candidate(image_id="a", dense_score=0.9, fused_score=0.9),
        Candidate(image_id="b", dense_score=0.8, fused_score=0.8),
        Candidate(image_id="c", dense_score=0.85, fused_score=0.85),
    ]

    results = rerank("cybersecurity", candidates, top_k=10, min_score=0.8)

    assert len(results) == 2
    assert results[0].image_id == "a"
    assert results[1].image_id == "c"


@patch("imagecb.retrieval.rerank.get_reranker")
@patch("imagecb.retrieval.rerank.metadata_db.get_records")
def test_rerank_min_score_zero_returns_all(mock_get_records, mock_get_reranker):
    records = [_record("a"), _record("b")]
    mock_get_records.return_value = records
    mock_get_reranker.return_value.score.return_value = [0.5, 0.4]

    candidates = [
        Candidate(image_id="a", dense_score=0.5, fused_score=0.5),
        Candidate(image_id="b", dense_score=0.4, fused_score=0.4),
    ]

    results = rerank("test", candidates, top_k=10, min_score=0.0)

    assert len(results) == 2


def test_candidate_text_includes_theme_not_aliases():
    record = _record("x")
    record.theme = "financial reporting"
    record.search_aliases_json = serialize_list(["sales", "earnings"])
    record.slide_body_text = "Quarterly metrics"
    record.asset_type = "chart"
    text = _candidate_text(record)
    assert "asset_type: Chart" in text
    assert "financial reporting" in text
    assert "Quarterly metrics" in text
    assert "aliases:" not in text
    assert "earnings" not in text
