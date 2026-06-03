"""Admin API key authentication."""

from __future__ import annotations

from dataclasses import replace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from imagecb.api.server import create_app
from imagecb.config import SETTINGS


@pytest.fixture
def client():
    patched = replace(SETTINGS, admin_api_key="test-admin-secret")
    with patch("imagecb.api.auth.SETTINGS", patched):
        yield TestClient(create_app())


def test_admin_summary_requires_key(client):
    res = client.get("/api/admin/analytics/summary")
    assert res.status_code == 401


def test_admin_summary_rejects_wrong_key(client):
    res = client.get(
        "/api/admin/analytics/summary",
        headers={"X-Admin-Api-Key": "wrong"},
    )
    assert res.status_code == 403


def test_admin_summary_accepts_key(client):
    res = client.get(
        "/api/admin/analytics/summary",
        headers={"X-Admin-Api-Key": "test-admin-secret"},
    )
    assert res.status_code == 200
    assert "total_searches" in res.json()
