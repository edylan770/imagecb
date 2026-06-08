"""Chroma-backed dense vector store.

Stores one record per image_id with the Bedrock Titan embedding plus a
compact subset of provenance metadata so Chroma can apply `where`
filters server-side.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence

import numpy as np

from imagecb.config import SETTINGS

_COLLECTION = "imagecb_images"


_client = None
_collection = None


def _get_collection():
    global _client, _collection
    if _collection is not None:
        return _collection
    import chromadb
    from chromadb.config import Settings as ChromaSettings

    _client = chromadb.PersistentClient(
        path=str(SETTINGS.chroma_dir),
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    _collection = _client.get_or_create_collection(
        name=_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )
    return _collection


def upsert(
    *,
    image_ids: Sequence[str],
    embeddings: np.ndarray,
    metadatas: Sequence[dict],
) -> None:
    if not image_ids:
        return
    col = _get_collection()
    col.upsert(
        ids=list(image_ids),
        embeddings=[e.tolist() for e in embeddings],
        metadatas=list(metadatas),
    )


def query(
    query_embedding: np.ndarray,
    *,
    top_k: int,
    allowed_ids: Optional[Iterable[str]] = None,
) -> List[tuple[str, float]]:
    col = _get_collection()
    where = None
    if allowed_ids is not None:
        ids_list = list(allowed_ids)
        if not ids_list:
            return []
        # Chroma uses image_id stored in metadata to allow $in filtering.
        where = {"image_id": {"$in": ids_list}}
    res = col.query(
        query_embeddings=[query_embedding.tolist()],
        n_results=top_k,
        where=where,
    )
    ids = res.get("ids", [[]])[0]
    distances = res.get("distances", [[]])[0]
    # Convert cosine distance (1 - similarity) to similarity.
    return [(i, 1.0 - float(d)) for i, d in zip(ids, distances)]


def count() -> int:
    col = _get_collection()
    return col.count()


def delete(image_ids: Sequence[str]) -> None:
    if not image_ids:
        return
    col = _get_collection()
    col.delete(ids=list(image_ids))


def list_ids(*, batch_size: int = 500) -> set[str]:
    """Return all image_id values present in the Chroma collection."""
    col = _get_collection()
    n = col.count()
    if n == 0:
        return set()
    out: set[str] = set()

    def _consume(res: dict) -> None:
        for i in res.get("ids") or []:
            out.add(str(i))

    try:
        offset = 0
        while offset < n:
            limit = min(batch_size, n - offset)
            res = col.get(include=[], limit=limit, offset=offset)
            offset += limit
            _consume(res)
    except TypeError:
        res = col.get(include=[], limit=n)
        _consume(res)
    return out


def get_all_embeddings(*, batch_size: int = 500) -> List[tuple[str, np.ndarray]]:
    """Return (image_id, embedding) for all vectors in the collection."""
    col = _get_collection()
    n = col.count()
    if n == 0:
        return []
    out: List[tuple[str, np.ndarray]] = []

    def _consume(res: dict) -> None:
        ids = res.get("ids") or []
        embs = res.get("embeddings") or []
        for i, emb in zip(ids, embs):
            if emb is None:
                continue
            try:
                arr = np.asarray(emb, dtype=np.float64)
            except (ValueError, TypeError):
                continue
            if arr.ndim != 1 or arr.size == 0:
                continue
            out.append((str(i), arr))

    try:
        offset = 0
        while offset < n:
            limit = min(batch_size, n - offset)
            res = col.get(
                include=["embeddings"],
                limit=limit,
                offset=offset,
            )
            offset += limit
            _consume(res)
    except TypeError:
        res = col.get(include=["embeddings"], limit=n)
        _consume(res)
    return out
