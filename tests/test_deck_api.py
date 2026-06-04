"""API tests for deck suggest endpoints."""

from __future__ import annotations

from unittest import mock

import pytest
from fastapi.testclient import TestClient

from imagecb.api.server import create_app
from imagecb.deck.pipeline import DeckSuggestResult, SlideSuggestion


@pytest.fixture
def client():
    return TestClient(create_app())


def test_deck_suggest_rejects_non_pptx(client):
    res = client.post(
        "/api/deck/suggest",
        files={"file": ("doc.pdf", b"%PDF", "application/pdf")},
        data={"top_k": "10"},
    )
    assert res.status_code == 400


def test_deck_suggest_success(client):
    fake = DeckSuggestResult(
        deck_hash="abc",
        filename="deck.pptx",
        slides=[
            SlideSuggestion(
                slide_index=1,
                title="Intro",
                body_preview="Hello",
                notes_preview="",
                content_hash="h1",
                status="image_needed",
                description="A welcome slide background",
                results=[],
            )
        ],
        deck_cached=False,
        llm_batches=1,
    )
    with mock.patch("imagecb.api.routes.process_deck_upload", return_value=fake):
        res = client.post(
            "/api/deck/suggest",
            files={
                "file": (
                    "deck.pptx",
                    b"PK\x03\x04",
                    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                )
            },
            data={"top_k": "10", "min_match_percent": "0"},
        )
    assert res.status_code == 200
    body = res.json()
    assert body["deck_hash"] == "abc"
    assert len(body["slides"]) == 1
    assert body["slides"][0]["description"] == "A welcome slide background"


def test_deck_force_success(client):
    slide = SlideSuggestion(
        slide_index=2,
        title=None,
        body_preview="Data",
        notes_preview="",
        content_hash="h2",
        status="image_needed",
        description="Spreadsheet graphic",
        results=[],
    )
    with mock.patch("imagecb.api.routes.force_slide_image", return_value=slide):
        res = client.post(
            "/api/deck/force",
            json={
                "deck_hash": "abc",
                "slide_index": 2,
                "top_k": 10,
                "min_match_percent": 0,
            },
        )
    assert res.status_code == 200
    assert res.json()["slide"]["slide_index"] == 2
