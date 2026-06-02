"""LLM-generated empty-state query suggestions with in-process cache."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from imagecb.config import SETTINGS
from imagecb.suggestions.corpus_summary import (
    CorpusContext,
    build_corpus_context,
    context_to_prompt_text,
)

SUGGESTIONS_SYSTEM_PROMPT = """You suggest starter search queries for an image search app over \
ingested slides, PDFs, and standalone images.

Return ONLY a JSON object:
{"suggestions": ["...", "..."]}

Rules:
- Each suggestion is a short natural-language phrase the user can click to search (under 80 chars).
- Use ONLY filenames, authors, and topics present in the corpus context. Never invent assets.
- Vary styles: semantic description, filter by source file, time-based filter, author filter, \
refinement-style phrasing.
- If recent chat titles are provided, include 1–2 suggestions that extend or paraphrase past searches \
(do not copy titles verbatim unless still useful).
- Do not include markdown, code fences, or explanation outside the JSON object."""

FALLBACK_SUGGESTIONS = [
    "Screenshots of dashboards from Q3_Review.pptx",
    "Charts showing revenue growth",
    "Only images modified this month",
    "Logos on white backgrounds",
]

ONBOARDING_SUGGESTIONS = [
    "Upload slides or PDFs in the Corpus panel, then search here",
    "Charts and diagrams",
    "Screenshots and UI mockups",
    "Logos and icons on plain backgrounds",
]

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


def _cache_key(ctx: CorpusContext, titles: Tuple[str, ...]) -> str:
    title_part = "|".join(t.lower() for t in titles)
    return f"{ctx.fingerprint}|{title_part}"


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


def _user_payload(ctx: CorpusContext, titles: Tuple[str, ...], limit: int) -> str:
    blocks = ["Corpus context:\n" + context_to_prompt_text(ctx)]
    if titles:
        blocks.append("Recent chat titles (most recent first):\n" + "\n".join(f"- {t}" for t in titles))
    blocks.append(f"Generate exactly {limit} suggestions.")
    return "\n\n".join(blocks)


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


def _fallback_list(limit: int, *, empty_index: bool) -> List[str]:
    base = ONBOARDING_SUGGESTIONS if empty_index else FALLBACK_SUGGESTIONS
    return _trim_suggestions(base, limit)


def _llm_suggestions(
    ctx: CorpusContext,
    titles: Tuple[str, ...],
    limit: int,
) -> List[str]:
    payload = _user_payload(ctx, titles, limit)
    raw = get_suggestion_llm().generate(payload)
    parsed = _coerce_suggestions_json(raw)
    if len(parsed) < 2:
        return _fallback_list(limit, empty_index=False)
    return _trim_suggestions(parsed, limit)


def generate_suggestions(
    recent_titles: Optional[Sequence[str]] = None,
    *,
    limit: Optional[int] = None,
    ctx: Optional[CorpusContext] = None,
) -> SuggestionsResult:
    """Return suggested queries; uses cache keyed by corpus fingerprint + titles."""
    n = limit if limit is not None else SETTINGS.suggestions_limit
    n = max(2, min(8, n))
    titles = normalize_recent_titles(recent_titles or [])
    corpus = ctx if ctx is not None else build_corpus_context()

    if corpus.indexed_count == 0:
        return SuggestionsResult(
            suggestions=_fallback_list(n, empty_index=True),
            cached=False,
        )

    key = _cache_key(corpus, titles)
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
        items = _llm_suggestions(corpus, titles, n)
    except Exception:  # noqa: BLE001
        items = _fallback_list(n, empty_index=False)

    _cache[key] = (now, items)
    return SuggestionsResult(suggestions=items, cached=False)
