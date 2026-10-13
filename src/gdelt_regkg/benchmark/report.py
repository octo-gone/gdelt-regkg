"""Render the same numeric results as compact Markdown and explicit-column CSV."""

import csv
from pathlib import Path

LABELS = {
    "precision": "Precision",
    "recall": "Recall",
    "f1": "F1",
    "label_macro_f1": "Label macro F1",
    "mae": "MAE",
    "rmse": "RMSE",
    "bias": "Bias",
    "ccc": "CCC",
    "spearman": "Spearman",
    "validity_rate": "Validity",
    "exact_agreement": "Agreement",
    "sign_agreement": "Sign agreement",
    "kappa": "Kappa",
    "count_wape": "WAPE",
    "mean_dimension_ccc": "Mean dimension CCC",
    "density_mae_pp": "Density MAE",
    "offset_mae_chars": "MAE",
    "offset_median_chars": "Median",
    "offset_p90_chars": "P90",
    "distance_median_km": "Median distance",
    "distance_p90_km": "P90 distance",
    "loa_lower": "Lower limit",
    "loa_upper": "Upper limit",
    "length_mae_chars": "Length MAE",
    "documents": "Documents",
    "reference_rows": "Reference",
    "prediction_rows": "Predicted",
    "reference_support": "Reference",
    "prediction_support": "Predicted",
    "reference_positive_documents": "Reference-positive",
    "prediction_positive_documents": "Predicted-positive",
    "dimension_coverage": "Dimension coverage",
    "assignment_coverage": "Assignment coverage",
    "occurrence_coverage": "Occurrence coverage",
    "reference_coverage": "Reference coverage",
}
PERCENTAGES = {
    "validity_rate",
    "exact_agreement",
    "sign_agreement",
    "presence_agreement",
    "verb_agreement",
    "count_wape",
    "dimension_coverage",
    "assignment_coverage",
    "occurrence_coverage",
    "reference_coverage",
    "within_25_km",
    "within_100_km",
}


def escape(value):
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def format_metric(key, value, unit="", *, labelled=True):
    label = LABELS.get(key, key.replace("_", " ").capitalize())
    if value is None:
        formatted = "-"
    elif key in PERCENTAGES:
        formatted = f"{value * 100:.3f}%"
    elif isinstance(value, int):
        formatted = str(value)
    else:
        formatted = f"{value:.4f}"
    if value is not None:
        if key.endswith("_chars"):
            formatted += " chars"
        elif key.endswith("_km") and not key.startswith("within_"):
            formatted += " km"
        elif key.endswith("_pp"):
            formatted += " pp"
        elif key in {"mae", "rmse", "bias", "loa_lower", "loa_upper"} and unit:
            formatted += " " + unit
    prefix = f"**{escape(label)}**<br>" if labelled else ""
    return prefix + escape(formatted)


def markdown(report):
    lines = [
        "# GKG benchmark",
        "",
        "Each row names a calculation. Scores measure agreement with the supplied reference.",
        "",
        "| Field / calculation | Metric 1 | Metric 2 | Metric 3 | Metric 4 | Metric 5 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    fields: dict[tuple[str, str], list] = {}
    for row in report.rows:
        fields.setdefault((row.subset, row.field), []).append(row)
    for (subset, field), rows in fields.items():
        heading = field if subset == "all" else subset + " / " + field
        lines.append("| " + " | ".join([f"**{escape(heading)}**", "", "", "", "", ""]) + " |")
        layouts: dict[tuple, list] = {}
        for row in rows:
            values = list(row.metrics.items())
            for start in range(0, max(len(values), 1), 5):
                name = row.calculation or row.field
                if start:
                    name += f" / continued {start // 5 + 1}"
                chunk = values[start : start + 5]
                layout = tuple(key for key, _ in chunk), row.unit
                layouts.setdefault(layout, []).append((name, chunk, row.unit))
        for entries in layouts.values():
            for index, (name, values, unit) in enumerate(entries):
                cells = [
                    format_metric(key, value, unit, labelled=index == 0) for key, value in values
                ]
                cells += [""] * (5 - len(cells))
                lines.append("| " + " | ".join([escape(name), *cells]) + " |")
    lines += [
        "",
        "Metric labels apply to the following rows with the same layout within each field group.",
        "A dash (-) means a metric has no value; an empty cell means no metric applies.",
        "Offset errors use content matches before offset gating.",
        "Precision, recall, F1, CCC and correlations use their native scales. Percentages are labelled explicitly.",
        "See audit.csv for exclusions and run.md for input hashes, matching rules and settings.",
        "",
    ]
    return "\n".join(lines)


def write_report(report, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / "metrics.md").write_text(markdown(report), encoding="utf-8")
    columns = ["field", "calculation", "subset", "documents", "unit"]
    metrics = list(
        dict.fromkeys(key for row in report.rows for key in row.metrics if key not in columns)
    )
    with (output / "metrics.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=[*columns, *metrics])
        writer.writeheader()
        for row in report.rows:
            writer.writerow(
                {
                    "field": row.field,
                    "calculation": row.calculation,
                    "subset": row.subset,
                    "documents": row.documents,
                    "unit": row.unit,
                    **row.metrics,
                }
            )
    with (output / "audit.csv").open("w", encoding="utf-8", newline="") as stream:
        audit_writer = csv.writer(stream)
        audit_writer.writerow(["side", "field", "subset", "issue", "count", "detail"])
        for (side, field, issue, detail, subset), count in sorted(report.audit.items()):
            if count:
                audit_writer.writerow([side, field, subset, issue, count, detail])
    lines = ["# Benchmark run", "", "| Setting | Value |", "| --- | --- |"]
    lines.extend(
        f"| {escape(key)} | {escape(value)} |" for key, value in report.configuration.items()
    )
    lines += [
        "",
        "CSV percentages are fractions; density error is in percentage points. Error units are recorded per row.",
        "Blank CSV metrics are undefined or inapplicable. Unknown/unavailable fields are not empty predictions.",
        "Label-macro averages use observed labels on either side; zero-support per-label precision/recall contributes zero. An empty label population is undefined.",
        "Malformed native fields are excluded only from their field. Malformed categorical predictions are scored as empty and audited.",
        "GCAM count errors require an explicit supported-dimension inventory; missing native weighted companion counts are excluded.",
        "Weighted scores are compared only where both sides report a defined score; coverage is reported separately.",
        "The reference may use a different body snapshot. Offset diagnostics do not isolate extraction errors.",
        "",
    ]
    (output / "run.md").write_text("\n".join(lines), encoding="utf-8")
    return output / "metrics.md"
