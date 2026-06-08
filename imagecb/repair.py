"""Index health assessment and targeted repair without full corpus re-ingest."""

from __future__ import annotations

import logging
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Sequence, Set, Tuple

import numpy as np
from PIL import Image
from tqdm import tqdm

from imagecb.caption.context import caption_context_from_record
from imagecb.caption.normalize import normalize_tags
from imagecb.caption.pipeline import enrich_caption_search_terms
from imagecb.caption.quality import CAPTION_FAILED, assess_caption
from imagecb.caption.vocab import load_tag_vocab
from imagecb.config import SETTINGS
from imagecb.ingest import _chroma_metadata, _flush_chroma_batch
from imagecb.ingest_context import embed_context_from_record
from imagecb.models.embedder import get_embedder
from imagecb.models.vlm import CaptionJSON, get_captioner
from imagecb.paths import resolve_source_file
from imagecb.storage import bm25_index, metadata_db, vector_store
from imagecb.storage.metadata_db import ImageRecord, get_all_records, get_records, session_scope

logger = logging.getLogger(__name__)


@dataclass
class IndexHealthReport:
    total_records: int
    chroma_vectors: int
    missing_cache_count: int
    missing_cache_records: List[ImageRecord] = field(default_factory=list)
    failed_caption_count: int = 0
    failed_caption_records: List[ImageRecord] = field(default_factory=list)
    weak_caption_count: int = 0
    weak_caption_records: List[ImageRecord] = field(default_factory=list)
    missing_chroma_count: int = 0
    missing_chroma_ids: List[str] = field(default_factory=list)
    unrecoverable_source_missing_count: int = 0
    unrecoverable_records: List[ImageRecord] = field(default_factory=list)
    recoverable_source_files: List[str] = field(default_factory=list)
    is_healthy: bool = True
    elapsed_sec: float = 0.0


def _cache_missing(record: ImageRecord) -> bool:
    return not Path(record.image_path).expanduser().is_file()


def _caption_failed(record: ImageRecord) -> bool:
    return (record.caption_short or "").strip() == CAPTION_FAILED or (
        (record.caption_quality or "").lower() == "failed"
    )


def _caption_weak(record: ImageRecord) -> bool:
    return (record.caption_quality or "").lower() == "weak"


def records_with_failed_captions() -> List[ImageRecord]:
    return [r for r in get_all_records() if _caption_failed(r)]


def records_with_weak_captions() -> List[ImageRecord]:
    return [r for r in get_all_records() if _caption_weak(r)]


def records_needing_regen(*, include_weak: bool = False) -> List[ImageRecord]:
    failed_ids = {r.image_id for r in records_with_failed_captions()}
    records = list(records_with_failed_captions())
    if include_weak:
        for r in records_with_weak_captions():
            if r.image_id not in failed_ids:
                records.append(r)
    return records


def assess_index_health(*, include_weak: bool = False) -> IndexHealthReport:
    """Read-only scan of SQLite, cache files, and Chroma for known issue classes."""
    t0 = time.perf_counter()
    records = get_all_records(include_deleted=False)

    missing_cache_records = [r for r in records if _cache_missing(r)]
    failed_caption_records = [r for r in records if _caption_failed(r)]
    weak_caption_records = [r for r in records if _caption_weak(r)] if include_weak else []

    unrecoverable_records: List[ImageRecord] = []
    recoverable_source_files: Set[str] = set()
    for r in missing_cache_records:
        src = resolve_source_file(r)
        if src is not None:
            recoverable_source_files.add(str(src))
        else:
            unrecoverable_records.append(r)

    sqlite_ids = {r.image_id for r in records}
    try:
        chroma_vectors = vector_store.count()
        chroma_ids = vector_store.list_ids()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Could not read Chroma collection: %s", exc)
        chroma_vectors = 0
        chroma_ids = set()

    missing_chroma_ids = sorted(sqlite_ids - chroma_ids)

    missing_cache_count = len(missing_cache_records)
    failed_caption_count = len(failed_caption_records)
    missing_chroma_count = len(missing_chroma_ids)
    is_healthy = (
        missing_cache_count == 0
        and failed_caption_count == 0
        and missing_chroma_count == 0
    )

    elapsed = round(time.perf_counter() - t0, 2)
    logger.info(
        "Index health assess: records=%s healthy=%s missing_cache=%s failed_captions=%s "
        "missing_chroma=%s unrecoverable=%s (%.2fs)",
        len(records),
        is_healthy,
        missing_cache_count,
        failed_caption_count,
        missing_chroma_count,
        len(unrecoverable_records),
        elapsed,
    )

    return IndexHealthReport(
        total_records=len(records),
        chroma_vectors=chroma_vectors,
        missing_cache_count=missing_cache_count,
        missing_cache_records=missing_cache_records,
        failed_caption_count=failed_caption_count,
        failed_caption_records=failed_caption_records,
        weak_caption_count=len(weak_caption_records),
        weak_caption_records=weak_caption_records,
        missing_chroma_count=missing_chroma_count,
        missing_chroma_ids=missing_chroma_ids,
        unrecoverable_source_missing_count=len(unrecoverable_records),
        unrecoverable_records=unrecoverable_records,
        recoverable_source_files=sorted(recoverable_source_files),
        is_healthy=is_healthy,
        elapsed_sec=elapsed,
    )


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


