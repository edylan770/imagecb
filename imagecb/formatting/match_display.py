"""Map raw retrieval scores to intuitive 0–100% display values.

Ranking and ``min_match_percent`` filtering use raw model scores unchanged.
This module only affects UI labels (result cards, LLM context blocks).

Rerank anchors target Cohere Rerank 3.5 relevance (conservative absolute scale).
Dense anchors target Chroma cosine similarity (typically lower in practice).
100% is reserved for near-excellent raw scores only (>= 0.93 rerank, >= 0.92 dense).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Sequence, Tuple


class ScoreKind(str, Enum):
    RERANK = "rerank"
    DENSE = "dense"


# (raw_score, display_percent) — monotonic, sorted by raw
_RERANK_ANCHORS: List[Tuple[float, int]] = [
    (0.00, 0),
    (0.12, 10),
    (0.25, 28),
    (0.40, 48),
    (0.55, 65),
    (0.70, 80),
    (0.85, 92),
    (0.93, 100),
]

_DENSE_ANCHORS: List[Tuple[float, int]] = [
    (0.00, 0),
    (0.20, 15),
    (0.35, 40),
    (0.50, 62),
    (0.65, 78),
    (0.80, 90),
    (0.92, 100),
]

_ANCHORS = {
    ScoreKind.RERANK: _RERANK_ANCHORS,
    ScoreKind.DENSE: _DENSE_ANCHORS,
}


def _interpolate(raw: float, anchors: Sequence[Tuple[float, int]]) -> int:
    if not anchors:
        return 0
    if raw <= anchors[0][0]:
        return anchors[0][1]
    if raw >= anchors[-1][0]:
        return anchors[-1][1]
    for i in range(1, len(anchors)):
        r0, d0 = anchors[i - 1]
        r1, d1 = anchors[i]
        if raw <= r1:
            if r1 == r0:
                return d1
            t = (raw - r0) / (r1 - r0)
            return round(d0 + t * (d1 - d0))
    return anchors[-1][1]


def display_match_percent(raw: float, kind: ScoreKind | str = ScoreKind.RERANK) -> int:
    """Convert a raw score in [0, 1] to a display percentage in [0, 100]."""
    if isinstance(kind, str):
        kind = ScoreKind(kind)
    raw_clamped = max(0.0, min(float(raw), 1.0))
    anchors = _ANCHORS[kind]
    return max(0, min(100, _interpolate(raw_clamped, anchors)))
