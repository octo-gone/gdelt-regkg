"""Count, amount, calendar, location and quotation identities and occurrences."""

import math
import statistics
from collections import Counter
from difflib import SequenceMatcher

from . import parsers
from .common import add_mentions, add_sets
from .matching import assignment, match_by_key
from .metrics import offset_metrics, prf, quantile


def counts(context, name):
    enhanced = name == "enhanced_counts"
    rows = context.parsed(name, lambda cell: parsers.counts(cell, enhanced=enhanced))
    label = "Enhanced counts" if enhanced else "Counts"
    if not enhanced:
        add_sets(
            context,
            label,
            "labels",
            [({v.label for v in a}, {v.label for v in b}) for a, b in rows],
        )
    levels = {
        "label + quantity": lambda v: (v.label, v.quantity),
        "object": lambda v: (v.label, v.quantity, v.object),
        "full tuple": lambda v: (v.label, v.quantity, v.object, v.geography),
    }
    for level, key in levels.items():
        if enhanced:
            add_mentions(context, label, level, rows, key)
        else:
            add_sets(
                context,
                label,
                level,
                [(Counter(key(v) for v in a), Counter(key(v) for v in b)) for a, b in rows],
            )
    if context.options.relaxed:
        relaxed_objects(context, label, rows, counts=True)


def relaxed_objects(context, label, rows, *, counts=False):
    def cost(a, b):
        if counts and a.label != b.label:
            return None
        similarity = SequenceMatcher(None, a.object, b.object, autojunk=False).ratio()
        if similarity < context.options.object_similarity:
            return None
        error = abs(a.quantity - b.quantity) / max(abs(a.quantity), 1)
        if error > context.options.number_tolerance:
            return None
        return 1 - similarity + float(error)

    comparisons = []
    offset_errors = []
    magnitude_errors = []
    for left, right in rows:
        matches = assignment(left, right, cost)
        paired = {j: i for i, j in matches}
        comparisons.append(
            (
                Counter(range(len(left))),
                Counter(paired.get(j, ("unmatched", j)) for j in range(len(right))),
            )
        )
        for i, j in matches:
            a, b = left[i], right[j]
            magnitude_errors.append(abs(float(a.quantity - b.quantity)))
            if a.offset is not None and b.offset is not None:
                offset_errors.append(abs(a.offset - b.offset))
    level = f"relaxed object ≥{context.options.object_similarity:g}, quantity ±{context.options.number_tolerance:.0%}"
    add_sets(context, label, level, comparisons)
    context.add(
        label,
        level + " / errors",
        {
            "quantity_mae": statistics.mean(magnitude_errors) if magnitude_errors else None,
            "matched_pairs": len(magnitude_errors),
        },
        len(rows),
    )
    if offset_errors:
        context.add(label, level + " / offset error", offset_metrics(offset_errors), len(rows))


def amounts(context, name):
    rows = context.parsed(name, parsers.amounts)
    add_sets(
        context,
        "Amounts",
        "values",
        [({v.quantity for v in a}, {v.quantity for v in b}) for a, b in rows],
    )
    key = lambda v: (v.quantity, v.object)
    add_sets(
        context,
        "Amounts",
        "value + object",
        [({key(v) for v in a}, {key(v) for v in b}) for a, b in rows],
    )
    add_mentions(context, "Amounts", "occurrences", rows, key)
    if context.options.relaxed:
        relaxed_objects(context, "Amounts", rows)


def dates(context, name):
    rows = context.parsed(name, parsers.dates)
    add_sets(
        context,
        "Dates",
        "components",
        [({v.identity for v in a}, {v.identity for v in b}) for a, b in rows],
    )
    for resolution, label in (
        (1, "year"),
        (2, "month/year"),
        (3, "day/month/year"),
        (4, "day/month"),
    ):
        subset = [
            (
                [v for v in a if v.identity[0] == resolution],
                [v for v in b if v.identity[0] == resolution],
            )
            for a, b in rows
        ]
        add_sets(
            context,
            "Dates",
            label + " components",
            [({v.identity for v in a}, {v.identity for v in b}) for a, b in subset],
        )
    add_mentions(context, "Dates", "occurrences", rows, lambda v: v.identity)


