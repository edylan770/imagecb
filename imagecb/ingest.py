"""End-to-end ingest pipeline.

For each source file under a root path:
  1. Dispatch to the right extractor.
  2. For each extracted image (optionally in parallel):
     a. Compute a content hash and skip if already ingested.
     b. Cache the image as a PNG under the image cache dir.
     c. Run OCR (optional).
     d. Call the VLM for a structured caption (parallel with embed).
     e. Embed with Bedrock.
     f. Upsert SQLite row + Chroma vector (batched).
  3. After everything is in SQLite, rebuild the BM25 index.
"""

from __future__ import annotations

import hashlib
import io
import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

from imagecb.config import SETTINGS
from imagecb.extractors.dispatch import extract_path, iter_corpus
from imagecb.extractors.types import ExtractedImage
from imagecb.ingest_context import embed_context_from_provenance
from imagecb.models.embedder import BedrockEmbedder, get_embedder
from imagecb.models.ocr import extract_text as ocr_extract
from imagecb.models.vlm import CaptionJSON, VLMCaptioner, get_captioner
from imagecb.storage import bm25_index, metadata_db, vector_store
from imagecb.storage.metadata_db import (
    ImageRecord,
    existing_hashes,
    get_all_records,
    get_record_by_hash,
    new_image_id,
    serialize_list,
    session_scope,
)

logger = logging.getLogger(__name__)


@dataclass
class _IngestWorkItem:
    file_path: Path
    extracted: ExtractedImage


@dataclass
class _IngestOutcome:
    skipped_duplicate: bool = False
    added: bool = False
    updated: bool = False
    record: Optional[ImageRecord] = None
    embedding: Optional[np.ndarray] = None
    error: Optional[str] = None


