"""GCAM agreement accumulators and publisher-cluster uncertainty estimates."""

import random
import statistics
from collections import Counter
from dataclasses import dataclass, field

from .metrics import prf, quantile

LANGUAGE_NAMES = {
    "eng": "English",
    "ara": "Arabic",
    "cat": "Catalan",
    "deu": "German",
    "fra": "French",
    "glg": "Galician",
    "hin": "Hindi",
    "hun": "Hungarian",
    "ind": "Indonesian",
    "kor": "Korean",
    "por": "Portuguese",
    "rus": "Russian",
    "spa": "Spanish",
    "swe": "Swedish",
    "urd": "Urdu",
    "zho": "Chinese",
    "ron": "Romanian",
    "lav": "Latvian",
}


def language_label(code):
    return f"{LANGUAGE_NAMES[code]} ({code})" if code in LANGUAGE_NAMES else code


def dimension_sort_key(key):
    """Order dictionary/category identifiers numerically, preserving c/v ties."""
    return (*map(int, key[1:].split(".")), key[0])


@dataclass
class CountStats:
    n: int = 0
    x: float = 0
    y: float = 0
    m2x: float = 0
    m2y: float = 0
    covariance: float = 0
    absolute_error: float = 0
    squared_error: float = 0
    bias: float = 0
    reference: float = 0
    density_error: float = 0
    density_n: int = 0
    exact: int = 0
    within_one: int = 0

    def add(self, left, right, reference_wc, prediction_wc):
        self.n += 1
        dx, dy = left - self.x, right - self.y
        self.x += dx / self.n
        self.y += dy / self.n
        self.m2x += dx * (left - self.x)
        self.m2y += dy * (right - self.y)
        self.covariance += dx * (right - self.y)
        error = right - left
        self.absolute_error += abs(error)
        self.squared_error += error * error
        self.bias += error
        self.reference += left
        self.exact += error == 0
        self.within_one += abs(error) <= 1
        if reference_wc > 0 and prediction_wc > 0:
            self.density_error += abs(right / prediction_wc - left / reference_wc) * 100
            self.density_n += 1

    @property
    def ccc(self):
        denominator = self.m2x + self.m2y + self.n * (self.x - self.y) ** 2
        return 2 * self.covariance / denominator if denominator and self.n > 1 else None


def count_summary(items):
    items = [item for item in items if item.n]
    n = sum(item.n for item in items)
    reference = sum(item.reference for item in items)
    density_n = sum(item.density_n for item in items)
    concordance = [item.ccc for item in items if item.m2x + item.m2y > 0]
    return {
        "mae": sum(item.absolute_error for item in items) / n if n else None,
        "rmse": (sum(item.squared_error for item in items) / n) ** 0.5 if n else None,
        "count_wape": sum(item.absolute_error for item in items) / reference if reference else None,
        "bias": sum(item.bias for item in items) / n if n else None,
        "mean_dimension_ccc": statistics.mean(concordance) if concordance else None,
        "density_mae_pp": sum(item.density_error for item in items) / density_n
        if density_n
        else None,
        "exact_agreement": sum(item.exact for item in items) / n if n else None,
        "within_one_count": sum(item.within_one for item in items) / n if n else None,
        "paired_values": n,
        "dimensions": len(items),
        "density_pairs": density_n,
        "ccc_dimensions": len(concordance),
    }


@dataclass
class PresenceCounts:
    matched: int = 0
    reference: int = 0
    prediction: int = 0
    reference_positive: int = 0
    prediction_positive: int = 0
    tp: Counter = field(default_factory=Counter)
    expected: Counter = field(default_factory=Counter)
    actual: Counter = field(default_factory=Counter)
    documents: int = 0
    active_documents: int = 0
    document_f1: float = 0
    jaccard: float = 0
    exact: int = 0

    def add(self, left, right):
        intersection = left & right
        self.matched += len(intersection)
        self.reference += len(left)
        self.prediction += len(right)
        self.reference_positive += bool(left)
        self.prediction_positive += bool(right)
        self.tp.update(intersection)
        self.expected.update(left)
        self.actual.update(right)
        self.documents += 1
        self.exact += left == right
        if left or right:
            self.active_documents += 1
            self.document_f1 += 2 * len(intersection) / (len(left) + len(right))
            self.jaccard += len(intersection) / len(left | right)

    def macro(self):
        labels = self.expected.keys() | self.actual.keys()
        values = [
            prf(self.tp[k], self.actual[k] - self.tp[k], self.expected[k] - self.tp[k])
            for k in labels
        ]
        return {
            "precision": statistics.mean(v["precision"] or 0 for v in values) if values else None,
            "recall": statistics.mean(v["recall"] or 0 for v in values) if values else None,
            "f1": statistics.mean(v["f1"] or 0 for v in values) if values else None,
            "dimensions": len(labels),
        }

    def report(self, context, label, calculation, documents):
        context.add(
            label,
            calculation,
            prf(self.matched, self.prediction - self.matched, self.reference - self.matched),
            documents,
        )
        context.add(label, calculation + " / label macro", self.macro(), documents)
        context.add(
            label,
            calculation + " / document agreement",
            {
                "mean_document_f1": self.document_f1 / self.active_documents
                if self.active_documents
                else None,
                "mean_document_jaccard": self.jaccard / self.active_documents
                if self.active_documents
                else None,
                "exact_agreement": self.exact / self.documents if self.documents else None,
                "active_documents": self.active_documents,
                "empty_documents": self.documents - self.active_documents,
            },
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


def publisher_intervals(clusters, samples, seed):
    """Resample whole publishers, preserving related articles within each draw."""
    groups = list(clusters.values())
    if len(groups) < 2 or not samples:
        return {key: (None, None) for key in ("micro_f1", "document_jaccard", "count_wape")}
    rng = random.Random(seed)
    distributions: dict[str, list[float]] = {
        key: [] for key in ("micro_f1", "document_jaccard", "count_wape")
    }
    for _ in range(samples):
        total = [0.0] * 7
        for _ in groups:
            values = rng.choice(groups)
            for index, value in enumerate(values):
                total[index] += value
        tp, reference, prediction, jaccard, documents, error, count_reference = total
        if reference + prediction:
            distributions["micro_f1"].append(2 * tp / (reference + prediction))
        if documents:
            distributions["document_jaccard"].append(jaccard / documents)
        if count_reference:
            distributions["count_wape"].append(error / count_reference)
    return {
        key: (quantile(values, 0.025), quantile(values, 0.975))
        for key, values in distributions.items()
    }
