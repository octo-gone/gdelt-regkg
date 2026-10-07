"""GKG count/theme cell parsing and serialization.

These helpers preserve entry order and component spelling. Nonempty output
ends in ';', matching the sampled original GKG archives. Empty cells stay ''.
"""

from __future__ import annotations

import re
import unicodedata


def _parse(cell: str, width: int, delimiter: str | None) -> tuple[tuple[str, ...], ...]:
    if not isinstance(cell, str):
        raise TypeError("GKG cells must be strings")
    if any(c in cell for c in "\t\r\n"):
        raise ValueError("Row delimiters are not allowed in cells")
    if not cell:
        return ()
    entries = cell.removesuffix(";").split(";")
    result = []
    for entry in entries:
        parts = tuple(entry.split(delimiter)) if delimiter else (entry,)
        if len(parts) != width or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", parts[0]):
            raise ValueError("Invalid GKG entry width or label")
        result.append(parts)
    return tuple(result)


def parse_counts_cell(cell: str, *, enhanced: bool = False) -> tuple[tuple[str, ...], ...]:
    entries = _parse(cell, 11 if enhanced else 10, "#")
    for entry in entries:
        if not re.fullmatch(r"[0-9]+", entry[1]):
            raise ValueError("Count quantity must be an integer")
        if enhanced and not re.fullmatch(r"[0-9]+", entry[-1]):
            raise ValueError("Count offset must be a nonnegative integer")
    return entries


def parse_themes_cell(cell: str, *, enhanced: bool = False) -> tuple[tuple[str, ...], ...]:
    entries = _parse(cell, 2 if enhanced else 1, "," if enhanced else None)
    if enhanced and any(not re.fullmatch(r"[0-9]+", entry[1]) for entry in entries):
        raise ValueError("Theme offset must be a nonnegative integer")
    return entries


def _serialize(entries, delimiter, parser, enhanced):
    entries = tuple(tuple(entry) for entry in entries)
    if any(not isinstance(value, str) for entry in entries for value in entry):
        raise TypeError("Wire components must be strings")
    if any(any(c in value for c in ";\t\r\n" + delimiter) for entry in entries for value in entry):
        raise ValueError("Wire components cannot contain separators")
    cell = "".join(delimiter.join(entry) + ";" for entry in entries)
    if parser(cell, enhanced=enhanced) != entries:
        raise ValueError("Invalid GKG components")
    return cell


def serialize_counts_cell(entries, *, enhanced: bool = False) -> str:
    return _serialize(entries, "#", parse_counts_cell, enhanced)


def serialize_themes_cell(entries, *, enhanced: bool = False) -> str:
    return _serialize(entries, "," if enhanced else "", parse_themes_cell, enhanced)


def text_component(value: str, *, separators: str = "") -> str:
    """Replace reserved separators and control characters with spaces.

    Apply to individual text values, never to an encoded field or NLP input.
    This is lossy normalization, not a GDELT escaping convention.
    """
    if not isinstance(value, str):
        raise TypeError("Text components must be strings")
    return " ".join(
        "".join(
            " " if char in separators or unicodedata.category(char) == "Cc" else char
            for char in value
        ).split()
    )
