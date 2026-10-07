"""Optional local language identification for prepared article bodies."""

from __future__ import annotations

import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from lingua import LanguageDetector as LinguaBackend


@dataclass(frozen=True)
class LanguageDetection:
    language: str
    confidence: float
    margin: float
    detector: str


class LanguageDetector(Protocol):
    def detect(self, text: str) -> LanguageDetection: ...


class LanguageDetectionError(ValueError):
    """The body does not provide enough evidence for a language decision."""


class LinguaDetector:
    """Reusable local detector with bounded input and confidence thresholds."""

    def __init__(self, *, min_confidence: float = 0.8, min_margin: float = 0.2):
        if not 0 <= min_confidence <= 1 or not 0 <= min_margin <= 1:
            raise ValueError("Language detection thresholds must be between 0 and 1")
        try:
            from lingua import LanguageDetectorBuilder
        except ImportError as error:
            raise RuntimeError("Install gdelt-regkg to detect missing languages") from error
        self.backend = (
            LanguageDetectorBuilder.from_all_spoken_languages().with_low_accuracy_mode().build()
        )
        self.min_confidence, self.min_margin = min_confidence, min_margin

    def detect(self, text: str) -> LanguageDetection:
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
        if sum(char.isalpha() for char in sample) < 40:
            raise LanguageDetectionError("Too little alphabetic text to detect a language reliably")
        values = backend.compute_language_confidence_values(sample)
        if not values:
            raise LanguageDetectionError("No language could be detected")
        best = values[0]
        margin = best.value - (values[1].value if len(values) > 1 else 0)
        if best.value < self.min_confidence or margin < self.min_margin:
            raise LanguageDetectionError(
                f"Uncertain language detection: confidence={best.value:.3f}, margin={margin:.3f}"
            )
        return LanguageDetection(
            best.language.iso_code_639_3.name.lower(), best.value, margin, identity
        )


@lru_cache(maxsize=8)
def _confirmation_backend(supplied: str, candidate: str):
    from lingua import IsoCode639_3, LanguageDetectorBuilder

    codes: list[IsoCode639_3] = []
    for language in (supplied, candidate):
        code = getattr(IsoCode639_3, language.upper(), None)
        if code is None:
            raise LanguageDetectionError("Supplied language cannot be verified by Lingua")
        codes.append(code)
    # Full n-gram models, loaded lazily for these two languages only.
    return LanguageDetectorBuilder.from_iso_codes_639_3(*codes).build()


@lru_cache(maxsize=1)
def default_language_detector() -> LinguaDetector:
    return LinguaDetector()


def detect_language(text: str, *, detector: LanguageDetector | None = None) -> LanguageDetection:
    """Identify the body language independently of translation or GKG generation."""
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
    text: str, language: str, *, check="script", detector: LanguageDetector | None = None
) -> LanguageDetection | None:
    """Check supplied labels; alphabet conflicts require a confident decision."""
    if check not in {"none", "script", "all"}:
        raise ValueError("language_check must be none, script, or all")
    if check == "none":
        return None
    conflict = script_mismatch(text, language)
    if not conflict and check != "all":
        return None
    try:
        result = detect_language(text, detector=detector)
        if result.language != language and result.detector == "lingua/low-accuracy":
            backend = default_language_detector() if detector is None else detector
            if isinstance(backend, LinguaDetector):
                result = backend.confirm(text, language, result.language)
        return result
    except LanguageDetectionError:
        if conflict:
            raise
        return None
