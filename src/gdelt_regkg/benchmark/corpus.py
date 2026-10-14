"""Generate predictions from saved bodies using the library's extraction API."""

import hashlib
import json
import warnings
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any

from gdelt_regkg import IncompleteGKGWarning, RecordMetadata, Resources, generate_gkg
from gdelt_regkg.fields.gcam import GCAMLexicon
from gdelt_regkg.fields.ner import (
    EntityMention,
    NameMention,
    NERResult,
    SpacyNER,
    default_name_rules,
)
from gdelt_regkg.pipeline import TEXT_COLUMNS
from gdelt_regkg.types import NumericDateOrder, StrPath
from gdelt_regkg.utils import GKG_COLUMNS

from .checkpoint import article_signature
from .inputs import iter_lines, resolve_inputs
from .model import FIELD_NAMES, GKGRow

BODY_KEYS = {
    "url",
    "document",
    "record_id",
    "recordid",
    "status",
    "text",
    "text_sha256",
    "translated",
    "translation_pending",
    "translation",
    "translation_info",
    "sharing_image",
    "related_images",
    "social_image_embeds",
    "social_video_embeds",
    "extras_xml",
}
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


def load_corpus(paths, *, report, include_translated=False, destination=None):
    rows = {} if destination is None else destination
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
            if row.get("translated") and (not include_translated):
                report.note("corpus", "body", "excluded_translated")
                continue
            document = row.get("url", row.get("document"))
            if not document:
                raise ValueError(f"{origin}: saved article requires url or document")
            checksum = hashlib.sha256(row["text"].encode("utf-8")).hexdigest()
            if row.get("text_sha256", checksum) != checksum:
                raise ValueError(f"{origin}: saved body checksum mismatch")
            key = (row.get("record_id", row.get("recordid")), document)
            if key in rows and rows[key]["text"] != row["text"]:
                raise ValueError(f"{origin}: conflicting saved bodies for {document}")
            rows[key] = {k: v for k, v in row.items() if k in BODY_KEYS} | {
                "text_sha256": checksum,
                "document": document,
            }
    if not rows:
        raise ValueError("No usable saved article bodies")
    return rows


@dataclass(frozen=True)
class PredictionOptions:
    fields: tuple[str, ...]
    resources_dir: StrPath | None = None
    ner_model: str = "en_core_web_sm"
    ner_cache: Path | None = None
    gcam_lexicon: GCAMLexicon | None = None
    numeric_date_order: NumericDateOrder | None = None
    batch_size: int = 16
    batch_chars: int = 100000

    def __post_init__(self):
        object.__setattr__(self, "fields", tuple(self.fields))
        if (
            type(self.batch_size) is not int
            or type(self.batch_chars) is not int
            or self.batch_size < 1
            or (self.batch_chars < 1)
        ):
            raise ValueError("Batch size and character limit must be positive integers")


