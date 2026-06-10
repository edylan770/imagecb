"""Multi-turn session state.

Tracks chat history, the last QuerySpec, and the last ranked results for
follow-up query parsing context. Each search runs parse_query -> hybrid -> rerank
over the full active corpus.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from imagecb.config import SETTINGS
from imagecb.retrieval.hybrid import search
from imagecb.retrieval.query_build import rerank_query_text, resolve_rerank_top_n
from imagecb.retrieval.query_parser import (
    QuerySpec,
    build_session_context,
    parse_query,
    summarize_history,
)
from imagecb.retrieval.rerank import RankedResult, rerank


@dataclass
class AskResult:
    spec: QuerySpec
    results: List[RankedResult]
    min_match_percent: int = 0
    candidate_count: int = 0
    relaxed_min_score: bool = False
    dense_failed: bool = False
    sparse_failed: bool = False
    indexed_count: int = 0


@dataclass
class ChatSession:
    history: List[Tuple[str, str]] = field(default_factory=list)
    last_spec: Optional[QuerySpec] = None
    last_candidate_ids: List[str] = field(default_factory=list)
    last_results: List[RankedResult] = field(default_factory=list)

    def reset(self) -> None:
        self.history.clear()
        self.last_spec = None
        self.last_candidate_ids = []
        self.last_results = []

    def ask(
        self,
        text: str,
        *,
        top_k: Optional[int] = None,
        min_match_percent: int = 0,
        sort: Optional[str] = None,
    ) -> AskResult:
        history_summary = summarize_history(self.history)
        session_ctx = build_session_context(self.last_spec, self.last_results)
        spec = parse_query(text, history_summary, session_context=session_ctx)

        if top_k is not None:
            spec.top_k = max(1, min(int(top_k), 50))

        # Without a floor, results are padded to top_k with low-scoring
        # candidates that are unrelated to the query. When the user has not
        # set an explicit minimum, drop the irrelevant tail instead.
        user_min = max(0.0, min(float(min_match_percent) / 100.0, 1.0))
        min_score = user_min if user_min > 0 else SETTINGS.weak_result_score_threshold

        outcome = search(spec)
        candidates = outcome.candidates
        query_for_rerank = rerank_query_text(spec, text)

        results = rerank(
            query_for_rerank,
            candidates,
            top_k=spec.top_k,
            top_n=resolve_rerank_top_n(spec),
            min_score=min_score,
            spec=spec,
        )
        relaxed_min_score = False
        if not results and candidates:
            results = rerank(
                query_for_rerank,
                candidates,
                top_k=spec.top_k,
                top_n=resolve_rerank_top_n(spec),
                min_score=0.0,
                spec=spec,
            )
            relaxed_min_score = bool(results)

        from imagecb.retrieval.sort import resolve_sort, sort_ranked_results

        resolved_sort = resolve_sort(sort, is_search=True)
        results = sort_ranked_results(results, resolved_sort)

        self.last_spec = spec
        self.last_results = list(results)
        self.last_candidate_ids = [r.image_id for r in results] or [
            c.image_id for c in candidates
        ]

        return AskResult(
            spec=spec,
            results=results,
            min_match_percent=min_match_percent,
            candidate_count=len(candidates),
            relaxed_min_score=relaxed_min_score,
            dense_failed=outcome.dense_failed,
            sparse_failed=outcome.sparse_failed,
        )

    def record_turn(self, user_text: str, assistant_message: str) -> None:
        """Append a turn using the full assistant reply for better follow-up context."""
        summary = assistant_message.strip() or _summarize_results(self.last_results)
        if len(summary) > 500:
            summary = summary[:497].rstrip() + "..."
        self.history.append((user_text, summary))

    def apply_similar_results(
        self,
        results: List[RankedResult],
        *,
        spec: QuerySpec,
    ) -> None:
        """Update candidate pool after similar-image search.

        Similar search is a new anchor, not a refinement of the prior result set.
        """
        self.last_results = list(results)
        self.last_candidate_ids = [r.image_id for r in results]
        merged = QuerySpec(
            semantic_query=spec.semantic_query,
            raw_text=spec.raw_text,
            must_have_keywords=list(spec.must_have_keywords),
            must_avoid_keywords=list(spec.must_avoid_keywords),
            source_filters=spec.source_filters,
            time_filter=spec.time_filter,
            top_k=spec.top_k,
            is_refinement=False,
        )
        self.last_spec = merged


def _summarize_results(results: List[RankedResult]) -> str:
    if not results:
        return "No results."
    bits = [f"{len(results)} results."]
    for r in results[:3]:
        bits.append(f"- {r.provenance_line}: {r.record.caption_short or ''}".strip())
    return "\n".join(bits)
