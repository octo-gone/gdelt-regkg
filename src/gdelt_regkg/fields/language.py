"""Optional local language identification for prepared article bodies."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

from ..dependencies import require_dependency
from ..types import LanguageCheck

if TYPE_CHECKING:
    from lingua import LanguageDetector as LinguaBackend


@dataclass(frozen=True)
class LanguageDetection:
    """A language candidate with confidence and detector identity.

    Attributes:
        language: Lowercase ISO 639-3 code.
        confidence: Detector score for the best candidate.
        margin: Score difference between the best and second-best candidates.
        detector: Detector identity.
    """

    language: str
    confidence: float
    margin: float
    detector: str


class LanguageDetector(Protocol):
    """Interface for backends implementing `detect(text)` with a `LanguageDetection`."""

    def detect(self, text: str) -> LanguageDetection: ...


class LanguageDetectionError(ValueError):
    """No language candidate exists, or strict detection rejects weak evidence."""


class LinguaDetector:
    """Local language identifier with optional confidence thresholds.

    Args:
        strict: Reject short text and candidates below the configured thresholds.
        min_letters: Minimum alphabetic sample length in strict mode.
        min_confidence: Minimum candidate confidence in strict mode.
        min_margin: Minimum gap from the next candidate in strict mode.
    """

    def __init__(
        self,
        *,
        strict: bool = False,
        min_letters: int = 40,
        min_confidence: float = 0.8,
        min_margin: float = 0.2,
    ):
        if not isinstance(strict, bool):
            raise TypeError("strict must be bool")
        if type(min_letters) is not int or min_letters < 0:
            raise ValueError("min_letters must be a nonnegative integer")
        if not 0 <= min_confidence <= 1 or not 0 <= min_margin <= 1:
            raise ValueError("Language detection thresholds must be between 0 and 1")
        builder = require_dependency("lingua", "lang").LanguageDetectorBuilder
        self.backend = builder.from_all_spoken_languages().with_low_accuracy_mode().build()
        self.strict, self.min_letters = strict, min_letters
        self.min_confidence, self.min_margin = min_confidence, min_margin

    def detect(self, text: str) -> LanguageDetection:
        """Identify a language candidate using this detector's thresholds."""
        return self._detect_with(text, self.backend, "lingua/low-accuracy")

    def confirm(self, text: str, supplied: str, candidate: str) -> LanguageDetection:
        """Use full models to compare a proposed correction with the supplied label."""
        backend = _confirmation_backend(*sorted((supplied, candidate)))
        return self._detect_with(text, backend, "lingua/high-accuracy-confirmation")

    def _detect_with(self, text: str, backend: LinguaBackend, identity: str) -> LanguageDetection:
        if not isinstance(text, str):
            raise TypeError("text must be str")
        # Sample the beginning, middle, and end rather than only page boilerplate.
        if len(text) > 6000:
            middle = len(text) // 2
            sample = "\n".join((text[:2000], text[middle - 1000 : middle + 1000], text[-2000:]))
        else:
            sample = text
        if self.strict and sum(char.isalpha() for char in sample) < self.min_letters:
            raise LanguageDetectionError("Too little alphabetic text to detect a language reliably")
        values = backend.compute_language_confidence_values(sample)
        if not values:
            raise LanguageDetectionError("No language could be detected")
        best = values[0]
        margin = best.value - (values[1].value if len(values) > 1 else 0)
        if self.strict and (best.value < self.min_confidence or margin < self.min_margin):
            raise LanguageDetectionError(
                f"Uncertain language detection: confidence={best.value:.3f}, margin={margin:.3f}"
            )
        return LanguageDetection(
            best.language.iso_code_639_3.name.lower(), best.value, margin, identity
        )


@lru_cache(maxsize=8)
def _confirmation_backend(supplied: str, candidate: str):
    lingua = require_dependency("lingua", "lang")
    iso_codes, builder = lingua.IsoCode639_3, lingua.LanguageDetectorBuilder

    codes = []
    for language in (supplied, candidate):
        code = getattr(iso_codes, language.upper(), None)
        if code is None:
            raise LanguageDetectionError("Supplied language cannot be verified by Lingua")
        codes.append(code)
    # Full n-gram models, loaded lazily for these two languages only.
    return builder.from_iso_codes_639_3(*codes).build()


