"""Shared dataclasses for extractor output."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from PIL import Image


@dataclass
class Provenance:
    source_file: str
    source_type: str  # "pptx" | "pdf" | "image"
    source_modified_at: Optional[datetime] = None
    source_created_at: Optional[datetime] = None
    author: Optional[str] = None
    # Document-specific
    slide_index: Optional[int] = None  # 1-based
    page_index: Optional[int] = None   # 1-based
    slide_title: Optional[str] = None
    slide_notes: Optional[str] = None
    extra: dict = field(default_factory=dict)


@dataclass
class ExtractedImage:
    image: Image.Image
    provenance: Provenance
