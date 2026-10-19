"""Sparse GCAM dictionary counts and matched-word mean scores."""

from __future__ import annotations

import gzip
import json
import math
import re
import string
from collections import Counter, OrderedDict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

from ..gcam_dictionaries import dictionary_id, resolve_dictionaries
from ..types import StrPath

if TYPE_CHECKING:
    from .themes import ThemeLexicon

from .gcam_tokens import tokenize_gcam, valid_gcam_word, valid_native_pattern
from .tone import tokenize_tone
from .translation import normalize_language


def _key(key, prefix):
    if not isinstance(key, str) or not re.fullmatch(prefix + r"[1-9][0-9]*\.[1-9][0-9]*", key):
        raise ValueError(f"Dimension keys must be {prefix}DictionaryID.DimensionID")


def _order(key):
    return (*map(int, key[1:].split(".")), key[0])


@dataclass(frozen=True)
class GCAMLexicon:
    """Reusable GCAM count dictionaries, weighted scores, and matching options.

    `dimensions` maps count keys to word sets; `weighted_dimensions` maps score
    keys to word weights. Load compiled profiles with `from_json` and select
    dictionaries or languages before analysis.
    """

    name: str
    dimensions: Mapping[str, frozenset[str]]
    weighted_dimensions: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    tokenization: Mapping[str, str] = field(default_factory=dict)
    patterns: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    lemmatization: Mapping[str, str] = field(default_factory=dict)
    exceptions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    theme_dimensions: Mapping[str, str] = field(default_factory=dict)
    theme_lexicon: ThemeLexicon | None = None
    emit_count: Mapping[str, bool] = field(default_factory=dict)
    exclusions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    languages: Mapping[str, str] = field(default_factory=dict)
    _indices: dict = field(init=False, repr=False, compare=False)
    _tries: dict = field(init=False, repr=False, compare=False)
    _wildcards: dict = field(init=False, repr=False, compare=False)
    _wildcard_trie: dict = field(init=False, repr=False, compare=False)
    _lemma_vocabulary: frozenset = field(init=False, repr=False, compare=False)
    _selections: OrderedDict = field(init=False, repr=False, compare=False)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("GCAM lexicon requires a profile name")
        for mapping in (
            self.dimensions,
            self.weighted_dimensions,
            self.tokenization,
            self.patterns,
            self.lemmatization,
            self.exceptions,
            self.theme_dimensions,
            self.emit_count,
            self.exclusions,
            self.languages,
        ):
            if not isinstance(mapping, Mapping):
                raise TypeError("GCAM dimensions and options must be mappings")
        dimensions, patterns = self._normalize_dimensions()
        weighted, modes = self._normalize_scores(dimensions, patterns)
        lemma_modes, exceptions = self._normalize_morphology(dimensions, patterns, weighted)
        self._normalize_languages(dimensions, weighted)
        indices, tries, wildcards, lemma_vocabulary, wildcard_trie = self._build_indices(
            dimensions, patterns, lemma_modes
        )
        object.__setattr__(self, "dimensions", MappingProxyType(dimensions))
        object.__setattr__(self, "weighted_dimensions", MappingProxyType(weighted))
        object.__setattr__(self, "tokenization", MappingProxyType(modes))
        object.__setattr__(
            self,
            "emit_count",
            MappingProxyType({key: self.emit_count.get(key, True) for key in weighted}),
        )
        object.__setattr__(self, "patterns", MappingProxyType(patterns))
        object.__setattr__(self, "lemmatization", MappingProxyType(lemma_modes))
        object.__setattr__(self, "exceptions", MappingProxyType(exceptions))
        object.__setattr__(self, "theme_dimensions", MappingProxyType(dict(self.theme_dimensions)))
        object.__setattr__(self, "_indices", indices)
        object.__setattr__(self, "_tries", tries)
        object.__setattr__(self, "_wildcards", wildcards)
        object.__setattr__(self, "_lemma_vocabulary", lemma_vocabulary)
        object.__setattr__(self, "_wildcard_trie", wildcard_trie)
        object.__setattr__(self, "_selections", OrderedDict())
        exclusions = {}
        for code, terms in self.exclusions.items():
            if not isinstance(code, str) or not re.fullmatch(r"[1-9][0-9]*", code):
                raise ValueError("Exclusions must be keyed by dictionary ID strings")
            if not any(dictionary_id(key) == int(code) for key in dimensions) or any(
                dictionary_id(key) == int(code) for key in (*weighted, *self.theme_dimensions)
            ):
                raise ValueError("Exclusions require a count-only vocabulary dictionary")
            if isinstance(terms, str):
                raise TypeError("Exclusions must be a collection of token patterns")
            terms = tuple(sorted(set(terms)))
            if any(
                not isinstance(term, str)
                or not valid_native_pattern(term)
                or term != term.casefold()
                or not re.search(r"\w", term)
                for term in terms
            ):
                raise ValueError("Exclusions require normalized token or phrase patterns")
            exclusions[code] = terms
        object.__setattr__(self, "exclusions", MappingProxyType(exclusions))

    @property
    def implemented_dimensions(self) -> tuple[str, ...]:
        """All supported serialized keys, including value-only dimensions."""
        return tuple(sorted((*self.dimensions, *self.weighted_dimensions), key=_order))

    def without_dictionaries(self, disabled: Iterable[int | str] = ()) -> GCAMLexicon:
        """Select a lexicon with the requested dictionaries excluded.

        Args:
            disabled: Collection of dictionary names, integer IDs, or numeric strings.

        Returns:
            A reusable selection, or this lexicon if no applicable IDs are excluded.

        Raises:
            TypeError: If selectors have invalid types or form a bare string.
            ValueError: If a dictionary name or ID is unknown.
        """
        present = {dictionary_id(key) for key in self.implemented_dimensions}
        ids = tuple(
            code for code in resolve_dictionaries(disabled, custom_ids=present) if code in present
        )
        if not ids:
            return self
        return self._selection(("dictionaries", *ids), lambda key: dictionary_id(key) not in ids)

    def for_language(self, language: str = "eng") -> GCAMLexicon:
        """Select dimensions for a supported language code, name, or regional tag."""
        language = normalize_language(language)
        if all(value == language for value in self.languages.values()):
            return self
        return self._selection(("language", language), lambda key: self.languages[key] == language)

    def _selection(self, cache_key, predicate):
        if cache_key in self._selections:
            self._selections.move_to_end(cache_key)
            return self._selections[cache_key]

        def keep(mapping):
            return {key: value for key, value in mapping.items() if predicate(key)}

        themes = keep(self.theme_dimensions)
        theme_lexicon = None
        if themes:
            from .themes import ThemeLexicon

            assert self.theme_lexicon is not None
            theme_lexicon = ThemeLexicon(
                self.theme_lexicon.name,
                tuple(
                    rule for rule in self.theme_lexicon.rules if rule.theme in set(themes.values())
                ),
            )
        selection = GCAMLexicon(
            name=self.name,
            dimensions=keep(self.dimensions),
            weighted_dimensions=keep(self.weighted_dimensions),
            tokenization=keep(self.tokenization),
            patterns=keep(self.patterns),
            lemmatization=keep(self.lemmatization),
            exceptions=self.exceptions,
            theme_dimensions=themes,
            theme_lexicon=theme_lexicon,
            emit_count=keep(self.emit_count),
            exclusions={
                code: terms
                for code, terms in self.exclusions.items()
                if any(
                    dictionary_id(key) == int(code) and predicate(key) for key in self.dimensions
                )
            },
            languages=keep(self.languages),
        )
        self._selections[cache_key] = selection
        if len(self._selections) > 8:
            self._selections.popitem(last=False)
        return selection

    def _language(self, key):
        return self.languages.get(
            key, self.languages.get(("v" if key.startswith("c") else "c") + key[1:], "eng")
        )

    def _normalize_languages(self, dimensions, weighted):
        keys = dimensions.keys() | weighted.keys()
        if set(self.languages) - keys:
            raise ValueError("Language metadata requires a supported dimension")
        languages = {key: normalize_language(self._language(key)) for key in keys}
        for key in keys:
            other = ("v" if key.startswith("c") else "c") + key[1:]
            if other in languages and languages[key] != languages[other]:
                raise ValueError("Companion count/value keys must have the same language")
            if languages[key] != "eng" and (
                key in self.lemmatization or key in self.theme_dimensions
            ):
                raise ValueError("WordNet morphology and theme rules require English dimensions")
        object.__setattr__(self, "languages", MappingProxyType(languages))

    def _normalize_dimensions(self):
        dimensions = {}
        for key, words in self.dimensions.items():
            _key(key, "c")
            if isinstance(words, str):
                raise TypeError("Dimension vocabulary must be a collection of tokens")
            values = frozenset(words)
            if any(
                not isinstance(w, str) or tokenize_gcam(w, self._language(key)) != [w]
                for w in values
            ):
                raise ValueError("GCAM words must be normalized single tokens")
            dimensions[key] = values
        patterns = {}
        for key, terms in self.patterns.items():
            _key(key, "c")
            if isinstance(terms, str):
                raise TypeError("Patterns must be a collection")
            terms = tuple(terms)
            if any(
                not isinstance(p, str)
                or not (
                    valid_native_pattern(p)
                    if self._language(key) != "eng"
                    else re.fullmatch(r"[\w'*? -]+", p)
                )
                or p != p.casefold()
                or p != " ".join(p.split())
                or not re.search(r"\w", p)
                for p in terms
            ):
                raise ValueError("Patterns require normalized words, spaces and optional * or ?")
            if dimensions.get(key):
                raise ValueError("Use words or patterns for a count dimension")
            dimensions.setdefault(key, frozenset())
            patterns[key] = tuple(sorted(set(terms), key=lambda p: (-len(p.split()), -len(p), p)))
        return dimensions, patterns

    def _normalize_scores(self, dimensions, patterns):
        if set(self.emit_count) - set(self.weighted_dimensions) or any(
            type(value) is not bool for value in self.emit_count.values()
        ):
            raise ValueError("emit_count requires boolean options for weighted dimensions")
        weighted: dict[str, Mapping[str, float]] = {}
        modes = {}
        for key, scores in self.weighted_dimensions.items():
            _key(key, "v")
            if not isinstance(scores, Mapping):
                raise TypeError("Weighted dimensions must map terms to finite scores")
            mode = self.tokenization.get(key, "words")
            if mode not in ("words", "whitespace"):
                raise ValueError("Weighted tokenization must be words or whitespace")
            scores_by_term: dict[str, float] = {}
            for term, score in scores.items():
                if (
                    not isinstance(term, str)
                    or not term
                    or term != term.casefold()
                    or any(c.isspace() for c in term)
                    or (mode == "words" and not valid_gcam_word(term, self._language(key)))
                ):
                    raise ValueError("Weighted terms must match the selected tokenizer")
                if (
                    isinstance(score, bool)
                    or not isinstance(score, (int, float))
                    or not math.isfinite(score)
                ):
                    raise ValueError("Weighted scores must be finite numbers")
                scores_by_term[term] = float(score)
            count_key = "c" + key[1:]
            if self.emit_count.get(key, True) and (
                dimensions.get(count_key) or count_key in patterns
            ):
                raise ValueError("A weighted score supplies its own companion match count")
            if self.emit_count.get(key, True):
                dimensions.setdefault(count_key, frozenset())
            weighted[key] = MappingProxyType(scores_by_term)
            modes[key] = mode
        if set(self.tokenization) - set(weighted):
            raise ValueError("Tokenization options require a weighted dimension")
        return weighted, modes

    def _normalize_morphology(self, dimensions, patterns, weighted):
        from .themes import ThemeLexicon

        if self.theme_dimensions and not isinstance(self.theme_lexicon, ThemeLexicon):
            raise ValueError("Theme dimensions require an explicit theme lexicon")
        for key, label in self.theme_dimensions.items():
            assert self.theme_lexicon is not None
            _key(key, "c")
            if not isinstance(label, str) or label not in {
                r.theme for r in self.theme_lexicon.rules
            }:
                raise ValueError("Theme dimension requires a supported theme label")
            if (
                dimensions.get(key)
                or key in patterns
                or ("v" + key[1:] in weighted and self.emit_count.get("v" + key[1:], True))
            ):
                raise ValueError("Theme dimensions cannot also contain words, patterns or scores")
            dimensions.setdefault(key, frozenset())
        lemma_modes = dict(self.lemmatization)
        if set(lemma_modes) - set(dimensions) or any(v != "wordnet" for v in lemma_modes.values()):
            raise ValueError("Lemmatization must select wordnet for count dimensions")
        if set(lemma_modes) & (
            set(self.theme_dimensions)
            | {"c" + k[1:] for k in weighted if self.emit_count.get(k, True)}
        ):
            raise ValueError("Themes and weighted counts cannot select lemmatization")
        exceptions = {}
        for token, lemmas in self.exceptions.items():
            if tokenize_tone(token) != [token] or isinstance(lemmas, str):
                raise ValueError("Morphology exceptions require normalized tokens and lemma lists")
            lemmas = tuple(lemmas)
            if not lemmas or any(tokenize_tone(w) != [w] for w in lemmas):
                raise ValueError("Morphology exception lemmas must be normalized tokens")
            exceptions[token] = lemmas
        return lemma_modes, exceptions

    def _build_indices(self, dimensions, patterns, lemma_modes):
        indices: dict[str, dict[str, set[str]]] = {"words": {}, "wordnet": {}}
        tries: dict[str, dict[str | None, Any]] = {"words": {}, "wordnet": {}}
        wildcards = {}
        lemma_vocabulary = set()
        for key, words in dimensions.items():
            mode = lemma_modes.get(key, "words")
            for word in words:
                indices[mode].setdefault(word, set()).add(key)
                if mode == "wordnet":
                    lemma_vocabulary.add(word)
        for key, terms in patterns.items():
            mode = lemma_modes.get(key, "words")
            if any("*" in term or "?" in term for term in terms):
                if mode == "wordnet":
                    raise ValueError("Lemmatized patterns must be literal phrases")
                wildcards[key] = terms
                continue
            for term in terms:
                node = tries[mode]
                for token in term.split():
                    node = node.setdefault(token, {})
                    if mode == "wordnet":
                        lemma_vocabulary.add(token)
                node.setdefault(None, set()).add(key)
        wildcard_trie: dict[str | None, Any] = {}
        for key, terms in wildcards.items():
            for rank, term in enumerate(terms):
                node = wildcard_trie
                for token in term.split():
                    node = node.setdefault(token, {})
                node.setdefault(None, {})[key] = rank
        return (
            indices,
            tries,
            wildcards,
            frozenset(lemma_vocabulary),
            _compile_wildcard_trie(wildcard_trie),
        )

    @classmethod
    def from_json(cls, path: str | Path) -> GCAMLexicon:
        """Load a compiled GCAM profile from JSON or gzip-compressed JSON."""
        return _load(read_gcam_json(path))


