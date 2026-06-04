"""Tests for direct deck search helper."""

from __future__ import annotations

from unittest import mock

from datetime import datetime

from imagecb.deck.search import search_for_description
from imagecb.retrieval.rerank import RankedResult
from imagecb.storage.metadata_db import ImageRecord


def _fake_record() -> ImageRecord:
    return ImageRecord(
        image_id="img1",
        content_hash="hash-img1",
        image_path="data/images/img1.png",
        source_file="/x/a.png",
        source_type="image",
        source_modified_at=None,
        source_created_at=None,
        author=None,
        slide_index=None,
        page_index=None,
        slide_title=None,
        slide_notes=None,
        ocr_text="",
        caption_short="test caption",
        caption_detailed=None,
        objects_json=None,
        tags_json=None,
        scene=None,
        text_overlay_summary=None,
        image_name="",
        use_case="",
        recommended_cases_json="[]",
        created_at=datetime.utcnow(),
    )


def test_search_for_description_calls_pipeline():
    fake_ranked = [
        RankedResult(
            image_id="img1",
            score=0.9,
            record=_fake_record(),
            provenance_line="a.png",
        )
    ]
    with (
        mock.patch("imagecb.deck.search.search") as mock_search,
        mock.patch("imagecb.deck.search.rerank", return_value=fake_ranked),
        mock.patch("imagecb.deck.search.build_result_cards") as mock_cards,
    ):
        from imagecb.retrieval.hybrid import SearchOutcome

        mock_search.return_value = SearchOutcome(candidates=[])
        mock_cards.return_value = []
        cards, ranked = search_for_description("sunset over mountains", top_k=5)
        assert cards == []
        assert ranked == fake_ranked
        mock_search.assert_called_once()
        call_spec = mock_search.call_args[0][0]
        assert call_spec.semantic_query == "sunset over mountains"
