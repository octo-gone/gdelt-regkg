"""Generate predictions from saved bodies using the library's extraction API."""

import hashlib
import json
import warnings

from gdelt_regkg import (
    EntityMention,
    IncompleteGKGWarning,
    NameMention,
    NERResult,
    SpacyNER,
    generate_gkg,
)
from gdelt_regkg.fields.ner import default_name_rules
from gdelt_regkg.pipeline import TEXT_EXTRACTORS
from gdelt_regkg.utils import GKG_COLUMNS

from .inputs import iter_lines, resolve_inputs
from .model import FIELD_NAMES, GKGRow

NER_FIELDS = {
    "counts",
    "enhanced_counts",
    "persons",
    "enhanced_persons",
    "organizations",
    "enhanced_organizations",
    "locations",
    "enhanced_locations",
    "all_names",
}


def load_corpus(paths, *, report, include_translated=False):
    rows: dict[tuple, dict] = {}
    for path in resolve_inputs(paths, corpus=True):
        for origin, line, is_json in iter_lines(path):
            if not line.strip():
                continue
            if not is_json:
                raise ValueError("--corpus requires saved JSONL article bodies")
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{origin}: saved article must be an object")
            if row.get("status", "ok") != "ok" or not isinstance(row.get("text"), str):
                report.note("corpus", "body", "unavailable")
                continue
            if row.get("translation_pending"):
                report.note("corpus", "body", "translation_pending")
                continue
            if row.get("translated") and not include_translated:
                report.note("corpus", "body", "excluded_translated")
                continue
            document = row.get("url", row.get("document"))
            if not document:
                raise ValueError(f"{origin}: saved article requires url or document")
            checksum = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
            if row.get("text_sha256", checksum) != checksum:
                raise ValueError(f"{origin}: saved body checksum mismatch")
            key = row.get("record_id", row.get("recordid")), document
            if key in rows and rows[key]["text"] != row["text"]:
                raise ValueError(f"{origin}: conflicting saved bodies for {document}")
            rows[key] = row | {"text_sha256": checksum, "document": document}
    if not rows:
        raise ValueError("No usable saved article bodies")
    return rows


def generate_predictions(
    corpus,
    references,
    *,
    fields,
    report,
    resources_dir,
    ner_model="en_core_web_sm",
    ner_cache=None,
    gcam_lexicon=None,
    numeric_date_order=None,
    progress=print,
):
    selected = set(fields)
    needs_ner = bool(selected & NER_FIELDS)
    cached: dict[tuple, dict] = {}
    recognizer = None
    name_rules = None
    if needs_ner:
        if ner_cache is not None:
            for origin, line, is_json in iter_lines(ner_cache):
                if not line.strip():
                    continue
                if not is_json:
                    raise ValueError("--ner-cache requires JSONL")
                row = json.loads(line)
                if not isinstance(row, dict) or not isinstance(row.get("entity_mentions"), list):
                    raise ValueError(f"{origin}: cached NER requires an entity_mentions list")
                identity = (
                    row.get("record_id", row.get("recordid")),
                    row.get("url", row.get("document")),
                )
                if identity in cached and cached[identity] != row:
                    raise ValueError(f"{origin}: conflicting cached NER records")
                cached[identity] = row
            name_rules = default_name_rules(resources_dir)
        else:
            progress(f"[benchmark] Loading NER model {ner_model}")
            recognizer = SpacyNER.from_model(ner_model, resources_dir=resources_dir)
    anonymous_bodies = {
        document: article for (record, document), article in corpus.items() if record is None
    }
    predictions = []
    for index, reference in enumerate(references, 1):
        identity = reference.get("recordid"), reference.get("document")
        article = corpus.get(identity)
        if article is None:
            article = anonymous_bodies.get(identity[1])
            if article is None:
                report.note("corpus", "alignment", "missing_body")
                continue
        text = article["text"]
        ner = None
        broad_names = True
        if needs_ner:
            if ner_cache is not None:
                row = cached.get(identity)
                if row is None or row.get("text_sha256") != article["text_sha256"]:
                    raise ValueError(f"Missing or mismatched cached NER for {identity}")
                broad_names = row.get("name_mentions") is not None
                ner = NERResult(
                    text,
                    tuple(EntityMention(**value) for value in row["entity_mentions"]),
                    backend_name=row.get("ner_backend", "cached-ner"),
                    name_policy="gdelt-full-names",
                    name_rules=name_rules,
                    name_mentions=tuple(NameMention(**value) for value in row["name_mentions"])
                    if broad_names
                    else None,
                )
            else:
                assert recognizer is not None
                ner = recognizer.analyze(text)
        supplied_fields = {
            "sharing_image",
            "related_images",
            "social_image_embeds",
            "social_video_embeds",
            "extras_xml",
        }
        overridable = set(TEXT_EXTRACTORS) | {
            "V2.1SHARINGIMAGE",
            "V2.1RELATEDIMAGES",
            "V2.1SOCIALIMAGEEMBEDS",
            "V2.1SOCIALVIDEOEMBEDS",
            "V2EXTRASXML",
        }
        overrides = {
            column: ""
            for field, column in zip(FIELD_NAMES, GKG_COLUMNS)
            if field not in selected and column in overridable
        }
        if selected & {"counts", "enhanced_counts"}:
            # Count geography depends on resolving the shared NER locations.
            overrides.pop("V1LOCATIONS", None)
            overrides.pop("V2ENHANCEDLOCATIONS", None)
        # Media and extension values must be caller-supplied, not copied from the reference.
        for field, column in zip(FIELD_NAMES, GKG_COLUMNS):
            if (
                field in selected
                and field in supplied_fields
                and isinstance(article.get(field), str)
            ):
                overrides[column] = article[field]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            result = generate_gkg(
                text,
                identifier=reference.get("document"),
                batch_time=reference.get("date"),
                sequence=1,
                source_collection=int(reference.get("source_collection") or "1"),
                source_name=reference.get("source"),
                field_values=overrides,
                resources_dir=resources_dir,
                ner=ner,
                gcam_lexicon=gcam_lexicon,
                numeric_date_order=numeric_date_order,
                detect_missing_language=False,
            )
        values = dict(zip(FIELD_NAMES, (result[column] for column in GKG_COLUMNS)))
        for name in ("recordid", "date", "source_collection", "source", "document"):
            values[name] = reference.get(name)
        for name in FIELD_NAMES:
            if name not in selected and name not in {
                "recordid",
                "date",
                "source_collection",
                "source",
                "document",
            }:
                values[name] = None
        if not broad_names:
            values["all_names"] = None
        # Translated cached bodies do not supply translation-engine provenance by inference.
        if "translation" in selected:
            values["translation"] = article.get("translation", article.get("translation_info"))
        predictions.append(GKGRow(values, article.get("url", article["document"])))
        if index % 100 == 0 or index == len(references):
            progress(f"[benchmark] Generated {index}/{len(references)} predictions")
    return predictions
