"""Field registry and evaluation orchestration, independent of CLI/report formats."""

from . import categorical, numeric, structured
from .model import FIELD_NAMES, GROUPS, BenchmarkOptions, BenchmarkReport, ScoreContext

SCORERS = {
    **{name: categorical.metadata for name in GROUPS["metadata"]},
    **{name: categorical.categorical for name in ("themes", "persons", "organizations")},
    **{
        name: categorical.enhanced
        for name in ("enhanced_themes", "enhanced_persons", "enhanced_organizations", "all_names")
    },
    **{name: structured.counts for name in GROUPS["counts"]},
    **{name: structured.locations for name in GROUPS["locations"]},
    **{name: categorical.media for name in GROUPS["media"]},
    "enhanced_dates": structured.dates,
    "amounts": structured.amounts,
    "quotations": structured.quotations,
    "tone": numeric.tone,
    "gcam": numeric.gcam,
    "translation": categorical.translation,
    "extras_xml": categorical.extras,
}


def select_fields(names):
    selected: set[str] = set()
    for name in names:
        for value in name.split(","):
            if value == "all":
                selected.update(FIELD_NAMES)
            elif value in GROUPS:
                selected.update(GROUPS[value])
            elif value in SCORERS:
                selected.add(value)
            else:
                raise ValueError(f"Unknown benchmark field/group: {value}")
    if not selected:
        raise ValueError("Select at least one field")
    return tuple(name for name in FIELD_NAMES if name in selected)


def evaluate(pairs, *, fields=("all",), options=None, report=None, subset="all", progress=None):
    options = BenchmarkOptions() if options is None else options
    report = BenchmarkReport() if report is None else report
    context = ScoreContext(list(pairs), options, report, subset)
    names = tuple(fields)
    # CLI selection already expands groups and applies exclusions. Preserve
    # canonical field lists here, including exclusion of an enhanced partner.
    selected = names if names and all(name in SCORERS for name in names) else select_fields(names)
    for index, name in enumerate(selected, 1):
        if progress is not None:
            progress(f"[benchmark {index}/{len(selected)}] {subset}: {name}")
        SCORERS[name](context, name)
    if options.diagnostics:
        from .diagnostics import evaluate_diagnostics

        evaluate_diagnostics(context)
    return report