def _caption_from_record(record: ImageRecord, img: Image.Image) -> CaptionJSON:
    vocab = set(load_tag_vocab())
    ctx = caption_context_from_record(record)
    captioner = get_captioner()
    cap = captioner.caption_image(
        img,
        context=ctx,
        source_file=record.source_file,
    )
    if cap.short_caption != CAPTION_FAILED:
        cap.search.tags = normalize_tags(list(cap.search.tags), vocab)
        cap = enrich_caption_search_terms(cap)
        cap.caption_quality = assess_caption(cap)
    else:
        cap.caption_quality = "failed"
    return cap


def _apply_caption_to_record(record: ImageRecord, caption: CaptionJSON) -> None:
    if caption.image_name:
        record.image_name = caption.image_name
    record.caption_short = caption.short_caption
    record.caption_detailed = caption.detailed_description
    record.use_case = caption.use_case
    record.theme = caption.theme
    record.scene = caption.scene
    record.text_overlay_summary = caption.text_overlay_summary
    record.text_read_uncertain = 1 if caption.text_read_uncertain else 0
    record.objects_json = metadata_db.serialize_list(caption.objects)
    record.tags_json = metadata_db.serialize_list(caption.tags)
    record.recommended_cases_json = metadata_db.serialize_list(caption.recommended_cases)
    record.search_aliases_json = metadata_db.serialize_list(caption.aliases)
    record.caption_quality = caption.caption_quality or "ok"


def _repair_one_caption(record: ImageRecord) -> Tuple[str, bool, Optional[str]]:
    img = _load_cached_image(record)
    if img is None:
        return record.image_id, False, "cached image missing"
    try:
        caption = _caption_from_record(record, img)
        if caption.caption_quality in ("weak", "failed"):
            retry = _caption_from_record(record, img)
            if retry.caption_quality == "ok" or (
                retry.caption_quality == "weak" and caption.caption_quality == "failed"
            ):
                caption = retry
        _apply_caption_to_record(record, caption)
        with session_scope() as s:
            s.merge(record)
        return record.image_id, True, None
    except Exception as exc:  # noqa: BLE001
        return record.image_id, False, str(exc)


def repair_failed_captions(
    *,
    workers: Optional[int] = None,
    include_weak: bool = False,
    rebuild_bm25: bool = True,
) -> dict:
    """Re-caption rows where VLM failed or quality is weak."""
    workers = max(1, workers if workers is not None else SETTINGS.ingest_workers)
    records = records_needing_regen(include_weak=include_weak)
    stats = {
        "attempted": len(records),
        "repaired": 0,
        "errors": 0,
        "include_weak": include_weak,
        "workers": workers,
    }
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

    if rebuild_bm25:
        bm25_index.rebuild_from_records(get_all_records())
    stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def _record_to_caption_json(record: ImageRecord) -> CaptionJSON:
    cap = CaptionJSON()
    cap.image_name = record.image_name or ""
    cap.interpretive.theme = record.theme or ""
    cap.search.tags = metadata_db.deserialize_list(record.tags_json)
    cap.search.recommended_cases = metadata_db.deserialize_list(record.recommended_cases_json)
    cap.search.aliases = metadata_db.deserialize_list(record.search_aliases_json)
    return cap