def read_gcam_json(path):
    path = Path(path)
    raw = path.read_bytes()
    if path.name.endswith(".gz"):
        raw = gzip.decompress(raw)
    return json.loads(raw.decode("utf-8"))


def _load(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("dimensions"), list):
        raise ValueError("GCAM JSON requires a dimensions array")
    dimensions, weighted, modes, patterns, seen = {}, {}, {}, {}, set()
    lemmatization, theme_dimensions, emit_count, languages = {}, {}, {}, {}
    for dimension in payload["dimensions"]:
        if not isinstance(dimension, dict) or "key" not in dimension:
            raise ValueError("GCAM dimensions require a key")
        key = dimension["key"]
        if not isinstance(key, str) or key in seen:
            raise ValueError("Invalid or duplicate GCAM dimension key")
        seen.add(key)
        if "language" in dimension:
            languages[key] = dimension["language"]
        forms = set(dimension) & {"words", "scores", "patterns", "theme"}
        if len(forms) != 1:
            raise ValueError("A dimension requires exactly one of words, scores or patterns")
        if "scores" not in forms and {"tokenization", "emit_count"} & dimension.keys():
            raise ValueError("Tokenization and emit_count are options for weighted dimensions only")
        if "scores" in forms:
            weighted[key] = dimension["scores"]
            modes[key] = dimension.get("tokenization", "words")
            emit_count[key] = dimension.get("emit_count", True)
        elif "theme" in forms:
            theme_dimensions[key] = dimension["theme"]
        else:
            form = next(iter(forms))
            if not isinstance(dimension[form], list):
                raise ValueError("Words and patterns must be arrays")
            if form == "words":
                dimensions[key] = frozenset(dimension[form])
            else:
                patterns[key] = tuple(dimension[form])
        if "lemmatization" in dimension:
            lemmatization[key] = dimension["lemmatization"]
    theme_lexicon = None
    if theme_dimensions:
        from .themes import ThemeLexicon, ThemeRule

        theme_lexicon = ThemeLexicon(
            payload["name"] + "-themes", tuple(ThemeRule(**r) for r in payload["theme_rules"])
        )
    return GCAMLexicon(
        payload["name"],
        dimensions,
        weighted,
        modes,
        patterns,
        lemmatization,
        payload.get("exceptions", {}),
        theme_dimensions,
        theme_lexicon,
        emit_count,
        payload.get("exclusions", {}),
        languages,
    )


