"""Serialize caller-supplied extension metadata into GKG XML fragments."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from xml.etree.ElementTree import Element, SubElement, tostring

_INVALID_XML = re.compile(r"[^\x09\x0A\x0D\x20-\uD7FF\uE000-\uFFFD\U00010000-\U0010FFFF]")
_TAG_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.-]*\Z")
type XMLValue = str | Mapping[str, XMLValue] | list[XMLValue] | tuple[XMLValue, ...] | None
_TAGS = {
    "title": "TITLE",
    "book_title": "BOOKTITLE",
    "date": "DATE",
    "journal": "JOURNAL",
    "volume": "VOLUME",
    "issue": "ISSUE",
    "pages": "PAGES",
    "institution": "INSTITUTION",
    "publisher": "PUBLISHER",
    "location": "LOCATION",
    "marker": "MARKER",
}


def _text(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("XML text values must be strings")
    if _INVALID_XML.search(value):
        raise ValueError("Values contain characters invalid in XML 1.0")
    return value


@dataclass(frozen=True)
class Citation:
    """Parsed reference metadata; omitted values produce no XML element.

    Supply author names in given-name-first order. Simple 'Surname, Given'
    names are reordered; multi-comma names are retained to avoid guessing.
    Dates, volumes, issues and pages remain strings, without reinterpretation.
    """

    authors: tuple[str, ...] = ()
    title: str | None = None
    book_title: str | None = None
    date: str | None = None
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    institution: str | None = None
    publisher: str | None = None
    location: str | None = None
    marker: str | None = None

    def __post_init__(self):
        if isinstance(self.authors, str):
            raise TypeError("authors must be a collection of names")
        authors = []
        for author in self.authors:
            author = _text(author).strip()
            if not author:
                raise ValueError("Author names must not be blank")
            if author.count(",") == 1:
                surname, given = (part.strip() for part in author.split(","))
                if surname and given:
                    author = f"{given} {surname}"
            authors.append(author)
        object.__setattr__(self, "authors", tuple(authors))
        for field in fields(self):
            if field.name == "authors":
                continue
            value = getattr(self, field.name)
            if value is not None:
                _text(value)
                if not value.strip():
                    object.__setattr__(self, field.name, None)
        if not self.authors and not any(getattr(self, name) for name in _TAGS):
            raise ValueError("A citation needs at least one author or metadata value")


def citation_elements(citations: Iterable[Citation]) -> dict[str, XMLValue]:
    """Convert references into an optional block for format_extras_xml."""
    references: list[XMLValue] = []
    for citation in citations:
        if not isinstance(citation, Citation):
            raise TypeError("citations must contain Citation instances")
        reference: dict[str, XMLValue] = {}
        if citation.authors:
            reference["AUTHORS"] = {"AUTHOR": citation.authors}
        for name, tag in _TAGS.items():
            value = getattr(citation, name)
            if value is not None:
                reference[tag] = value
        references.append(reference)
    return {"CITEDREFERENCESLIST": {"CITATION": references}} if references else {}


def _append(parent: Element, name: str, value: XMLValue) -> None:
    if not isinstance(name, str) or not _TAG_NAME.fullmatch(name):
        raise ValueError("XML element names must be simple valid names without namespace prefixes")
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _append(parent, name, item)
        return
    node = SubElement(parent, name)
    if isinstance(value, Mapping):
        for child_name, child_value in value.items():
            _append(node, child_name, child_value)
    else:
        node.text = _text(value)


def format_extras_xml(elements: Mapping[str, XMLValue]) -> str:
    """Format arbitrary extension elements as a rootless XML fragment.

    Strings become escaped text, mappings become nested elements, lists/tuples
    repeat an element, and None omits it. Insertion order is preserved. Values
    are caller-supplied; no page metadata is extracted or inferred.
    """
    if not isinstance(elements, Mapping):
        raise TypeError("elements must be a mapping of XML tag names to values")
    root = Element("_fragment")
    for name, value in elements.items():
        _append(root, name, value)
    return (
        "".join(tostring(node, encoding="unicode", short_empty_elements=False) for node in root)
        .replace("\t", "&#9;")
        .replace("\r", "&#13;")
        .replace("\n", "&#10;")
    )
