"""Compose prepared English text and explicit metadata into one GKG record."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from typing import TextIO

from .fields.amounts import analyze_amounts
from .fields.counts import CountLocation, analyze_counts
from .fields.dates import analyze_dates
from .fields.gcam import analyze_gcam
from .fields.locations import analyze_locations
from .fields.metadata import (
    RecordMetadata,
    format_optional_extras,
    format_related_images,
    format_sharing_image,
    format_social_image_embeds,
    format_social_video_embeds,
)
from .fields.names import analyze_names
from .fields.ner import NERResult, analyze_entities
from .fields.quotations import analyze_quotations
from .fields.themes import analyze_themes
from .fields.tone import analyze_tone
from .profiles import Resources
from .record import GKGRecord, mapping_row
from .types import NumericDateOrder


class IncompleteGKGWarning(UserWarning):
    """The record contains unavailable fields."""


class IncompleteGKGError(ValueError):
    """Strict generation requires every field to be available."""


COUNT_COLUMNS = ("V1COUNTS", "V2.1COUNTS")
LOCATION_COLUMNS = ("V1LOCATIONS", "V2ENHANCEDLOCATIONS")
THEME_COLUMNS = ("V1THEMES", "V2ENHANCEDTHEMES")
ENTITY_COLUMNS = {
    "V1PERSONS": ("PERSON", False),
    "V2ENHANCEDPERSONS": ("PERSON", True),
    "V1ORGANIZATIONS": ("ORG", False),
    "V2ENHANCEDORGANIZATIONS": ("ORG", True),
}
NER_COLUMNS = (*ENTITY_COLUMNS, *LOCATION_COLUMNS, "V2.1ALLNAMES")
TEXT_COLUMNS = (
    *COUNT_COLUMNS,
    *THEME_COLUMNS,
    *NER_COLUMNS,
    "V1.5TONE",
    "V2.1ENHANCEDDATES",
    "V2GCAM",
    "V2.1QUOTATIONS",
    "V2.1AMOUNTS",
)
METADATA_COLUMNS = (
    "V2.1SHARINGIMAGE",
    "V2.1RELATEDIMAGES",
    "V2.1SOCIALIMAGEEMBEDS",
    "V2.1SOCIALVIDEOEMBEDS",
    "V2EXTRASXML",
)
OVERRIDABLE_COLUMNS = frozenset((*TEXT_COLUMNS, *METADATA_COLUMNS))


def _entity_fields(text, resources, supplied, ner_result, count_locations):
    needs_counts = any(c not in supplied for c in COUNT_COLUMNS)
    needs_locations = any(c not in supplied for c in LOCATION_COLUMNS) or (
        needs_counts and not count_locations
    )
    needs_entities = any(c not in supplied for c in NER_COLUMNS) or needs_locations
    entities = ner_result
    if entities is not None and (not isinstance(entities, NERResult) or entities.text != text):
        raise ValueError("NER result must refer to the supplied body text")
    if entities is None and needs_entities and resources.recognizer is not None:
        entities = analyze_entities(text, recognizer=resources.recognizer)
    values = {}
    for column, (label, enhanced) in ENTITY_COLUMNS.items():
        if column not in supplied:
            values[column] = None if entities is None else entities.to_gkg(label, enhanced=enhanced)
    if "V2.1ALLNAMES" not in supplied:
        values["V2.1ALLNAMES"] = (
            None if entities is None else analyze_names(text, ner=entities).to_gkg()
        )
    locations = None
    if needs_locations and entities is not None:
        locations = analyze_locations(text, ner=entities, gazetteer=resources.places())
    for position, column in enumerate(LOCATION_COLUMNS):
        if column not in supplied:
            values[column] = (
                None if locations is None else locations.to_gkg(enhanced=bool(position))
            )
    if not count_locations and locations is not None:
        count_locations = locations.count_locations
    return values, count_locations


def _paired_fields(text, resources, supplied, count_locations):
    values = {}
    if any(c not in supplied for c in COUNT_COLUMNS):
        counts = analyze_counts(text, locations=count_locations, rules=resources.counts())
        for position, column in enumerate(COUNT_COLUMNS):
            if column not in supplied:
                values[column] = counts.to_gkg(enhanced=bool(position))
    if any(c not in supplied for c in THEME_COLUMNS):
        themes = analyze_themes(text, lexicon=resources.themes())
        for position, column in enumerate(THEME_COLUMNS):
            if column not in supplied:
                values[column] = themes.to_gkg(enhanced=bool(position))
    return values


def _scalar_fields(
    text,
    resources,
    supplied,
    numeric_date_order,
    gcam_disabled_dictionaries,
    original_text,
    original_language,
):
    analyzers = {
        "V1.5TONE": lambda: analyze_tone(text, lexicon=resources.tone()).to_gkg(),
        "V2GCAM": lambda: analyze_gcam(
            text,
            lexicon=resources.gcam(),
            disabled_dictionaries=gcam_disabled_dictionaries,
            original_text=original_text,
            original_language=original_language if original_text is not None else None,
        ).to_gkg(),
        "V2.1ENHANCEDDATES": lambda: analyze_dates(text, numeric_order=numeric_date_order).to_gkg(),
        "V2.1AMOUNTS": lambda: analyze_amounts(text, numeric_order=numeric_date_order).to_gkg(),
        "V2.1QUOTATIONS": lambda: analyze_quotations(text).to_gkg(),
    }
    return {column: analyze() for column, analyze in analyzers.items() if column not in supplied}


def _metadata_fields(metadata, supplied):
    formatters = {
        "V2.1SHARINGIMAGE": lambda: format_sharing_image(metadata.sharing_image),
        "V2.1RELATEDIMAGES": lambda: format_related_images(metadata.related_images),
        "V2.1SOCIALIMAGEEMBEDS": lambda: format_social_image_embeds(metadata.social_image_embeds),
        "V2.1SOCIALVIDEOEMBEDS": lambda: format_social_video_embeds(metadata.social_video_embeds),
        "V2EXTRASXML": lambda: format_optional_extras(metadata.extensions()),
    }
    return {
        column: format_value()
        for column, format_value in formatters.items()
        if column not in supplied
    }


def generate_gkg(
    text: str,
    metadata: RecordMetadata,
    resources: Resources | None = None,
    *,
    overrides: Mapping[str, str | None] | None = None,
    ner_result: NERResult | None = None,
    count_locations: Iterable[CountLocation] = (),
    numeric_date_order: NumericDateOrder | None = None,
    gcam_disabled_dictionaries: Iterable[int | str] = (),
    gcam_original_text: str | None = None,
    strict: bool = False,
) -> GKGRecord:
    """Analyze prepared English text. Enhanced offsets index this exact body.

    Translate separately and copy language and engine values with RecordMetadata.from_translation.
    Overrides replace output cells, not dependencies needed by other fields.
    None marks unavailable fields; an empty string marks an available empty result.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if not isinstance(metadata, RecordMetadata):
        raise TypeError("metadata must be RecordMetadata")
    resources = Resources() if resources is None else resources
    if not isinstance(resources, Resources):
        raise TypeError("resources must be Resources")
    if numeric_date_order not in (None, "mdy", "dmy"):
        raise ValueError("numeric_date_order must be mdy, dmy, or None")
    supplied = dict(overrides or {})
    if unknown := supplied.keys() - OVERRIDABLE_COLUMNS:
        raise ValueError(f"Unsupported overrides keys: {sorted(unknown)}")
    values = metadata.to_mapping()
    entities, locations = _entity_fields(
        text, resources, supplied, ner_result, tuple(count_locations)
    )
    values.update(entities)
    values.update(_paired_fields(text, resources, supplied, locations))
    values.update(
        _scalar_fields(
            text,
            resources,
            supplied,
            numeric_date_order,
            gcam_disabled_dictionaries,
            gcam_original_text,
            metadata.source_language,
        )
    )
    values.update(_metadata_fields(metadata, supplied))
    values.update(supplied)
    record = GKGRecord.from_mapping(values)
    missing = [column for column, value in record.items() if value is None]
    if missing:
        message = f"Unavailable GKG fields: {', '.join(missing)}"
        if strict:
            raise IncompleteGKGError(message)
        warnings.warn(message, IncompleteGKGWarning, stacklevel=2)
    return record


def serialize_gkg(record: Mapping[str, str | None], *, allow_incomplete: bool = False) -> str:
    """Return one validated, unquoted 27-column TSV line with a final newline."""
    return "\t".join(mapping_row(record, allow_incomplete=allow_incomplete)) + "\n"


def write_gkg(
    records: Iterable[Mapping[str, str | None]], stream: TextIO, *, allow_incomplete: bool = False
) -> int:
    """Write headerless rows; earlier rows remain written if a later row fails."""
    count = 0
    for record in records:
        stream.write(serialize_gkg(record, allow_incomplete=allow_incomplete))
        count += 1
    return count