def default_gcam_lexicon(resources_dir: StrPath | None = None) -> GCAMLexicon:
    from ..utils import ResourceStore

    return _cached_gcam_lexicon(ResourceStore(resources_dir).profile("gcam"))


@lru_cache(maxsize=8)
def _cached_gcam_lexicon(path):
    return GCAMLexicon.from_json(path)


@dataclass(frozen=True)
class GCAMResult:
    """GCAM counts and weighted scores with the profile's supported dimensions.

    Attributes:
        word_count: English input token count.
        counts: Count-dimension matches, including supported zero counts.
        implemented_dimensions: Keys computed by the selected lexicon.
        lexicon_name: Profile identity.
        values: Weighted means for dimensions with matched words.
        native_word_count: Original-language token count when native text is supplied.
    """

    word_count: int
    counts: Mapping[str, int]
    implemented_dimensions: tuple[str, ...]
    lexicon_name: str
    values: Mapping[str, float] = field(default_factory=dict)
    native_word_count: int | None = None

    def to_gkg(self):
        """Serialize word counts and sparse dimension values in GCAM key order.

        Zero counts are omitted. Matched weighted means of zero are retained.
        """
        entries = [f"wc:{self.word_count}"]
        if self.native_word_count is not None:
            entries.append(f"nwc:{self.native_word_count}")
        for key in self.implemented_dimensions:
            if key in self.counts and self.counts[key]:
                entries.append(f"{key}:{self.counts[key]}")
            elif key in self.values:
                entries.append(f"{key}:{self.values[key]:.15g}")
        return ",".join(entries)


