"""Build short text context for Titan multimodal embeddings at ingest."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from imagecb.extractors.types import Provenance
    from imagecb.storage.metadata_db import ImageRecord

# Titan Multimodal Embeddings: inputText up to ~256 tokens; keep conservative.
_MAX_CONTEXT_CHARS = 200


def embed_context_text(
    *,
    slide_title: Optional[str] = None,
    slide_notes: Optional[str] = None,
    page_text: Optional[str] = None,
    source_type: Optional[str] = None,
) -> str:
    """Join slide/PDF context for embedding; empty when nothing useful."""
    parts: list[str] = []
    if slide_title and slide_title.strip():
        parts.append(slide_title.strip())
    if slide_notes and slide_notes.strip():
        parts.append(slide_notes.strip())
    if page_text and page_text.strip():
        first_line = page_text.strip().splitlines()[0].strip()
        if first_line:
            parts.append(first_line)
    if not parts:
        return ""
    text = " | ".join(parts)
    if len(text) > _MAX_CONTEXT_CHARS:
        return text[: _MAX_CONTEXT_CHARS - 3].rstrip() + "..."
    return text


def embed_context_from_provenance(provenance: "Provenance") -> str:
    page_text = None
    if provenance.extra:
        page_text = provenance.extra.get("page_text")
    return embed_context_text(
        slide_title=provenance.slide_title,
        slide_notes=provenance.slide_notes,
        page_text=page_text,
        source_type=provenance.source_type,
    )


def embed_context_from_record(record: "ImageRecord") -> str:
    return embed_context_text(
        slide_title=record.slide_title,
        slide_notes=record.slide_notes,
        source_type=record.source_type,
    )
