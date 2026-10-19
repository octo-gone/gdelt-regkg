"""Format caller-supplied document metadata without extracting article text."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from numbers import Integral
from urllib.parse import urlsplit

from ..record import cell as _cell
from ..wire import text_component
from .extras import XMLValue, format_extras_xml
from .translation import TranslationResult, normalize_language


def format_date(value: datetime | str | int | None) -> str:
    """Format a UTC timestamp as YYYYMMDDHHMMSS; None/0 means unknown.

    Aware datetimes are converted to UTC; naive datetimes are treated as UTC.
    Strings must already contain exactly fourteen ASCII digits (or '0').
    """
    if value is None:
        return "0"
    if isinstance(value, datetime):
        if value.utcoffset() is not None:
            value = value.astimezone(timezone.utc)
        return f"{value.year:04d}{value.month:02d}{value.day:02d}{value.hour:02d}{value.minute:02d}{value.second:02d}"
    if isinstance(value, bool) or not isinstance(value, (str, Integral)):
        raise TypeError("Expected datetime, compact timestamp, integer, or None")
    result = str(value)
    if result == "0":
        return result
    if not re.fullmatch(r"[0-9]{14}", result):
        raise ValueError("Date must be YYYYMMDDHHMMSS or 0")
    # Parsing rejects impossible calendar dates before formatting the result.
    return format_date(datetime.strptime(result, "%Y%m%d%H%M%S"))


def format_record_id(
    batch_time: datetime | str | int, sequence: int, *, translated: bool = False
) -> str:
    """Build a local record ID from batch time and caller-managed sequence.

    The caller owns uniqueness; these IDs are not assigned by GDELT.
    Batch time is separate from the document's publication time.
    """
    stamp = format_date(batch_time)
    if stamp == "0":
        raise ValueError("Record IDs require a known batch timestamp")
    if isinstance(sequence, bool) or not isinstance(sequence, Integral) or sequence < 1:
        raise ValueError("Sequence must be a positive integer")
    if not isinstance(translated, bool):
        raise TypeError("translated must be bool")
    return f"{stamp}-{'T' if translated else ''}{sequence}"


def format_source_collection(value: int = 1) -> str:
    """1 web, 2 citation, 3 CORE, 4 DTIC, 5 JSTOR, 6 nontextual source."""
    if isinstance(value, bool) or not isinstance(value, Integral) or value not in range(1, 7):
        raise ValueError("Source collection must be an integer from 1 through 6")
    return str(value)


def source_common_name(identifier: str, *, name: str | None = None) -> str:
    """Use an explicit source label, otherwise extract a web URL's hostname.

    Keeps subdomains; registrable-domain normalization is not implemented.
    Offline sources should always supply name explicitly.
    """
    if name is not None:
        return _cell(name)
    parsed = urlsplit(_cell(identifier))
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Supply an HTTP(S) URL or an explicit source name")
    return parsed.hostname.lower()


def document_identifier(value: str) -> str:
    """Preserve a supplied URL, DOI, or citation without fetching it."""
    value = _cell(value)
    if not value.strip():
        raise ValueError("Document identifier must not be empty")
    return value


def format_translation_info(source_language: str | None = None, engine: str | None = None) -> str:
    """Format the source language and translation engine; does not translate.

    Supply both an ISO 639-2 code and an engine citation, or neither.
    Only the code's shape is checked, not membership in ISO 639-2.
    """
    if source_language is None and engine is None:
        return ""
    if not isinstance(source_language, str) or not re.fullmatch(r"[a-z]{3}", source_language):
        raise ValueError("Source language must be a lowercase three-letter ISO 639-2 code")
    if not isinstance(engine, str):
        raise ValueError("Provide a nonempty engine citation")
    engine = text_component(engine, separators=";")
    if not engine:
        raise ValueError("Provide a nonempty engine citation")
    return f"srclc:{source_language};eng:{engine}"


def _media_url(value: str) -> str:
    value = _cell(value)
    parsed = urlsplit(value)
    if (
        parsed.scheme.lower() not in {"http", "https"}
        or not parsed.hostname
        or any(c.isspace() for c in value)
    ):
        raise ValueError("Media URLs must be absolute HTTP(S) URLs without whitespace")
    return value


def format_sharing_image(url: str | None) -> str | None:
    """Format a supplied image URL; None is unavailable and '' means no image."""
    return url if url is None or url == "" else _media_url(url)


def _media_urls(urls: Iterable[str] | None) -> str | None:
    if urls is None:
        return None
    if isinstance(urls, str):
        raise TypeError("Supply a collection of URLs, not an encoded cell")
    values = []
    for url in urls:
        url = _media_url(url)
        values.append(url.replace(";", "%3B"))
    return ";".join(values)


def format_related_images(urls: Iterable[str] | None) -> str | None:
    """Format caller-selected article image URLs, preserving order and duplicates."""
    return _media_urls(urls)


def format_social_image_embeds(urls: Iterable[str] | None) -> str | None:
    """Format supplied social-post URLs; the caller determines image content."""
    return _media_urls(urls)


def format_social_video_embeds(urls: Iterable[str] | None) -> str | None:
    """Format supplied video URLs; the caller identifies and normalizes embeds."""
    return _media_urls(urls)


Timestamp = datetime | str | int


def format_optional_extras(elements: Mapping[str, XMLValue] | None) -> str | None:
    return None if elements is None else format_extras_xml(elements)


@dataclass(frozen=True)
class RecordMetadata:
    identifier: str
    batch_time: Timestamp
    sequence: int
    published_at: Timestamp | None = None
    source_collection: int = 1
    source_name: str | None = None
    sharing_image: str | None = None
    related_images: Iterable[str] | None = None
    social_image_embeds: Iterable[str] | None = None
    social_video_embeds: Iterable[str] | None = None
    extras: Mapping[str, XMLValue] | None = None
    source_language: str | None = None
    translation_engine: str | None = None

    @classmethod
    def from_translation(
        cls, result: TranslationResult, metadata: RecordMetadata
    ) -> RecordMetadata:
        """Copy translation metadata; enhanced offsets must index result.text."""
        if not isinstance(result, TranslationResult) or not isinstance(metadata, cls):
            raise TypeError("Expected TranslationResult and RecordMetadata")
        language = normalize_language(result.source_language)
        translation_info = (language, result.engine) if language != "eng" else (None, None)
        if (metadata.source_language, metadata.translation_engine) not in (
            (None, None),
            translation_info,
        ):
            raise ValueError(
                "Existing metadata conflicts with the source language or translation engine"
            )
        format_translation_info(*translation_info)
        return replace(
            metadata, source_language=translation_info[0], translation_engine=translation_info[1]
        )

    def to_mapping(self) -> dict[str, str | None]:
        stamp = format_date(self.batch_time)
        translation = format_translation_info(self.source_language, self.translation_engine)
        return {
            "GKGRECORDID": format_record_id(stamp, self.sequence, translated=bool(translation)),
            "V2.1DATE": stamp,
            "V2SOURCECOLLECTIONIDENTIFIER": format_source_collection(self.source_collection),
            "V2SOURCECOMMONNAME": source_common_name(self.identifier, name=self.source_name),
            "V2DOCUMENTIDENTIFIER": document_identifier(self.identifier),
            "V2.1TRANSLATIONINFO": translation,
        }

    def extensions(self) -> Mapping[str, XMLValue] | None:
        extras = self.extras
        if self.published_at is not None:
            stamp = format_date(self.published_at)
            if stamp != "0":
                extras = dict(extras or {})
                extras.setdefault("PAGE_PRECISEPUBTIMESTAMP", stamp)
        return extras
