"""Lightweight schema migration (create_all + ALTER for new columns)."""

from __future__ import annotations

import logging
from sqlalchemy import inspect, text

from imagecb.storage.metadata_db import Base, get_engine

logger = logging.getLogger(__name__)


def ensure_telemetry_schema() -> None:
    """Create telemetry tables and add soft-delete columns on images if missing."""
    engine = get_engine()
    Base.metadata.create_all(engine)

    insp = inspect(engine)
    if not insp.has_table("images"):
        return

    existing = {c["name"] for c in insp.get_columns("images")}
    alters: list[str] = []
    if "deleted_at" not in existing:
        alters.append("ALTER TABLE images ADD COLUMN deleted_at DATETIME")
    if "deleted_by" not in existing:
        alters.append("ALTER TABLE images ADD COLUMN deleted_by VARCHAR")

    if not alters:
        return

    with engine.begin() as conn:
        for stmt in alters:
            logger.info("Applying schema migration: %s", stmt)
            conn.execute(text(stmt))
