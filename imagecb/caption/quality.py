"""Caption quality assessment for auto-flagging weak outputs."""

from __future__ import annotations

import re
from typing import Literal, TYPE_CHECKING

if TYPE_CHECKING:
    from imagecb.models.vlm import CaptionJSON

CAPTION_FAILED = "[caption failed]"
_VLM_ERROR_PREFIX = "VLM error:"

_GENERIC_PATTERNS = [
    re.compile(r"^an?\s+(image|photo|picture|illustration|graphic)\s+(of|showing)\b", re.I),
    re.compile(r"^this\s+(image|photo|picture)\s+(shows|depicts)\b", re.I),
    re.compile(r"^various\s+objects\b", re.I),
    re.compile(r"^a\s+scene\s+with\b", re.I),
]


def assess_caption(caption: "CaptionJSON") -> Literal["ok", "weak", "failed"]:
    short = (caption.short_caption or "").strip()
    detailed = (caption.detailed_description or "").strip()

    if short == CAPTION_FAILED or detailed.startswith(_VLM_ERROR_PREFIX):
        return "failed"

    name = (caption.image_name or "").strip()
    scene = (caption.scene or "").strip()
    objects = [o for o in (caption.objects or []) if (o or "").strip()]

    weak_reasons = 0

    if not name:
        weak_reasons += 1
    if not short:
        weak_reasons += 1
    elif len(short) < 15 or len(short.split()) < 4:
        weak_reasons += 1

    for pat in _GENERIC_PATTERNS:
        if pat.search(short):
            weak_reasons += 1
            break

    if not scene and not objects:
        weak_reasons += 1

    if caption.text_read_uncertain and (caption.readable_text or "").strip() and not objects:
        weak_reasons += 1

    recommended = [c for c in (caption.recommended_cases or []) if (c or "").strip()]
    aliases = [a for a in (caption.aliases or []) if (a or "").strip()]
    if len(recommended) < 3:
        weak_reasons += 1
    if len(aliases) < 2:
        weak_reasons += 1

    if weak_reasons > 0:
        return "weak"
    return "ok"
