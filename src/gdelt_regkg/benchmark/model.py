"""Shared data contracts for input readers, field scorers and report writers."""

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Callable

from ..gcam_dictionaries import dictionary_id, resolve_dictionaries
from ..record import FIELD_NAMES

__all__ = [
    "FIELD_NAMES",
    "GKGRow",
    "BenchmarkOptions",
    "BenchmarkReport",
    "ScoreContext",
    "ResultRow",
]

GROUPS = {
    "metadata": ("recordid", "date", "source_collection", "source", "document"),
    "counts": ("counts", "enhanced_counts"),
    "themes": ("themes", "enhanced_themes"),
    "ner": ("persons", "enhanced_persons", "organizations", "enhanced_organizations"),
    "locations": ("locations", "enhanced_locations"),
    "dates": ("enhanced_dates",),
    "media": ("sharing_image", "related_images", "social_image_embeds", "social_video_embeds"),
}
Number = int | float | None


@dataclass(frozen=True)
class GKGRow:
    values: dict[str, str | None]
    origin: str = ""

    def get(self, name: str) -> str | None:
        return self.values.get(name)


@dataclass(frozen=True)
class BenchmarkOptions:
    offset_tolerance: int = 100
    relaxed: bool = False
    number_tolerance: float = 0.1
    object_similarity: float = 0.6
    quote_similarity: float = 0.5
    tone_neutral: float = 0.5
    diagnostics: bool = False
    proximity_window: int = 200
    theme_labels: frozenset[str] | None = None
    gcam_keys: frozenset[str] | None = None
    gcam_disabled_dictionaries: tuple[int | str, ...] = ()
    gcam_languages: Mapping[str, str] | None = None
    gcam_approximate_dimensions: frozenset[str] | None = None
    gcam_dimension_names: Mapping[str, str] | None = None
    gcam_evaluation_language: str | None = None
    gcam_max_word_count_difference: float | None = None
    gcam_sample_size: int | None = None
    gcam_bootstrap_samples: int = 0
    gcam_seed: int = 0
    gcam_split_languages: bool = False

    def __post_init__(self):
        object.__setattr__(
            self,
            "gcam_disabled_dictionaries",
            resolve_dictionaries(
                self.gcam_disabled_dictionaries,
                custom_ids=(
                    dictionary_id(key)
                    for key in (self.gcam_keys or ())
                    if key.startswith(("c", "v"))
                ),
            ),
        )
        if type(self.offset_tolerance) is not int or self.offset_tolerance < 0:
            raise ValueError("Offset tolerance must be a nonnegative integer")
        if type(self.proximity_window) is not int or self.proximity_window < 0:
            raise ValueError("Proximity window must be a nonnegative integer")
        import math

        if self.gcam_evaluation_language is not None:
            from ..fields.translation import normalize_language

            object.__setattr__(
                self, "gcam_evaluation_language", normalize_language(self.gcam_evaluation_language)
            )
        if self.gcam_max_word_count_difference is not None and (
            not math.isfinite(self.gcam_max_word_count_difference)
            or self.gcam_max_word_count_difference < 0
        ):
            raise ValueError("GCAM word-count difference must be finite and nonnegative")
        if self.gcam_sample_size is not None and (
            type(self.gcam_sample_size) is not int or self.gcam_sample_size < 1
        ):
            raise ValueError("GCAM sample size must be a positive integer")
        if type(self.gcam_bootstrap_samples) is not int or self.gcam_bootstrap_samples < 0:
            raise ValueError("GCAM bootstrap samples must be a nonnegative integer")
        if type(self.gcam_seed) is not int:
            raise ValueError("GCAM seed must be an integer")
        if type(self.gcam_split_languages) is not bool:
            raise ValueError("GCAM split languages must be bool")

        if not math.isfinite(self.number_tolerance) or self.number_tolerance < 0:
            raise ValueError("Number tolerance must be finite and nonnegative")
        if not math.isfinite(self.tone_neutral) or self.tone_neutral < 0:
            raise ValueError("Tone neutral threshold must be finite and nonnegative")
        if not 0 <= self.object_similarity <= 1 or not 0 <= self.quote_similarity <= 1:
            raise ValueError("Text similarities must be between zero and one")


