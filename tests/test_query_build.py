"""Tests for shared query text and refinement heuristics."""

from __future__ import annotations

from imagecb.retrieval.query_build import (
    dense_query_text,
    rerank_query_text,
    should_restrict_to_previous,
)
from imagecb.retrieval.query_parser import QuerySpec


def test_dense_query_includes_must_have():
    spec = QuerySpec(
        semantic_query="dashboard screenshots",
        must_have_keywords=["revenue", "chart"],
        raw_text="dashboards with revenue charts",
    )
    assert "dashboard screenshots" in dense_query_text(spec)
    assert "revenue" in dense_query_text(spec)
    assert "chart" in dense_query_text(spec)


def test_rerank_query_falls_back():
    spec = QuerySpec(raw_text="")
    assert rerank_query_text(spec, "user asked") == "user asked"


def test_cues_alone_do_not_restrict():
    spec = QuerySpec(is_refinement=False, raw_text="only the charts")
    assert not should_restrict_to_previous(spec, "only the charts", pool_size=10)


def test_only_cybersecurity_does_not_restrict_without_refinement_flag():
    spec = QuerySpec(is_refinement=False, raw_text="only cybersecurity")
    assert not should_restrict_to_previous(spec, "only cybersecurity", pool_size=10)


def test_refinement_heuristic_without_pool():
    spec = QuerySpec(is_refinement=True, raw_text="only the charts")
    assert not should_restrict_to_previous(spec, "only the charts", pool_size=0)


def test_refinement_flag_restricts_when_pool_available():
    spec = QuerySpec(is_refinement=True, raw_text="more")
    assert should_restrict_to_previous(spec, "more", pool_size=5)
