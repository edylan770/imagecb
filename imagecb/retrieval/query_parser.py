"""Convert a chat turn into a validated `QuerySpec` via the LLM."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import TYPE_CHECKING, List, Optional

from imagecb.config import SETTINGS
from imagecb.models.llm import get_query_llm

if TYPE_CHECKING:
    from imagecb.retrieval.rerank import RankedResult

logger = logging.getLogger(__name__)


@dataclass
class SourceFilters:
    file_types: List[str] = field(default_factory=list)
    filename_contains: List[str] = field(default_factory=list)
    authors: List[str] = field(default_factory=list)


@dataclass
class TimeFilter:
    before: Optional[datetime] = None
    after: Optional[datetime] = None


@dataclass
class QuerySpec:
    semantic_query: str = ""
    must_have_keywords: List[str] = field(default_factory=list)
    must_avoid_keywords: List[str] = field(default_factory=list)
    source_filters: SourceFilters = field(default_factory=SourceFilters)
    time_filter: TimeFilter = field(default_factory=TimeFilter)
    top_k: int = 10
    is_refinement: bool = False
    raw_text: str = ""


@dataclass
class SessionContext:
    """Extra context for query parsing on follow-up turns."""

    previous_spec: Optional[QuerySpec] = None
    previous_results_summary: str = ""


def _serialize_previous_spec(spec: QuerySpec) -> str:
    sf = spec.source_filters
    tf = spec.time_filter
    payload = {
        "source_filters": {
            "file_types": list(sf.file_types),
            "filename_contains": list(sf.filename_contains),
            "authors": list(sf.authors),
        },
        "time_filter": {
            "before": tf.before.date().isoformat() if tf.before else None,
            "after": tf.after.date().isoformat() if tf.after else None,
        },
        "must_have_keywords": list(spec.must_have_keywords),
        "must_avoid_keywords": list(spec.must_avoid_keywords),
    }
    return json.dumps(payload, ensure_ascii=False)


def build_session_context(
    previous_spec: Optional[QuerySpec],
    previous_results: "List[RankedResult]",
    *,
    max_results: int = 5,
) -> Optional[SessionContext]:
    if previous_spec is None and not previous_results:
        return None
    lines: List[str] = []
    for r in previous_results[:max_results]:
        cap = (r.record.caption_short or "")[:80]
        lines.append(f"- {r.provenance_line}: {cap}".strip())
    return SessionContext(
        previous_spec=previous_spec,
        previous_results_summary="\n".join(lines),
    )


def _parse_iso(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    # Accept date-only or full ISO.
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d"):
            try:
                return datetime.strptime(s, fmt)
            except ValueError:
                continue
        logger.debug("Could not parse date: %s", value)
        return None


def _slist(value) -> List[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if x is not None and str(x).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


_ALLOWED_FILE_TYPES = {"pptx", "pdf", "image"}


def _normalize_file_types(values: List[str]) -> List[str]:
    out = []
    for v in values:
        v2 = v.lower().strip().lstrip(".")
        if v2 in {"jpg", "jpeg", "png", "webp", "gif", "tiff", "tif", "bmp", "img", "images"}:
            v2 = "image"
        if v2 in _ALLOWED_FILE_TYPES and v2 not in out:
            out.append(v2)
    return out


def parse_query(
    text: str,
    history_summary: str = "",
    *,
    session_context: Optional[SessionContext] = None,
) -> QuerySpec:
    """Use the LLM to convert `text` into a validated `QuerySpec`."""
    text = (text or "").strip()
    if not text:
        return QuerySpec(raw_text=text)

    today_iso = date.today().isoformat()
    prev_spec_json = ""
    prev_results = ""
    if session_context is not None:
        if session_context.previous_spec is not None:
            prev_spec_json = _serialize_previous_spec(session_context.previous_spec)
        prev_results = session_context.previous_results_summary or ""

    try:
        raw = get_query_llm().parse(
            text,
            history_summary,
            today_iso,
            previous_spec_json=prev_spec_json,
            previous_results_summary=prev_results,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Query LLM failed (%s); falling back to literal query.", exc)
        return QuerySpec(semantic_query=text, raw_text=text)

    return _build_spec(raw, text)


def _build_spec(raw: dict, original_text: str) -> QuerySpec:
    sf_raw = raw.get("source_filters") or {}
    tf_raw = raw.get("time_filter") or {}
    spec = QuerySpec(
        semantic_query=str(raw.get("semantic_query") or original_text).strip() or original_text,
        must_have_keywords=_slist(raw.get("must_have_keywords")),
        must_avoid_keywords=_slist(raw.get("must_avoid_keywords")),
        source_filters=SourceFilters(
            file_types=_normalize_file_types(_slist(sf_raw.get("file_types"))),
            filename_contains=_slist(sf_raw.get("filename_contains")),
            authors=_slist(sf_raw.get("authors")),
        ),
        time_filter=TimeFilter(
            before=_parse_iso(tf_raw.get("before")),
            after=_parse_iso(tf_raw.get("after")),
        ),
        top_k=int(raw.get("top_k") or SETTINGS.default_top_k),
        is_refinement=bool(raw.get("is_refinement", False)),
        raw_text=original_text,
    )
    # Clamp top_k to sane bounds.
    spec.top_k = max(1, min(spec.top_k, 50))
    return spec


def summarize_history(history: List[tuple[str, str]], max_turns: int = 6) -> str:
    """Compact (user, assistant) history into a few bullet lines for the LLM."""
    if not history:
        return ""
    recent = history[-max_turns:]
    lines = []
    for user, assistant in recent:
        if user:
            lines.append(f"- user: {user.strip()[:200]}")
        if assistant:
            lines.append(f"  assistant: {assistant.strip()[:200]}")
    return "\n".join(lines)
