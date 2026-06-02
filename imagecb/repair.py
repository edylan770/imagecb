"""Repair captions and reindex embeddings without full re-extraction."""

from __future__ import annotations

import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

from imagecb.config import SETTINGS
from imagecb.ingest import _chroma_metadata, _flush_chroma_batch
from imagecb.ingest_context import embed_context_from_record
from imagecb.models.embedder import get_embedder
from imagecb.models.vlm import get_captioner
from imagecb.storage import bm25_index, metadata_db, vector_store
from imagecb.storage.metadata_db import ImageRecord, get_all_records, serialize_list, session_scope

logger = logging.getLogger(__name__)

_CAPTION_FAILED = "[caption failed]"


def records_with_failed_captions() -> List[ImageRecord]:
    return [
        r
        for r in get_all_records()
        if (r.caption_short or "").strip() == _CAPTION_FAILED
    ]


def _load_cached_image(record: ImageRecord) -> Optional[Image.Image]:
    path = Path(record.image_path).expanduser()
    if not path.is_file():
        return None
    try:
        img = Image.open(path)
        img.load()
        return img
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not load %s: %s", path, exc)
        return None


def _repair_one_caption(record: ImageRecord) -> Tuple[str, bool, Optional[str]]:
    img = _load_cached_image(record)
    if img is None:
        return record.image_id, False, "cached image missing"
    try:
        caption = get_captioner().caption_image(img)
        record.caption_short = caption.short_caption
        record.caption_detailed = caption.detailed_description
        record.scene = caption.scene
        record.text_overlay_summary = caption.text_overlay_summary
        record.objects_json = serialize_list(caption.objects)
        record.tags_json = serialize_list(caption.tags)
        with session_scope() as s:
            s.merge(record)
        return record.image_id, True, None
    except Exception as exc:  # noqa: BLE001
        return record.image_id, False, str(exc)


def repair_failed_captions(*, workers: Optional[int] = None) -> dict:
    """Re-caption rows where VLM failed during ingest."""
    workers = max(1, workers if workers is not None else SETTINGS.ingest_workers)
    records = records_with_failed_captions()
    stats = {"attempted": len(records), "repaired": 0, "errors": 0, "workers": workers}
    if not records:
        return stats

    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_repair_one_caption, r): r for r in records}
        pbar = tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Repair captions",
            unit="img",
            disable=not sys.stderr.isatty(),
        )
        for future in pbar:
            _id, ok, err = future.result()
            if ok:
                stats["repaired"] += 1
            else:
                stats["errors"] += 1
                if err:
                    logger.warning("Caption repair failed for %s: %s", _id, err)

    bm25_index.rebuild_from_records(get_all_records())
    stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def _reindex_one(record: ImageRecord, embedder) -> Tuple[str, bool, Optional[np.ndarray], Optional[str]]:
    img = _load_cached_image(record)
    if img is None:
        return record.image_id, False, None, "cached image missing"
    try:
        ctx = embed_context_from_record(record)
        emb = embedder.embed_image_with_context(img, ctx or None)
        return record.image_id, True, emb, None
    except Exception as exc:  # noqa: BLE001
        return record.image_id, False, None, str(exc)


def reindex_embeddings(
    *,
    workers: Optional[int] = None,
    batch_upsert: Optional[int] = None,
) -> dict:
    """Re-embed all indexed images from cached PNGs (picks up context-aware vectors)."""
    workers = max(1, workers if workers is not None else SETTINGS.ingest_workers)
    batch_upsert = max(1, batch_upsert if batch_upsert is not None else SETTINGS.ingest_batch_upsert)
    records = get_all_records()
    stats = {
        "records": len(records),
        "reindexed": 0,
        "errors": 0,
        "workers": workers,
        "elapsed_sec": 0.0,
    }
    if not records:
        return stats

    embedder = get_embedder()
    chroma_batch: List[Tuple[str, np.ndarray, dict]] = []
    chroma_lock = threading.Lock()
    t0 = time.perf_counter()

    def _submit(record: ImageRecord):
        return _reindex_one(record, embedder)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_submit, r): r for r in records}
        pbar = tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Reindex embeddings",
            unit="img",
            disable=not sys.stderr.isatty(),
        )
        for future in pbar:
            record = futures[future]
            image_id, ok, emb, err = future.result()
            if not ok or emb is None:
                stats["errors"] += 1
                if err:
                    logger.warning("Reindex failed for %s: %s", image_id, err)
                continue
            stats["reindexed"] += 1
            pending: Optional[List[Tuple[str, np.ndarray, dict]]] = None
            with chroma_lock:
                chroma_batch.append((image_id, emb, _chroma_metadata(record)))
                if len(chroma_batch) >= batch_upsert:
                    pending = list(chroma_batch)
                    chroma_batch.clear()
            if pending:
                _flush_chroma_batch(pending)

    with chroma_lock:
        if chroma_batch:
            _flush_chroma_batch(list(chroma_batch))

    stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    return stats