@dataclass(frozen=True)
class ResultRow:
    field: str
    calculation: str
    metrics: dict[str, Number]
    documents: int = 0
    unit: str = ""
    subset: str = "all"
    dimension_key: str = ""
    dimension_name: str = ""
    language: str = ""

    @property
    def name(self) -> str:
        prefix = "" if self.subset == "all" else self.subset + " / "
        if self.language:
            prefix += self.language + " / "
        return prefix + self.field + (" / " + self.calculation if self.calculation else "")


@dataclass
class BenchmarkReport:
    rows: list[ResultRow] = field(default_factory=list)
    audit: Counter = field(default_factory=Counter)
    configuration: dict[str, str] = field(default_factory=dict)
    tables: dict[str, list[ResultRow]] = field(default_factory=dict)
    details: dict[str, list[dict]] = field(default_factory=dict)

    def note(
        self,
        side: str,
        field_name: str,
        issue: str,
        detail: str = "",
        count: int = 1,
        *,
        subset: str = "all",
    ):
        self.audit[(side, field_name, issue, detail, subset)] += count


@dataclass
class ScoreContext:
    pairs: list[tuple[GKGRow, GKGRow]]
    options: BenchmarkOptions
    report: BenchmarkReport
    subset: str = "all"
    language: str = ""
    _parsed: dict = field(default_factory=dict)
    article_sink: Callable[[dict], None] | None = None
    _article_references: list = field(default_factory=list)

    def clear_parsed(self):
        """Release field-local objects before scoring the next field."""
        self._parsed.clear()
        self._article_references.clear()

    def note(self, side, field_name, issue, detail="", count=1):
        self.report.note(side, field_name, issue, detail, count, subset=self.subset)

    def parsed(self, field_name: str, parser: Callable) -> list[tuple]:
        if field_name not in self._parsed:
            if self.article_sink is None:
                self._parsed[field_name] = list(self.iter_parsed(field_name, parser))
            else:
                parsed = list(self.iter_parsed(field_name, parser, include_rows=True))
                self._parsed[field_name] = [(a, b) for a, b, _, _ in parsed]
                self._article_references = [reference for _, _, reference, _ in parsed]
        return self._parsed[field_name]

    def article(self, reference_row, field_name, calculation, kind, **values):
        """Stream sufficient statistics without retaining a second corpus in RAM."""
        if self.article_sink is not None:
            self.article_sink(
                {
                    "recordid": reference_row.get("recordid"),
                    "document": reference_row.get("document"),
                    "date": reference_row.get("date"),
                    "publisher": reference_row.get("source"),
                    "subset": self.subset,
                    "language": self.language or self.options.gcam_evaluation_language or "",
                    "field": field_name,
                    "calculation": calculation,
                    "kind": kind,
                    **values,
                }
            )

    def iter_parsed(self, field_name: str, parser: Callable, *, include_rows=False):
        """Exclude unavailable/native-invalid fields; invalid predictions become empty.

        A malformed prediction must never improve a score by removing its document.
        Native-invalid values have no trustworthy reference and are audited per field.
        """
        for reference, prediction in self.pairs:
            left, right = reference.get(field_name), prediction.get(field_name)
            if left is None or right is None:
                side = "reference" if left is None else "prediction"
                self.note(side, field_name, "unavailable")
                continue
            try:
                expected = parser(left)
            except (ValueError, ArithmeticError) as error:
                self.note("reference", field_name, "malformed", str(error))
                continue
            try:
                actual = parser(right)
            except (ValueError, ArithmeticError) as error:
                self.note("prediction", field_name, "malformed", str(error))
                actual = parser("")
            yield (expected, actual, reference, prediction) if include_rows else (expected, actual)

    def add(
        self,
        name: str,
        calculation: str,
        metrics: dict[str, Number],
        documents=0,
        unit="",
        *,
        dimension_key="",
        dimension_name="",
    ):
        self.report.rows.append(
            ResultRow(
                name,
                calculation,
                metrics,
                documents,
                unit,
                self.subset,
                dimension_key,
                dimension_name,
                self.language,
            )
        )

    def table(
        self,
        table: str,
        name: str,
        calculation: str,
        metrics: dict[str, Number],
        documents=0,
        unit="",
        *,
        dimension_key="",
        dimension_name="",
    ):
        self.report.tables.setdefault(table, []).append(
            ResultRow(
                name,
                calculation,
                metrics,
                documents,
                unit,
                self.subset,
                dimension_key,
                dimension_name,
                self.language,
            )
        )
