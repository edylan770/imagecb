"""Query-understanding LLM wrapper.

Parses a natural language turn (plus a short compacted chat history)
into a `QuerySpec` JSON object. The schema is enforced via a strict
JSON instruction; the parsing layer (`retrieval.query_parser`) is
responsible for validating and applying defaults.
"""

from __future__ import annotations

import json
from typing import List, Optional

from imagecb.config import SETTINGS


QUERY_SYSTEM_PROMPT = """You translate a user's natural-language image search request \
into a STRICT JSON search specification. Today's date is provided so you can resolve \
relative times like "last quarter" or "in May". Return ONLY a JSON object with these keys:

{
  "semantic_query": string,                  // short phrase that captures what to retrieve
  "must_have_keywords": [string],            // optional, lowercase
  "must_avoid_keywords": [string],           // optional, lowercase
  "source_filters": {
    "file_types": [string],                  // any of: "pptx", "pdf", "image"
    "filename_contains": [string],           // substrings to require in the source filename
    "authors": [string]                      // author names
  },
  "time_filter": {                           // ISO 8601 dates, omit fields you don't need
    "before": string | null,
    "after": string | null
  },
  "top_k": integer,                          // 1..50, default 10
  "is_refinement": boolean                   // true if the user is refining the previous result set
}

Rules:
- Omit a filter by leaving its list empty or its value null.
- Do not set source_filters (file_types, filename_contains, authors) or time_filter unless the user
  explicitly mentioned them in this turn or they appear in active filters from a prior refinement.
- Treat phrases like "narrow it down", "only the ones with...", "from those" as refinements.
- Never invent filenames or authors that the user did not mention or that aren't visible in history.
- Keep semantic_query close to the user's wording; acronym and synonym expansion happens downstream."""


ACRONYM_SYSTEM_PROMPT = (
    "You expand acronyms and abbreviations for image search. "
    "Return ONLY a JSON object: {\"expansion\": string}. "
    "The expansion should be the full phrase in lowercase. "
    "If you cannot expand the acronym, return {\"expansion\": \"\"}."
)


def _user_payload(
    text: str,
    history_summary: str,
    today_iso: str,
    *,
    previous_spec_json: str = "",
    previous_results_summary: str = "",
) -> str:
    blocks = [f"Today is {today_iso}."]
    blocks.append(
        f"Conversation so far (most recent last):\n{history_summary or '(none)'}"
    )
    if previous_spec_json:
        blocks.append(f"Active filters from the previous search:\n{previous_spec_json}")
    if previous_results_summary:
        blocks.append(
            "Top results from the previous search (for refinement context):\n"
            f"{previous_results_summary}"
        )
    blocks.append(f"New user turn: {text}")
    blocks.append("Return the JSON object now.")
    return "\n\n".join(blocks)


class QueryLLM:
    def __init__(self, provider: Optional[str] = None, model: Optional[str] = None) -> None:
        self.provider = (provider or SETTINGS.llm_provider).lower()
        self.model = model or SETTINGS.llm_model

    def parse(
        self,
        text: str,
        history_summary: str,
        today_iso: str,
        *,
        previous_spec_json: str = "",
        previous_results_summary: str = "",
    ) -> dict:
        kwargs = {
            "previous_spec_json": previous_spec_json,
            "previous_results_summary": previous_results_summary,
        }
        if self.provider == "bedrock":
            raw = self._parse_bedrock(text, history_summary, today_iso, **kwargs)
        elif self.provider == "openai":
            raw = self._parse_openai(text, history_summary, today_iso, **kwargs)
        elif self.provider == "anthropic":
            raw = self._parse_anthropic(text, history_summary, today_iso, **kwargs)
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")
        return _coerce_json(raw)

    def expand_acronym(self, token: str, corpus_vocab: List[str]) -> str:
        """Expand an unrecognized acronym using the query LLM."""
        vocab_block = ", ".join(corpus_vocab[:50]) if corpus_vocab else "(empty)"
        user_text = (
            f"Acronym: {token}\n"
            f"Corpus vocabulary (for context): {vocab_block}\n"
            "Return the JSON object now."
        )
        if self.provider == "bedrock":
            raw = self._expand_acronym_bedrock(user_text)
        elif self.provider == "openai":
            raw = self._expand_acronym_openai(user_text)
        elif self.provider == "anthropic":
            raw = self._expand_acronym_anthropic(user_text)
        else:
            return ""
        data = _coerce_json(raw)
        return str(data.get("expansion") or "").strip().lower()

    def _expand_acronym_bedrock(self, user_text: str) -> str:
        from imagecb.models.bedrock_client import get_bedrock_runtime

        response = get_bedrock_runtime().converse(
            modelId=self.model,
            system=[{"text": ACRONYM_SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_text}]}],
            inferenceConfig={"temperature": 0.0, "maxTokens": 200},
        )
        parts = [
            block.get("text", "")
            for block in response["output"]["message"]["content"]
            if "text" in block
        ]
        return "".join(parts) or "{}"

    def _expand_acronym_openai(self, user_text: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=SETTINGS.openai_api_key)
        resp = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": ACRONYM_SYSTEM_PROMPT},
                {"role": "user", "content": user_text},
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content or "{}"

    def _expand_acronym_anthropic(self, user_text: str) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=SETTINGS.anthropic_api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=200,
            system=ACRONYM_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_text}],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts) or "{}"

    def _parse_bedrock(
        self,
        text: str,
        history: str,
        today: str,
        *,
        previous_spec_json: str = "",
        previous_results_summary: str = "",
    ) -> str:
        from imagecb.models.bedrock_client import get_bedrock_runtime

        response = get_bedrock_runtime().converse(
            modelId=self.model,
            system=[{"text": QUERY_SYSTEM_PROMPT}],
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "text": _user_payload(
                                text,
                                history,
                                today,
                                previous_spec_json=previous_spec_json,
                                previous_results_summary=previous_results_summary,
                            )
                        }
                    ],
                }
            ],
            inferenceConfig={"temperature": 0.0, "maxTokens": 600},
        )
        parts = [
            block.get("text", "")
            for block in response["output"]["message"]["content"]
            if "text" in block
        ]
        return "".join(parts) or "{}"

    def _parse_openai(
        self,
        text: str,
        history: str,
        today: str,
        *,
        previous_spec_json: str = "",
        previous_results_summary: str = "",
    ) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=SETTINGS.openai_api_key)
        resp = client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": QUERY_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": _user_payload(
                        text,
                        history,
                        today,
                        previous_spec_json=previous_spec_json,
                        previous_results_summary=previous_results_summary,
                    ),
                },
            ],
            temperature=0.0,
        )
        return resp.choices[0].message.content or "{}"

    def _parse_anthropic(
        self,
        text: str,
        history: str,
        today: str,
        *,
        previous_spec_json: str = "",
        previous_results_summary: str = "",
    ) -> str:
        import anthropic

        client = anthropic.Anthropic(api_key=SETTINGS.anthropic_api_key)
        msg = client.messages.create(
            model=self.model,
            max_tokens=600,
            system=QUERY_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": _user_payload(
                        text,
                        history,
                        today,
                        previous_spec_json=previous_spec_json,
                        previous_results_summary=previous_results_summary,
                    ),
                }
            ],
        )
        parts = [b.text for b in msg.content if getattr(b, "type", None) == "text"]
        return "".join(parts) or "{}"


def _coerce_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


_llm: Optional[QueryLLM] = None


def get_query_llm() -> QueryLLM:
    global _llm
    if _llm is None:
        _llm = QueryLLM()
    return _llm
