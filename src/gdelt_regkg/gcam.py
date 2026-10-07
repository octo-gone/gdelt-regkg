"""Sparse GCAM dictionary counts and matched-word mean scores."""

from __future__ import annotations

import gzip
import json
import math
import re
import string
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .themes import ThemeLexicon

from .tone import tokenize_tone
from .utils import read_resource_json, resource_path


def _key(key, prefix):
    if not isinstance(key, str) or not re.fullmatch(prefix + r"[1-9][0-9]*\.[1-9][0-9]*", key):
        raise ValueError(f"Dimension keys must be {prefix}DictionaryID.DimensionID")


def _order(key):
    return (*map(int, key[1:].split(".")), key[0])


@dataclass(frozen=True)
class GCAMLexicon:
    name: str
    dimensions: Mapping[str, frozenset[str]]
    weighted_dimensions: Mapping[str, Mapping[str, float]] = field(default_factory=dict)
    tokenization: Mapping[str, str] = field(default_factory=dict)
    patterns: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    lemmatization: Mapping[str, str] = field(default_factory=dict)
    exceptions: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    theme_dimensions: Mapping[str, str] = field(default_factory=dict)
    theme_lexicon: ThemeLexicon | None = None
    _indices: dict = field(init=False, repr=False, compare=False)
    _tries: dict = field(init=False, repr=False, compare=False)
    _wildcards: dict = field(init=False, repr=False, compare=False)
    _wildcard_trie: dict = field(init=False, repr=False, compare=False)
    _lemma_vocabulary: frozenset = field(init=False, repr=False, compare=False)

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
        ):
            if not isinstance(mapping, Mapping):
                raise TypeError("GCAM dimensions and options must be mappings")
        dimensions = {}
        for key, words in self.dimensions.items():
            _key(key, "c")
            if isinstance(words, str):
                raise TypeError("Dimension vocabulary must be a collection of tokens")
            values = frozenset(words)
            if any(not isinstance(w, str) or tokenize_tone(w) != [w] for w in values):
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
                or not re.fullmatch(r"[\w'*? -]+", p)
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
                    or (mode == "words" and tokenize_tone(term) != [term])
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
            if dimensions.get(count_key) or count_key in patterns:
                raise ValueError("A weighted score supplies its own companion match count")
            dimensions.setdefault(count_key, frozenset())
            weighted[key] = MappingProxyType(scores_by_term)
            modes[key] = mode
        if set(self.tokenization) - set(weighted):
            raise ValueError("Tokenization options require a weighted dimension")
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
            if dimensions.get(key) or key in patterns or "v" + key[1:] in weighted:
                raise ValueError("Theme dimensions cannot also contain words, patterns or scores")
            dimensions.setdefault(key, frozenset())
        lemma_modes = dict(self.lemmatization)
        if set(lemma_modes) - set(dimensions) or any(v != "wordnet" for v in lemma_modes.values()):
            raise ValueError("Lemmatization must select wordnet for count dimensions")
        if set(lemma_modes) & (set(self.theme_dimensions) | {"c" + k[1:] for k in weighted}):
            raise ValueError("Themes and weighted counts cannot select lemmatization")
        exceptions = {}
        for token, lemmas in self.exceptions.items():
            if tokenize_tone(token) != [token] or isinstance(lemmas, str):
                raise ValueError("Morphology exceptions require normalized tokens and lemma lists")
            lemmas = tuple(lemmas)
            if not lemmas or any(tokenize_tone(w) != [w] for w in lemmas):
                raise ValueError("Morphology exception lemmas must be normalized tokens")
            exceptions[token] = lemmas
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
        object.__setattr__(self, "dimensions", MappingProxyType(dimensions))
        object.__setattr__(self, "weighted_dimensions", MappingProxyType(weighted))
        object.__setattr__(self, "tokenization", MappingProxyType(modes))
        object.__setattr__(self, "patterns", MappingProxyType(patterns))
        object.__setattr__(self, "lemmatization", MappingProxyType(lemma_modes))
        object.__setattr__(self, "exceptions", MappingProxyType(exceptions))
        object.__setattr__(self, "theme_dimensions", MappingProxyType(dict(self.theme_dimensions)))
        object.__setattr__(self, "_indices", indices)
        object.__setattr__(self, "_tries", tries)
        object.__setattr__(self, "_wildcards", wildcards)
        wildcard_trie: dict[str | None, Any] = {}
        for key, terms in wildcards.items():
            for rank, term in enumerate(terms):
                node = wildcard_trie
                for token in term.split():
                    node = node.setdefault(token, {})
                node.setdefault(None, {})[key] = rank
        object.__setattr__(self, "_wildcard_trie", _compile_wildcard_trie(wildcard_trie))
        object.__setattr__(self, "_lemma_vocabulary", frozenset(lemma_vocabulary))

    @classmethod
    def from_json(cls, path):
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
    lemmatization, theme_dimensions = {}, {}
    for dimension in payload["dimensions"]:
        if not isinstance(dimension, dict) or "key" not in dimension:
            raise ValueError("GCAM dimensions require a key")
        key = dimension["key"]
        if not isinstance(key, str) or key in seen:
            raise ValueError("Invalid or duplicate GCAM dimension key")
        seen.add(key)
        forms = set(dimension) & {"words", "scores", "patterns", "theme"}
        if len(forms) != 1:
            raise ValueError("A dimension requires exactly one of words, scores or patterns")
        if "scores" in forms:
            weighted[key] = dimension["scores"]
            modes[key] = dimension.get("tokenization", "words")
        elif "theme" in forms:
            if "tokenization" in dimension:
                raise ValueError("Tokenization is an option for weighted dimensions only")
            theme_dimensions[key] = dimension["theme"]
        else:
            if "tokenization" in dimension:
                raise ValueError("Tokenization is an option for weighted dimensions only")
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
    )


