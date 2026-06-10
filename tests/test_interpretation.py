"""Tests for query interpretation notes."""

from __future__ import annotations

from datetime import datetime

from imagecb.api.interpretation import build_interpretation_notes
from imagecb.retrieval.query_parser import QuerySpec, SourceFilters


def test_notes_refinement_pool():
    spec = QuerySpec(semantic_query="charts")
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=True,
        pool_size=12,
        sticky_merged=False,
    )
    assert any("12" in n for n in notes)


def test_notes_sticky_filters():
    spec = QuerySpec(
        semantic_query="dashboards",
        source_filters=SourceFilters(filename_contains=["Q3_Review.pptx"]),
    )
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=True,
    )
    assert any("Carried forward" in n for n in notes)
    assert any("Q3_Review" in n for n in notes)


def test_notes_asset_types():
    spec = QuerySpec(
        semantic_query="team photos",
        source_filters=SourceFilters(asset_types=["photo", "illustration"]),
    )
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=True,
    )
    assert any("asset types" in n and "photo" in n for n in notes)


def test_notes_must_have():
    spec = QuerySpec(
        semantic_query="screenshots",
        must_have_keywords=["revenue"],
        must_avoid_keywords=["logo"],
    )
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=False,
    )
    assert any("Must include" in n for n in notes)
    assert any("Excluding" in n for n in notes)


def test_notes_min_match_percent():
    spec = QuerySpec(semantic_query="cybersecurity")
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=False,
        min_match_percent=80,
    )
    assert any("80%" in n for n in notes)


def test_notes_relaxed_min_score():
    spec = QuerySpec(semantic_query="charts")
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=False,
        min_match_percent=80,
        relaxed_min_score=True,
    )
    assert any("80%" in n and "best available" in n for n in notes)


def test_notes_retrieval_failures():
    spec = QuerySpec(semantic_query="charts")
    notes = build_interpretation_notes(
        spec,
        applied_refinement_pool=False,
        pool_size=0,
        sticky_merged=False,
        dense_failed=True,
        sparse_failed=True,
    )
    assert any("Dense and sparse" in n for n in notes)