def repair_search_terms(*, rebuild_bm25: bool = True) -> dict:
    """Re-enrich aliases and recommended_cases from stored tags (no VLM)."""
    from imagecb.caption.lexicon import refresh_lexicon_cache

    t0 = time.perf_counter()
    records = get_all_records()
    updated = 0
    refresh_lexicon_cache()

    for record in records:
        if _caption_failed(record):
            continue
        cap = _record_to_caption_json(record)
        if not cap.search.tags:
            continue
        enriched = enrich_caption_search_terms(cap)
        record.recommended_cases_json = metadata_db.serialize_list(enriched.recommended_cases)
        record.search_aliases_json = metadata_db.serialize_list(enriched.aliases)
        with session_scope() as s:
            s.merge(record)
        updated += 1

    if rebuild_bm25 and updated:
        bm25_index.rebuild_from_records(get_all_records())

    return {
        "records": len(records),
        "updated": updated,
        "elapsed_sec": round(time.perf_counter() - t0, 1),
    }


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
    image_ids: Optional[Sequence[str]] = None,
) -> dict:
    """Re-embed indexed images from cached PNGs (picks up context-aware vectors)."""
    workers = max(1, workers if workers is not None else SETTINGS.ingest_workers)
    batch_upsert = max(1, batch_upsert if batch_upsert is not None else SETTINGS.ingest_batch_upsert)
    if image_ids is not None:
        id_set = set(image_ids)
        records = [r for r in get_records(image_ids) if r.image_id in id_set]
    else:
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


def repair_missing_cache(
    records: Optional[List[ImageRecord]] = None,
    *,
    workers: Optional[int] = None,
) -> dict:
    """Re-extract from source files to rebuild missing cached PNGs."""
    t0 = time.perf_counter()
    if records is None:
        report = assess_index_health()
        records = report.missing_cache_records

    repair_queue: Set[Path] = set()
    unrecoverable = 0
    for record in records:
        src = resolve_source_file(record)
        if src is not None:
            repair_queue.add(src)
        else:
            unrecoverable += 1
            logger.warning(
                "Unrecoverable missing cache for %s (source missing: %s)",
                record.image_id,
                record.source_file or "(none)",
            )

    stats = {
        "source_files_attempted": len(repair_queue),
        "source_files_repaired": 0,
        "images_updated": 0,
        "errors": 0,
        "unrecoverable": unrecoverable,
    }
    if not repair_queue:
        stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
        return stats

    from imagecb.ingest import ingest_paths

    ingest_stats = ingest_paths(
        sorted(repair_queue, key=str),
        force=True,
        auto_repair=False,
        rebuild_bm25=False,
        refresh_vocab=False,
        workers=workers,
    )
    stats["source_files_repaired"] = ingest_stats.get("files", 0)
    stats["images_updated"] = ingest_stats.get("images_updated", 0) + ingest_stats.get("images_added", 0)
    stats["errors"] = ingest_stats.get("errors", 0)
    stats["ingest"] = ingest_stats
    stats["elapsed_sec"] = round(time.perf_counter() - t0, 1)
    return stats


