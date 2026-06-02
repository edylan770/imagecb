"""Extract images plus slide context from .pptx files."""

from __future__ import annotations

import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from PIL import Image

from .types import ExtractedImage, Provenance

logger = logging.getLogger(__name__)


def _slide_title(slide) -> Optional[str]:
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None and title_shape.has_text_frame:
        text = (title_shape.text or "").strip()
        if text:
            return text
    # Fall back to first text shape with content.
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = (shape.text_frame.text or "").strip()
            if text:
                first_line = text.splitlines()[0].strip()
                if first_line:
                    return first_line
    return None


def _slide_notes(slide) -> Optional[str]:
    try:
        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text or ""
            notes_text = notes_text.strip()
            return notes_text or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _iter_picture_shapes(shapes):
    """Recursively yield picture shapes, descending into group shapes."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
            yield shape
        elif shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _iter_picture_shapes(shape.shapes)


def extract(path: Path) -> Iterator[ExtractedImage]:
    try:
        from pptx import Presentation
    except ImportError as exc:  # pragma: no cover
        logger.error("python-pptx not installed: %s", exc)
        return

    try:
        prs = Presentation(str(path))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to open pptx %s: %s", path, exc)
        return

    core = prs.core_properties
    author = core.author or core.last_modified_by or None
    created_at = core.created
    modified_at = core.modified
    if not modified_at:
        modified_at = datetime.fromtimestamp(path.stat().st_mtime)

    for slide_idx, slide in enumerate(prs.slides, start=1):
        title = _slide_title(slide)
        notes = _slide_notes(slide)
        for shape in _iter_picture_shapes(slide.shapes):
            try:
                blob = shape.image.blob
                img = Image.open(io.BytesIO(blob))
                img.load()
            except Exception as exc:  # noqa: BLE001
                logger.debug("Could not load image on slide %s of %s: %s", slide_idx, path, exc)
                continue
            provenance = Provenance(
                source_file=str(path),
                source_type="pptx",
                source_modified_at=modified_at,
                source_created_at=created_at,
                author=author,
                slide_index=slide_idx,
                slide_title=title,
                slide_notes=notes,
            )
            yield ExtractedImage(image=img, provenance=provenance)
