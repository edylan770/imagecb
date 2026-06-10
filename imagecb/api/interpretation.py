"""Human-readable notes about how a query was interpreted."""

from __future__ import annotations

from typing import List

from imagecb.retrieval.query_parser import QuerySpec


def build_interpretation_notes(
    spec: QuerySpec,
    *,
    applied_refinement_pool: bool,
    pool_size: int,
    sticky_merged: bool,
    min_match_percent: int = 0,
    relaxed_min_score: bool = False,
    dense_failed: bool = False,
    sparse_failed: bool = False,
) -> List[str]:
    notes: List[str] = []
    if min_match_percent > 0:
        notes.append(f"Showing matches at or above {min_match_percent}%.")
    notes.append(
        "Match % on cards is calibrated for display; the min-match slider uses raw model scores."
    )
    if relaxed_min_score:
        notes.append(
            f"No matches met the {min_match_percent}% threshold; showing best available matches."
        )
    if dense_failed and sparse_failed:
        notes.append("Dense and sparse retrieval both failed (check Bedrock / index).")
    elif dense_failed:
        notes.append("Dense embedding search failed (check Bedrock embedding access).")
    elif sparse_failed:
        notes.append("Sparse BM25 search failed (index may need re-ingest).")
    if applied_refinement_pool and pool_size > 0:
        notes.append(f"Searching within {pool_size} previous result(s).")
    elif spec.is_refinement and pool_size == 0:
        notes.append("Refinement requested, but no previous results to narrow from.")

    if sticky_merged:
        sf = spec.source_filters
        tf = spec.time_filter
        carried: List[str] = []
        if sf.file_types:
            carried.append(f"types: {', '.join(sf.file_types)}")
        if sf.asset_types:
            carried.append(f"asset types: {', '.join(sf.asset_types)}")
        if sf.filename_contains:
            carried.append(f"filename contains: {', '.join(sf.filename_contains)}")
        if sf.authors:
            carried.append(f"authors: {', '.join(sf.authors)}")
        if tf.after:
            carried.append(f"modified after {tf.after.date().isoformat()}")
        if tf.before:
            carried.append(f"modified before {tf.before.date().isoformat()}")
        if carried:
            notes.append("Carried forward: " + "; ".join(carried) + ".")

    if spec.must_have_keywords:
        notes.append("Must include: " + ", ".join(spec.must_have_keywords) + ".")
    if spec.must_avoid_keywords:
        notes.append("Excluding: " + ", ".join(spec.must_avoid_keywords) + ".")

    for note in spec.sanitization_notes:
        notes.append(note)

    return notes
