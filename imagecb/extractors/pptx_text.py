"""Shared PowerPoint text extraction helpers."""

from __future__ import annotations

from typing import List, Optional, Tuple


def slide_title(slide) -> Optional[str]:
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None and title_shape.has_text_frame:
        text = (title_shape.text or "").strip()
        if text:
            return text
    for shape in slide.shapes:
        if shape.has_text_frame:
            text = (shape.text_frame.text or "").strip()
            if text:
                first_line = text.splitlines()[0].strip()
                if first_line:
                    return first_line
    return None


def slide_notes(slide) -> Optional[str]:
    try:
        if slide.has_notes_slide:
            notes_text = slide.notes_slide.notes_text_frame.text or ""
            notes_text = notes_text.strip()
            return notes_text or None
    except Exception:  # noqa: BLE001
        return None
    return None


def _title_shape_id(slide) -> Optional[int]:
    title_shape = getattr(slide.shapes, "title", None)
    if title_shape is not None:
        return id(title_shape)
    return None


def slide_body_text(slide, *, title: Optional[str] = None) -> str:
    """Collect non-title text shapes on the slide."""
    resolved_title = title if title is not None else slide_title(slide)
    title_id = _title_shape_id(slide)
    parts: List[str] = []
    seen: set[str] = set()

    for shape in slide.shapes:
        if not shape.has_text_frame:
            continue
        if title_id is not None and id(shape) == title_id:
            continue
        text = (shape.text_frame.text or "").strip()
        if not text:
            continue
        if resolved_title and text.splitlines()[0].strip() == resolved_title.splitlines()[0].strip():
            if len(text.splitlines()) <= 1:
                continue
        key = text
        if key in seen:
            continue
        seen.add(key)
        parts.append(text)

    return "\n\n".join(parts)


def slide_text_parts(slide) -> Tuple[Optional[str], str, Optional[str]]:
    """Return (title, body, notes) for one slide."""
    title = slide_title(slide)
    body = slide_body_text(slide, title=title)
    notes = slide_notes(slide)
    return title, body, notes
