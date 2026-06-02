"""Cross-encoder reranking of fused candidates.

We build a single text representation per candidate by concatenating
caption + OCR + slide context, and ask the cross-encoder to score each
against the user's query.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Literal, Optional, Sequence

from imagecb.config import SETTINGS
from imagecb.models.reranker import get_reranker
from imagecb.retrieval.hybrid import Candidate
from imagecb.storage import metadata_db
from imagecb.storage.metadata_db import ImageRecord, deserialize_list


@dataclass
class RankedResult:
    image_id: str
    score: float
    record: ImageRecord
    provenance_line: str
    score_kind: Literal["rerank", "dense"] = "rerank"

    @property
    def image_path(self) -> str:
        return self.record.image_path

    def explanation(self) -> str:
        bits = []
        if self.record.caption_short:
            bits.append(self.record.caption_short)
        tags = deserialize_list(self.record.tags_json)
        if tags:
            bits.append("tags: " + ", ".join(tags[:6]))
        if self.record.ocr_text:
            ocr = self.record.ocr_text.strip()
            if ocr:
                bits.append('OCR: "' + (ocr[:120] + ("..." if len(ocr) > 120 else "")) + '"')
        return " | ".join(bits)


def _candidate_text(r: ImageRecord) -> str:
    parts: List[str] = []
    for v in (
        r.caption_detailed,
        r.caption_short,
        r.scene,
        r.text_overlay_summary,
        r.slide_title,
        r.slide_notes,
        r.ocr_text,
    ):
        if v:
            parts.append(v)
    tags = deserialize_list(r.tags_json)
    if tags:
        parts.append("tags: " + ", ".join(tags))
    objects = deserialize_list(r.objects_json)
    if objects:
        parts.append("objects: " + ", ".join(objects))
    return "\n".join(parts)


def _format_provenance(r: ImageRecord) -> str:
    src_name = Path(r.source_file or "").name or "(unknown)"
    loc: Optional[str] = None
    if r.source_type == "pptx" and r.slide_index:
        loc = f"Slide {r.slide_index} of {src_name}"
    elif r.source_type == "pdf" and r.page_index:
        loc = f"Page {r.page_index} of {src_name}"
    else:
        loc = src_name

    modified = ""
    if isinstance(r.source_modified_at, datetime):
        modified = f", modified {r.source_modified_at.date().isoformat()}"
    author = f", by {r.author}" if r.author else ""
    return f"{loc}{modified}{author}"


def rerank(
    query: str,
    candidates: Sequence[Candidate],
    *,
    top_k: int,
    top_n: Optional[int] = None,
    min_score: float = 0.0,
) -> List[RankedResult]:
    if not candidates:
        return []
    top_n = top_n or SETTINGS.rerank_top_n
    head = list(candidates[:top_n])
    ids = [c.image_id for c in head]
    records = {r.image_id: r for r in metadata_db.get_records(ids)}
    head = [c for c in head if c.image_id in records]
    if not head:
        return []
    docs = [_candidate_text(records[c.image_id]) for c in head]
    scores = get_reranker().score(query, docs)

    ranked = sorted(
        (
            RankedResult(
                image_id=c.image_id,
                score=float(s),
                record=records[c.image_id],
                provenance_line=_format_provenance(records[c.image_id]),
            )
            for c, s in zip(head, scores)
        ),
        key=lambda r: r.score,
        reverse=True,
    )
    if min_score > 0:
        ranked = [r for r in ranked if r.score >= min_score]
    return ranked[:top_k]