def distance(a, b):
    if None in (a.latitude, a.longitude, b.latitude, b.longitude):
        return None
    first, second = math.radians(a.latitude), math.radians(b.latitude)
    latitude = second - first
    longitude = math.radians(b.longitude - a.longitude)
    chord = (
        math.sin(latitude / 2) ** 2
        + math.cos(first) * math.cos(second) * math.sin(longitude / 2) ** 2
    )
    return 6371.0088 * 2 * math.asin(min(1, math.sqrt(chord)))


def locations(context, name):
    enhanced = name == "enhanced_locations"
    rows = context.parsed(name, lambda cell: parsers.locations(cell, enhanced=enhanced))
    label = "Enhanced locations" if enhanced else "Locations"
    add_sets(
        context,
        label,
        "identities",
        [({v.identity for v in a}, {v.identity for v in b}) for a, b in rows],
    )
    for level, key in (
        ("country", lambda v: (v.country,) if v.country else None),
        ("ADM1", lambda v: (v.country, v.adm1) if v.adm1 else None),
        ("ADM2", lambda v: (v.country, v.adm1, v.adm2) if v.adm2 else None),
    ):
        if level == "ADM2" and not enhanced:
            continue
        add_sets(
            context,
            label,
            level,
            [
                (
                    {key(v) for v in a if key(v) is not None},
                    {key(v) for v in b if key(v) is not None},
                )
                for a, b in rows
            ],
        )
    if enhanced:
        add_mentions(context, label, "occurrences", rows, lambda v: v.identity)
    distances = []
    for left, right in rows:
        for i, j in match_by_key(left, right, lambda v: v.identity):
            error = distance(left[i], right[j])
            if error is not None:
                distances.append(error)
    context.add(
        label,
        "coordinate error on identity matches",
        {
            "distance_median_km": quantile(distances, 0.5),
            "distance_p90_km": quantile(distances, 0.9),
            "within_25_km": sum(v <= 25 for v in distances) / len(distances) if distances else None,
            "within_100_km": sum(v <= 100 for v in distances) / len(distances)
            if distances
            else None,
            "matched_pairs": len(distances),
        },
        len(rows),
    )


def quotations(context, name):
    rows = context.parsed(name, parsers.quotations)
    add_sets(
        context,
        "Quotations",
        "content",
        [({v.text for v in a}, {v.text for v in b}) for a, b in rows],
    )
    add_sets(
        context,
        "Quotations",
        "content + verb",
        [({(v.text, v.verb) for v in a}, {(v.text, v.verb) for v in b}) for a, b in rows],
    )
    add_mentions(context, "Quotations", "occurrences", rows, lambda v: v.text)
    matches = [
        (left[i], right[j])
        for left, right in rows
        for i, j in match_by_key(left, right, lambda v: v.text)
    ]
    context.add(
        "Quotations",
        "boundaries and verbs on content matches",
        {
            "length_mae_chars": statistics.mean(abs(a.length - b.length) for a, b in matches)
            if matches
            else None,
            "verb_agreement": sum(a.verb == b.verb for a, b in matches) / len(matches)
            if matches
            else None,
            "matched_pairs": len(matches),
        },
        len(rows),
    )
    if context.options.relaxed:
        relaxed = []
        tokens: Counter[str] = Counter()
        matched_count = 0
        for left, right in rows:

            def cost(a, b):
                similarity = SequenceMatcher(None, a.text, b.text, autojunk=False).ratio()
                gap = abs(a.offset - b.offset)
                return (
                    gap + 1 - similarity
                    if similarity >= context.options.quote_similarity
                    and gap <= context.options.offset_tolerance
                    else None
                )

            paired = assignment(left, right, cost)
            mapping = {j: i for i, j in paired}
            relaxed.append(
                (
                    Counter(range(len(left))),
                    Counter(mapping.get(j, ("unmatched", j)) for j in range(len(right))),
                )
            )
            for i, j in paired:
                a, b = Counter(left[i].text.split()), Counter(right[j].text.split())
                common = sum((a & b).values())
                tokens.update(tp=common, fp=sum(b.values()) - common, fn=sum(a.values()) - common)
                matched_count += 1
        level = f"relaxed text ≥{context.options.quote_similarity:g}, offset ≤{context.options.offset_tolerance} chars"
        add_sets(context, "Quotations", level, relaxed)
        context.add(
            "Quotations",
            level + " / text",
            {
                **prf(tokens["tp"], tokens["fp"], tokens["fn"]),
                "matched_pairs": matched_count,
            },
            len(rows),
        )