@lru_cache(maxsize=64)
def _pattern_regex(patterns):
    alternatives = []
    for pattern in patterns:
        alternatives.append(re.escape(pattern).replace(r"\*", r"\S*").replace(r"\?", r"\S"))
    return re.compile(r"(?<!\S)(?:" + "|".join(alternatives) + r")(?!\S)")


@lru_cache(maxsize=16)
def _exclusion_trie(patterns):
    trie: dict = {}
    for pattern in patterns:
        node = trie
        for token in pattern.split():
            node = node.setdefault(token, {})
        node[None] = {"exclude": 0}
    return _compile_wildcard_trie(trie)


def _mask_exclusions(tokens, patterns):
    trie = _exclusion_trie(patterns)
    masked = list(tokens)
    for start in range(len(tokens)):
        nodes = [trie]
        for end in range(start, len(tokens)):
            nodes = _wildcard_children(nodes, tokens[end])
            if not nodes:
                break
            if any(node["output"] for node in nodes):
                masked[start : end + 1] = [None] * (end + 1 - start)
    return masked


def _compile_wildcard_trie(node):
    literal = {}
    wild: dict[str, list[tuple[str | re.Pattern[str], Any]]] = {}
    for token, child in node.items():
        if token is None:
            continue
        child = _compile_wildcard_trie(child)
        if "*" not in token and "?" not in token:
            literal[token] = child
        else:
            prefix = re.split(r"[*?]", token, maxsplit=1)[0][:2]
            matcher = (
                token[:-1]
                if token.endswith("*") and token.count("*") == 1 and "?" not in token
                else re.compile(re.escape(token).replace(r"\*", r"\S*").replace(r"\?", r"\S"))
            )
            wild.setdefault(prefix, []).append((matcher, child))
    return {"literal": literal, "wild": wild, "output": node.get(None, {})}


