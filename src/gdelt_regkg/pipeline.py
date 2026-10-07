"""Optional composition and tab-delimited export of independent fields."""

from __future__ import annotations

import warnings
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import TextIO

from . import fields
from .config import ExtractionConfig
from .counts import CountLocation, CountRules, analyze_counts, default_count_rules
from .extras import XMLValue
from .gcam import GCAMLexicon, default_gcam_lexicon
from .language import LanguageDetector
from .locations import Gazetteer, analyze_locations, default_gazetteer
from .names import analyze_names
from .ner import EntityRecognizer, NERResult, analyze_entities
from .themes import ThemeLexicon, analyze_themes, default_theme_lexicon
from .tone import ToneLexicon, default_tone_lexicon
from .translation import Translator, translate_text
from .utils import GKG_COLUMNS


class IncompleteGKGWarning(UserWarning):
    """The record contains unavailable or unimplemented fields."""


# Scalar extractors are resolved by name; counts/themes share one analysis per pair.
TEXT_EXTRACTORS = {
    "V1COUNTS": "extract_counts",
    "V2.1COUNTS": "extract_enhanced_counts",
    "V1THEMES": "extract_themes",
    "V2ENHANCEDTHEMES": "extract_enhanced_themes",
    "V1LOCATIONS": "extract_locations",
    "V2ENHANCEDLOCATIONS": "extract_enhanced_locations",
    "V1PERSONS": "extract_persons",
    "V2ENHANCEDPERSONS": "extract_enhanced_persons",
    "V1ORGANIZATIONS": "extract_organizations",
    "V2ENHANCEDORGANIZATIONS": "extract_enhanced_organizations",
    "V1.5TONE": "extract_tone",
    "V2.1ENHANCEDDATES": "extract_enhanced_dates",
    "V2GCAM": "extract_gcam",
    "V2.1QUOTATIONS": "extract_quotations",
    "V2.1ALLNAMES": "extract_all_names",
    "V2.1AMOUNTS": "extract_amounts",
}


