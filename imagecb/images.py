"""Image utilities for ingest and model input."""

from __future__ import annotations

from PIL import Image


def resize_for_model(image: Image.Image, max_side: int) -> Image.Image:
    """Downscale so the longest edge is at most ``max_side`` (RGB)."""
    if max_side <= 0:
        return image.convert("RGB")
    img = image.convert("RGB")
    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)
