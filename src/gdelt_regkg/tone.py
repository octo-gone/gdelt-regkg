"""Dictionary-frequency approximation of GKG tone; see docs/fields/tone.md.

The locally built General Inquirer categories are NOT GDELT's production lexicon.
No POS model, sentiment reasoning, negation inversion, or stopword removal.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .utils import read_resource_json, resource_path

_WORD = re.compile(r"[^\W_]+(?:['-][^\W_]+)*", re.UNICODE)
_CATEGORIES = ("positive", "negative", "activity", "self_group")


def _normalize(text: str) -> str:
    return (
        unicodedata.normalize("NFKC", text).casefold().replace("\u2019", "'").replace("\u2018", "'")
    )


def tokenize_tone(text: str) -> list[str]:
    """Return casefolded word/number tokens, retaining internal apostrophes/hyphens.

    This explicit local policy is not a verified GDELT tokenizer. Punctuation
    alone is not a token; stopwords and repeated words stay in the denominator.
    Input must already be article text, not HTML.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str; normalize missing values before scoring")
    return _WORD.findall(_normalize(text))


@dataclass(frozen=True)
class ToneLexicon:
    """Four sets of exact tokens, reusable across documents and pandas rows.

    Collections are normalized and frozen at construction. Every category is
    required; an explicitly empty category is permitted for controlled tests.
    Overlap across categories is allowed. No stemming or sense disambiguation.
    """

    name: str
    positive: frozenset[str]
    negative: frozenset[str]
    activity: frozenset[str]
    self_group: frozenset[str]
    _tonal: frozenset[str] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("Lexicon name must identify its source/version")
        for category in _CATEGORIES:
            entries = getattr(self, category)
            if isinstance(entries, str):
                raise TypeError(f"{category} must be a collection of tokens, not a string")
            normalized = set()
            for entry in entries:
                if not isinstance(entry, str):
                    raise TypeError(f"{category} entries must be strings")
                token = _normalize(entry)
                if not _WORD.fullmatch(token):
                    raise ValueError(f"{category}: {entry!r} is not a single supported token")
                normalized.add(token)
            object.__setattr__(self, category, frozenset(normalized))
        object.__setattr__(self, "_tonal", self.positive | self.negative)

    @classmethod
    def from_json(cls, path: str | Path) -> "ToneLexicon":
        """Load once outside row loops; JSON needs name and all four categories."""
        return _parse_lexicon(Path(path).read_text(encoding="utf-8"))


def _parse_lexicon(text: str) -> ToneLexicon:
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("Lexicon JSON must be an object")
    required = {"name", *_CATEGORIES}
    if missing := required - payload.keys():
        raise ValueError(f"Missing lexicon fields: {sorted(missing)}")
    for category in _CATEGORIES:
        if not isinstance(payload[category], list):
            raise ValueError(f"{category} must be a JSON array")
    return ToneLexicon(**{key: payload[key] for key in required})


def default_tone_lexicon(resources_dir=None) -> ToneLexicon:
    """Load the selected local revision; never download during scoring."""
    resource = resource_path(
        "lexicons",
        read_resource_json("defaults.json", resources_dir=resources_dir)["tone"],
        resources_dir=resources_dir,
    )
    return _cached_tone_lexicon(resource)


@lru_cache(maxsize=8)
def _cached_tone_lexicon(resource):
    return _parse_lexicon(resource.read_text(encoding="utf-8"))


def benchmark_tone_lexicon(resources_dir=None) -> ToneLexicon:
    """Compatibility alias for the benchmark-refined default dictionary."""
    return default_tone_lexicon(resources_dir)


def baseline_tone_lexicon(resources_dir=None) -> ToneLexicon:
    """Version 1, retained for reproducible dictionary builds and comparisons."""
    return _cached_tone_lexicon(
        resource_path("lexicons", "tone.v1.json", resources_dir=resources_dir)
    )


@dataclass(frozen=True)
class ToneResult:
    tone: float
    positive_score: float
    negative_score: float
    polarity: float
    activity_reference_density: float
    self_group_reference_density: float
    word_count: int
    lexicon_name: str

    def to_gkg(self) -> str:
        """Six scores and integer word count, in the V1.5TONE field order."""
        scores = (
            self.tone,
            self.positive_score,
            self.negative_score,
            self.polarity,
            self.activity_reference_density,
            self.self_group_reference_density,
        )
        return ",".join(format(value, ".15g") for value in scores) + f",{self.word_count}"


def analyze_tone(text: str, *, lexicon: ToneLexicon | None = None) -> ToneResult:
    """Compute percentages of all tokens using exact, case-insensitive matches.

    Default: benchmark-refined English dictionary approximation. Supply English text (or
    its translation), or an appropriate custom lexicon for other languages.
    Polarity counts the union of positive/negative matches once per token.
    Empty or punctuation-only input returns zero scores and a zero word count.
    """
    tokens = tokenize_tone(text)
    if lexicon is None:
        lexicon = default_tone_lexicon()
    if not isinstance(lexicon, ToneLexicon):
        raise TypeError("lexicon must be a ToneLexicon")
    counts = Counter(tokens)
    total = len(tokens)

    def density(category: frozenset[str]) -> float:
        matches = sum(count for token, count in counts.items() if token in category)
        return 100.0 * matches / total if total else 0.0

    positive = density(lexicon.positive)
    negative = density(lexicon.negative)
    return ToneResult(
        tone=positive - negative,
        positive_score=positive,
        negative_score=negative,
        polarity=density(lexicon._tonal),
        activity_reference_density=density(lexicon.activity),
        self_group_reference_density=density(lexicon.self_group),
        word_count=total,
        lexicon_name=lexicon.name,
    )