def repair_index_issues(
    *,
    workers: Optional[int] = None,
    include_weak_captions: Optional[bool] = None,
    repair_missing_vectors: Optional[bool] = None,
    skip_caption_phases: bool = False,
) -> dict:
    """Phased repair: missing cache, failed captions, optional weak, missing Chroma vectors."""
    if include_weak_captions is None:
        include_weak_captions = SETTINGS.post_ingest_repair_include_weak
    if repair_missing_vectors is None:
        repair_missing_vectors = SETTINGS.post_ingest_repair_reindex_vectors

    t0 = time.perf_counter()
    report = assess_index_health(include_weak=include_weak_captions)
    if report.is_healthy:
        logger.info("Post-ingest repair skipped: index is healthy")
        return {
            "skipped": True,
            "is_healthy": True,
            "elapsed_sec": round(time.perf_counter() - t0, 1),
            "assess": {"elapsed_sec": report.elapsed_sec},
        }

    logger.info(
        "Post-ingest repair starting: missing_cache=%s failed_captions=%s missing_chroma=%s",
        report.missing_cache_count,
        report.failed_caption_count,
        report.missing_chroma_count,
    )

    phases: dict = {}
    any_phase_ran = False

    if report.missing_cache_count > 0:
        any_phase_ran = True
        phases["cache"] = repair_missing_cache(workers=workers)

    if not skip_caption_phases:
        report = assess_index_health(include_weak=include_weak_captions)
        if report.failed_caption_count > 0:
            any_phase_ran = True
            phases["captions"] = repair_failed_captions(
                workers=workers,
                include_weak=False,
                rebuild_bm25=False,
            )

        if include_weak_captions:
            report = assess_index_health(include_weak=True)
            if report.weak_caption_count > 0:
                any_phase_ran = True
                phases["weak_captions"] = repair_failed_captions(
                    workers=workers,
                    include_weak=True,
                    rebuild_bm25=False,
                )

    if repair_missing_vectors:
        report = assess_index_health(include_weak=include_weak_captions)
        if report.missing_chroma_count > 0:
            records_by_id = {r.image_id: r for r in get_all_records()}
            reindex_ids = [
                iid
                for iid in report.missing_chroma_ids
                if iid in records_by_id and not _cache_missing(records_by_id[iid])
            ]
            if reindex_ids:
                any_phase_ran = True
                phases["vectors"] = reindex_embeddings(workers=workers, image_ids=reindex_ids)

    if any_phase_ran:
        bm25_index.rebuild_from_records(get_all_records())

    final = assess_index_health(include_weak=include_weak_captions)
    elapsed = round(time.perf_counter() - t0, 1)

    summary = {
        "skipped": False,
        "is_healthy": final.is_healthy,
        "phases": phases,
        "elapsed_sec": elapsed,
        "cache_recached": phases.get("cache", {}).get("images_updated", 0),
        "captions_repaired": phases.get("captions", {}).get("repaired", 0)
        + phases.get("weak_captions", {}).get("repaired", 0),
        "vectors_reindexed": phases.get("vectors", {}).get("reindexed", 0),
        "source_files_attempted": phases.get("cache", {}).get("source_files_attempted", 0),
        "unrecoverable": phases.get("cache", {}).get("unrecoverable", 0),
        "remaining_missing_cache": final.missing_cache_count,
        "remaining_failed_captions": final.failed_caption_count,
        "remaining_missing_chroma": final.missing_chroma_count,
    }
    logger.info(
        "Post-ingest repair done in %.1fs: recached=%s captions=%s vectors=%s healthy=%s",
        elapsed,
        summary["cache_recached"],
        summary["captions_repaired"],
        summary["vectors_reindexed"],
        final.is_healthy,
    )
    return summary


def format_post_repair_summary(repair_stats: dict) -> str:
    """Human-readable one-liner for ingest API/UI; empty when repair was skipped."""
    if not repair_stats or repair_stats.get("skipped"):
        return ""

    parts: List[str] = []
    cache = repair_stats.get("cache_recached", 0)
    sources = repair_stats.get("source_files_attempted", 0)
    if cache or sources:
        parts.append(f"re-cached {cache} images from {sources} source file(s)")
    captions = repair_stats.get("captions_repaired", 0)
    if captions:
        parts.append(f"re-captioned {captions}")
    vectors = repair_stats.get("vectors_reindexed", 0)
    if vectors:
        parts.append(f"re-indexed {vectors} vectors")
    unrecoverable = repair_stats.get("unrecoverable", 0)
    if unrecoverable:
        parts.append(f"{unrecoverable} unrecoverable (source file missing)")

    if not parts:
        return ""
    return "Post-ingest repair: " + "; ".join(parts) + "."
