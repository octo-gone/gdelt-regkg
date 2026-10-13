"""Tone components, GCAM family counts and independently defined weighted scores."""

import statistics
from collections import defaultdict
from dataclasses import dataclass

from . import parsers
from .common import add_sets
from .metrics import numeric_metrics, quantile

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


def gcam(context, name):
    rows = context.parsed(name, parsers.gcam)
    observed = set().union(*(a.keys() | b.keys() for a, b in rows)) if rows else set()
    families = sorted({family(k) for k in observed if k.startswith("c")}, key=int)
    known = context.options.gcam_keys
    count_keys = set() if known is None else {k for k in known if k.startswith("c")}
    supported = count_keys
    all_sets = []
    for a, b in rows:
        unreported = {"c" + key[1:] for key in a if key.startswith("v") and "c" + key[1:] not in a}
        all_sets.append(
            (
                {k for k, v in a.items() if k.startswith("c") and v > 0 and k not in unreported},
                {k for k, v in b.items() if k.startswith("c") and v > 0 and k not in unreported},
            )
        )
    add_sets(context, "GCAM", "all-native category presence", all_sets)
    for code in families:
        label = "GCAM / " + FAMILY_NAMES.get(code, "Dictionary " + code)
        subset = [
            ({k for k in a if family(k) == code}, {k for k in b if family(k) == code})
            for a, b in all_sets
        ]
        add_sets(context, label, "all-native presence", subset)
        if known is not None:
            keys = {k for k in supported if family(k) == code}
            add_sets(
                context, label, "supported presence", [(a & keys, b & keys) for a, b in subset]
            )
    if known is None:
        context.note(
            "configuration",
            "gcam",
            "missing_inventory",
            "Supply --gcam-lexicon or prepared resources for supported count errors and coverage",
        )
    else:
        unexpected = {key for a, b in rows for key in b if key.startswith("c")} - supported
        if unexpected:
            context.note(
                "prediction",
                "gcam",
                "outside_inventory",
                "Predicted count keys exceed the declared supported inventory",
                len(unexpected),
            )
        statistics_by_key = {key: CountStats() for key in sorted(count_keys)}
        exclusions: dict[str, int] = defaultdict(int)
        for left, right in rows:
            for key, stats in statistics_by_key.items():
                # Native weighted means can be reported without companion counts.
                # Their missing count is unreported, rather than a measured zero.
                companion = "v" + key[1:]
                if key not in left and companion in left:
                    exclusions[family(key)] += 1
                    continue
                stats.add(
                    left.get(key, 0), right.get(key, 0), left.get("wc", 0), right.get("wc", 0)
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
                len(rows),
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
                len(rows),
            )
        native = {k for a, b in all_sets for k in a}
        assignments = sum(len(a) for a, b in all_sets)
        occurrences = sum(value for a, b in rows for key, value in a.items() if key.startswith("c"))
        context.add(
            "GCAM",
            "coverage",
            {
                "dimension_coverage": len(native & supported) / len(native) if native else None,
                "assignment_coverage": sum(len(a & supported) for a, b in all_sets) / assignments
                if assignments
                else None,
                "occurrence_coverage": sum(
                    value for a, b in rows for key, value in a.items() if key in supported
                )
                / occurrences
                if occurrences
                else None,
                "supported_dimensions": len(supported),
                "observed_native_dimensions": len(native),
            },
            len(rows),
        )
    for key in sorted(k for k in observed if k.startswith("v")):
        pairs = [(a[key], b[key]) for a, b in rows if key in a and key in b]
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
                "reference_support": sum(key in a for a, b in rows),
                "prediction_support": sum(key in b for a, b in rows),
                "sign_agreement": sum((a > 0) - (a < 0) == (b > 0) - (b < 0) for a, b in pairs)
                / len(pairs)
                if pairs
                else None,
            },
            len(rows),
        )
    for key in ("wc", "nwc"):
        pairs = [(a[key], b[key]) for a, b in rows if key in a and key in b]
        if pairs:
            values = numeric_metrics(pairs)
            context.add(
                "GCAM",
                key,
                {k: values[k] for k in ("mae", "rmse", "bias", "ccc", "spearman")},
                len(pairs),
                "words",
            )
