"""Optional consistency and proximity diagnostics derived from existing fields."""

from . import parsers
from .common import add_sets


def evaluate_diagnostics(context):
    for plain, enhanced in (
        ("themes", "enhanced_themes"),
        ("persons", "enhanced_persons"),
        ("organizations", "enhanced_organizations"),
    ):
        for side, index in (("reference", 0), ("prediction", 1)):
            total = equal = 0
            for pair in context.pairs:
                row = pair[index]
                if row.get(plain) is None or row.get(enhanced) is None:
                    continue
                try:
                    left = {parsers.normalize(v) for v in parsers.blocks(row.get(plain))}
                    right = {
                        parsers.normalize(v.identity) for v in parsers.mentions(row.get(enhanced))
                    }
                except ValueError:
                    continue
                total += 1
                equal += left == right
            context.add(
                "Consistency",
                side + " / " + plain,
                {"exact_agreement": equal / total if total else None, "documents": total},
                total,
            )

    def values(row, name):
        cell = row.get(name)
        if cell is None:
            return None
        items = (
            parsers.locations(cell, enhanced=True)
            if name == "enhanced_locations"
            else parsers.mentions(cell)
        )
        return [(v.identity, v.offset) for v in items]

    window = context.options.proximity_window
    for first, second in (
        ("enhanced_themes", "enhanced_persons"),
        ("enhanced_themes", "enhanced_locations"),
        ("enhanced_persons", "enhanced_locations"),
    ):
        comparisons = []
        for pair in context.pairs:
            edges = []
            try:
                for row in pair:
                    a, b = values(row, first), values(row, second)
                    if a is None or b is None:
                        break
                    edges.append({(x, y) for x, u in a for y, v in b if abs(u - v) <= window})
            except ValueError:
                continue
            if len(edges) == 2:
                comparisons.append(tuple(edges))
        add_sets(context, "Proximity", f"{first} + {second}, ≤{window} chars", comparisons)