def default_gcam_lexicon(resources_dir=None):
    return _cached_gcam_lexicon(
        resource_path(
            "lexicons",
            read_resource_json("defaults.json", resources_dir=resources_dir)["gcam"],
            resources_dir=resources_dir,
        )
    )


@lru_cache(maxsize=8)
def _cached_gcam_lexicon(path):
    return GCAMLexicon.from_json(path)


@dataclass(frozen=True)
class GCAMResult:
    word_count: int
    counts: Mapping[str, int]
    implemented_dimensions: tuple[str, ...]
    lexicon_name: str
    values: Mapping[str, float] = field(default_factory=dict)

    def to_gkg(self):
        entries = [f"wc:{self.word_count}"]
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
            token, next_nodes = tokens[end], []
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


def analyze_gcam(text: str, *, lexicon: GCAMLexicon | None = None) -> GCAMResult:
    """Counts and means of matched occurrences, without VADER sentence heuristics.

    A supported zero-match count is sparse; its mean is undefined and omitted.
    A matched mean of zero is retained. Unsupported dimensions are uncomputed.
    """
    tokens = tokenize_tone(text)
    lexicon = default_gcam_lexicon() if lexicon is None else lexicon
    if not isinstance(lexicon, GCAMLexicon):
        raise TypeError("lexicon must be GCAMLexicon")
    frequencies = Counter(tokens)
    counts = dict.fromkeys(lexicon.dimensions, 0)
    lemma_tokens = None
    for token, frequency in frequencies.items():
        for key in lexicon._indices["words"].get(token, ()):
            counts[key] += frequency
    if lexicon.lemmatization:
        candidates = {token: _lemma_candidates(token, lexicon) for token in frequencies}
        lemma_tokens = [candidates[token] for token in tokens]
        for token, frequency in frequencies.items():
            lemma_keys = {
                key for w in candidates[token] for key in lexicon._indices["wordnet"].get(w, ())
            }
            for key in lemma_keys:
                counts[key] += frequency
    for mode, trie in lexicon._tries.items():
        if trie:
            stream = [{token} for token in tokens] if mode == "words" else lemma_tokens
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
        counts["c" + key[1:]] = count
        if count:
            values[key] = math.fsum(score * (n / count) for score, n in matches)
    keys = tuple(sorted((*counts, *lexicon.weighted_dimensions), key=_order))
    return GCAMResult(
        len(tokens), MappingProxyType(counts), keys, lexicon.name, MappingProxyType(values)
    )