@lru_cache(maxsize=2)
def default_language_detector(*, strict: bool = False) -> LinguaDetector:
    return LinguaDetector(strict=strict)


def detect_language(text: str, *, detector: LanguageDetector | None = None) -> LanguageDetection:
    """Identify a language candidate for a prepared article body.

    Args:
        text: Body to analyze.
        detector: Custom detector. Defaults to a permissive local Lingua detector.

    Returns:
        A language code, confidence, margin, and detector identity.

    Raises:
        TypeError: If `text` or the detector result has an invalid type.
        LanguageDetectionError: If no candidate exists or strict thresholds fail.
        OptionalDependencyError: If the default detector's dependency is unavailable.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    result = (default_language_detector() if detector is None else detector).detect(text)
    if not isinstance(result, LanguageDetection):
        raise TypeError("Language detector must return LanguageDetection")
    return result


_SCRIPTS = {
    **dict.fromkeys(("ara", "urd", "fas", "pus", "snd"), {"ARABIC"}),
    **dict.fromkeys(("rus", "ukr", "bul", "bel", "mkd", "kaz", "kir", "tgk"), {"CYRILLIC"}),
    "srp": {"LATIN", "CYRILLIC"},
    "uzb": {"LATIN", "CYRILLIC", "ARABIC"},
    "zho": {"CJK"},
    "jpn": {"CJK", "HIRAGANA", "KATAKANA"},
    "kor": {"HANGUL", "CJK"},
    "hin": {"DEVANAGARI"},
    "mar": {"DEVANAGARI"},
    "nep": {"DEVANAGARI"},
    "ben": {"BENGALI"},
    "pan": {"GURMUKHI", "ARABIC"},
    "guj": {"GUJARATI"},
    "tam": {"TAMIL"},
    "tel": {"TELUGU"},
    "kan": {"KANNADA"},
    "mal": {"MALAYALAM"},
    "ori": {"ORIYA"},
    "sin": {"SINHALA"},
    "tha": {"THAI"},
    "lao": {"LAO"},
    "khm": {"KHMER"},
    "mya": {"MYANMAR"},
    "amh": {"ETHIOPIC"},
    "heb": {"HEBREW"},
    "yid": {"HEBREW"},
    "ell": {"GREEK"},
    "hye": {"ARMENIAN"},
    "kat": {"GEORGIAN"},
    "mon": {"CYRILLIC", "MONGOLIAN"},
    "aze": {"LATIN", "CYRILLIC", "ARABIC"},
}


def script_mismatch(text: str, language: str) -> bool:
    """Flag a dominant alphabet incompatible with a normalized language label."""
    expected = _SCRIPTS.get(language, {"LATIN"})
    letters = [unicodedata.name(char, "").split()[0] for char in text[:6000] if char.isalpha()]
    if len(letters) < 40:
        return False
    counts = Counter(letters)
    return sum(counts[script] for script in expected) / len(letters) < 0.3


def verify_language(
    text: str,
    language: str,
    *,
    check: LanguageCheck = "script",
    detector: LanguageDetector | None = None,
) -> LanguageDetection | None:
    """Check supplied labels; alphabet conflicts require a confident decision."""
    if check not in {"none", "script", "all"}:
        raise ValueError("language_check must be none, script, or all")
    if check == "none":
        return None
    conflict = script_mismatch(text, language)
    if not conflict and check != "all":
        return None
    # Automatic corrections to a supplied label still need confident evidence.
    backend = default_language_detector(strict=True) if detector is None else detector
    try:
        result = detect_language(text, detector=backend)
        if result.language != language and result.detector == "lingua/low-accuracy":
            if isinstance(backend, LinguaDetector):
                result = backend.confirm(text, language, result.language)
        return result
    except LanguageDetectionError:
        if conflict:
            raise
        return None
