"""Shared search lexicon: bidirectional synonyms, corpus terms, query expansion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from imagecb.storage.metadata_db import deserialize_list, get_all_records

_SYNONYM_PATH = Path(__file__).with_name("tag_synonyms.json")

_PLURAL_EXCEPTIONS = frozenset(
    {
        "news",
        "series",
        "status",
        "business",
        "graphics",
        "analytics",
        "sales",
        "process",
    }
)


def normalize_tag(term: str) -> str:
    t = (term or "").strip().lower()
    t = re.sub(r"\s+", " ", t)
    if not t:
        return ""
    if t.endswith("ies") and len(t) > 4:
        candidate = t[:-3] + "y"
        if candidate not in _PLURAL_EXCEPTIONS:
            t = candidate
    elif t.endswith("s") and len(t) > 3 and not t.endswith("ss") and t not in _PLURAL_EXCEPTIONS:
        t = t[:-1]
    return t
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_ACRONYM_RE = re.compile(r"^[a-z]{2,6}$")

_lexicon_cache: Optional["SearchLexicon"] = None


def load_seed_synonyms() -> Dict[str, str]:
    """Load alias→expansion map from tag_synonyms.json."""
    if not _SYNONYM_PATH.is_file():
        return {}
    try:
        with open(_SYNONYM_PATH, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return {str(k).lower().strip(): str(v).lower().strip() for k, v in data.items()}
    except (json.JSONDecodeError, OSError):
        return {}


def _build_synonym_groups(seed: Dict[str, str]) -> Dict[str, FrozenSet[str]]:
    """Build bidirectional equivalence groups from seed alias map."""
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for alias, expansion in seed.items():
        alias_n = normalize_tag(alias)
        if not alias_n:
            continue
        union(alias_n, alias_n)
        for token in tokenize_text(expansion):
            union(alias_n, token)
        exp_norm = normalize_tag(expansion)
        if exp_norm and " " not in exp_norm:
            union(alias_n, exp_norm)

    groups: Dict[str, Set[str]] = {}
    for term in parent:
        root = find(term)
        groups.setdefault(root, set()).add(term)

    return {root: frozenset(members) for root, members in groups.items()}


def tokenize_text(text: str) -> List[str]:
    """Lowercase alphanumeric tokens from free text."""
    return _TOKEN_RE.findall((text or "").lower())


def is_acronym_like(token: str) -> bool:
    """Heuristic: short token with no vowels, or present in seed keys."""
    t = normalize_tag(token)
    if not t or " " in t:
        return False
    if t in load_seed_synonyms():
        return True
    if len(t) < 2 or len(t) > 6:
        return False
    return bool(_ACRONYM_RE.match(t) and not re.search(r"[aeiou]", t))


@dataclass
class SearchLexicon:
    corpus_terms: FrozenSet[str] = field(default_factory=frozenset)
    seed_synonyms: Dict[str, str] = field(default_factory=dict)
    synonym_groups: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    acronym_expansions: Dict[str, str] = field(default_factory=dict)
    term_to_group: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    def synonym_group(self, term: str) -> Set[str]:
        """Return all terms in the same synonym group as term (including itself)."""
        norm = normalize_tag(term)
        if not norm:
            return set()
        if norm in self.term_to_group:
            return set(self.term_to_group[norm])
        return {norm}

    def expand_acronym_static(self, token: str) -> Optional[str]:
        """Return static expansion for acronym token, or None."""
        norm = normalize_tag(token)
        if not norm:
            return None
        if norm in self.acronym_expansions:
            return self.acronym_expansions[norm]
        if norm in self.seed_synonyms:
            return self.seed_synonyms[norm]
        return None

    def corpus_matches(self, terms: Set[str]) -> Set[str]:
        """Return terms that appear in the corpus lexicon."""
        return {t for t in terms if t in self.corpus_terms}


def _collect_corpus_terms(records) -> Set[str]:
    terms: Set[str] = set()
    for r in records:
        for tag in deserialize_list(r.tags_json):
            norm = normalize_tag(tag)
            if norm:
                terms.add(norm)
        for alias in deserialize_list(r.search_aliases_json):
            for tok in tokenize_text(alias):
                norm = normalize_tag(tok)
                if norm:
                    terms.add(norm)
            norm = normalize_tag(alias)
            if norm and " " not in norm:
                terms.add(norm)
        for case in deserialize_list(r.recommended_cases_json):
            for tok in tokenize_text(case):
                norm = normalize_tag(tok)
                if norm:
                    terms.add(norm)
    return terms


def _build_acronym_expansions(
    seed: Dict[str, str],
    records,
) -> Dict[str, str]:
    """Merge seed acronyms with corpus alias patterns like 'sdlc: software development life cycle'."""
    expansions = dict(seed)
    for r in records:
        for alias in deserialize_list(r.search_aliases_json):
            alias = (alias or "").strip().lower()
            if not alias:
                continue
            if ":" in alias:
                left, _, right = alias.partition(":")
                key = normalize_tag(left.strip())
                val = right.strip()
                if key and val and is_acronym_like(key):
                    expansions.setdefault(key, val)
            elif is_acronym_like(alias.split()[0] if alias.split() else ""):
                parts = alias.split(None, 1)
                if len(parts) == 2 and len(parts[0]) <= 6:
                    key = normalize_tag(parts[0])
                    if key:
                        expansions.setdefault(key, parts[1])
    return expansions


def build_search_lexicon(*, refresh: bool = False) -> SearchLexicon:
    global _lexicon_cache
    if _lexicon_cache is not None and not refresh:
        return _lexicon_cache

    seed = load_seed_synonyms()
    records = get_all_records()
    corpus = frozenset(_collect_corpus_terms(records))
    groups = _build_synonym_groups(seed)
    acronym_exp = _build_acronym_expansions(seed, records)

    term_to_group: Dict[str, FrozenSet[str]] = {}
    for group in groups.values():
        for member in group:
            term_to_group[member] = group

    _lexicon_cache = SearchLexicon(
        corpus_terms=corpus,
        seed_synonyms=seed,
        synonym_groups=groups,
        acronym_expansions=acronym_exp,
        term_to_group=term_to_group,
    )
    return _lexicon_cache


def refresh_lexicon_cache() -> SearchLexicon:
    """Invalidate and rebuild the in-process lexicon cache."""
    global _lexicon_cache
    _lexicon_cache = None
    return build_search_lexicon(refresh=True)


@dataclass
class ExpandedQuery:
    original: str
    tokens: List[str] = field(default_factory=list)
    acronym_expansions: Dict[str, str] = field(default_factory=dict)
    synonym_matches: Dict[str, List[str]] = field(default_factory=dict)
    expanded_terms: List[str] = field(default_factory=list)

    @property
    def all_terms(self) -> List[str]:
        seen: set[str] = set()
        out: List[str] = []
        for t in self.expanded_terms:
            if t not in seen:
                seen.add(t)
                out.append(t)
        return out


def expand_term(term: str, lexicon: SearchLexicon) -> Set[str]:
    """Expand a single token: acronym → synonym group → corpus intersection."""
    norm = normalize_tag(term)
    if not norm:
        return set()

    results: Set[str] = set()
    phrase_tokens: List[str] = []

    expansion = lexicon.expand_acronym_static(norm)
    if expansion:
        phrase_tokens = tokenize_text(expansion)

    group = lexicon.synonym_group(norm)
    results.update(group)

    for pt in phrase_tokens:
        results.update(lexicon.synonym_group(pt))
        results.add(pt)

    corpus_hits = lexicon.corpus_matches(results)
    return corpus_hits if corpus_hits else set()


def expand_text(text: str, lexicon: SearchLexicon) -> ExpandedQuery:
    """Expand free text through acronym, synonym, and corpus matching."""
    original = (text or "").strip()
    tokens = tokenize_text(original)
    result = ExpandedQuery(original=original, tokens=tokens)

    seen_expansions: set[str] = set()
    for token in tokens:
        norm = normalize_tag(token)
        if not norm:
            continue

        expansion = lexicon.expand_acronym_static(norm)
        if expansion and norm not in result.acronym_expansions:
            result.acronym_expansions[norm] = expansion

        matched = expand_term(token, lexicon)
        if matched:
            result.synonym_matches[norm] = sorted(matched)
            for m in matched:
                if m not in seen_expansions and m != norm:
                    seen_expansions.add(m)
                    result.expanded_terms.append(m)

        if expansion:
            for pt in tokenize_text(expansion):
                pt_matched = expand_term(pt, lexicon)
                for m in pt_matched:
                    if m not in seen_expansions:
                        seen_expansions.add(m)
                        result.expanded_terms.append(m)

    return result


def enrich_aliases_for_tags(
    tags: List[str],
    lexicon: SearchLexicon,
    existing_aliases: Optional[List[str]] = None,
    *,
    max_aliases: int = 15,
) -> List[str]:
    """Add corpus-aligned synonym and acronym variants for tags."""
    seen: set[str] = set()
    out: List[str] = []

    def add(item: str) -> None:
        item = (item or "").strip().lower()
        if not item or item in seen:
            return
        seen.add(item)
        out.append(item)

    for a in existing_aliases or []:
        add(a)

    for tag in tags:
        norm = normalize_tag(tag)
        if not norm:
            continue
        for member in lexicon.synonym_group(norm):
            if member != norm and member in lexicon.corpus_terms:
                add(member)
        expansion = lexicon.expand_acronym_static(norm)
        if expansion:
            add(f"{norm}: {expansion}")
            add(expansion)
        elif is_acronym_like(norm):
            add(norm)

    return out[:max_aliases]


def enrich_recommended_cases(
    tags: List[str],
    theme: str,
    existing_cases: Optional[List[str]] = None,
    lexicon: Optional[SearchLexicon] = None,
    *,
    max_cases: int = 8,
) -> List[str]:
    """Generate additional searcher-style queries from synonym variants."""
    if lexicon is None:
        lexicon = build_search_lexicon()

    seen: set[str] = set()
    out: List[str] = []

    def add(item: str) -> None:
        item = (item or "").strip().lower()
        if not item or item in seen:
            return
        seen.add(item)
        out.append(item)

    for c in existing_cases or []:
        add(c)

    theme_l = (theme or "").strip().lower()
    for tag in tags:
        norm = normalize_tag(tag)
        if not norm:
            continue
        variants = {norm}
        for member in lexicon.synonym_group(norm):
            if member in lexicon.corpus_terms:
                variants.add(member)
        for v in variants:
            if theme_l and v != theme_l:
                add(f"{v} {theme_l}")
            add(f"{v} chart")
            add(f"{v} diagram")

    return out[:max_cases]
