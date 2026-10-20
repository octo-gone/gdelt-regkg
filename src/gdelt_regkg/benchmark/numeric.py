"""Tone components, GCAM family counts and independently defined weighted scores."""

import json
import re
import statistics
from collections import defaultdict
from dataclasses import replace
from urllib.parse import urlsplit

from ..fields.translation import normalize_language
from ..gcam_dictionaries import DICTIONARIES, dictionary_id
from . import parsers
from .gcam_metrics import (
    CountStats,
    PresenceCounts,
    count_summary,
    dimension_sort_key,
    language_label,
    publisher_intervals,
)
from .gcam_sampling import GCAMSelection
from .metrics import numeric_metrics, prf, quantile
from .model import ScoreContext

TONE_PARTS = (
    "tone",
    "positive",
    "negative",
    "polarity",
    "activity density",
    "self-group density",
    "word count",
)
FAMILY_NAMES = {
    **{str(code): name.replace("-", " ").title() for code, name in DICTIONARIES.items()},
    "2": "General Inquirer",
    "3": "Lexicoder",
    "9": "Roget",
    "15": "WordNet Affect",
    "16": "WordNet Domains",
    "17": "WordNet lexical",
    "18": "Themes",
    "26": "VADER",
    "20": "ML-SENTICON",
    "23": "ML-SENTICON Multilingual",
}
WEIGHTED_ZERO_TOLERANCE = 1e-09


def weighted_sign(value):
    return 0 if abs(value) <= WEIGHTED_ZERO_TOLERANCE else 1 if value > 0 else -1


