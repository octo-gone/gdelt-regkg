"""Parse, validate, and serialize GKG count and theme cells."""

from __future__ import annotations

import re
import unicodedata


def text_component(value: str, *, separators: str = "") -> str:
    """Replace reserved separators and control characters with spaces.

    Use this helper to prepare individual text values for field serialization.
    The replacements discard information, so retain the original text for NLP
    analysis.

    Args:
        value: Text to normalize before including it in a field component.
        separators: Characters to replace with spaces in addition to Unicode
            control characters (category `Cc`). Defaults to no extra separators.

    Returns:
        The normalized text with leading and trailing whitespace removed and
        whitespace runs collapsed to single spaces. Empty or whitespace-only
        input returns an empty string.

    Raises:
        TypeError: If `value` is not a string.
    """
    if not isinstance(value, str):
        raise TypeError("Text components must be strings")
    return " ".join(
        "".join(
            " " if char in separators or unicodedata.category(char) == "Cc" else char
            for char in value
        ).split()
    )


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
    """Parse a standard or enhanced GKG counts cell into string components.

    Entries are separated by semicolons, with an optional trailing semicolon.
    Each entry has ten hash-separated components: label, quantity, object,
    location type, location name, country code, ADM1 code, latitude, longitude,
    and feature ID. Enhanced entries add a final quantity character offset.

    Args:
        cell: Encoded counts cell, or an empty string for no entries.
        enhanced: Whether to require the eleventh component containing the offset.

    Returns:
        A tuple of component tuples in input order, preserving duplicates and
        component spelling. Quantities and offsets remain strings. An empty cell
        returns an empty tuple.

    Raises:
        TypeError: If `cell` is not a string.
        ValueError: If the cell contains tabs, carriage returns, or newlines; an
            entry has the wrong number of components; a label does not match
            `[A-Z][A-Z0-9_-]*`; or a quantity or enhanced offset is not a
            nonnegative integer written with ASCII digits.
    """
    entries = _parse(cell, 11 if enhanced else 10, "#")
    for entry in entries:
        if not re.fullmatch(r"[0-9]+", entry[1]):
            raise ValueError("Count quantity must be an integer")
        if enhanced and not re.fullmatch(r"[0-9]+", entry[-1]):
            raise ValueError("Count offset must be a nonnegative integer")
    return entries


def parse_themes_cell(cell: str, *, enhanced: bool = False) -> tuple[tuple[str, ...], ...]:
    """Parse a standard or enhanced GKG themes cell into string components.

    Entries are separated by semicolons, with an optional trailing semicolon.
    Standard entries contain only a theme label. Enhanced entries contain a label
    and a character offset separated by a comma.

    Args:
        cell: Encoded themes cell, or an empty string for no entries.
        enhanced: Whether to require a comma-separated offset after each label.

    Returns:
        A tuple of one-component or two-component tuples in input order,
        preserving duplicates and component spelling. Offsets remain strings.
        An empty cell returns an empty tuple.

    Raises:
        TypeError: If `cell` is not a string.
        ValueError: If the cell contains tabs, carriage returns, or newlines; an
            entry has the wrong number of components; a label does not match
            `[A-Z][A-Z0-9_-]*`; or an enhanced offset is not a nonnegative integer
            written with ASCII digits.
    """
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
    """Validate and serialize count entries into a GKG counts cell.

    Components follow the order accepted by `parse_counts_cell`. Entry order,
    duplicates, and component spelling are preserved.

    Args:
        entries (Iterable[Iterable[str]]): Count entries containing ten string
            components each, or eleven when `enhanced` is true. Quantities and
            enhanced offsets must be nonnegative integers written with ASCII
            digits, supplied as strings.
        enhanced: Whether entries include a final quantity character offset.

    Returns:
        A cell with hash-separated components and a semicolon after every entry.
        An empty iterable returns an empty string.

    Raises:
        TypeError: If `entries` or an entry is not iterable, or a component is not
            a string.
        ValueError: If a component contains a hash, semicolon, tab, carriage
            return, or newline; an entry has the wrong number of components; or
            a label, quantity, or enhanced offset fails counts-cell validation.
    """
    return _serialize(entries, "#", parse_counts_cell, enhanced)


def serialize_themes_cell(entries, *, enhanced: bool = False) -> str:
    """Validate and serialize theme entries into a GKG themes cell.

    Entry order, duplicates, and component spelling are preserved.

    Args:
        entries (Iterable[Iterable[str]]): Entries containing a single label
            string, or a label and an offset string when `enhanced` is true.
            Offsets must be nonnegative integers written with ASCII digits.
        enhanced: Whether to include a comma-separated character offset after
            each label.

    Returns:
        A cell with a semicolon after every entry and comma-separated components
        for enhanced entries. An empty iterable returns an empty string.

    Raises:
        TypeError: If `entries` or an entry is not iterable, or a component is not
            a string.
        ValueError: If a component contains a reserved separator, tab, carriage
            return, or newline; an entry has the wrong number of components; or
            a label or enhanced offset fails themes-cell validation.
    """
    return _serialize(entries, "," if enhanced else "", parse_themes_cell, enhanced)
