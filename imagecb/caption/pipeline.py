"""End-to-end caption generation with normalization and quality gating."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Set

from imagecb.caption.asset_type import normalize_asset_type
from imagecb.caption.context import caption_context_from_provenance
from imagecb.caption.lexicon import (
    SearchLexicon,
    build_search_lexicon,
    enrich_aliases_for_tags,
    enrich_recommended_cases,
    refresh_lexicon_cache,
)
from imagecb.caption.normalize import normalize_tags
from imagecb.caption.quality import assess_caption
from imagecb.caption.vocab import load_tag_vocab
from imagecb.models.vlm import CaptionJSON, VLMCaptioner

if TYPE_CHECKING:
    from imagecb.extractors.types import ExtractedImage


def _apply_normalized_tags(
    caption: CaptionJSON,
    vocab: Set[str],
    lexicon: SearchLexicon,
) -> CaptionJSON:
    raw = list(caption.search.tags)
    normalized = normalize_tags(raw, vocab, lexicon=lexicon)
    caption.search.tags = normalized
    return caption


def _enrich_search_terms(caption: CaptionJSON, lexicon: SearchLexicon) -> CaptionJSON:
    """Add corpus-aligned aliases; dedupe and strip boilerplate from recommended_cases."""
    tags = list(caption.search.tags)
    caption.search.aliases = enrich_aliases_for_tags(
        tags,
        lexicon,
        existing_aliases=list(caption.search.aliases),
    )
    caption.search.recommended_cases = enrich_recommended_cases(
        tags,
        caption.theme,
        existing_cases=list(caption.search.recommended_cases),
        lexicon=lexicon,
        asset_type=caption.grounded.asset_type,
    )
    return caption


def enrich_caption_search_terms(caption: CaptionJSON) -> CaptionJSON:
    """Public helper for repair-search-terms (no VLM re-call)."""
    lexicon = build_search_lexicon()
    return _enrich_search_terms(caption, lexicon)


def generate_caption(
    extracted: "ExtractedImage",
    captioner: VLMCaptioner,
    *,
    max_side: int,
    vocab: Optional[Set[str]] = None,
) -> CaptionJSON:
    """Generate caption with context, tag normalization, quality gate, and one retry."""
    if vocab is None:
        vocab = set(load_tag_vocab())

    ctx = caption_context_from_provenance(extracted.provenance)
    source_file = extracted.provenance.source_file

    def _run() -> CaptionJSON:
        lexicon = build_search_lexicon()
        cap = captioner.caption_image(
            extracted.image,
            max_side=max_side,
            context=ctx,
            source_file=source_file,
        )
        if cap.short_caption == "[caption failed]":
            return cap
        cap.grounded.asset_type = normalize_asset_type(cap.grounded.asset_type)
        cap = _apply_normalized_tags(cap, vocab, lexicon)
        cap = _enrich_search_terms(cap, lexicon)
        quality = assess_caption(cap)
        cap.caption_quality = quality
        return cap

    caption = _run()
    if caption.caption_quality in ("weak", "failed"):
        retry = _run()
        if retry.caption_quality == "ok" or (
            retry.caption_quality == "weak" and caption.caption_quality == "failed"
        ):
            caption = retry
        elif retry.caption_quality == "weak" and caption.caption_quality == "weak":
            caption = retry

    return caption


def refresh_vocab_cache() -> Set[str]:
    """Rebuild in-memory vocab and lexicon after ingest batch."""
    from imagecb.caption import vocab as vocab_mod

    vocab_mod._vocab_cache = None  # noqa: SLF001
    refresh_lexicon_cache()
    return set(load_tag_vocab(refresh=True))
