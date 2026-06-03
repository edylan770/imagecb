"""Corpus curation: soft delete, restore, orphans."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import numpy as np
from PIL import Image
from sqlalchemy import select

from imagecb.config import SETTINGS
from imagecb.ingest import _chroma_metadata
from imagecb.models.embedder import get_embedder
from imagecb.images import resize_for_model
from imagecb.paths import resolve_image_file
from imagecb.storage import bm25_index, metadata_db, vector_store
from imagecb.storage.metadata_db import ImageRecord, get_all_records, session_scope
from imagecb.telemetry.models import InteractionEvent, SearchEvent
from imagecb.telemetry.schema import ensure_telemetry_schema
from imagecb.admin.audit import append_audit


def rebuild_bm25_active() -> None:
    bm25_index.rebuild_from_records(get_all_records(include_deleted=False))


def soft_delete_image(*, image_id: str, actor: str) -> None:
    ensure_telemetry_schema()
    with session_scope() as s:
        row = s.execute(
            select(ImageRecord).where(ImageRecord.image_id == image_id)
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("image not found")
        if row.deleted_at is not None:
            raise ValueError("image already soft-deleted")
        row.deleted_at = datetime.utcnow()
        row.deleted_by = actor

    vector_store.delete([image_id])
    rebuild_bm25_active()
    append_audit(
        actor=actor,
        action="soft_delete",
        target_type="image",
        target_id=image_id,
        details={},
    )


def restore_image(*, image_id: str, actor: str) -> None:
    ensure_telemetry_schema()
    with session_scope() as s:
        row = s.execute(
            select(ImageRecord).where(ImageRecord.image_id == image_id)
        ).scalar_one_or_none()
        if row is None:
            raise ValueError("image not found")
        if row.deleted_at is None:
            raise ValueError("image is not deleted")
        row.deleted_at = None
        row.deleted_by = None
        record = row
        s.expunge(record)

    path = resolve_image_file(record)
    if path is None or not path.is_file():
        raise ValueError("cached image file missing; cannot restore embedding")

    img = Image.open(path)
    img.load()
    img = resize_for_model(img, SETTINGS.ingest_max_image_side)
    embedder = get_embedder()
    emb = embedder.embed_image(img)
    if isinstance(emb, np.ndarray) and emb.ndim == 1:
        emb = emb.reshape(1, -1)

    vector_store.upsert(
        image_ids=[image_id],
        embeddings=emb,
        metadatas=[_chroma_metadata(record)],
    )
    rebuild_bm25_active()
    append_audit(
        actor=actor,
        action="restore",
        target_type="image",
        target_id=image_id,
        details={},
    )


def _all_served_image_ids() -> set[str]:
    ensure_telemetry_schema()
    served: set[str] = set()
    with session_scope() as s:
        rows = s.execute(select(SearchEvent.served_image_ids_json)).all()
        for (raw,) in rows:
            try:
                ids = json.loads(raw or "[]")
                if isinstance(ids, list):
                    served.update(str(x) for x in ids)
            except json.JSONDecodeError:
                continue
    return served


def _all_interacted_image_ids() -> set[str]:
    ensure_telemetry_schema()
    with session_scope() as s:
        rows = s.execute(select(InteractionEvent.image_id).distinct()).all()
        return {r[0] for r in rows}


def list_corpus_images() -> List[dict]:
    """All active indexed images for admin corpus browser."""
    active = get_all_records(include_deleted=False)
    out: List[dict] = []
    for r in active:
        out.append(
            {
                "image_id": r.image_id,
                "caption_short": r.caption_short,
                "source_file": Path(r.source_file or "").name,
                "source_type": r.source_type,
                "author": r.author,
                "image_url": f"/api/images/{r.image_id}",
            }
        )
    out.sort(key=lambda x: (x.get("source_file") or "", x["image_id"]))
    return out


def list_orphans(*, never_interacted: bool = False) -> List[dict]:
    active = get_all_records(include_deleted=False)
    served = _all_served_image_ids()
    interacted = _all_interacted_image_ids() if never_interacted else set()

    out: List[dict] = []
    for r in active:
        if r.image_id in served:
            continue
        if never_interacted and r.image_id in interacted:
            continue
        out.append(
            {
                "image_id": r.image_id,
                "caption_short": r.caption_short,
                "source_file": Path(r.source_file or "").name,
                "source_type": r.source_type,
                "image_url": f"/api/images/{r.image_id}",
            }
        )
    return out


def list_soft_deleted() -> List[dict]:
    rows = metadata_db.get_deleted_records()
    return [
        {
            "image_id": r.image_id,
            "deleted_at": r.deleted_at.isoformat() if r.deleted_at else None,
            "deleted_by": r.deleted_by,
            "caption_short": r.caption_short,
            "source_file": Path(r.source_file or "").name,
        }
        for r in rows
    ]
