"""Admin corpus API tests."""

from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from imagecb.admin import curation
from imagecb.api.server import create_app
from imagecb.config import SETTINGS
from imagecb.storage.metadata_db import ImageRecord, get_engine, upsert_image
from imagecb.telemetry.schema import ensure_telemetry_schema


@pytest.fixture(autouse=True)
def _db():
    get_engine()
    ensure_telemetry_schema()
    yield


@pytest.fixture
def admin_client():
    patched = replace(SETTINGS, admin_api_key="test-admin-secret")
    with patch("imagecb.api.auth.SETTINGS", patched):
        yield TestClient(create_app())


def _record(image_id: str) -> ImageRecord:
    return ImageRecord(
        image_id=image_id,
        content_hash=f"h-{image_id}",
        image_path=f"/tmp/{image_id}.png",
        source_file="/tmp/report.pptx",
        source_type="pptx",
        created_at=datetime.utcnow(),
    )


def test_list_corpus_images():
    iid = f"corpus-{uuid.uuid4().hex[:8]}"
    upsert_image(_record(iid))
    images = curation.list_corpus_images()
    ids = {img["image_id"] for img in images}
    assert iid in ids
    row = next(img for img in images if img["image_id"] == iid)
    assert row["image_url"] == f"/api/images/{iid}"


def test_corpus_images_endpoint(admin_client):
    iid = f"api-{uuid.uuid4().hex[:8]}"
    upsert_image(_record(iid))
    res = admin_client.get(
        "/api/admin/corpus/images",
        headers={"X-Admin-Api-Key": "test-admin-secret"},
    )
    assert res.status_code == 200
    ids = {img["image_id"] for img in res.json()["images"]}
    assert iid in ids


@patch("imagecb.admin.routes.duplicates.find_duplicate_clusters")
def test_duplicate_clusters_returns_error_not_500(mock_find, admin_client):
    mock_find.side_effect = RuntimeError("chroma unavailable")
    res = admin_client.get(
        "/api/admin/corpus/duplicate-clusters",
        headers={"X-Admin-Api-Key": "test-admin-secret"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["clusters"] == []
    assert "chroma" in (body.get("error") or "").lower()