def generate_gkg(
    text: str,
    *,
    identifier: str,
    published_at: datetime | str | int | None = None,
    batch_time: datetime | str | int,
    sequence: int,
    source_collection: int = 1,
    source_name: str | None = None,
    sharing_image: str | None = None,
    related_images: Iterable[str] | None = None,
    social_image_embeds: Iterable[str] | None = None,
    social_video_embeds: Iterable[str] | None = None,
    source_language: str | None = None,
    translation_engine: str | None = None,
    input_language: str | None = None,
    translator: Translator | None = None,
    detect_missing_language: bool = True,
    language_detector: LanguageDetector | None = None,
    language_check: str = "script",
    field_values: Mapping[str, str | None] | None = None,
    tone_lexicon: ToneLexicon | None = None,
    resources_dir=None,
    config: ExtractionConfig | None = None,
    theme_lexicon: ThemeLexicon | None = None,
    count_rules: CountRules | None = None,
    count_locations: Iterable[CountLocation] = (),
    gazetteer: Gazetteer | None = None,
    gcam_lexicon: GCAMLexicon | None = None,
    numeric_date_order: str | None = None,
    extras: Mapping[str, XMLValue] | None = None,
    ner: EntityRecognizer | NERResult | None = None,
    strict: bool = False,
) -> dict[str, str | None]:
    """Assemble one record, retaining None for work not done.

    field_values supplies already encoded extraction results, e.g. from an
    external model. Metadata is supplied through the explicit parameters.
    strict=True rejects any remaining None; otherwise emit one warning.
    This scaffold does not enforce GDELT's minimum inclusion criteria.
    Themes and counts are analyzed once per pair of legacy/enhanced fields.
    Both pairs are approximations; see their standalone analyze_* results for
    provenance and count diagnostics (not representable in GKG cells).
    config supplies both profiles; explicit theme_lexicon/count_rules override
    their respective section. field_values overrides still take precedence.
    resources_dir selects local profiles; explicit profile objects take precedence.
    Media URLs and extras are supplied metadata. text is the prepared article
    body used for NLP; metadata collection is the caller's responsibility.
    ner enables a shared entity analysis or supplies a result for this text.
    Without ner, person, organization, location and all-name fields remain unavailable.
    Gazetteer resolution shares that analysis; resolved mentions supply count
    geography when count_locations is empty. gcam_lexicon overrides the minimal
    locally prepared GCAM subset independently of tone. numeric_date_order optionally
    resolves ambiguous slash dates, consistently for dates and amounts.
    batch_time supplies both V2.1DATE and the record ID timestamp. Optional
    published_at supplies the available publication time for extras XML only;
    a caller-supplied PAGE_PRECISEPUBTIMESTAMP takes precedence.
    translator enables optional translation to English before NLP; missing
    input_language is detected locally unless detect_missing_language=False.
    Enhanced offsets then index the translated body; use the
    standalone translate_text result when the analyzed body must be retained.
    """
    if not isinstance(text, str):
        raise TypeError("text must be str")
    if translator is not None:
        result = translate_text(
            text,
            language=input_language,
            translator=translator,
            detect_missing_language=detect_missing_language,
            language_detector=language_detector,
            language_check=language_check,
        )
        if result.translated:
            if source_language is not None or translation_engine is not None:
                raise ValueError(
                    "Automatic translation supplies provenance; do not also supply source_language/translation_engine"
                )
            if isinstance(ner, NERResult):
                raise ValueError("Analyze translated text before supplying precomputed NER spans")
            count_locations = tuple(count_locations)
            if count_locations:
                raise ValueError(
                    "Count location offsets must refer to the translated text; translate separately first"
                )
            text, source_language, translation_engine = (
                result.text,
                result.source_language,
                result.engine,
            )
    if config is not None:
        if not isinstance(config, ExtractionConfig):
            raise TypeError("config must be ExtractionConfig")
        theme_lexicon = config.theme_lexicon if theme_lexicon is None else theme_lexicon
        count_rules = config.count_rules if count_rules is None else count_rules
    supplied = dict(field_values or {})
    batch_stamp = fields.format_date(batch_time)
    if published_at is not None:
        publication_stamp = fields.format_date(published_at)
        if publication_stamp != "0":
            extras = dict(extras or {})
            extras.setdefault("PAGE_PRECISEPUBTIMESTAMP", publication_stamp)
    metadata = (
        ("V2.1SHARINGIMAGE", lambda: fields.format_sharing_image(sharing_image)),
        ("V2.1RELATEDIMAGES", lambda: fields.format_related_images(related_images)),
        ("V2.1SOCIALIMAGEEMBEDS", lambda: fields.format_social_image_embeds(social_image_embeds)),
        ("V2.1SOCIALVIDEOEMBEDS", lambda: fields.format_social_video_embeds(social_video_embeds)),
        ("V2EXTRASXML", lambda: fields.extract_extras_xml(extras)),
    )
    allowed = set(TEXT_EXTRACTORS) | {column for column, _ in metadata}
    if unknown := supplied.keys() - allowed:
        raise ValueError(f"Unsupported field_values keys: {sorted(unknown)}")
    translation = fields.format_translation_info(source_language, translation_engine)
    record: dict[str, str | None] = {
        "GKGRECORDID": fields.format_record_id(batch_stamp, sequence, translated=bool(translation)),
        "V2.1DATE": batch_stamp,
        "V2SOURCECOLLECTIONIDENTIFIER": fields.format_source_collection(source_collection),
        "V2SOURCECOMMONNAME": fields.source_common_name(identifier, name=source_name),
        "V2DOCUMENTIDENTIFIER": fields.document_identifier(identifier),
        "V2.1TRANSLATIONINFO": translation,
    }
    # Analyze a pair only if at least one partner is not overridden. Preserve
    # independent overrides, and do not consume location iterators twice.
    paired = {}
    entity_columns = {
        "V1PERSONS": ("PERSON", False),
        "V2ENHANCEDPERSONS": ("PERSON", True),
        "V1ORGANIZATIONS": ("ORG", False),
        "V2ENHANCEDORGANIZATIONS": ("ORG", True),
    }
    location_columns = ("V1LOCATIONS", "V2ENHANCEDLOCATIONS")
    ner_columns = set(entity_columns) | set(location_columns) | {"V2.1ALLNAMES"}
    if any(column not in supplied for column in ner_columns):
        entities = None
        if ner is not None:
            entities = ner if isinstance(ner, NERResult) else analyze_entities(text, recognizer=ner)
            if entities.text != text:
                raise ValueError("NER result must refer to the supplied body text")
        for column, (label, enhanced) in entity_columns.items():
            if column not in supplied:
                paired[column] = (
                    None if entities is None else entities.to_gkg(label, enhanced=enhanced)
                )
        if "V2.1ALLNAMES" not in supplied:
            paired["V2.1ALLNAMES"] = (
                None if entities is None else analyze_names(text, ner=entities).to_gkg()
            )
        if any(column not in supplied for column in location_columns):
            if entities is not None and gazetteer is None:
                gazetteer = default_gazetteer(resources_dir)
            locations = (
                None
                if entities is None
                else analyze_locations(text, ner=entities, gazetteer=gazetteer)
            )
            for position, column in enumerate(location_columns):
                if column not in supplied:
                    paired[column] = (
                        None if locations is None else locations.to_gkg(enhanced=bool(position))
                    )
            count_locations = tuple(count_locations)
            if not count_locations and locations is not None:
                count_locations = locations.count_locations
    count_columns = ("V1COUNTS", "V2.1COUNTS")
    if not all(column in supplied for column in count_columns):
        if count_rules is None:
            count_rules = default_count_rules(resources_dir)
        counts = analyze_counts(text, locations=count_locations, rules=count_rules)
        for position, column in enumerate(count_columns):
            if column not in supplied:
                paired[column] = counts.to_gkg(enhanced=bool(position))
    theme_columns = ("V1THEMES", "V2ENHANCEDTHEMES")
    if not all(column in supplied for column in theme_columns):
        if theme_lexicon is None:
            theme_lexicon = default_theme_lexicon(resources_dir)
        themes = analyze_themes(text, lexicon=theme_lexicon)
        for position, column in enumerate(theme_columns):
            if column not in supplied:
                paired[column] = themes.to_gkg(enhanced=bool(position))
    for column, function_name in TEXT_EXTRACTORS.items():
        if column in supplied:
            record[column] = supplied[column]
            continue
        if column in paired:
            record[column] = paired[column]
            continue
        try:
            if column == "V1.5TONE":
                if tone_lexicon is None:
                    tone_lexicon = default_tone_lexicon(resources_dir)
                record[column] = fields.extract_tone(text, lexicon=tone_lexicon)
            elif column == "V2GCAM":
                if gcam_lexicon is None:
                    gcam_lexicon = default_gcam_lexicon(resources_dir)
                record[column] = fields.extract_gcam(text, lexicon=gcam_lexicon)
            elif column == "V2.1ENHANCEDDATES":
                record[column] = fields.extract_enhanced_dates(
                    text, numeric_order=numeric_date_order
                )
            elif column == "V2.1AMOUNTS":
                record[column] = fields.extract_amounts(text, numeric_order=numeric_date_order)
            else:
                record[column] = getattr(fields, function_name)(text)
        except NotImplementedError:
            record[column] = None
    for column, formatter in metadata:
        record[column] = supplied[column] if column in supplied else formatter()
    record = {column: record[column] for column in GKG_COLUMNS}
    for value in record.values():
        if value is not None:
            fields._cell(value)
    missing = [column for column, value in record.items() if value is None]
    if missing:
        message = f"Unavailable or unimplemented GKG fields: {', '.join(missing)}"
        if strict:
            raise NotImplementedError(message)
        warnings.warn(message, IncompleteGKGWarning, stacklevel=2)
    return record


def serialize_gkg(record: Mapping[str, str | None], *, allow_incomplete: bool = False) -> str:
    """Return one unquoted 27-column TSV line, including its final newline.

    Explicitly allow incomplete records to convert None to empty cells. This
    loses the distinction between 'not extracted' and 'no matches' on disk.
    Internal subfield syntax of caller-supplied values is not validated.
    """
    if set(record) != set(GKG_COLUMNS):
        raise ValueError("Record keys must exactly match GKG_COLUMNS")
    cells = []
    for column in GKG_COLUMNS:
        value = record[column]
        if value is None:
            if not allow_incomplete:
                raise ValueError(
                    f"{column} is unavailable; use allow_incomplete=True for a scaffold export"
                )
            value = ""
        cells.append(fields._cell(value))
    return "\t".join(cells) + "\n"


def write_gkg(
    records: Iterable[Mapping[str, str | None]],
    stream: TextIO,
    *,
    allow_incomplete: bool = False,
) -> int:
    """Stream headerless GKG rows to a caller-owned UTF-8 text file.

    Returns the number written. Earlier rows remain written if a later row fails.
    """
    count = 0
    for record in records:
        stream.write(serialize_gkg(record, allow_incomplete=allow_incomplete))
        count += 1
    return count
