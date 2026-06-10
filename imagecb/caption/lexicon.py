"""Shared search lexicon: bidirectional synonyms, corpus terms, query expansion."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Set, Tuple

from imagecb.config import SETTINGS
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
_UPPER_ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")

_ACRONYM_DENYLIST = frozenset(
    {
        "avg",
        "max",
        "min",
        "msg",
        "nth",
        "qty",
        "std",
        "sys",
        "why",
    }
)

_lexicon_cache: Optional["SearchLexicon"] = None
_acronym_file_cache: Optional["AcronymCache"] = None


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
    """Build synonym groups from seed pairs without cross-linking expansion tokens.

    Each seed entry links its alias to a single-word expansion target and to
    sibling aliases that share the same expansion string. Multi-word expansion
    phrases are not tokenized into a global graph (avoids saas/sdlc pollution).
    """
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

    def alias_key(alias: str) -> str:
        a = (alias or "").strip().lower()
        if " " in a:
            return re.sub(r"\s+", " ", a)
        return normalize_tag(a)

    by_expansion: Dict[str, List[str]] = {}
    for alias, expansion in seed.items():
        key = alias_key(alias)
        exp = (expansion or "").strip().lower()
        if not key or not exp:
            continue
        union(key, key)
        by_expansion.setdefault(exp, []).append(key)
        if " " not in exp:
            target = normalize_tag(exp)
            if target:
                union(key, target)

    for aliases in by_expansion.values():
        for i in range(1, len(aliases)):
            union(aliases[0], aliases[i])

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


def has_acronym_expansion(token: str, lexicon: "SearchLexicon") -> bool:
    """Return True when a static or cached expansion exists for token."""
    return lexicon.expand_acronym_static(token) is not None


def _is_consonant_heavy_acronym(token: str) -> bool:
    """2-6 letter token with no vowels and at least two consonants."""
    t = normalize_tag(token)
    if not t or " " in t:
        return False
    if len(t) < 2 or len(t) > 6:
        return False
    if not _ACRONYM_RE.match(t) or re.search(r"[aeiou]", t):
        return False
    return len(re.findall(r"[bcdfghjklmnpqrstvwxyz]", t)) >= 2


def _uppercase_acronym_in_text(token: str, raw_text: str) -> bool:
    """True when token appears as an all-caps word in the original query."""
    norm = normalize_tag(token)
    if not norm or not raw_text:
        return False
    upper = norm.upper()
    return any(m.group(0) == upper for m in _UPPER_ACRONYM_RE.finditer(raw_text))


def is_llm_acronym_candidate(
    token: str,
    raw_text: str = "",
    *,
    lexicon: Optional["SearchLexicon"] = None,
) -> bool:
    """Stricter gate for LLM acronym expansion (reduces false positives)."""
    norm = normalize_tag(token)
    if not norm:
        return False
    if norm in _ACRONYM_DENYLIST:
        return False
    cache = load_acronym_cache()
    if norm in cache.negative:
        return False
    if lexicon is not None and lexicon.expand_acronym_static(norm):
        return False
    if _uppercase_acronym_in_text(norm, raw_text):
        return True
    return _is_consonant_heavy_acronym(norm)


@dataclass
class AcronymCache:
    expansions: Dict[str, str] = field(default_factory=dict)
    negative: Set[str] = field(default_factory=set)


def load_acronym_cache() -> AcronymCache:
    """Load persistent acronym cache from disk (in-process memoized)."""
    global _acronym_file_cache
    if _acronym_file_cache is not None:
        return _acronym_file_cache

    path = SETTINGS.acronym_cache_path
    if not path.is_file():
        _acronym_file_cache = AcronymCache()
        return _acronym_file_cache

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            _acronym_file_cache = AcronymCache()
            return _acronym_file_cache
        expansions = {
            str(k).lower().strip(): str(v).lower().strip()
            for k, v in (data.get("expansions") or {}).items()
            if str(k).strip() and str(v).strip()
        }
        negative = {str(x).lower().strip() for x in (data.get("negative") or []) if str(x).strip()}
        _acronym_file_cache = AcronymCache(expansions=expansions, negative=negative)
    except (json.JSONDecodeError, OSError):
        _acronym_file_cache = AcronymCache()
    return _acronym_file_cache


def save_acronym_cache(cache: AcronymCache) -> None:
    """Persist acronym cache to disk."""
    global _acronym_file_cache
    path = SETTINGS.acronym_cache_path
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "expansions": dict(sorted(cache.expansions.items())),
        "negative": sorted(cache.negative),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    _acronym_file_cache = cache


def add_acronym_expansion(token: str, expansion: str) -> None:
    """Record a successful LLM acronym expansion."""
    norm = normalize_tag(token)
    phrase = (expansion or "").strip().lower()
    if not norm or not phrase:
        return
    cache = load_acronym_cache()
    cache.expansions[norm] = phrase
    cache.negative.discard(norm)
    save_acronym_cache(cache)


def add_acronym_negative(token: str) -> None:
    """Record a failed LLM acronym lookup to skip future calls."""
    norm = normalize_tag(token)
    if not norm:
        return
    cache = load_acronym_cache()
    cache.negative.add(norm)
    save_acronym_cache(cache)


def reset_acronym_file_cache() -> None:
    """Clear in-process file cache state (for tests)."""
    global _acronym_file_cache
    _acronym_file_cache = None


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
    for key, phrase in load_acronym_cache().expansions.items():
        acronym_exp.setdefault(key, phrase)

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


def _direct_seed_aliases_for_tag(norm: str, lexicon: SearchLexicon) -> List[str]:
    """Alias strings justified by a direct seed entry relationship to `norm`."""
    if not norm:
        return []

    out: List[str] = []
    seen: set[str] = set()

    def add(item: str) -> None:
        item = (item or "").strip().lower()
        if not item or item in seen:
            return
        seen.add(item)
        out.append(item)

    def alias_key(alias: str) -> str:
        a = (alias or "").strip().lower()
        if " " in a:
            return re.sub(r"\s+", " ", a)
        return normalize_tag(a)

    matched_as_key = False
    for alias, exp in lexicon.seed_synonyms.items():
        key = alias_key(alias)
        if norm != key and norm != normalize_tag(alias):
            continue
        matched_as_key = True
        add(f"{key}: {exp}")
        add(exp)
        for other, other_exp in lexicon.seed_synonyms.items():
            if other_exp != exp:
                continue
            other_key = alias_key(other)
            if other_key != norm:
                add(other_key)

    if matched_as_key:
        return out

    for alias, exp in lexicon.seed_synonyms.items():
        if " " in exp.strip():
            continue
        if normalize_tag(exp) != norm:
            continue
        add(alias_key(alias))
        add(exp)

    for alias, exp in lexicon.seed_synonyms.items():
        if norm not in tokenize_text(exp):
            continue
        key = alias_key(alias)
        add(f"{key}: {exp}")
        add(exp)

    return out


def enrich_aliases_for_tags(
    tags: List[str],
    lexicon: SearchLexicon,
    existing_aliases: Optional[List[str]] = None,
    *,
    max_aliases: int = 8,
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
        for item in _direct_seed_aliases_for_tag(norm, lexicon):
            add(item)
        if norm in lexicon.seed_synonyms:
            continue
        expansion = lexicon.expand_acronym_static(norm)
        if expansion:
            add(f"{norm}: {expansion}")
            add(expansion)
        elif is_acronym_like(norm):
            add(norm)

    return out[:max_aliases]


def _tag_variants_for_boilerplate(tags: List[str], lexicon: SearchLexicon) -> Set[str]:
    variants: Set[str] = set()
    for tag in tags:
        norm = normalize_tag(tag)
        if not norm:
            continue
        variants.add(norm)
        for member in lexicon.synonym_group(norm):
            if member in lexicon.corpus_terms:
                variants.add(member)
    return variants


def _is_boilerplate_recommended_case(
    case: str,
    tags: List[str],
    theme: str,
    lexicon: SearchLexicon,
    *,
    asset_type: str = "",
) -> bool:
    case_l = (case or "").strip().lower()
    if not case_l:
        return False
    from imagecb.caption.asset_type import ASSET_TYPE_SET, normalize_asset_type

    asset = normalize_asset_type(asset_type)
    if asset in ASSET_TYPE_SET and case_l == asset:
        return True
    if case_l in ASSET_TYPE_SET:
        return True
    theme_l = (theme or "").strip().lower()
    for v in _tag_variants_for_boilerplate(tags, lexicon):
        if case_l == f"{v} chart" or case_l == f"{v} diagram":
            return True
        if theme_l and v != theme_l and case_l == f"{v} {theme_l}":
            return True
    return False


def enrich_recommended_cases(
    tags: List[str],
    theme: str,
    existing_cases: Optional[List[str]] = None,
    lexicon: Optional[SearchLexicon] = None,
    *,
    asset_type: str = "",
    max_cases: int = 5,
) -> List[str]:
    """Deduplicate and strip auto-generated boilerplate from recommended_cases."""
    if lexicon is None:
        lexicon = build_search_lexicon()

    seen: set[str] = set()
    out: List[str] = []

    def add(item: str) -> None:
        item = (item or "").strip().lower()
        if not item or item in seen:
            return
        if _is_boilerplate_recommended_case(item, tags, theme, lexicon, asset_type=asset_type):
            return
        seen.add(item)
        out.append(item)

    for c in existing_cases or []:
        add(c)

    return out[:max_cases]
