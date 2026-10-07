"""Quotation spans and conservative reporting-verb matching in prepared text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .wire import text_component

_PAIRS = {'"': '"', "“": "”", "‘": "’", "'": "'", "«": "»"}
_VERBS = re.compile(
    r"\b(?:said|says|say|saying|told|tell|tells|added|adds|asked|asks|"
    r"replied|replies|responded|responds|stated|states|wrote|writes|"
    r"announced|announces|argued|argues|warned|warns|agreed|agrees|"
    r"denied|denies|insisted|insists|claimed|claims|explained|explains|"
    r"noted|notes|retorted|retorts|recalled|recalls|admitted|admits|"
    r"reported|reports|declared|declares|commented|comments)\b",
    re.I,
)


@dataclass(frozen=True)
class QuotationMention:
    text: str
    start: int
    end: int
    verb: str = ""

    def __post_init__(self):
        if not isinstance(self.text, str) or not self.text.strip():
            raise ValueError("Quotation text must be nonempty")
        if (
            type(self.start) is not int
            or type(self.end) is not int
            or not 0 <= self.start < self.end
        ):
            raise ValueError("Quotation offsets must satisfy 0 <= start < end")
        if self.end - self.start != len(self.text):
            raise ValueError("Quotation length must match its original span")
        if not isinstance(self.verb, str):
            raise TypeError("Reporting verb must be a string")

    def to_gkg(self) -> str:
        quote = text_component(self.text, separators="#|")
        verb = text_component(self.verb, separators="#|")
        return f"{self.start}|{self.end - self.start}|{verb}|{quote}"


@dataclass(frozen=True)
class QuotationIssue:
    start: int
    end: int
    reason: str


@dataclass(frozen=True)
class QuotationResult:
    mentions: tuple[QuotationMention, ...]
    issues: tuple[QuotationIssue, ...]

    def to_gkg(self) -> str:
        return "#".join(mention.to_gkg() for mention in self.mentions)


def _escaped(text, index):
    preceding = index - 1
    while preceding >= 0 and text[preceding] == "\\":
        preceding -= 1
    return (index - preceding - 1) % 2 == 1


def _apostrophe(text, index):
    return 0 < index < len(text) - 1 and text[index - 1].isalnum() and text[index + 1].isalnum()


def _verb(text, opening, closing, previous_end, next_start):
    # Do not borrow a verb from another quote or across a sentence/paragraph.
    prefix = text[max(previous_end, opening - 100) : opening]
    prefix = re.split(r"[.!?\n]", prefix)[-1]
    suffix = re.split(r"[.!?\n]", text[closing + 1 : min(next_start, closing + 101)])[0]
    candidates = [
        (len(prefix) - match.end(), match.group().lower()) for match in _VERBS.finditer(prefix)
    ]
    candidates += [(match.start(), match.group().lower()) for match in _VERBS.finditer(suffix)]
    return min(candidates, key=lambda item: item[0])[1] if candidates else ""


def analyze_quotations(text: str) -> QuotationResult:
    """Find outer quoted spans without modifying original coordinates.

    Accept straight/curly double and single quotes and guillemets. Apostrophes
    inside words are ignored. Nested quotes of another style remain in the outer text.
    Unmatched openings and normalized wire delimiters are reported in ``issues``. Quoted
    titles and scare quotes are not distinguished from speech. Verb association
    is a bounded English heuristic, not speaker attribution or parsing.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    spans, issues = [], []
    index = 0
    while index < len(text):
        opening = text[index]
        if (
            opening not in _PAIRS
            or _escaped(text, index)
            or (opening in {"'", "‘"} and index and text[index - 1].isalnum())
        ):
            index += 1
            continue
        closing = index + 1
        while closing < len(text):
            if text[closing] == _PAIRS[opening] and not _escaped(text, closing):
                if opening not in {"'", "‘"} or not _apostrophe(text, closing):
                    break
            closing += 1
        if closing == len(text):
            issues.append(QuotationIssue(index, len(text), "unclosed_quote"))
            index += 1
            continue
        start, end = index + 1, closing
        while start < end and text[start].isspace():
            start += 1
        while end > start and text[end - 1].isspace():
            end -= 1
        if start < end:
            spans.append((index, closing, start, end))
        index = closing + 1
    mentions = []
    for position, (opening_offset, closing, start, end) in enumerate(spans):
        quote = text[start:end]
        if not text_component(quote, separators="#|"):
            issues.append(QuotationIssue(start, end, "empty_after_normalization"))
            continue
        if any(c in quote for c in "#|"):
            issues.append(QuotationIssue(start, end, "normalized_delimiter"))
        previous_end = spans[position - 1][1] + 1 if position else 0
        next_start = spans[position + 1][0] if position + 1 < len(spans) else len(text)
        mentions.append(
            QuotationMention(
                quote, start, end, _verb(text, opening_offset, closing, previous_end, next_start)
            )
        )
    return QuotationResult(tuple(mentions), tuple(sorted(issues, key=lambda issue: issue.start)))