def _wildcard_counts(tokens, trie):
    counts: Counter[str] = Counter()
    ends: dict[str, int] = {}
    for start in range(len(tokens)):
        nodes = [trie]
        matches: dict[str, tuple[int, int]] = {}
        for end in range(start, len(tokens)):
            if tokens[end] is None:
                break
            token, next_nodes = tokens[end], []
            next_nodes = _wildcard_children(nodes, token)
            nodes = next_nodes
            if not nodes:
                break
            for node in nodes:
                for key, rank in node["output"].items():
                    if key not in matches or rank < matches[key][0]:
                        matches[key] = rank, end + 1
        for key, (_, end) in matches.items():
            if start >= ends.get(key, 0):
                counts[key] += 1
                ends[key] = end
    return counts


# WordNet's documented one-pass detachment rules. Candidate senses are unioned;
# this performs no contextual disambiguation or POS tagging.
_SUFFIXES = (
    ("s", ""),
    ("ses", "s"),
    ("ves", "f"),
    ("xes", "x"),
    ("zes", "z"),
    ("ches", "ch"),
    ("shes", "sh"),
    ("men", "man"),
    ("ies", "y"),
    ("ies", "y"),
    ("es", "e"),
    ("es", ""),
    ("ed", "e"),
    ("ed", ""),
    ("ing", "e"),
    ("ing", ""),
    ("er", ""),
    ("est", ""),
    ("er", "e"),
    ("est", "e"),
)


