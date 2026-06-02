"""Resolve on-disk paths for UI display and ingest."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from imagecb.storage.metadata_db import ImageRecord


def resolve_source_file(record: ImageRecord) -> Optional[Path]:
    """Return the original source file (.pptx, .pdf, image) if it exists on disk."""
    if not record.source_file:
        return None
    path = Path(record.source_file).expanduser()
    if path.is_file():
        return path.resolve()
    return None


def resolve_image_file(record: ImageRecord) -> Optional[Path]:
    """Return an existing image file for display, or None if none found."""
    candidates = []
    if record.image_path:
        candidates.append(record.image_path)
    if record.source_file and record.source_file not in candidates:
        candidates.append(record.source_file)
    for raw in candidates:
        path = Path(raw).expanduser()
        if path.is_file():
            return path.resolve()
    return None
