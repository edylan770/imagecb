"""Search and interaction telemetry."""

from __future__ import annotations

import json
from datetime import datetime

import pytest

from imagecb.retrieval.query_parser import QuerySpec
from imagecb.retrieval.rerank import RankedResult
from imagecb.storage.metadata_db import ImageRecord, get_engine, session_scope
from imagecb.telemetry.models import SearchEvent
from imagecb.telemetry.recorder import record_interaction, record_search_from_results
from imagecb.telemetry.schema import ensure_telemetry_schema


def _sample_record(image_id: str) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        content_hash=f"hash-{image_id}",
        image_path=f"/tmp/{image_id}.png",
        source_file="/tmp/doc.pptx",
        source_type="pptx",
        created_at=datetime.utcnow(),
    )


@pytest.fixture(autouse=True)
def _ensure_db():
    get_engine()
    ensure_telemetry_schema()
    yield


def test_record_search_and_interaction_linkage():
    results = [
        RankedResult(
            image_id="img-a",
            score=0.5,
            record=_sample_record("img-a"),
            provenance_line="slide 1",
            score_kind="rerank",
        )
    ]
    spec = QuerySpec(semantic_query="charts", raw_text="charts")
    event_id = record_search_from_results(
        query_text="charts",
        user_id="user-1",
        session_id="sess-1",
        search_kind="chat",
        results=results,
        spec=spec,
    )

    iid = record_interaction(
        search_event_id=event_id,
        image_id="img-a",
        interaction_type="view",
        user_id="user-1",
        rank=1,
    )
    assert iid

    with session_scope() as s:
        from sqlalchemy import select

        row = s.execute(select(SearchEvent).where(SearchEvent.id == event_id)).scalar_one()
        served = json.loads(row.served_image_ids_json)
        assert served == ["img-a"]
        assert row.top_score == 0.5
        assert row.result_count == 1


def test_interaction_rejects_unknown_image():
    event_id = record_search_from_results(
        query_text="q",
        user_id="u",
        session_id=None,
        search_kind="chat",
        results=[
            RankedResult(
                image_id="only-one",
                score=0.3,
                record=_sample_record("only-one"),
                provenance_line="",
            )
        ],
    )
    with pytest.raises(ValueError, match="not in the originating"):
        record_interaction(
            search_event_id=event_id,
            image_id="other",
            interaction_type="view",
        )
