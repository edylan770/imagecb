"""LLM-generated empty-state query suggestions with in-process cache."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from imagecb.config import SETTINGS
from imagecb.suggestions.corpus_summary import (
    CorpusContext,
    build_corpus_context,
    context_to_prompt_text,
)
from imagecb.telemetry.recorder import get_recent_user_queries

SUGGESTIONS_SYSTEM_PROMPT = """You suggest starter search queries for an image search app over \
ingested slides, PDFs, and standalone images.

Return ONLY a JSON object:
{"suggestions": ["...", "..."]}

Rules:
- Each suggestion is a short natural-language phrase the user can click to search (under 80 chars).
- Use ONLY topics, tags, captions, and recommended search phrases present in the corpus context. \
Never invent assets or topics.
- Prefer semantic, topic-based search phrases drawn from tags, captions, and recommended search phrases.
- NEVER suggest "images from [filename]", "slides from [filename]", or any filename-only filter query.
- Source filenames in the corpus context are for grounding only — do not use them in suggestions.
- If recent user queries are provided, include 1–2 suggestions that extend or paraphrase them \
(do not copy verbatim unless still useful).
- Recent chat titles are secondary context only when queries are absent.
- Do not include markdown, code fences, or explanation outside the JSON object."""

ONBOARDING_SUGGESTIONS = [
    "Upload slides or PDFs in the Corpus panel, then search here",
    "Charts and diagrams",
    "Screenshots and UI mockups",
    "Logos and icons on plain backgrounds",
]

_FILENAME_FILTER_RE = re.compile(
    r"^(?:images?|slides?|photos?|pictures?|content|visuals?|graphics?)\s+from\s+",
    re.IGNORECASE,
)
_FILENAME_EXT_RE = re.compile(r"\.(?:pptx?|pdf|docx?|xlsx?|png|jpe?g|gif|webp|bmp|tiff?)\b", re.IGNORECASE)

_cache: dict[str, Tuple[float, List[str]]] = {}


@dataclass(frozen=True)
class SuggestionsResult:
    suggestions: List[str]
    cached: bool


def normalize_recent_titles(titles: Sequence[str], *, limit: int = 8) -> Tuple[str, ...]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in titles:
        t = raw.strip()
        if not t or t.lower() == "new chat":
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
        if len(out) >= limit:
            break
    return tuple(out)


def normalize_recent_queries(queries: Sequence[str], *, limit: int = 8) -> Tuple[str, ...]:
    seen: set[str] = set()
    out: List[str] = []
    for raw in queries:
        q = raw.strip()
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= limit:
            break
    return tuple(out)


def merge_recent_queries(
    client_queries: Sequence[str],
    telemetry_queries: Sequence[str],
    *,
    limit: int = 8,
) -> Tuple[str, ...]:
    """Client queries first; telemetry fills remaining slots."""
    seen: set[str] = set()
    out: List[str] = []
    for raw in list(client_queries) + list(telemetry_queries):
        q = raw.strip()
        if not q:
            continue
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(q)
        if len(out) >= limit:
            break
    return tuple(out)


def _cache_key(
    ctx: CorpusContext,
    titles: Tuple[str, ...],
    queries: Tuple[str, ...],
) -> str:
    title_part = "|".join(t.lower() for t in titles)
    query_part = "|".join(q.lower() for q in queries)
    return f"{ctx.fingerprint}|q:{query_part}|t:{title_part}"


def _coerce_suggestions_json(raw: str) -> List[str]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end <= start:
            return []
        try:
            data = json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            return []
    if isinstance(data, dict):
        items = data.get("suggestions", [])
    elif isinstance(data, list):
        items = data
    else:
        return []
    if not isinstance(items, list):
        return []
    out: List[str] = []
    for item in items:
        if not isinstance(item, str):
            continue
        s = item.strip()
        if s:
            out.append(s)
    return out


def _trim_suggestions(items: Sequence[str], limit: int) -> List[str]:
    return list(items[:limit]) if items else []


def _is_filename_filter_suggestion(text: str) -> bool:
    s = text.strip()
    if not s:
        return False
    if _FILENAME_FILTER_RE.match(s):
        return True
    if _FILENAME_EXT_RE.search(s) and re.search(r"\bfrom\b", s, re.IGNORECASE):
        return True
    return False


def _corpus_semantic_pool(ctx: CorpusContext) -> List[str]:
    pool: List[str] = []
    seen: set[str] = set()

    def add(text: str) -> None:
        s = text.strip()
        if not s or _is_filename_filter_suggestion(s):
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        pool.append(s)

    for case in ctx.sample_recommended_cases:
        add(case)

    for tag in ctx.top_tags[:6]:
        add(f"{tag} and related visuals")

    for cap in ctx.sample_captions[:6]:
        if len(cap) <= 60:
            add(cap)
        else:
            add(cap[:57] + "...")

    return pool


def _blend_suggestions(
    candidates: Sequence[str],
    ctx: CorpusContext,
    queries: Tuple[str, ...],
    limit: int,
) -> List[str]:
    """Merge user queries, corpus semantic seeds, and filtered candidates."""
    out: List[str] = []
    seen: set[str] = set()
    backfill = _corpus_semantic_pool(ctx)

    def add(text: str) -> None:
        s = text.strip()
        if not s or _is_filename_filter_suggestion(s):
            return
        key = s.lower()
        if key in seen:
            return
        seen.add(key)
        out.append(s)

    for q in queries[:2]:
        add(q)

    for c in candidates:
        add(c)

    for item in backfill:
        if len(out) >= limit:
            break
        add(item)

    if len(out) < 2:
        for item in ONBOARDING_SUGGESTIONS:
            if len(out) >= limit:
                break
            add(item)

    return _trim_suggestions(out, limit)


def _user_payload(
    ctx: CorpusContext,
    titles: Tuple[str, ...],
    queries: Tuple[str, ...],
    limit: int,
) -> str:
    blocks: List[str] = []
    if queries:
        blocks.append(
            "Recent user queries (highest priority — extend or paraphrase 1–2):\n"
            + "\n".join(f"- {q}" for q in queries)
        )
    if ctx.sample_recommended_cases:
        blocks.append(
            "Recommended search phrases from corpus:\n"
            + "\n".join(f"- {c}" for c in ctx.sample_recommended_cases)
        )
    if ctx.top_tags or ctx.sample_captions:
        topic_lines: List[str] = []
        if ctx.top_tags:
            topic_lines.append(f"Tags: {', '.join(ctx.top_tags)}")
        if ctx.sample_captions:
            topic_lines.append("Captions:")
            topic_lines.extend(f"  - {c}" for c in ctx.sample_captions[:6])
        blocks.append("Corpus topics:\n" + "\n".join(topic_lines))
    blocks.append("Corpus context:\n" + context_to_prompt_text(ctx))
    if not queries and titles:
        blocks.append(
            "Recent chat titles (secondary context):\n"
            + "\n".join(f"- {t}" for t in titles)
        )
    blocks.append(
        f"Generate exactly {limit} semantic, topic-based suggestions. "
        "Never use filename-filter phrasing."
    )
    return "\n\n".join(blocks)


def _corpus_heuristic_suggestions(
    ctx: CorpusContext,
    queries: Tuple[str, ...],
    limit: int,
) -> List[str]:
    """Build suggestions from corpus metadata and user history only."""
    candidates: List[str] = []

    for q in queries[:2]:
        candidates.append(q)

    for case in ctx.sample_recommended_cases:
        candidates.append(case)

    for cap in ctx.sample_captions[:4]:
        if len(cap) <= 60:
            candidates.append(cap)
        else:
            candidates.append(cap[:57] + "...")

    for tag in ctx.top_tags[:4]:
        candidates.append(f"{tag} and related visuals")

    return _blend_suggestions(candidates, ctx, queries, limit)


class SuggestionLLM:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None) -> None:
        self.provider = (provider or SETTINGS.llm_provider).lower()
        self.model = model or SETTINGS.llm_model

    def generate(self, user_payload: str) -> str:
        if self.provider == "bedrock":
            return self._bedrock(user_payload)
        if self.provider == "openai":
            return self._openai(user_payload)
        if self.provider == "anthropic":
            return self._anthropic(user_payload)
        raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _bedrock(self, user_payload: str) -> str:
        from imagecb.models.bedrock_client import get_bedrock_runtime

        response = get_bedrock_runtime().converse(
            modelId=self.model,
            system=[{"text": SUGGESTIONS_SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_payload}]}],
            inferenceConfig={"temperature": 0.3, "maxTokens": 400},
        )
        parts = [
            block.get("text", "")
            for block in response["output"]["message"]["content"]
            if "text" in block
        ]
        return "".join(parts) or "{}"

    def _openai(self, user_payload: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=SETTINGS.openai_api_key)
        resp = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SUGGESTIONS_SYSTEM_PROMPT},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.3,
        )
        return resp.choices[0].message.content or "{}"

    def _anthropic(self, user_payload: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=SETTINGS.anthropic_api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=400,
            system=SUGGESTIONS_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_payload}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts) or "{}"


_llm: Optional[SuggestionLLM] = None


def get_suggestion_llm() -> SuggestionLLM:
    global _llm
    if _llm is None:
        _llm = SuggestionLLM()
    return _llm


def _onboarding_list(limit: int) -> List[str]:
    return _trim_suggestions(ONBOARDING_SUGGESTIONS, limit)


def _llm_suggestions(
    ctx: CorpusContext,
    titles: Tuple[str, ...],
    queries: Tuple[str, ...],
    limit: int,
) -> List[str]:
    payload = _user_payload(ctx, titles, queries, limit)
    raw = get_suggestion_llm().generate(payload)
    parsed = _coerce_suggestions_json(raw)
    if len(parsed) < 2:
        return _corpus_heuristic_suggestions(ctx, queries, limit)
    return _blend_suggestions(parsed, ctx, queries, limit)


def generate_suggestions(
    recent_titles: Optional[Sequence[str]] = None,
    *,
    recent_queries: Optional[Sequence[str]] = None,
    user_id: Optional[str] = None,
    limit: Optional[int] = None,
    ctx: Optional[CorpusContext] = None,
) -> SuggestionsResult:
    """Return suggested queries; uses cache keyed by corpus fingerprint + user history."""
    n = limit if limit is not None else SETTINGS.suggestions_limit
    n = max(2, min(8, n))
    titles = normalize_recent_titles(recent_titles or [])
    telemetry = get_recent_user_queries(user_id or "", limit=8)
    queries = merge_recent_queries(recent_queries or [], telemetry, limit=8)
    corpus = ctx if ctx is not None else build_corpus_context()

    if corpus.indexed_count == 0:
        return SuggestionsResult(
            suggestions=_onboarding_list(n),
            cached=False,
        )

    key = _cache_key(corpus, titles, queries)
    now = time.monotonic()
    ttl = SETTINGS.suggestions_cache_ttl_sec
    cached_entry = _cache.get(key)
    if cached_entry is not None:
        ts, items = cached_entry
        if now - ts < ttl and len(items) >= 2:
            return SuggestionsResult(
                suggestions=_trim_suggestions(items, n),
                cached=True,
            )

    try:
        items = _llm_suggestions(corpus, titles, queries, n)
    except Exception:  # noqa: BLE001
        items = _corpus_heuristic_suggestions(corpus, queries, n)

    _cache[key] = (now, items)
    return SuggestionsResult(suggestions=items, cached=False)
