"""Explicit English date mentions without inferring absent years or relative dates."""

from __future__ import annotations

import calendar
import re
from dataclasses import dataclass

_MONTHS = {name.casefold(): i for i, name in enumerate(calendar.month_name) if name}
_MONTHS.update({name.casefold(): i for i, name in enumerate(calendar.month_abbr) if name})
_MONTHS["sept"] = 9
_MONTH = "(?:" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\.?"
_DAY = r"[0-9]{1,2}(?:st|nd|rd|th)?"
_YEAR = r"(?:1[5-9]|20|21)[0-9]{2}"
_PATTERNS = (
    ("iso", re.compile(rf"(?<![\w.])(?P<y>{_YEAR})-(?P<m>[0-9]{{2}})-(?P<d>[0-9]{{2}})(?![\w-])")),
    (
        "named",
        re.compile(
            rf"\b(?P<m>{_MONTH})\s+(?P<d>{_DAY})(?:(?:,\s*|\s+)(?P<y>{_YEAR}))?(?!\w)", re.I
        ),
    ),
    (
        "named",
        re.compile(
            rf"\b(?P<d>{_DAY})\s+(?:of\s+)?(?P<m>{_MONTH})(?:(?:,\s*|\s+)(?P<y>{_YEAR}))?(?!\w)",
            re.I,
        ),
    ),
    (
        "numeric",
        re.compile(rf"(?<![\w./-])(?P<a>[0-9]{{1,2}})/(?P<b>[0-9]{{1,2}})/(?P<y>{_YEAR})(?![\w/])"),
    ),
    ("month", re.compile(rf"\b(?P<m>{_MONTH})\s+(?P<y>{_YEAR})(?!\w)", re.I)),
    ("year", re.compile(rf"(?<![\w.$€£₹/+-])(?P<y>{_YEAR})(?![\w./%-])")),
)


@dataclass(frozen=True)
class DateMention:
    text: str
    start: int
    end: int
    resolution: int
    month: int
    day: int
    year: int

    def __post_init__(self):
        if any(
            type(n) is not int
            for n in (self.start, self.end, self.resolution, self.month, self.day, self.year)
        ):
            raise TypeError("Date components and offsets must be integers")
        if not 0 <= self.start < self.end or len(self.text) != self.end - self.start:
            raise ValueError("Date text must match its span length")
        if self.resolution not in {1, 2, 3, 4}:
            raise ValueError("Date resolution must be 1 through 4")
        if (self.resolution == 4) != (self.year == 0) or not 0 <= self.year <= 9999:
            raise ValueError("Only month-day dates have no year")
        if self.resolution == 1:
            valid = self.month == self.day == 0
        elif self.resolution == 2:
            valid = 1 <= self.month <= 12 and self.day == 0
        else:
            valid = (
                1 <= self.month <= 12
                and 1 <= self.day <= calendar.monthrange(self.year or 2000, self.month)[1]
            )
        if not valid:
            raise ValueError("Invalid calendar date or resolution")

    def to_gkg(self):
        # Actual GKG 2.1 archives use '#' despite the original codebook prose.
        return f"{self.resolution}#{self.month}#{self.day}#{self.year}#{self.start}"


@dataclass(frozen=True)
class DateIssue:
    text: str
    start: int
    reason: str


@dataclass(frozen=True)
class DateResult:
    text: str
    mentions: tuple[DateMention, ...]
    issues: tuple[DateIssue, ...] = ()

    def to_gkg(self):
        return ";".join(m.to_gkg() for m in self.mentions)


def analyze_dates(text: str, *, numeric_order: str | None = None) -> DateResult:
    """Extract years 1500–2199 and explicit calendar dates; reject ambiguous slashes.

    Set numeric_order to 'mdy' or 'dmy' to resolve ambiguous numeric dates.
    Missing date components stay zero. Invalid full dates never fall back to years.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if numeric_order not in {None, "mdy", "dmy"}:
        raise ValueError("numeric_order must be mdy, dmy, or None")
    occupied: list[tuple[int, int]] = []
    mentions, issues = [], []
    for kind, pattern in _PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span()
            if any(start < b and a < end for a, b in occupied):
                continue
            # Standalone years next to quantities are not calendar references.
            if kind == "year" and re.match(
                r"\s*(?:percent|people|residents|houses|trucks|soldiers|dollars|euros|pounds|million|billion|kg|km)\b",
                text[end:],
                re.I,
            ):
                continue
            occupied.append((start, end))
            groups = match.groupdict()
            year = int(groups.get("y") or 0)
            day = int(re.sub(r"\D", "", groups.get("d") or "0"))
            month = groups.get("m") or "0"
            month = _MONTHS[month.lower().rstrip(".")] if kind in {"named", "month"} else int(month)
            if kind == "numeric":
                a, b = int(groups["a"]), int(groups["b"])
                if numeric_order is None and a <= 12 and b <= 12 and a != b:
                    issues.append(DateIssue(match[0], start, "ambiguous-numeric-date"))
                    continue
                month, day = (
                    (b, a)
                    if numeric_order == "dmy" or (numeric_order is None and a > 12)
                    else (a, b)
                )
            resolution = 1 if kind == "year" else 2 if kind == "month" else 3 if year else 4
            try:
                mentions.append(DateMention(match[0], start, end, resolution, month, day, year))
            except ValueError:
                issues.append(DateIssue(match[0], start, "invalid-calendar-date"))
    return DateResult(
        text,
        tuple(sorted(mentions, key=lambda m: m.start)),
        tuple(sorted(issues, key=lambda m: m.start)),
    )