class _PredictionRun:
    recognizer: SpacyNER | None
    cached: Any
    predictions: list[Any]

    def __init__(self, corpus, references, options, report, progress, store, signature):
        self.corpus = corpus
        self.references = references
        self.options = options
        self.report = report
        self.progress = progress
        self.store = store
        self.signature = signature
        if self.store is not None and (not self.signature):
            raise ValueError("A prediction configuration signature is required for checkpointing")
        if self.options.batch_size < 1 or self.options.batch_chars < 1:
            raise ValueError("Batch size and character limit must be positive")
        self.selected = set(self.options.fields)
        self.needs_ner = bool(self.selected & NER_FIELDS)
        self.cached = {} if self.store is None else self.store.corpus("ner")
        self.recognizer = None
        self.name_rules = None
        if self.needs_ner:
            if self.options.ner_cache is not None:
                for origin, line, is_json in iter_lines(self.options.ner_cache):
                    if not line.strip():
                        continue
                    if not is_json:
                        raise ValueError("--ner-cache requires JSONL")
                    row = json.loads(line)
                    if not isinstance(row, dict) or not isinstance(
                        row.get("entity_mentions"), list
                    ):
                        raise ValueError(f"{origin}: cached NER requires an entity_mentions list")
                    identity = (
                        row.get("record_id", row.get("recordid")),
                        row.get("url", row.get("document")),
                    )
                    if identity in self.cached and self.cached[identity] != row:
                        raise ValueError(f"{origin}: conflicting cached NER records")
                    self.cached[identity] = row
                self.name_rules = default_name_rules(self.options.resources_dir)
        self.predictions = []
        self.started = perf_counter()
        self.generated = self.reused = 0

    def pending(self):
        for index, reference in enumerate(self.references, 1):
            identity = (reference.get("recordid"), reference.get("document"))
            article = self.corpus.get(identity)
            if article is None:
                article = self.corpus.get((None, identity[1]))
            if article is None:
                self.report.note("corpus", "alignment", "missing_body")
                continue
            key = article_signature(self.signature, reference, article) if self.store else None
            saved = self.store.cached(key) if self.store else None
            if saved is not None:
                self.predictions.append(saved)
                self.reused += 1
                if self.reused % 1000 == 0:
                    self.progress(f"[benchmark] Reused {self.reused} cached predictions")
                continue
            yield (index, reference, article, key)

    def batches(self):
        batch: list[tuple] = []
        characters = 0
        for item in self.pending():
            length = len(item[2]["text"])
            if batch and (
                len(batch) >= self.options.batch_size
                or characters + length > self.options.batch_chars
            ):
                yield batch
                batch, characters = ([], 0)
            batch.append(item)
            characters += length
        if batch:
            yield batch

    def prepared(self):
        results: Iterator[NERResult | None]
        for batch in self.batches():
            if self.needs_ner and self.options.ner_cache is None:
                if self.recognizer is None:
                    self.progress(f"[benchmark] Loading NER model {self.options.ner_model}")
                    self.recognizer = SpacyNER.from_model(
                        self.options.ner_model, resources_dir=self.options.resources_dir
                    )
                results = self.recognizer.analyze_many(
                    [item[2]["text"] for item in batch], batch_size=self.options.batch_size
                )
            else:
                results = iter([None] * len(batch))
            yield from zip(batch, results, strict=True)
            if self.store:
                self.store.commit()

    def _entities(self, reference, article, batch_ner):
        identity = (reference.get("recordid"), reference.get("document"))
        text = article["text"]
        ner = None
        broad_names = True
        if self.needs_ner:
            if self.options.ner_cache is not None:
                row = self.cached.get(identity)
                if row is None or row.get("text_sha256") != article["text_sha256"]:
                    raise ValueError(f"Missing or mismatched cached NER for {identity}")
                broad_names = row.get("name_mentions") is not None
                ner = NERResult(
                    text,
                    tuple((EntityMention(**value) for value in row["entity_mentions"])),
                    backend_name=row.get("ner_backend", "cached-ner"),
                    name_policy="gdelt-full-names",
                    name_rules=self.name_rules,
                    name_mentions=tuple((NameMention(**value) for value in row["name_mentions"]))
                    if broad_names
                    else None,
                )
            else:
                ner = batch_ner
        return (ner, broad_names)

    def _overrides(self, article):
        supplied_fields = {
            "sharing_image",
            "related_images",
            "social_image_embeds",
            "social_video_embeds",
            "extras_xml",
        }
        overridable = set(TEXT_COLUMNS) | {
            "V2.1SHARINGIMAGE",
            "V2.1RELATEDIMAGES",
            "V2.1SOCIALIMAGEEMBEDS",
            "V2.1SOCIALVIDEOEMBEDS",
            "V2EXTRASXML",
        }
        overrides = {
            column: ""
            for field, column in zip(FIELD_NAMES, GKG_COLUMNS)
            if field not in self.selected and column in overridable
        }
        if self.selected & {"counts", "enhanced_counts"}:
            overrides.pop("V1LOCATIONS", None)
            overrides.pop("V2ENHANCEDLOCATIONS", None)
        for field, column in zip(FIELD_NAMES, GKG_COLUMNS):
            if (
                field in self.selected
                and field in supplied_fields
                and isinstance(article.get(field), str)
            ):
                overrides[column] = article[field]
        return overrides

    def _prediction(self, reference, article, batch_ner):
        text = article["text"]
        ner, broad_names = self._entities(reference, article, batch_ner)
        overrides = self._overrides(article)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            result = generate_gkg(
                text,
                RecordMetadata(
                    identifier=reference.get("document"),
                    batch_time=reference.get("date"),
                    sequence=1,
                    source_collection=int(reference.get("source_collection") or "1"),
                    source_name=reference.get("source"),
                ),
                Resources(
                    resources_dir=self.options.resources_dir, gcam_lexicon=self.options.gcam_lexicon
                ),
                overrides=overrides,
                ner_result=ner,
                numeric_date_order=self.options.numeric_date_order,
            )
        values = dict(zip(FIELD_NAMES, (result[column] for column in GKG_COLUMNS)))
        for name in ("recordid", "date", "source_collection", "source", "document"):
            values[name] = reference.get(name)
        for name in FIELD_NAMES:
            if name not in self.selected and name not in {
                "recordid",
                "date",
                "source_collection",
                "source",
                "document",
            }:
                values[name] = None
        if not broad_names:
            values["all_names"] = None
        if "translation" in self.selected:
            values["translation"] = article.get("translation", article.get("translation_info"))
        row = GKGRow(values, article.get("url", article["document"]))
        return row

    def run(self):
        for (index, reference, article, key), batch_ner in self.prepared():
            row = self._prediction(reference, article, batch_ner)
            self.predictions.append(self.store.put(row, signature=key) if self.store else row)
            self.generated += 1
            if index % 100 == 0 or index == len(self.references):
                elapsed = perf_counter() - self.started
                self.progress(
                    f"[benchmark] Generated {self.generated}, reused {self.reused}; {index}/{len(self.references)} references ({self.generated / elapsed:.1f} new/s)"
                )
        if self.store:
            self.store.commit()
        self.progress(
            f"[benchmark] Predictions ready: {self.generated} generated, {self.reused} reused"
        )
        return self.predictions


def generate_predictions(
    corpus,
    references,
    *,
    options: PredictionOptions,
    report,
    progress=print,
    store=None,
    signature=None,
):
    return _PredictionRun(corpus, references, options, report, progress, store, signature).run()
