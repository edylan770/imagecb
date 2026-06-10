"""Tests for shared query text and refinement heuristics."""

from __future__ import annotations

from imagecb.retrieval.query_build import (
    dense_query_text,
    is_short_query,
    rerank_query_text,
    resolve_rerank_top_n,
    resolve_retrieval_top_k,
    should_restrict_to_previous,
)
from imagecb.retrieval.query_parser import QuerySpec


def test_dense_query_text_excludes_expanded_keywords():
    spec = QuerySpec(
        semantic_query="sales dashboard",
        must_have_keywords=["chart"],
        expanded_keywords=["revenue"],
        raw_text="sales dashboard chart",
    )
    text = dense_query_text(spec)
    assert "sales dashboard" in text
    assert "chart" in text
    assert "revenue" not in text


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


def test_seed_expansion_for_sdlc():
    spec = QuerySpec(semantic_query="sdlc", raw_text="sdlc")
    text = dense_query_text(spec)
    assert "sdlc" in text
    assert "software development life cycle" in text


def test_seed_expansion_for_flowchart():
    spec = QuerySpec(semantic_query="flowchart", raw_text="flowchart")
    text = dense_query_text(spec)
    assert "flowchart" in text
    assert "diagram" not in text


def test_seed_expansion_skipped_for_long_query():
    spec = QuerySpec(
        semantic_query="office worker giving a presentation",
        raw_text="office worker giving a presentation",
    )
    text = dense_query_text(spec)
    assert "office worker giving a presentation" in text
    assert "slide" not in text.split()[-1:]  # no presentation->slide append on long query


def test_short_query_uses_wider_retrieval_pool():
    spec = QuerySpec(semantic_query="diagram", raw_text="diagram")
    assert is_short_query(spec)
    dense_k, sparse_k = resolve_retrieval_top_k(spec)
    assert dense_k == 100
    assert sparse_k == 100
    assert resolve_rerank_top_n(spec) == 100