def _lemma_candidates(token, lexicon):
    candidates = {token}
    if token in lexicon.exceptions:
        candidates.update(lexicon.exceptions[token])
    else:
        candidates.update(
            token[: -len(suffix)] + replacement
            for suffix, replacement in _SUFFIXES
            if token.endswith(suffix)
        )
    return {w for w in candidates if w in lexicon._lemma_vocabulary}


def _literal_counts(candidates, trie):
    counts: Counter[str] = Counter()
    ends: dict[str, int] = {}
    for start in range(len(candidates)):
        nodes, matches = [trie], {}
        for end in range(start, len(candidates)):
            nodes = [node[token] for node in nodes for token in candidates[end] if token in node]
            if not nodes:
                break
            for node in nodes:
                for key in node.get(None, ()):
                    matches[key] = end + 1
        for key, end in matches.items():
            if start >= ends.get(key, 0):
                counts[key] += 1
                ends[key] = end
    return counts


def analyze_gcam(
    text: str,
    *,
    lexicon: GCAMLexicon | None = None,
    disabled_dictionaries: Iterable[int | str] = (),
    original_text: str | None = None,
    original_language: str | None = None,
) -> GCAMResult:
    """Compute dictionary match counts and matched-word weighted means.

    Original-language text is scored with dimensions for that language.

    Args:
        text: Prepared English body.
        lexicon: Reusable GCAM profile. Defaults to the configured local profile.
        disabled_dictionaries: Dictionary names or IDs to exclude before matching.
        original_text: Optional body before English translation.
        original_language: Non-English language of `original_text`; supply both together.

    Returns:
        Counts, weighted means, and supported dimension keys. Unmatched weighted
        means are omitted.

    Raises:
        TypeError: If text, lexicon, or dictionary selectors have invalid types.
        ValueError: If dictionary selectors or the original-language inputs are invalid.
        ResourceUnavailableError: If the default local profile is unavailable.
    """
    if (original_text is None) != (original_language is None):
        raise ValueError("Supply original_text and original_language together")
    native_language = (
        normalize_language(original_language) if original_language is not None else None
    )
    if native_language == "eng":
        raise ValueError("Original GCAM text must have a non-English language")
    lexicon = default_gcam_lexicon() if lexicon is None else lexicon
    if not isinstance(lexicon, GCAMLexicon):
        raise TypeError("lexicon must be GCAMLexicon")
    lexicon = lexicon.without_dictionaries(disabled_dictionaries)
    result = _analyze_language(text, lexicon.for_language("eng"), "eng")
    if original_text is None:
        return result
    assert native_language is not None
    native = _analyze_language(
        original_text, lexicon.for_language(native_language), native_language
    )
    return GCAMResult(
        result.word_count,
        MappingProxyType({**result.counts, **native.counts}),
        tuple(sorted((*result.implemented_dimensions, *native.implemented_dimensions), key=_order)),
        result.lexicon_name,
        MappingProxyType({**result.values, **native.values}),
        native.word_count,
    )


