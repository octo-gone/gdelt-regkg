"""Dictionary-frequency scoring for the GKG tone field."""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from ..types import StrPath
from ..utils import resource_path

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
    """Named positive, negative, activity, and self-group token collections.

    Categories are normalized and frozen at construction. Empty categories and
    overlap between categories are supported.
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


def default_tone_lexicon(resources_dir: StrPath | None = None) -> ToneLexicon:
    from ..utils import ResourceStore

    return _cached_tone_lexicon(ResourceStore(resources_dir).profile("tone"))


@lru_cache(maxsize=8)
def _cached_tone_lexicon(resource):
    return _parse_lexicon(resource.read_text(encoding="utf-8"))


def benchmark_tone_lexicon(resources_dir: StrPath | None = None) -> ToneLexicon:
    """Compatibility alias for the benchmark-refined default dictionary."""
    return default_tone_lexicon(resources_dir)


def baseline_tone_lexicon(resources_dir: StrPath | None = None) -> ToneLexicon:
    """Version 1, retained for reproducible dictionary builds and comparisons."""
    return _cached_tone_lexicon(
        resource_path("lexicons", "tone.v1.json", resources_dir=resources_dir)
    )


@dataclass(frozen=True)
class ToneResult:
    """Tone scores, token count, and the lexicon identity.

    Attributes:
        tone: Positive score minus negative score.
        positive_score: Percentage of tokens matching positive words.
        negative_score: Percentage of tokens matching negative words.
        polarity: Percentage matching either positive or negative words.
        activity_reference_density: Percentage matching activity words.
        self_group_reference_density: Percentage matching self-group words.
        word_count: Total tokens, including repetitions.
        lexicon_name: Name of the dictionary used.
    """

    tone: float
    positive_score: float
    negative_score: float
    polarity: float
    activity_reference_density: float
    self_group_reference_density: float
    word_count: int
    lexicon_name: str

    def to_gkg(self) -> str:
        """Serialize six scores and the word count in GKG tone field order."""
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
    """Compute dictionary-based tone scores for article text.

    Args:
        text: Plain article text in the lexicon's language. The default lexicon
            expects English text or an English translation.
        lexicon: Reusable tone dictionary. If omitted, load the configured
            default English dictionary from local resources.

    Returns:
        The seven tone components and the name of the dictionary used.

    Raises:
        TypeError: If text is not a string or lexicon is not a ToneLexicon.
        ResourceUnavailableError: If the default local dictionary is unavailable.

    Examples:
        >>> lexicon = ToneLexicon("example", {"good"}, {"bad"}, set(), set())
        >>> result = analyze_tone("good good bad", lexicon=lexicon)
        >>> result.word_count
        3
        >>> round(result.tone, 2)
        33.33
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
