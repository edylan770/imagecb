"""Tests for POST /api/suggestions."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from imagecb.api.server import create_app
from imagecb.suggestions.generate import SuggestionsResult


@pytest.fixture
def client():
    return TestClient(create_app())


@patch("imagecb.api.routes.generate_suggestions")
def test_suggestions_endpoint_returns_list(mock_gen, client):
    mock_gen.return_value = SuggestionsResult(
        suggestions=["Find charts in deck.pptx", "Recent logos"],
        cached=True,
    )
    res = client.post(
        "/api/suggestions",
        json={
            "recent_titles": ["Charts"],
            "recent_queries": ["find bar charts"],
            "limit": 4,
        },
        headers={"X-User-Id": "test-user"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["suggestions"] == ["Find charts in deck.pptx", "Recent logos"]
    assert body["cached"] is True
    mock_gen.assert_called_once_with(
        ["Charts"],
        recent_queries=["find bar charts"],
        user_id="test-user",
        limit=4,
    )
