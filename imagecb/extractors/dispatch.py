"""Route a path to the right extractor based on extension."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from . import image_file, pdf, pptx
from .image_file import IMAGE_EXTS
from .types import ExtractedImage

logger = logging.getLogger(__name__)

SUPPORTED_EXTS = IMAGE_EXTS | {".pptx", ".pdf"}


def extract_path(path: Path) -> Iterator[ExtractedImage]:
    ext = path.suffix.lower()
    if ext == ".pptx":
        yield from pptx.extract(path)
    elif ext == ".pdf":
        yield from pdf.extract(path)
    elif ext in IMAGE_EXTS:
        yield from image_file.extract(path)
    else:
        logger.debug("Skipping unsupported file: %s", path)


def iter_corpus(root: Path) -> Iterator[Path]:
    """Yield every supported file under `root`. Single files are also accepted."""
    if root.is_file():
        if root.suffix.lower() in SUPPORTED_EXTS:
            yield root
        return
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            yield p