def _analyze_language(text, lexicon, language):
    tokens = tokenize_gcam(text, language)
    if not lexicon.exclusions:
        return _analyze_tokens(text, tokens, lexicon)
    result = _analyze_tokens(
        text, tokens, lexicon.without_dictionaries(map(int, lexicon.exclusions))
    )
    counts, values = dict(result.counts), dict(result.values)
    present = {dictionary_id(key) for key in lexicon.implemented_dimensions}
    for code, patterns in lexicon.exclusions.items():
        selection = lexicon.without_dictionaries(present - {int(code)})
        masked = _mask_exclusions(tokens, patterns)
        part = _analyze_tokens(text, masked, selection)
        counts.update(part.counts)
        values.update(part.values)
    return GCAMResult(
        len(tokens),
        MappingProxyType(counts),
        lexicon.implemented_dimensions,
        lexicon.name,
        MappingProxyType(values),
    )


def _analyze_tokens(text, tokens, lexicon):
    frequencies = Counter(tokens)
    frequencies.pop(None, None)
    counts = dict.fromkeys(lexicon.dimensions, 0)
    lemma_tokens = None
    for token, frequency in frequencies.items():
        for key in lexicon._indices["words"].get(token, ()):
            counts[key] += frequency
    if lexicon.lemmatization:
        candidates = {token: _lemma_candidates(token, lexicon) for token in frequencies}
        lemma_tokens = [candidates[token] if token is not None else set() for token in tokens]
        for token, frequency in frequencies.items():
            lemma_keys = {
                key for w in candidates[token] for key in lexicon._indices["wordnet"].get(w, ())
            }
            for key in lemma_keys:
                counts[key] += frequency
    for mode, trie in lexicon._tries.items():
        if trie:
            stream = (
                [set() if token is None else {token} for token in tokens]
                if mode == "words"
                else lemma_tokens
            )
            counts.update(_literal_counts(stream, trie))
    if lexicon._wildcards:
        counts.update(_wildcard_counts(tokens, lexicon._wildcard_trie))
    if lexicon.theme_dimensions:
        from .themes import analyze_themes

        mentions = analyze_themes(text, lexicon=lexicon.theme_lexicon).mentions
        frequencies_by_theme = Counter(
            label for label, _, _ in {(m.theme, m.start, m.end) for m in mentions}
        )
        for key, label in lexicon.theme_dimensions.items():
            counts[key] = frequencies_by_theme[label]
    values = _weighted_values(text, lexicon, frequencies, counts)
    keys = tuple(sorted((*counts, *lexicon.weighted_dimensions), key=_order))
    return GCAMResult(
        len(tokens), MappingProxyType(counts), keys, lexicon.name, MappingProxyType(values)
    )


def _wildcard_children(nodes, token):
    next_nodes = []
    for node in nodes:
        if token in node["literal"]:
            next_nodes.append(node["literal"][token])
        # Deduplicate prefixes for one-character tokens.
        for prefix in {token[:2], token[:1], ""}:  # pylint: disable=use-sequence-for-iteration
            for matcher, child in node["wild"].get(prefix, ()):
                hit = (
                    token.startswith(matcher)
                    if isinstance(matcher, str)
                    else matcher.fullmatch(token)
                )
                if hit:
                    next_nodes.append(child)
    return next_nodes


def _weighted_values(text, lexicon, frequencies, counts):
    values = {}
    for key, scores in lexicon.weighted_dimensions.items():
        if lexicon.tokenization[key] == "words":
            matches = [
                (scores[token], count) for token, count in frequencies.items() if token in scores
            ]
        else:
            # Preserve standalone emoticons; strip surrounding ASCII punctuation
            # only if the entire whitespace token is absent from the dictionary.
            weighted_tokens: Counter[str] = Counter()
            for token in text.casefold().split():
                candidate = token if token in scores else token.strip(string.punctuation)
                if candidate in scores:
                    weighted_tokens[candidate] += 1
            matches = [(scores[token], count) for token, count in weighted_tokens.items()]
        count = sum(n for _, n in matches)
        if lexicon.emit_count[key]:
            counts["c" + key[1:]] = count
        if count:
            values[key] = math.fsum(score * (n / count) for score, n in matches)
    return values
