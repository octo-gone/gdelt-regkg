"""Precise English quantities and currencies with bounded object attachment."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .counts import _N1000, _VALUES
from .dates import analyze_dates
from .wire import text_component

_SCALES = {"hundred": 100, "thousand": 1000, "million": 10**6, "billion": 10**9, "trillion": 10**12}
_WORDS = rf"(?:{_N1000}(?: trillion(?: {_N1000} billion)?(?: {_N1000} million)?(?: {_N1000} thousand)?(?: (?:and )?{_N1000})?| billion(?: {_N1000} million)?(?: {_N1000} thousand)?(?: (?:and )?{_N1000})?| million(?: {_N1000} thousand)?(?: (?:and )?{_N1000})?| thousand(?: (?:and )?{_N1000})?)?)"
_NUMBER = rf"(?:[+-]?(?:[0-9]{{1,3}}(?:,[0-9]{{3}})+|[0-9]+)(?:\.[0-9]+)?(?:\s*(?:trillion|billion|million|thousand|bn|[kmbt])\b)?|{_WORDS})"
_CURRENCY = {
    "$": "dollars",
    "€": "euros",
    "£": "pounds",
    "₹": "rupees",
    "usd": "dollars",
    "eur": "euros",
    "gbp": "pounds",
    "inr": "rupees",
}
_RE = re.compile(
    rf"(?<![\w.])(?P<currency>[$€£₹]\s*|(?:USD|EUR|GBP|INR)\s+)?(?P<number>{_NUMBER})(?!\w)", re.I
)
_MULTIPLIERS = _SCALES | {"k": 1000, "m": 10**6, "b": 10**9, "bn": 10**9, "t": 10**12}
_STOP = set(
    "a an the and or but of in on at to for from by with as than per was were is are be been being will would can could may might must should has have had said says say reported reports report killed injured died displaced arrested spent cost costs rose fell increased decreased reached donated pledged paid worth during after before about around approximately over under more less nearly only it this that these those their his her our its who which when where they we you he she not no".split()
)
_PERCENT = re.compile(r"\s*(?:%|percent(?:age)?\b|per\s+cent\b)", re.I)


def _number(value: str) -> Decimal:
    value = value.casefold().replace(",", "")
    numeric = re.fullmatch(r"([+-]?[0-9]+(?:\.[0-9]+)?)\s*([a-z]+)?", value)
    if numeric:
        return Decimal(numeric[1]) * _MULTIPLIERS.get(numeric[2], 1)
    total, group = 0, 0
    for word in value.replace("-", " ").split():
        if word == "and":
            continue
        if word == "hundred":
            group *= 100
        elif word in _SCALES:
            total += group * _SCALES[word]
            group = 0
        else:
            group += _VALUES[word]
    return Decimal(total + group)


@dataclass(frozen=True)
class AmountMention:
    text: str
    start: int
    end: int
    amount: Decimal
    object_type: str = ""

    def __post_init__(self):
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end
            or len(self.text) != self.end - self.start
        ):
            raise ValueError("Amount text must match valid integer offsets")
        if not isinstance(self.amount, Decimal) or not self.amount.is_finite():
            raise ValueError("amount must be a finite Decimal")
        if not isinstance(self.object_type, str):
            raise TypeError("object_type must be str")

    def to_gkg(self):
        number = format(self.amount, "f")
        if "." in number:
            number = number.rstrip("0").rstrip(".")
        return f"{number},{text_component(self.object_type, separators=';,')},{self.start}"


@dataclass(frozen=True)
class AmountResult:
    text: str
    mentions: tuple[AmountMention, ...]

    def to_gkg(self):
        return ";".join(m.to_gkg() for m in self.mentions)


def analyze_amounts(text: str, *, numeric_order: str | None = None) -> AmountResult:
    """Parse exact numbers, magnitude suffixes and currencies; exclude dates/percentages.

    Object attachment reads at most three following words, stopping at common
    verbs, prepositions and punctuation. This is not dependency parsing.
    Indefinite 'hundreds of' quantities are deliberately not assigned exact values.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    dates = analyze_dates(text, numeric_order=numeric_order)
    excluded = [(m.start, m.end) for m in dates.mentions] + [
        (m.start, m.start + len(m.text)) for m in dates.issues
    ]
    mentions = []
    for match in _RE.finditer(text):
        start, end = match.span()
        if any(start < b and a < end for a, b in excluded) or _PERCENT.match(text[end:]):
            continue
        # Versions, times, identifiers and fractions are not scalar amounts.
        if re.match(r"[.:/][0-9]", text[end:]) or (start and text[start - 1] in ":/"):
            continue
        currency = (match["currency"] or "").strip().casefold()
        obj = _CURRENCY.get(currency, "")
        if not obj:
            cursor = end
            words: list[str] = []
            for _ in range(3):
                following = re.match(r"\s+([A-Za-z]+(?:[-'][A-Za-z]+)*)\b", text[cursor:])
                modifier = bool(
                    following
                    and not words
                    and following[1].casefold() in {"displaced", "injured", "arrested"}
                    and re.match(
                        r"\s+(?:civilians|people|residents|workers|soldiers|children|families)\b",
                        text[cursor + following.end() :],
                        re.I,
                    )
                )
                if not following or (following[1].casefold() in _STOP and not modifier):
                    break
                words.append(following[1])
                cursor += following.end()
            obj = " ".join(words)
        # Bare textual numbers are often pronouns ('one of them').
        if not obj and not currency and not re.search(r"[0-9]", match["number"]):
            continue
        mentions.append(AmountMention(match[0], start, end, _number(match["number"]), obj))
    return AmountResult(text, tuple(mentions))