def tone(context, name):
    from ..dependencies import require_dependency

    cohen_kappa_score = require_dependency("sklearn.metrics", "benchmark").cohen_kappa_score

    rows = context.parsed(name, parsers.tone)
    if context.article_sink is not None:
        for reference, (expected, actual) in zip(context._article_references, rows, strict=True):
            for index, part in enumerate(TONE_PARTS):
                context.article(
                    reference,
                    "Tone",
                    part,
                    "numeric",
                    reference=expected[index] if expected is not None else None,
                    prediction=actual[index] if actual is not None else None,
                )
    pairs = [(a, b) for a, b in rows if a is not None and b is not None]
    for index, part in enumerate(TONE_PARTS):
        values = numeric_metrics([(a[index], b[index]) for a, b in pairs])
        unit = "words" if index == 6 else "points"
        context.add(
            "Tone",
            part,
            {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
            len(pairs),
            unit,
        )
        context.add(
            "Tone",
            part + " / limits of agreement",
            {k: values[k] for k in ("loa_lower", "loa_upper", "paired_values")},
            len(pairs),
            unit,
        )
    threshold = context.options.tone_neutral
    sign = lambda v: -1 if v < -threshold else 1 if v > threshold else 0
    expected, actual = ([sign(a[0]) for a, b in pairs], [sign(b[0]) for a, b in pairs])
    observed = sum((a == b for a, b in zip(expected, actual))) / len(pairs) if pairs else None
    kappa = (
        float(cohen_kappa_score(expected, actual))
        if pairs and len(set(expected) | set(actual)) > 1
        else None
    )
    context.add(
        "Tone",
        f"sign, neutral ±{threshold:g}",
        {"sign_agreement": observed, "kappa": kappa, "paired_values": len(pairs)},
        len(pairs),
    )
    valid = sum((b is not None for a, b in rows))
    context.add(
        "Tone",
        "validity",
        {
            "validity_rate": valid / len(rows) if rows else None,
            "paired_values": len(pairs),
            "prediction_identity_violations": sum(
                (
                    abs(b[0] - (b[1] - b[2])) > 0.0001 or abs(b[3] - (b[1] + b[2])) > 0.0001
                    for a, b in pairs
                )
            ),
        },
        len(rows),
    )
    ratios = [b[6] / a[6] for a, b in pairs if a[6] > 0]
    context.add(
        "Tone",
        "word-count ratios",
        {
            "ratio_median": quantile(ratios, 0.5),
            "ratio_p10": quantile(ratios, 0.1),
            "ratio_p90": quantile(ratios, 0.9),
        },
        len(ratios),
    )


def family(key):
    return key[1:].split(".", 1)[0]


class _GCAMReport:
    def __init__(self, context, name):
        self.context = context
        self.name = name
        self.known = self.context.options.gcam_keys
        if self.known is not None:
            self.known = frozenset(
                key
                for key in self.known
                if key.startswith(("c", "v"))
                and dictionary_id(key) not in self.context.options.gcam_disabled_dictionaries
            )
            if context.options.gcam_evaluation_language is not None:
                self.known = frozenset(
                    key
                    for key in self.known
                    if (context.options.gcam_languages or {}).get(key, "eng")
                    == context.options.gcam_evaluation_language
                )
        self.count_keys = (
            set() if self.known is None else {k for k in self.known if k.startswith("c")}
        )
        self.supported = self.count_keys
        self.supported_dimensions = {key[1:] for key in (self.known or ())}
        self.applied_dimensions: set[str] = set()
        self.native_dimensions: set[str] = set()
        self.observed: set[str] = set()
        self.native: set[str] = set()
        self.unexpected: set[str] = set()
        self.all_presence = PresenceCounts()
        self.all_supported_presence = PresenceCounts()
        self.presence: dict[str, PresenceCounts] = defaultdict(PresenceCounts)
        self.supported_presence: dict[str, PresenceCounts] = defaultdict(PresenceCounts)
        self.statistics_by_key = {
            key: CountStats() for key in sorted(self.count_keys, key=dimension_sort_key)
        }
        self.active_by_key = {
            key: CountStats() for key in sorted(self.count_keys, key=dimension_sort_key)
        }
        self.source_presence = {
            name: PresenceCounts() for name in ("source-backed", "approximate", "unspecified")
        }
        self.source_keys = {
            name: {key for key in self.count_keys if self.source_type(key) == name}
            for name in self.source_presence
        }
        self.clusters: dict[str, list[float]] = {}
        self.exclusions: dict[str, int] = defaultdict(int)
        self.paired_scores: dict[str, list[tuple[float, float]]] = defaultdict(list)
        self.reference_scores: dict[str, int] = defaultdict(int)
        self.prediction_scores: dict[str, int] = defaultdict(int)
        self.article_counts: dict[str, list[float]] = {}
        self.article_scores: dict[str, tuple[float | None, float | None]] = {}
        self.documents = self.assignments = self.supported_assignments = 0
        self.occurrences = self.supported_occurrences = 0.0

    def _applicable(self, languages):
        supported = self.supported
        language_map = self.context.options.gcam_languages
        if language_map is not None:
            applicable = {"eng"} if languages is None else set(languages)
            supported = {key for key in supported if language_map.get(key, "eng") in applicable}
            self.applied_dimensions.update(
                key[1:] for key in (self.known or ()) if language_map.get(key, "eng") in applicable
            )
        else:
            self.applied_dimensions.update(self.supported_dimensions)
        return supported

    def _selected_dimension(self, key, languages):
        if key == "wc":
            return "eng" in languages
        if key == "nwc":
            return any(code != "eng" for code in languages)
        if not key.startswith(("c", "v")):
            return True
        if dictionary_id(key) in self.context.options.gcam_disabled_dictionaries:
            return False
        language_map = self.context.options.gcam_languages
        target_language = self.context.options.gcam_evaluation_language
        mapped = (language_map or {}).get(
            key, (language_map or {}).get(("v" if key.startswith("c") else "c") + key[1:])
        )
        if target_language is not None:
            if mapped is None:
                self.context.note("configuration", "gcam", "unmapped_dimension_language", key)
            return mapped == target_language
        return mapped is None or mapped in languages

    def _count_errors(self, left, right, supported, unreported):
        count_error = count_reference = 0.0
        if self.known is None:
            return count_error, count_reference
        language_map = self.context.options.gcam_languages
        self.unexpected.update(
            key for key in right if key.startswith("c") and key not in self.supported
        )
        for key in supported:
            if key in unreported:
                self.exclusions[family(key)] += 1
                continue
            expected, actual = left.get(key, 0), right.get(key, 0)
            word_key = "nwc" if language_map and language_map.get(key, "eng") != "eng" else "wc"
            args = (expected, actual, left.get(word_key, 0), right.get(word_key, 0))
            self.statistics_by_key[key].add(*args)
            if expected or actual:
                self.active_by_key[key].add(*args)
                count_error += abs(actual - expected)
                count_reference += expected
                if self.context.article_sink is not None:
                    item = self.article_counts.setdefault(family(key), [0.0, 0.0, 0])
                    item[0] += abs(actual - expected)
                    item[1] += expected
                    item[2] += 1
        return count_error, count_reference

    def observe(self, left, right, languages=None, publisher="unknown"):
        self.article_counts = {}
        self.article_scores = {}
        supported = self._applicable(languages)
        applicable = {"eng"} if languages is None else set(languages)
        left = {
            key: value for key, value in left.items() if self._selected_dimension(key, applicable)
        }
        right = {
            key: value for key, value in right.items() if self._selected_dimension(key, applicable)
        }
        self.documents += 1
        self.observed.update(left)
        self.observed.update(right)
        unreported = {
            "c" + key[1:] for key in left if key.startswith("v") and "c" + key[1:] not in left
        }
        a = {k for k, v in left.items() if k.startswith("c") and v > 0 and (k not in unreported)}
        b = {k for k, v in right.items() if k.startswith("c") and v > 0 and (k not in unreported)}
        self.all_presence.add(a, b)
        self.all_supported_presence.add(a & supported, b & supported)
        for source_type, presence in self.source_presence.items():
            keys = self.source_keys[source_type] & supported
            presence.add(a & keys, b & keys)
        self.native.update(a)
        self.native_dimensions.update(
            key[1:]
            for key, value in left.items()
            if key.startswith("v") or (key.startswith("c") and value > 0)
        )
        self.assignments += len(a)
        self.supported_assignments += len(a & supported)
        left_families, right_families = (defaultdict(set), defaultdict(set))
        for key in a:
            left_families[family(key)].add(key)
        for key in b:
            right_families[family(key)].add(key)
        for code in left_families.keys() | right_families.keys():
            aa, bb = (left_families[code], right_families[code])
            self.presence[code].add(aa, bb)
            if self.known is not None:
                self.supported_presence[code].add(aa & supported, bb & supported)
        for key, value in left.items():
            if key.startswith("c"):
                self.occurrences += value
                if key in supported:
                    self.supported_occurrences += value
        count_error, count_reference = self._count_errors(left, right, supported, unreported)
        if self.context.options.gcam_bootstrap_samples:
            cluster = self.clusters.setdefault(publisher, [0.0] * 7)
            values = [
                len(a & b),
                len(a),
                len(b),
                len(a & b) / len(a | b) if a or b else 0,
                int(bool(a or b)),
                count_error,
                count_reference,
            ]
            for index, value in enumerate(values):
                cluster[index] += value
        for key in left.keys() | right.keys():
            if key.startswith("v") or key in {"wc", "nwc"}:
                if self.context.article_sink is not None:
                    self.article_scores[key] = (left.get(key), right.get(key))
                self.reference_scores[key] += key in left
                self.prediction_scores[key] += key in right
                if key in left and key in right:
                    self.paired_scores[key].append((left[key], right[key]))
        return a, b

    def report(self, *, dictionary_details=True):
        self.all_presence.report(self.context, "GCAM", "presence", self.documents)
        if self.known is not None:
            self.all_supported_presence.report(
                self.context, "GCAM", "supported presence", self.documents
            )
        families = (
            sorted({family(k) for k in self.observed if k.startswith("c")}, key=int)
            if dictionary_details
            else []
        )
        for code in families:
            label = "GCAM / " + FAMILY_NAMES.get(code, "Dictionary " + code)
            self.presence[code].report(self.context, label, "presence", self.documents)
            if self.known is not None:
                self.supported_presence[code].report(
                    self.context, label, "supported presence", self.documents
                )
        if self.known is None:
            self.context.note(
                "configuration",
                "gcam",
                "missing_inventory",
                "Supply --gcam-lexicon or prepared resources for supported count errors and coverage",
            )
        else:
            if self.unexpected:
                self.context.note(
                    "prediction",
                    "gcam",
                    "outside_inventory",
                    "Predicted count keys exceed the declared supported inventory",
                    len(self.unexpected),
                )
            for code in sorted({family(k) for k in self.count_keys if dictionary_details}, key=int):
                items = [s for k, s in self.statistics_by_key.items() if family(k) == code and s.n]
                n = sum((s.n for s in items))
                label = "GCAM / " + FAMILY_NAMES.get(code, "Dictionary " + code)
                self.context.add(
                    label,
                    "supported counts",
                    count_summary(items),
                    self.documents,
                    "counts",
                )
                self.context.add(
                    label,
                    "active supported counts",
                    count_summary(
                        s for key, s in self.active_by_key.items() if family(key) == code
                    ),
                    self.documents,
                    "counts",
                )
                self.context.add(
                    label,
                    "count coverage",
                    {
                        "paired_values": n,
                        "dimensions": len(items),
                        "excluded_unreported_counts": self.exclusions[code],
                    },
                    self.documents,
                )
            self.context.add(
                "GCAM",
                "coverage",
                {
                    "dimension_coverage": len(self.native_dimensions & self.applied_dimensions)
                    / len(self.native_dimensions)
                    if self.native_dimensions
                    else None,
                    "assignment_coverage": self.supported_assignments / self.assignments
                    if self.assignments
                    else None,
                    "occurrence_coverage": self.supported_occurrences / self.occurrences
                    if self.occurrences
                    else None,
                    "supported_dimensions": len(self.supported_dimensions),
                    "evaluated_dimensions": len(self.applied_dimensions),
                    "observed_native_dimensions": len(self.native_dimensions),
                },
                self.documents,
            )
            self.report_sources(include_scores=dictionary_details)
            if dictionary_details:
                self.report_dimensions()
        if dictionary_details:
            self.report_scores()
        self.report_word_counts()
        self.report_uncertainty()

    def report_scores(self):
        for key in sorted((k for k in self.observed if k.startswith("v")), key=dimension_sort_key):
            if self.known is not None and key not in self.known and "c" + key[1:] not in self.known:
                continue
            pairs = self.paired_scores[key]
            values = numeric_metrics(pairs)
            self.context.report.details.setdefault("gcam-dimensions", []).append(
                {
                    "subset": self.context.subset,
                    "key": key,
                    "dictionary": FAMILY_NAMES.get(family(key), family(key)),
                    "category": (self.context.options.gcam_dimension_names or {}).get(key, key),
                    "language": (self.context.options.gcam_languages or {}).get(key, "unknown"),
                    "source_type": self.source_type(key),
                    "reference_support": self.reference_scores[key],
                    "prediction_support": self.prediction_scores[key],
                    "score_pairs": len(pairs),
                    "score_mae": values["mae"],
                    "score_rmse": values["rmse"],
                    "score_bias": values["bias"],
                    "score_ccc": values["ccc"],
                    "score_spearman": values["spearman"],
                }
            )
            self.context.add(
                self._score_field(key),
                key + " / weighted score",
                {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
                len(pairs),
                "score",
                **self._score_metadata(key),
            )
            self.context.add(
                self._score_field(key),
                key + " / score availability",
                prf(
                    len(pairs),
                    self.prediction_scores[key] - len(pairs),
                    self.reference_scores[key] - len(pairs),
                ),
                self.documents,
                **self._score_metadata(key),
            )
            self.context.add(
                self._score_field(key),
                key + " / score agreement diagnostics",
                {
                    "reference_mean": statistics.mean(a for a, _ in pairs) if pairs else None,
                    "prediction_mean": statistics.mean(b for _, b in pairs) if pairs else None,
                    "loa_lower": values["loa_lower"],
                    "loa_upper": values["loa_upper"],
                    "paired_values": len(pairs),
                },
                len(pairs),
                "score",
                **self._score_metadata(key),
            )
            self.context.add(
                self._score_field(key),
                key + " / weighted-score coverage",
                {
                    "paired_values": len(pairs),
                    "reference_support": self.reference_scores[key],
                    "prediction_support": self.prediction_scores[key],
                    "sign_agreement": sum((weighted_sign(a) == weighted_sign(b) for a, b in pairs))
                    / len(pairs)
                    if pairs
                    else None,
                },
                self.documents,
                **self._score_metadata(key),
            )

    def report_word_counts(self):
        target = self.context.options.gcam_evaluation_language
        word_keys = ("wc", "nwc") if target is None else ("wc",) if target == "eng" else ("nwc",)
        for key in word_keys:
            pairs = self.paired_scores[key]
            if pairs:
                values = numeric_metrics(pairs)
                self.context.add(
                    "GCAM",
                    key,
                    {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
                    len(pairs),
                    "words",
                )

    def _score_field(self, key):
        return "GCAM / " + FAMILY_NAMES.get(family(key), "Dictionary " + family(key))

    def _score_metadata(self, key):
        names = self.context.options.gcam_dimension_names or {}
        companion = "c" + key[1:]
        category = names.get(key, names.get(companion, ""))
        if category in (key, companion):
            category = ""
        category = re.sub(r"\s*\(Scored Value\)\s*$", "", category, flags=re.I).strip()
        category = re.sub(
            r"(?<=[a-z])(?=[A-Z])|(?<=[a-zA-Z])(?=\d)|(?<=\d)(?=[a-zA-Z])", " ", category
        )
        languages = self.context.options.gcam_languages or {}
        language = languages.get(key, languages.get(companion, "eng"))
        if language not in ("eng", self.context.language):
            category = language_label(language) + (" / " + category if category else "")
        return {"dimension_key": key, "dimension_name": category}

    def source_type(self, key):
        approximate = self.context.options.gcam_approximate_dimensions
        return (
            "unspecified"
            if approximate is None
            else "approximate"
            if key[1:] in approximate
            else "source-backed"
        )

    def report_sources(self, *, include_scores=True):
        for group, presence in self.source_presence.items():
            dimensions = {key for key in self.known or () if self.source_type(key) == group}
            keys = {key for key in self.count_keys if self.source_type(key) == group}
            if not dimensions:
                continue
            self.context.table(
                "gcam-sources",
                "GCAM / " + group,
                "inventory",
                {
                    "compiled_dimensions": len({key[1:] for key in dimensions}),
                    "count_dimensions": len(keys),
                    "weighted_dimensions": sum(key.startswith("v") for key in dimensions),
                },
                self.documents,
            )
            self._source_counts(group, presence, keys)
            for key in sorted(
                (key for key in dimensions if key.startswith("v") and include_scores),
                key=dimension_sort_key,
            ):
                pairs = self.paired_scores[key]
                values = numeric_metrics(pairs)
                self.context.table(
                    "gcam-sources",
                    "GCAM / " + group + " / " + self._score_field(key).removeprefix("GCAM / "),
                    key + " / weighted score",
                    {
                        metric: values[metric]
                        for metric in ("mae", "rmse", "bias", "ccc", "spearman")
                    },
                    len(pairs),
                    "score",
                    **self._score_metadata(key),
                )
                self.context.table(
                    "gcam-sources",
                    "GCAM / " + group + " / " + self._score_field(key).removeprefix("GCAM / "),
                    key + " / score availability",
                    {
                        "paired_values": len(pairs),
                        "reference_support": self.reference_scores[key],
                        "prediction_support": self.prediction_scores[key],
                    },
                    self.documents,
                    **self._score_metadata(key),
                )

    def _source_counts(self, group, presence, keys):
        if keys:
            self.context.table(
                "gcam-sources",
                "GCAM / " + group,
                "supported presence",
                {
                    **prf(
                        presence.matched,
                        presence.prediction - presence.matched,
                        presence.reference - presence.matched,
                    ),
                    "macro_f1": presence.macro()["f1"],
                },
                self.documents,
            )
            self.context.table(
                "gcam-sources",
                "GCAM / " + group,
                "active supported counts",
                count_summary(self.active_by_key[key] for key in keys),
                self.documents,
                "counts",
            )

    def report_dimensions(self):
        presence = self.all_presence
        for key in sorted(
            presence.expected.keys() | presence.actual.keys() | self.count_keys,
            key=dimension_sort_key,
        ):
            stats = self.statistics_by_key.get(key, CountStats())
            active = self.active_by_key.get(key, CountStats())
            self.context.report.details.setdefault("gcam-dimensions", []).append(
                {
                    "subset": self.context.subset,
                    "key": key,
                    "dictionary": FAMILY_NAMES.get(family(key), family(key)),
                    "category": (self.context.options.gcam_dimension_names or {}).get(key, key),
                    "language": (self.context.options.gcam_languages or {}).get(key, "unknown"),
                    "source_type": self.source_type(key)
                    if key in self.count_keys
                    else "unimplemented",
                    **prf(
                        presence.tp[key],
                        presence.actual[key] - presence.tp[key],
                        presence.expected[key] - presence.tp[key],
                    ),
                    "true_positives": presence.tp[key],
                    "reference_support": presence.expected[key],
                    "prediction_support": presence.actual[key],
                    "count_pairs": stats.n,
                    "active_count_pairs": active.n,
                    "count_mae": stats.absolute_error / stats.n if stats.n else None,
                    "active_count_mae": active.absolute_error / active.n if active.n else None,
                    "active_count_wape": active.absolute_error / active.reference
                    if active.reference
                    else None,
                    "count_ccc": stats.ccc,
                }
            )

    def report_uncertainty(self):
        samples = self.context.options.gcam_bootstrap_samples
        if not samples:
            return
        intervals = publisher_intervals(self.clusters, samples, self.context.options.gcam_seed)
        active = count_summary(self.active_by_key.values())
        estimates = {
            "micro_f1": prf(
                self.all_presence.matched,
                self.all_presence.prediction - self.all_presence.matched,
                self.all_presence.reference - self.all_presence.matched,
            )["f1"],
            "document_jaccard": self.all_presence.jaccard / self.all_presence.active_documents
            if self.all_presence.active_documents
            else None,
            "count_wape": active["count_wape"],
        }
        for metric, (lower, upper) in intervals.items():
            self.context.table(
                "gcam-sampling",
                "GCAM",
                metric + " / publisher bootstrap",
                {
                    "estimate": estimates[metric],
                    "ci_lower": lower,
                    "ci_upper": upper,
                    "publisher_clusters": len(self.clusters),
                    "resamples": samples,
                },
                self.documents,
            )


def _evaluated_languages(prediction, context):
    encoded = prediction.get("_gcam_languages")
    if not encoded:
        return None
    try:
        values = json.loads(encoded)
        if (
            not isinstance(values, list)
            or not values
            or any(not isinstance(value, str) for value in values)
        ):
            raise ValueError("Expected a nonempty JSON array of analyzed language codes")
        return [normalize_language(value) for value in values]
    except (ValueError, TypeError) as error:
        context.note("prediction", "gcam", "malformed_language_metadata", str(error))
        # Invalid applicability metadata must not improve errors by excluding
        # native dimensions from their denominators.
        return sorted(set((context.options.gcam_languages or {}).values()) | {"eng"})


def _observe_article(report, left, right, reference, prediction, languages, publisher):
    a, b = report.observe(left, right, languages, publisher)
    context = report.context
    if context.article_sink is not None:
        supported = report._applicable(languages)
        groups = [
            ("GCAM", "presence", a, b),
            ("GCAM", "supported presence", a & supported, b & supported),
        ]
        for code in sorted({family(key) for key in a | b}, key=int):
            aa, bb = ({key for key in values if family(key) == code} for values in (a, b))
            label = "GCAM / " + FAMILY_NAMES.get(code, code)
            groups.extend(
                [
                    (label, "presence", aa, bb),
                    (label, "supported presence", aa & supported, bb & supported),
                ]
            )
        for label, calculation, aa, bb in groups:
            union = aa | bb
            context.article(
                reference,
                label,
                calculation,
                "set",
                tp=len(aa & bb),
                reference=len(aa),
                prediction=len(bb),
                exact=int(aa == bb),
                jaccard=len(aa & bb) / len(union) if union else None,
            )
        for code, (error, total, active) in report.article_counts.items():
            context.article(
                reference,
                "GCAM / " + FAMILY_NAMES.get(code, code),
                "active supported counts",
                "count",
                absolute_error=error,
                reference=total,
                active=active,
            )
        for key, (expected, actual) in report.article_scores.items():
            if key.startswith("v") and (
                report.known is None or key in report.known or "c" + key[1:] in report.known
            ):
                context.article(
                    reference,
                    report._score_field(key),
                    key + " / weighted score",
                    "numeric",
                    reference=expected,
                    prediction=actual,
                )
    context.report.details.setdefault("gcam-articles", []).append(
        {
            "subset": context.subset,
            "language": context.language,
            "recordid": reference.get("recordid"),
            "document": reference.get("document"),
            "publisher": publisher,
            "evaluated_languages": ",".join(languages or ["eng"]),
            "evaluation_language": context.options.gcam_evaluation_language or "all",
            "reference_wc": left.get("wc"),
            "prediction_wc": right.get("wc"),
            "reference_nwc": left.get("nwc"),
            "prediction_nwc": right.get("nwc"),
            "reference_categories": len(a),
            "prediction_categories": len(b),
            "matched_categories": len(a & b),
            "document_f1": 2 * len(a & b) / (len(a) + len(b)) if a or b else None,
            "document_jaccard": len(a & b) / len(a | b) if a or b else None,
            "exact_category_set": int(a == b),
            "reference_origin": reference.origin,
            "prediction_origin": prediction.origin,
        }
    )


def _language_report(context, name, code):
    options = replace(context.options, gcam_evaluation_language=code)
    return _GCAMReport(
        ScoreContext(
            [],
            options,
            context.report,
            context.subset,
            language=code,
            article_sink=context.article_sink,
        ),
        name,
    )


def _report_languages(context, report, breakdowns):
    languages = context.options.gcam_languages
    if languages is None:
        return
    target = context.options.gcam_evaluation_language
    inventory = {languages.get(key, "eng") for key in report.known or ()}
    codes = {target} if target else inventory | breakdowns.keys()
    for code in sorted(codes):
        group = report if target else breakdowns.get(code)
        presence = group.all_presence if group else PresenceCounts()
        context.add(
            "GCAM / languages",
            language_label(code),
            {
                "documents": group.documents if group else 0,
                "compiled_dimensions": sum(
                    languages.get("c" + key, languages.get("v" + key, "eng")) == code
                    for key in report.supported_dimensions
                ),
                **prf(
                    presence.matched,
                    presence.prediction - presence.matched,
                    presence.reference - presence.matched,
                ),
            },
            group.documents if group else 0,
        )


def gcam(context, name):
    if context.options.gcam_split_languages and context.options.gcam_languages is None:
        raise ValueError("Split GCAM language groups require per-dimension language metadata")
    report = _GCAMReport(context, name)
    selection = GCAMSelection(context)
    breakdowns: dict[str, _GCAMReport] = {}
    automatic = (
        context.options.gcam_evaluation_language is None
        and context.options.gcam_languages is not None
    )
    split = context.options.gcam_split_languages
    for left, right, reference, prediction, languages in selection.pairs(
        name, _evaluated_languages
    ):
        publisher = (
            reference.get("source")
            or urlsplit(reference.get("document") or "").hostname
            or "unknown"
        )
        if split:
            report.observe(left, right, languages, publisher)
        else:
            _observe_article(report, left, right, reference, prediction, languages, publisher)
        if automatic or split:
            codes = (
                {context.options.gcam_evaluation_language}
                if context.options.gcam_evaluation_language
                else set(languages or ["eng"])
            )
            for code in sorted(codes):
                if code not in breakdowns:
                    breakdowns[code] = _language_report(context, name, code)
                if split:
                    _observe_article(
                        breakdowns[code], left, right, reference, prediction, languages, publisher
                    )
                else:
                    breakdowns[code].observe(left, right, languages, publisher)
    _report_languages(context, report, breakdowns)
    report.report(dictionary_details=not split)
    for code in sorted(breakdowns):
        if split:
            breakdowns[code].report()
        else:
            breakdowns[code].report_uncertainty()
    selection.report()
