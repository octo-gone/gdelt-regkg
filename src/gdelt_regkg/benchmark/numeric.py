"""Tone components, GCAM family counts and independently defined weighted scores."""

import statistics
from collections import defaultdict
from dataclasses import dataclass

from . import parsers
from .metrics import numeric_metrics, prf, quantile

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
    "2": "General Inquirer",
    "3": "Lexicoder",
    "9": "Roget",
    "15": "WordNet Affect",
    "16": "WordNet Domains",
    "17": "WordNet lexical",
    "18": "Themes",
    "26": "VADER",
}
# Weighted means can leave tiny residuals when positive and negative scores cancel.
WEIGHTED_ZERO_TOLERANCE = 1e-9


def weighted_sign(value):
    return 0 if abs(value) <= WEIGHTED_ZERO_TOLERANCE else (1 if value > 0 else -1)


def tone(context, name):
    from sklearn.metrics import cohen_kappa_score

    rows = context.parsed(name, parsers.tone)
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
    observed = sum(a == b for a, b in zip(expected, actual)) / len(pairs) if pairs else None
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
    valid = sum(b is not None for a, b in rows)
    context.add(
        "Tone",
        "validity",
        {
            "validity_rate": valid / len(rows) if rows else None,
            "paired_values": len(pairs),
            "prediction_identity_violations": sum(
                abs(b[0] - (b[1] - b[2])) > 1e-4 or abs(b[3] - (b[1] + b[2])) > 1e-4
                for a, b in pairs
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


@dataclass
class CountStats:
    n: int = 0
    x: float = 0
    y: float = 0
    m2x: float = 0
    m2y: float = 0
    covariance: float = 0
    absolute_error: float = 0
    bias: float = 0
    reference: float = 0
    density_error: float = 0
    density_n: int = 0

    def add(self, left, right, reference_wc, prediction_wc):
        self.n += 1
        dx, dy = left - self.x, right - self.y
        self.x += dx / self.n
        self.y += dy / self.n
        self.m2x += dx * (left - self.x)
        self.m2y += dy * (right - self.y)
        self.covariance += dx * (right - self.y)
        self.absolute_error += abs(right - left)
        self.bias += right - left
        self.reference += left
        if reference_wc > 0 and prediction_wc > 0:
            self.density_error += abs(right / prediction_wc - left / reference_wc) * 100
            self.density_n += 1

    @property
    def ccc(self):
        denominator = self.m2x + self.m2y + self.n * (self.x - self.y) ** 2
        return 2 * self.covariance / denominator if denominator and self.n > 1 else None


def family(key):
    return key[1:].split(".", 1)[0]


@dataclass
class PresenceCounts:
    matched: int = 0
    reference: int = 0
    prediction: int = 0
    reference_positive: int = 0
    prediction_positive: int = 0

    def add(self, left, right):
        self.matched += len(left & right)
        self.reference += len(left)
        self.prediction += len(right)
        self.reference_positive += bool(left)
        self.prediction_positive += bool(right)

    def report(self, context, label, calculation, documents):
        context.add(
            label,
            calculation,
            prf(self.matched, self.prediction - self.matched, self.reference - self.matched),
            documents,
        )
        context.add(
            label,
            calculation + " / coverage",
            {
                "documents": documents,
                "reference_support": self.reference,
                "prediction_support": self.prediction,
                "reference_positive_documents": self.reference_positive,
                "prediction_positive_documents": self.prediction_positive,
            },
            documents,
        )


def gcam(context, name):
    """Accumulate count families without retaining parsed document/dimension matrices."""
    known = context.options.gcam_keys
    count_keys = set() if known is None else {k for k in known if k.startswith("c")}
    supported = count_keys
    observed: set[str] = set()
    native: set[str] = set()
    unexpected: set[str] = set()
    all_presence = PresenceCounts()
    presence: dict[str, PresenceCounts] = defaultdict(PresenceCounts)
    supported_presence: dict[str, PresenceCounts] = defaultdict(PresenceCounts)
    statistics_by_key = {key: CountStats() for key in sorted(count_keys)}
    exclusions: dict[str, int] = defaultdict(int)
    paired_scores = defaultdict(list)
    reference_scores: dict[str, int] = defaultdict(int)
    prediction_scores: dict[str, int] = defaultdict(int)
    documents = assignments = supported_assignments = 0
    occurrences = supported_occurrences = 0.0
    for left, right in context.iter_parsed(name, parsers.gcam):
        documents += 1
        observed.update(left)
        observed.update(right)
        unreported = {
            "c" + key[1:] for key in left if key.startswith("v") and "c" + key[1:] not in left
        }
        a = {k for k, v in left.items() if k.startswith("c") and v > 0 and k not in unreported}
        b = {k for k, v in right.items() if k.startswith("c") and v > 0 and k not in unreported}
        all_presence.add(a, b)
        native.update(a)
        assignments += len(a)
        supported_assignments += len(a & supported)
        left_families, right_families = defaultdict(set), defaultdict(set)
        for key in a:
            left_families[family(key)].add(key)
        for key in b:
            right_families[family(key)].add(key)
        for code in left_families.keys() | right_families.keys():
            aa, bb = left_families[code], right_families[code]
            presence[code].add(aa, bb)
            if known is not None:
                supported_presence[code].add(aa & supported, bb & supported)
        for key, value in left.items():
            if key.startswith("c"):
                occurrences += value
                if key in supported:
                    supported_occurrences += value
        if known is not None:
            unexpected.update(key for key in right if key.startswith("c") and key not in supported)
            for key, stats in statistics_by_key.items():
                if key in unreported:
                    exclusions[family(key)] += 1
                    continue
                stats.add(
                    left.get(key, 0), right.get(key, 0), left.get("wc", 0), right.get("wc", 0)
                )
        for key in left.keys() | right.keys():
            if key.startswith("v") or key in {"wc", "nwc"}:
                reference_scores[key] += key in left
                prediction_scores[key] += key in right
                if key in left and key in right:
                    paired_scores[key].append((left[key], right[key]))
    all_presence.report(context, "GCAM", "all-native category presence", documents)
    families = sorted({family(k) for k in observed if k.startswith("c")}, key=int)
    for code in families:
        label = "GCAM / " + FAMILY_NAMES.get(code, "Dictionary " + code)
        presence[code].report(context, label, "all-native presence", documents)
        if known is not None:
            supported_presence[code].report(context, label, "supported presence", documents)
    if known is None:
        context.note(
            "configuration",
            "gcam",
            "missing_inventory",
            "Supply --gcam-lexicon or prepared resources for supported count errors and coverage",
        )
    else:
        if unexpected:
            context.note(
                "prediction",
                "gcam",
                "outside_inventory",
                "Predicted count keys exceed the declared supported inventory",
                len(unexpected),
            )
        for code in sorted({family(k) for k in count_keys}, key=int):
            items = [s for k, s in statistics_by_key.items() if family(k) == code and s.n]
            n = sum(s.n for s in items)
            reference = sum(s.reference for s in items)
            density_n = sum(s.density_n for s in items)
            nonconstant = [s.ccc for s in items if s.m2x + s.m2y > 0]
            label = "GCAM / " + FAMILY_NAMES.get(code, "Dictionary " + code)
            context.add(
                label,
                "supported counts",
                {
                    "mae": sum(s.absolute_error for s in items) / n if n else None,
                    "count_wape": sum(s.absolute_error for s in items) / reference
                    if reference
                    else None,
                    "bias": sum(s.bias for s in items) / n if n else None,
                    "mean_dimension_ccc": statistics.mean(nonconstant) if nonconstant else None,
                    "density_mae_pp": sum(s.density_error for s in items) / density_n
                    if density_n
                    else None,
                },
                documents,
                "counts",
            )
            context.add(
                label,
                "count coverage",
                {
                    "paired_values": n,
                    "dimensions": len(items),
                    "excluded_unreported_counts": exclusions[code],
                },
                documents,
            )
        context.add(
            "GCAM",
            "coverage",
            {
                "dimension_coverage": len(native & supported) / len(native) if native else None,
                "assignment_coverage": supported_assignments / assignments if assignments else None,
                "occurrence_coverage": supported_occurrences / occurrences if occurrences else None,
                "supported_dimensions": len(supported),
                "observed_native_dimensions": len(native),
            },
            documents,
        )
    for key in sorted(k for k in observed if k.startswith("v")):
        pairs = paired_scores[key]
        values = numeric_metrics(pairs)
        context.add(
            "GCAM / " + FAMILY_NAMES.get(family(key), "Dictionary " + family(key)),
            key + " / weighted score",
            {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
            len(pairs),
            "score",
        )
        context.add(
            "GCAM",
            key + " / weighted-score coverage",
            {
                "paired_values": len(pairs),
                "reference_support": reference_scores[key],
                "prediction_support": prediction_scores[key],
                "sign_agreement": sum(weighted_sign(a) == weighted_sign(b) for a, b in pairs)
                / len(pairs)
                if pairs
                else None,
            },
            documents,
        )
    for key in ("wc", "nwc"):
        pairs = paired_scores[key]
        if pairs:
            values = numeric_metrics(pairs)
            context.add(
                "GCAM",
                key,
                {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
                len(pairs),
                "words",
            )
