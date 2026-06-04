"""Tests for deck LLM JSON coercion."""

from __future__ import annotations

from imagecb.deck.llm import _coerce_slides_json


def test_coerce_slides_json_image_needed():
    raw = """{"slides": [
        {"slide_index": 1, "status": "image_needed", "description": "A red chart on white"},
        {"slide_index": 2, "status": "no_image_needed", "reason": "Agenda only"}
    ]}"""
    out = _coerce_slides_json(raw, [1, 2])
    assert len(out) == 2
    assert out[0].status == "image_needed"
    assert "chart" in out[0].description
    assert out[1].status == "no_image_needed"
    assert out[1].reason


def test_coerce_slides_json_fills_missing_index():
    raw = '{"slides": [{"slide_index": 1, "status": "image_needed", "description": "x"}]}'
    out = _coerce_slides_json(raw, [1, 2])
    assert out[1].status == "no_image_needed"
