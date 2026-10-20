"""Reusable score rows; coverage and offset diagnostics have separate rows."""

from collections import Counter

from .matching import match_by_key
from .metrics import offset_metrics, set_metrics


def add_sets(context, field, calculation, rows, *, agreement=False, macro=False):
    if context.article_sink is not None:
        from .metrics import size

        for reference, (expected, actual) in zip(context._article_references, rows, strict=True):
            tp = size(expected & actual)
            support, predicted = size(expected), size(actual)
            union = support + predicted - tp
            context.article(
                reference,
                field,
                calculation,
                "set",
                tp=tp,
                reference=support,
                prediction=predicted,
                exact=int(expected == actual),
                jaccard=tp / union if union else None,
            )
    values = set_metrics(rows)
    metrics = {name: values[name] for name in ("precision", "recall", "f1")}
    if macro:
        totals: dict[object, list[int]] = {}
        for expected, actual in rows:
            for label in expected | actual:
                counts = totals.setdefault(label, [0, 0, 0])
                counts[0] += label in expected and label in actual
                counts[1] += label in actual and label not in expected
                counts[2] += label in expected and label not in actual
    context.add(field, calculation, metrics, len(rows))
    if macro:
        count = len(totals)
        context.add(
            field,
            calculation + " / label macro",
            {
                "precision": sum(tp / (tp + fp) if tp + fp else 0 for tp, fp, fn in totals.values())
                / count
                if count
                else None,
                "recall": sum(tp / (tp + fn) if tp + fn else 0 for tp, fp, fn in totals.values())
                / count
                if count
                else None,
                "f1": sum(2 * tp / (2 * tp + fp + fn) for tp, fp, fn in totals.values()) / count
                if count
                else None,
            },
            len(rows),
        )
    if agreement:
        context.add(
            field,
            calculation + " / document agreement",
            {"exact_agreement": values["exact_agreement"]},
            len(rows),
        )
    context.add(
        field,
        calculation + " / coverage",
        {
            "documents": len(rows),
            "reference_support": values["reference_support"],
            "prediction_support": values["prediction_support"],
            "reference_positive_documents": values["reference_positive_documents"],
            "prediction_positive_documents": values["prediction_positive_documents"],
        },
        len(rows),
    )


def add_mentions(context, field, calculation, rows, key):
    """Content matches determine offset errors before any offset gate is applied."""
    add_sets(
        context,
        field,
        calculation + " / content",
        [(Counter(key(item) for item in a), Counter(key(item) for item in b)) for a, b in rows],
    )
    tolerances = [0]
    if context.options.offset_tolerance:
        tolerances.append(context.options.offset_tolerance)
    for tolerance in tolerances:
        pairs = []
        for left, right in rows:
            matched = match_by_key(left, right, key, tolerance)
            actual = {j: i for i, j in matched}
            pairs.append(
                (
                    Counter(range(len(left))),
                    Counter(actual.get(j, ("unmatched", j)) for j in range(len(right))),
                )
            )
        suffix = "exact offset" if tolerance == 0 else f"offset ≤{tolerance} chars"
        add_sets(context, field, calculation + " / " + suffix, pairs)
    errors = []
    for left, right in rows:
        for i, j in match_by_key(left, right, key):
            errors.append(abs(left[i].offset - right[j].offset))
    context.add(field, calculation + " / offset error", offset_metrics(errors), len(rows))
