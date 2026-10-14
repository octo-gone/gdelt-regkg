"""Statistical summaries with explicit empty-sample behavior."""

import math
import statistics
from collections import Counter

from ..dependencies import require_dependency


def prf(tp, fp, fn):
    return {
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def size(values):
    return sum(values.values()) if isinstance(values, Counter) else len(values)


def set_metrics(rows):
    tp = sum(size(a & b) for a, b in rows)
    reference, prediction = sum(size(a) for a, b in rows), sum(size(b) for a, b in rows)
    return prf(tp, prediction - tp, reference - tp) | {
        "true_positives": tp,
        "reference_support": reference,
        "prediction_support": prediction,
        "reference_positive_documents": sum(bool(a) for a, b in rows),
        "prediction_positive_documents": sum(bool(b) for a, b in rows),
        "exact_agreement": sum(a == b for a, b in rows) / len(rows) if rows else None,
    }


def quantile(values, probability):
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def numeric_metrics(pairs):
    if not pairs:
        return dict.fromkeys(
            ("mae", "rmse", "bias", "ccc", "spearman", "loa_lower", "loa_upper")
        ) | {"paired_values": 0}
    spearmanr = require_dependency("scipy.stats", "benchmark").spearmanr
    metrics = require_dependency("sklearn.metrics", "benchmark")
    mean_absolute_error = metrics.mean_absolute_error
    root_mean_squared_error = metrics.root_mean_squared_error

    left, right = map(list, zip(*pairs))
    errors = [b - a for a, b in pairs]
    x, y = statistics.mean(left), statistics.mean(right)
    vx, vy = statistics.pvariance(left), statistics.pvariance(right)
    covariance = statistics.mean((a - x) * (b - y) for a, b in pairs)
    denominator = vx + vy + (x - y) ** 2
    bias = statistics.mean(errors)
    spread = 1.96 * statistics.stdev(errors) if len(errors) > 1 else None
    return {
        "mae": float(mean_absolute_error(left, right)),
        "rmse": float(root_mean_squared_error(left, right)),
        "bias": bias,
        "ccc": 2 * covariance / denominator if denominator and len(pairs) > 1 else None,
        "spearman": float(spearmanr(left, right).statistic)
        if vx and vy and len(pairs) > 1
        else None,
        "paired_values": len(pairs),
        "loa_lower": bias - spread if spread is not None else None,
        "loa_upper": bias + spread if spread is not None else None,
    }


def offset_metrics(errors):
    return {
        "offset_mae_chars": statistics.mean(errors) if errors else None,
        "offset_median_chars": quantile(errors, 0.5),
        "offset_p90_chars": quantile(errors, 0.9),
        "matched_pairs": len(errors),
    }
