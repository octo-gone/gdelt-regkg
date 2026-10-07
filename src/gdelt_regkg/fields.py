"""Independent scalar field functions.

Return wire-format strings from prepared text or supplied metadata.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from numbers import Integral
from urllib.parse import urlsplit

from .amounts import analyze_amounts
from .counts import CountLocation, CountRules, analyze_counts
from .dates import analyze_dates
from .extras import XMLValue, format_extras_xml
from .gcam import GCAMLexicon, analyze_gcam
from .locations import Gazetteer, analyze_locations
from .names import analyze_names
from .ner import EntityMention, EntityRecognizer, NERResult, analyze_entities
from .quotations import analyze_quotations
from .themes import ThemeLexicon, analyze_themes
from .tone import ToneLexicon, analyze_tone
from .wire import text_component


def _cell(value: str) -> str:
    if not isinstance(value, str):
        raise TypeError("Expected a string; normalize missing values before extraction")
    if any(c in value for c in "\t\r\n"):
        raise ValueError("GKG cells cannot contain tabs or newlines")
    return value


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
    """Format supplied machine-translation provenance; does not translate.

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


def extract_counts(
    text: str, *, locations: Iterable[CountLocation] = (), rules: CountRules | None = None
) -> str:
    """Extract counts using bundled event rules; unresolved geography uses type 0."""
    return analyze_counts(text, locations=locations, rules=rules).to_gkg()


def extract_enhanced_counts(
    text: str, *, locations: Iterable[CountLocation] = (), rules: CountRules | None = None
) -> str:
    """Count tuples plus original-text number offset; no ADM2 field."""
    return analyze_counts(text, locations=locations, rules=rules).to_gkg(enhanced=True)


def extract_themes(text: str, *, lexicon: ThemeLexicon | None = None) -> str:
    """Distinct matched themes from locally prepared theme rules."""
    return analyze_themes(text, lexicon=lexicon).to_gkg()


def extract_enhanced_themes(text: str, *, lexicon: ThemeLexicon | None = None) -> str:
    """Theme,offset per mention; zero-based original-text character offsets."""
    return analyze_themes(text, lexicon=lexicon).to_gkg(enhanced=True)


def extract_locations(
    text: str,
    *,
    recognizer: EntityRecognizer | None = None,
    ner: NERResult | None = None,
    gazetteer: Gazetteer | None = None,
) -> str:
    """Resolve distinct observed place names into seven geographic components."""
    return analyze_locations(text, recognizer=recognizer, ner=ner, gazetteer=gazetteer).to_gkg()


def extract_enhanced_locations(
    text: str,
    *,
    recognizer: EntityRecognizer | None = None,
    ner: NERResult | None = None,
    gazetteer: Gazetteer | None = None,
) -> str:
    """Every resolved place mention, with ADM2 and unchanged-body offset."""
    return analyze_locations(text, recognizer=recognizer, ner=ner, gazetteer=gazetteer).to_gkg(
        enhanced=True
    )


def extract_persons(text: str, *, recognizer: EntityRecognizer | None = None) -> str:
    """Distinct recognized person names, in first-mention order."""
    return analyze_entities(text, recognizer=recognizer).to_gkg("PERSON")


def extract_enhanced_persons(text: str, *, recognizer: EntityRecognizer | None = None) -> str:
    """Person,offset for each mention, using original-text character offsets."""
    return analyze_entities(text, recognizer=recognizer).to_gkg("PERSON", enhanced=True)


def extract_organizations(text: str, *, recognizer: EntityRecognizer | None = None) -> str:
    """Distinct recognized organization names, in first-mention order."""
    return analyze_entities(text, recognizer=recognizer).to_gkg("ORG")


def extract_enhanced_organizations(text: str, *, recognizer: EntityRecognizer | None = None) -> str:
    """Organization,offset for each mention, using original-text coordinates."""
    return analyze_entities(text, recognizer=recognizer).to_gkg("ORG", enhanced=True)


def extract_location_mentions(
    text: str, *, recognizer: EntityRecognizer | None = None
) -> tuple[EntityMention, ...]:
    """Recognize place mentions without geographic codes or coordinates."""
    return analyze_entities(text, recognizer=recognizer).locations


def extract_tone(text: str, *, lexicon: ToneLexicon | None = None) -> str:
    """Return all seven tone components using a documented GI approximation.

    English text is expected by default. This is dictionary word-frequency
    scoring, not an exact reproduction of GDELT. See docs/fields/tone.md.
    """
    return analyze_tone(text, lexicon=lexicon).to_gkg()


def extract_enhanced_dates(text: str, *, numeric_order: str | None = None) -> str:
    """Explicit English dates; absent components stay zero, resolutions 1–4."""
    return analyze_dates(text, numeric_order=numeric_order).to_gkg()


def extract_gcam(text: str, *, lexicon: GCAMLexicon | None = None) -> str:
    """Minimal GCAM count subset; wc first, sparse native c keys afterward."""
    return analyze_gcam(text, lexicon=lexicon).to_gkg()


def format_related_images(urls: Iterable[str] | None) -> str | None:
    """Format caller-selected article image URLs, preserving order and duplicates."""
    return _media_urls(urls)


def format_social_image_embeds(urls: Iterable[str] | None) -> str | None:
    """Format supplied social-post URLs; the caller determines image content."""
    return _media_urls(urls)


def format_social_video_embeds(urls: Iterable[str] | None) -> str | None:
    """Format supplied video URLs; the caller identifies and normalizes embeds."""
    return _media_urls(urls)


# Compatibility names accept the same prepared metadata as the formatters.
extract_sharing_image = format_sharing_image
extract_related_images = format_related_images
extract_social_image_embeds = format_social_image_embeds
extract_social_video_embeds = format_social_video_embeds


def extract_quotations(text: str) -> str:
    """Quoted spans and nearby reporting verbs as offset|length|verb|quote."""
    return analyze_quotations(text).to_gkg()


def extract_all_names(
    text: str, *, recognizer: EntityRecognizer | None = None, ner: NERResult | None = None
) -> str:
    """Broad surface names, including events, laws and products; name,offset."""
    return analyze_names(text, recognizer=recognizer, ner=ner).to_gkg()


def extract_amounts(text: str, *, numeric_order: str | None = None) -> str:
    """Exact English quantities and objects; percentages and dates excluded."""
    return analyze_amounts(text, numeric_order=numeric_order).to_gkg()


def extract_extras_xml(elements: Mapping[str, XMLValue] | None) -> str | None:
    """Format supplied elements; None means metadata unavailable, {} means empty.

    This field does not extract data from article text or HTML.
    """
    return None if elements is None else format_extras_xml(elements)