def _hash_image(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return hashlib.sha256(buf.getvalue()).hexdigest()


def _cache_image(img: Image.Image, image_id: str) -> Path:
    out_path = SETTINGS.image_cache_dir / f"{image_id}.png"
    img.convert("RGB").save(out_path, format="PNG")
    return out_path


def _default_image_name(extracted: ExtractedImage) -> str:
    p = extracted.provenance
    base = Path(p.source_file or "").stem or "image"
    if p.source_type == "pptx" and p.slide_index is not None:
        return f"{base} — slide {p.slide_index}"
    if p.source_type == "pdf" and p.page_index is not None:
        return f"{base} — page {p.page_index}"
    return base


def _chroma_metadata(record: ImageRecord) -> dict:
    """Compact, JSON-safe metadata for Chroma filtering & display."""

    def _iso(v: Optional[datetime]) -> Optional[str]:
        return v.isoformat() if isinstance(v, datetime) else None

    return {
        "image_id": record.image_id,
        "source_type": record.source_type or "",
        "source_file": record.source_file or "",
        "author": record.author or "",
        "slide_index": int(record.slide_index) if record.slide_index else 0,
        "page_index": int(record.page_index) if record.page_index else 0,
        "source_modified_at": _iso(record.source_modified_at) or "",
    }


def _record_for(
    *,
    image_id: str,
    extracted: ExtractedImage,
    image_path: Path,
    content_hash: str,
    ocr_text: str,
    caption: CaptionJSON,
) -> ImageRecord:
    p = extracted.provenance
    return ImageRecord(
        image_id=image_id,
        content_hash=content_hash,
        image_path=str(image_path),
        source_file=p.source_file,
        source_type=p.source_type,
        source_modified_at=p.source_modified_at,
        source_created_at=p.source_created_at,
        author=p.author,
        slide_index=p.slide_index,
        page_index=p.page_index,
        slide_title=p.slide_title,
        slide_notes=p.slide_notes,
        ocr_text=ocr_text,
        image_name=(caption.image_name or "").strip() or _default_image_name(extracted),
        caption_short=caption.short_caption,
        caption_detailed=caption.detailed_description,
        use_case=caption.use_case,
        scene=caption.scene,
        text_overlay_summary=caption.text_overlay_summary,
        objects_json=serialize_list(caption.objects),
        tags_json=serialize_list(caption.tags),
        recommended_cases_json=serialize_list(caption.recommended_cases),
    )


def _caption_and_embed(
    extracted: ExtractedImage,
    *,
    captioner: Optional[VLMCaptioner],
    embedder: BedrockEmbedder,
    max_image_side: int,
) -> Tuple[CaptionJSON, np.ndarray]:
    """Run VLM caption and embedding in parallel (independent Bedrock calls)."""

    def _caption() -> CaptionJSON:
        if captioner is None:
            return CaptionJSON.empty()
        return captioner.caption_image(extracted.image, max_side=max_image_side)

    def _embed() -> np.ndarray:
        ctx = embed_context_from_provenance(extracted.provenance)
        return embedder.embed_image_with_context(extracted.image, ctx or None)

    with ThreadPoolExecutor(max_workers=2) as pool:
        cap_future = pool.submit(_caption)
        emb_future = pool.submit(_embed)
        return cap_future.result(), emb_future.result()


def _ingest_one_image(
    item: _IngestWorkItem,
    *,
    known: Set[str],
    known_lock: threading.Lock,
    force: bool,
    skip_caption: bool,
    skip_ocr: bool,
    captioner: Optional[VLMCaptioner],
    embedder: BedrockEmbedder,
    max_image_side: int,
) -> _IngestOutcome:
    extracted = item.extracted
    try:
        content_hash = _hash_image(extracted.image)
        with known_lock:
            existing = get_record_by_hash(content_hash) if content_hash in known else None
            if existing is not None and not force:
                return _IngestOutcome(skipped_duplicate=True)
            if existing is not None:
                image_id = existing.image_id
                outcome = _IngestOutcome(updated=True)
            else:
                image_id = new_image_id()
                outcome = _IngestOutcome(added=True)

        cached_path = _cache_image(extracted.image, image_id)
        ocr_text = "" if skip_ocr else ocr_extract(extracted.image)
        caption, emb = _caption_and_embed(
            extracted,
            captioner=captioner,
            embedder=embedder,
            max_image_side=max_image_side,
        )
        record = _record_for(
            image_id=image_id,
            extracted=extracted,
            image_path=cached_path,
            content_hash=content_hash,
            ocr_text=ocr_text,
            caption=caption,
        )
        with session_scope() as s:
            s.merge(record)
        with known_lock:
            known.add(content_hash)
        outcome.record = record
        outcome.embedding = emb
        return outcome
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to ingest an image from %s: %s", item.file_path, exc)
        return _IngestOutcome(error=str(exc))


def _flush_chroma_batch(batch: List[Tuple[str, np.ndarray, dict]]) -> None:
    if not batch:
        return
    ids = [b[0] for b in batch]
    embeddings = np.stack([b[1] for b in batch])
    metadatas = [b[2] for b in batch]
    vector_store.upsert(image_ids=ids, embeddings=embeddings, metadatas=metadatas)


def _collect_work_items(paths: Iterable[Path]) -> Tuple[List[_IngestWorkItem], int]:
    items: List[_IngestWorkItem] = []
    errors = 0
    for file_path in paths:
        try:
            for extracted in extract_path(file_path):
                items.append(_IngestWorkItem(file_path=file_path, extracted=extracted))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Extractor failed for %s: %s", file_path, exc)
            errors += 1
    return items, errors


def ingest_paths(
    paths: Iterable[Path],
    *,
    skip_caption: bool = False,
    skip_ocr: bool = False,
    force: bool = False,
    workers: Optional[int] = None,
    max_image_side: Optional[int] = None,
    batch_upsert: Optional[int] = None,
) -> dict:
    """Ingest a list of source files. Returns a stats dict."""
    SETTINGS.ensure_dirs()
    paths = list(paths)
    workers = workers if workers is not None else SETTINGS.ingest_workers
    workers = max(1, workers)
    max_image_side = max_image_side if max_image_side is not None else SETTINGS.ingest_max_image_side
    batch_upsert = batch_upsert if batch_upsert is not None else SETTINGS.ingest_batch_upsert
    batch_upsert = max(1, batch_upsert)

    stats = {
        "files": len(paths),
        "images_seen": 0,
        "images_added": 0,
        "images_updated": 0,
        "skipped_duplicates": 0,
        "errors": 0,
        "workers": workers,
        "elapsed_sec": 0.0,
    }

    work_items, extract_errors = _collect_work_items(paths)
    stats["errors"] += extract_errors
    stats["images_seen"] = len(work_items)
    if not work_items:
        return stats

    t0 = time.perf_counter()
    known = existing_hashes()
    known_lock = threading.Lock()
    embedder = get_embedder()
    captioner = None if skip_caption else get_captioner()

    chroma_batch: List[Tuple[str, np.ndarray, dict]] = []
    chroma_lock = threading.Lock()

    def _submit(item: _IngestWorkItem) -> _IngestOutcome:
        return _ingest_one_image(
            item,
            known=known,
            known_lock=known_lock,
            force=force,
            skip_caption=skip_caption,
            skip_ocr=skip_ocr,
            captioner=captioner,
            embedder=embedder,
            max_image_side=max_image_side,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_submit, item): item for item in work_items}
        pbar = tqdm(
            as_completed(futures),
            total=len(futures),
            desc="Images",
            unit="img",
            disable=not sys.stderr.isatty(),
        )
        for future in pbar:
            item = futures[future]
            pbar.set_postfix_str(item.file_path.name)
            outcome = future.result()
            if outcome.skipped_duplicate:
                stats["skipped_duplicates"] += 1
                continue
            if outcome.error:
                stats["errors"] += 1
                continue
            if outcome.added:
                stats["images_added"] += 1
            if outcome.updated:
                stats["images_updated"] += 1
            if outcome.record is not None and outcome.embedding is not None:
                pending: Optional[List[Tuple[str, np.ndarray, dict]]] = None
                with chroma_lock:
                    chroma_batch.append(
                        (
                            outcome.record.image_id,
                            outcome.embedding,
                            _chroma_metadata(outcome.record),
                        )
                    )
                    if len(chroma_batch) >= batch_upsert:
                        pending = list(chroma_batch)
                        chroma_batch.clear()
                if pending:
                    _flush_chroma_batch(pending)

    with chroma_lock:
        if chroma_batch:
            _flush_chroma_batch(list(chroma_batch))
            chroma_batch.clear()

    records = get_all_records()
    bm25_index.rebuild_from_records(records)

    stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def ingest_root(
    root: Path,
    *,
    skip_caption: bool = False,
    skip_ocr: bool = False,
    force: bool = False,
    workers: Optional[int] = None,
    max_image_side: Optional[int] = None,
    batch_upsert: Optional[int] = None,
) -> dict:
    paths = list(iter_corpus(root))
    return ingest_paths(
        paths,
        skip_caption=skip_caption,
        skip_ocr=skip_ocr,
        force=force,
        workers=workers,
        max_image_side=max_image_side,
        batch_upsert=batch_upsert,
    )
