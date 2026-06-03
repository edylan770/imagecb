"""Image-to-image similarity search (skips query LLM)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional

from PIL import Image

from imagecb.config import SETTINGS
from imagecb.ingest_context import embed_context_from_record
from imagecb.models.embedder import get_embedder
from imagecb.retrieval.hybrid import Candidate
from imagecb.retrieval.rerank import RankedResult, rerank
from imagecb.storage import metadata_db, vector_store
from imagecb.storage.metadata_db import ImageRecord

logger = logging.getLogger(__name__)

_SIMILAR_RERANK_QUERY = "visually similar images"


def _load_image_for_record(record: ImageRecord) -> Optional[Image.Image]:
    path = Path(record.image_path).expanduser()
    if not path.is_file():
        return None
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load image %s: %s", path, exc)
        return None


def _filter_by_min_score(results: List[RankedResult], min_score: float) -> List[RankedResult]:
    if min_score <= 0:
        return results
    return [r for r in results if r.score >= min_score]


def search_similar(
    *,
    image_id: Optional[str] = None,
    image: Optional[Image.Image] = None,
    top_k: int = 10,
    exclude_image_id: Optional[str] = None,
    min_match_percent: int = 0,
) -> List[RankedResult]:
    """Find images visually similar to a reference image."""
    top_k = max(1, min(int(top_k), 50))
    min_score = max(0.0, min(float(min_match_percent) / 100.0, 1.0))
    embedder = get_embedder()
    record: Optional[ImageRecord] = None

    if image_id:
        record = metadata_db.get_record(image_id)
        if record is None:
            return []
        pil = _load_image_for_record(record)
        if pil is None:
            return []
        ctx = embed_context_from_record(record)
        query_emb = embedder.embed_image_with_context(pil, ctx or None)
        exclude_image_id = exclude_image_id or image_id
    elif image is not None:
        query_emb = embedder.embed_image(image)
    else:
        return []

    dense_k = min(SETTINGS.dense_top_k, max(top_k * 5, 25))
    active_ids = metadata_db.get_active_image_ids()
    try:
        hits = vector_store.query(
            query_emb,
            top_k=dense_k,
            allowed_ids=active_ids if active_ids else None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Similar search failed: %s", exc)
        return []

    if exclude_image_id:
        hits = [(i, s) for i, s in hits if i != exclude_image_id]

    candidates = [Candidate(image_id=i, dense_score=s, fused_score=s) for i, s in hits]
    if not candidates:
        return []

    if top_k <= 5:
        # Skip rerank for small result sets — save latency and cost.
        ids = [c.image_id for c in candidates[:top_k]]
        records = {r.image_id: r for r in metadata_db.get_records(ids)}
        from imagecb.retrieval.rerank import _format_provenance

        results = [
            RankedResult(
                image_id=c.image_id,
                score=c.dense_score,
                record=records[c.image_id],
                provenance_line=_format_provenance(records[c.image_id]),
                score_kind="dense",
            )
            for c in candidates[:top_k]
            if c.image_id in records
        ]
        return _filter_by_min_score(results, min_score)

    return rerank(
        _SIMILAR_RERANK_QUERY,
        candidates,
        top_k=top_k,
        min_score=min_score,
    )
