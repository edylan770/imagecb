"""Post-generation tag normalization: case, plurality, synonym map."""

from __future__ import annotations

from typing import Dict, List, Set

from imagecb.caption.lexicon import load_seed_synonyms, normalize_tag

_SEED_SYNONYMS = load_seed_synonyms()


def _canonical_via_synonym(tag: str, synonym_map: Dict[str, str]) -> str:
    normalized = normalize_tag(tag)
    if not normalized:
        return ""
    if normalized in synonym_map:
        return normalize_tag(synonym_map[normalized])
    return normalized


def normalize_tags(
    raw_tags: List[str],
    vocab: Set[str],
    *,
    min_length: int = 2,
) -> List[str]:
    """Map tags to canonical forms; prefer vocab terms when synonym resolves to one."""
    vocab_normalized = {normalize_tag(v): v for v in vocab}
    vocab_keys = set(vocab_normalized.keys())

    seen: set[str] = set()
    out: List[str] = []

    for raw in raw_tags:
        canonical = _canonical_via_synonym(raw, _SEED_SYNONYMS)
        if not canonical or len(canonical) < min_length:
            continue
        if canonical in vocab_keys:
            canonical = vocab_normalized[canonical]
        else:
            canonical = normalize_tag(canonical)
        if canonical in seen:
            continue
        seen.add(canonical)
        out.append(canonical)

    return out


__all__ = ["normalize_tag", "normalize_tags"]
