"""Shared data contracts for input readers, field scorers and report writers."""

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

FIELD_NAMES = tuple(
    "recordid date source_collection source document counts enhanced_counts themes enhanced_themes "
    "locations enhanced_locations persons enhanced_persons organizations enhanced_organizations "
    "tone enhanced_dates gcam sharing_image related_images social_image_embeds social_video_embeds "
    "quotations all_names amounts translation extras_xml".split()
)
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

    def __post_init__(self):
        if type(self.offset_tolerance) is not int or self.offset_tolerance < 0:
            raise ValueError("Offset tolerance must be a nonnegative integer")
        if type(self.proximity_window) is not int or self.proximity_window < 0:
            raise ValueError("Proximity window must be a nonnegative integer")
        import math

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

    @property
    def name(self) -> str:
        prefix = "" if self.subset == "all" else self.subset + " / "
        return prefix + self.field + (" / " + self.calculation if self.calculation else "")


@dataclass
class BenchmarkReport:
    rows: list[ResultRow] = field(default_factory=list)
    audit: Counter = field(default_factory=Counter)
    configuration: dict[str, str] = field(default_factory=dict)

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
    _parsed: dict = field(default_factory=dict)

    def clear_parsed(self):
        """Release field-local objects before scoring the next field."""
        self._parsed.clear()

    def note(self, side, field_name, issue, detail="", count=1):
        self.report.note(side, field_name, issue, detail, count, subset=self.subset)

    def parsed(self, field_name: str, parser: Callable) -> list[tuple]:
        if field_name not in self._parsed:
            self._parsed[field_name] = list(self.iter_parsed(field_name, parser))
        return self._parsed[field_name]

    def iter_parsed(self, field_name: str, parser: Callable):
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
            yield expected, actual

    def add(self, name: str, calculation: str, metrics: dict[str, Number], documents=0, unit=""):
        self.report.rows.append(ResultRow(name, calculation, metrics, documents, unit, self.subset))
