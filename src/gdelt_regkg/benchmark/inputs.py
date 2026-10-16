"""Discover local inputs and read encoded GKG rows."""

import gzip
import io
import json
import zipfile
from pathlib import Path

from gdelt_regkg.utils import GKG_COLUMNS

from .metrics import prf
from .model import FIELD_NAMES, BenchmarkReport, GKGRow, ResultRow

ALIASES = dict(zip(GKG_COLUMNS, FIELD_NAMES)) | {
    "record_id": "recordid",
    "batch": "date",
    "url": "document",
    "translation_info": "translation",
}
GKG_SUFFIXES = (".csv", ".tsv", ".jsonl", ".csv.gz", ".tsv.gz", ".jsonl.gz", ".zip")
CORPUS_SUFFIXES = (".jsonl", ".jsonl.gz", ".zip")


def resolve_inputs(paths, *, corpus=False):
    """Expand directories recursively and include each resolved file once."""
    suffixes = CORPUS_SUFFIXES if corpus else GKG_SUFFIXES
    resolved = []
    seen = set()
    for path in map(Path, paths):
        if path.is_dir():
            candidates = sorted(
                (p for p in path.rglob("*") if p.is_file() and p.name.lower().endswith(suffixes)),
                key=lambda p: p.as_posix(),
            )
            if not candidates:
                raise ValueError(f"No supported input files in directory: {path}")
        else:
            if not path.is_file():
                raise ValueError(f"Input file or directory does not exist: {path}")
            if not path.name.lower().endswith(suffixes):
                raise ValueError(
                    f"Unsupported input extension: {path}; expected {', '.join(suffixes)}"
                )
            candidates = [path]
        for candidate in candidates:
            identity = candidate.resolve()
            if identity not in seen:
                seen.add(identity)
                resolved.append(identity)
    if not resolved:
        raise ValueError("Select at least one input file or directory")
    return resolved


def json_row(payload: dict, origin: str = "") -> GKGRow:
    if not isinstance(payload, dict):
        raise ValueError("GKG JSONL requires an object")
    if "native_cells" in payload:
        cells = payload["native_cells"]
        if not isinstance(cells, list) or len(cells) != len(FIELD_NAMES):
            raise ValueError("native_cells must contain 27 strings")
        payload = dict(zip(FIELD_NAMES, cells))
    values = {}
    for key, value in payload.items():
        name = ALIASES.get(key, key)
        if name not in FIELD_NAMES and name != "_gcam_languages":
            continue
        if value is not None and not isinstance(value, str):
            raise ValueError(f"GKG field {name} must be a string or null")
        values[name] = value
    if not values.get("document"):
        raise ValueError("Missing document identifier")
    return GKGRow(values, origin)


def iter_lines(path: Path):
    """Yield (origin, line, is_json) from plain, gzip or ZIP inputs."""
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            found = False
            for member in sorted(archive.namelist()):
                if member.endswith("/") or not member.lower().endswith((".csv", ".tsv", ".jsonl")):
                    continue
                found = True
                with (
                    archive.open(member) as raw,
                    io.TextIOWrapper(raw, encoding="utf-8-sig", errors="replace") as stream,
                ):
                    for index, line in enumerate(stream, 1):
                        yield f"{path}:{member}:{index}", line, member.lower().endswith(".jsonl")
            if not found:
                raise ValueError(f"ZIP contains no CSV, TSV or JSONL members: {path}")
    else:
        opener = gzip.open if path.suffix.lower() == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig", errors="replace") as stream:
            for index, line in enumerate(stream, 1):
                yield f"{path}:{index}", line, path.name.lower().endswith((".jsonl", ".jsonl.gz"))


def load_rows(
    paths,
    *,
    report: BenchmarkReport,
    side: str,
    strict=False,
    source_collections=("1",),
    wanted_documents=None,
    destination=None,
):
    rows = [] if destination is None else destination
    for path in resolve_inputs(paths):
        for origin, line, is_json in iter_lines(path):
            if not line.strip():
                continue
            try:
                if is_json:
                    row = json_row(json.loads(line), origin)
                else:
                    cells = line.rstrip("\r\n").split("\t")
                    if cells == GKG_COLUMNS:
                        continue
                    if len(cells) != len(FIELD_NAMES):
                        raise ValueError("Expected 27 tab-separated GKG columns")
                    row = json_row(dict(zip(FIELD_NAMES, cells)), origin)
                if (
                    source_collections is not None
                    and row.get("source_collection") not in source_collections
                ):
                    report.note(side, "alignment", "filtered_source_collection")
                    continue
                if wanted_documents is not None and row.get("document") not in wanted_documents:
                    report.note(side, "alignment", "outside_corpus")
                    continue
                rows.append(row)
            except (ValueError, TypeError) as error:
                if strict:
                    raise ValueError(f"{origin}: {error}") from error
                report.note(side, "input", "malformed_row", str(error))
    return rows


def align_rows(reference, prediction, *, report: BenchmarkReport, match="document-date"):
    """Reject ambiguous keys instead of pairing unrelated duplicate rows by order."""

    def key(row):
        if match == "record-id":
            if not row.get("recordid"):
                raise ValueError("--match record-id requires record IDs on both sides")
            return row.get("recordid"), row.get("document")
        base = row.get("source_collection"), row.get("document")
        return (*base, row.get("date")) if match == "document-date" else base

    def index(rows, side):
        grouped: dict[tuple, GKGRow] = {}
        conflicts = set()
        for row in rows:
            identity = key(row)
            if identity in grouped:
                report.note(side, "alignment", "duplicate_row")
                if grouped[identity].values != row.values:
                    conflicts.add(identity)
            else:
                grouped[identity] = row
        for identity in conflicts:
            report.note(side, "alignment", "conflicting_key")
            grouped.pop(identity)
        return grouped, conflicts

    left, bad_left = index(reference, "reference")
    right, bad_right = index(prediction, "prediction")
    ambiguous = bad_left | bad_right
    keys = (left.keys() & right.keys()) - ambiguous
    report.note(
        "reference",
        "alignment",
        "unmatched_document",
        count=len(left.keys() - right.keys() - ambiguous),
    )
    report.note(
        "prediction",
        "alignment",
        "unmatched_document",
        count=len(right.keys() - left.keys() - ambiguous),
    )
    report.note("both", "alignment", "ambiguous_document", count=len(ambiguous))
    if not keys:
        raise ValueError("No unambiguous matching documents; check --match and the input datasets")
    report.rows.append(
        ResultRow(
            "Alignment",
            "documents",
            prf(
                len(keys),
                len(right.keys() - left.keys() - ambiguous),
                len(left.keys() - right.keys() - ambiguous),
            ),
            len(keys),
        )
    )
    report.rows.append(
        ResultRow(
            "Alignment",
            "coverage",
            {
                "matched": len(keys),
                "reference_rows": len(reference),
                "prediction_rows": len(prediction),
            },
            len(keys),
        )
    )
    return [
        (left[k], right[k]) for k in sorted(keys, key=lambda values: tuple(v or "" for v in values))
    ]
