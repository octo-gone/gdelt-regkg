"""Download the original ANEW report and convert its three rating tables to CSV.

Run with ``python -m gdelt_regkg.builders.anew --help``. The build command uses
the same converter. PDF extraction requires the ``build`` extra or pdftotext.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from ..dependencies import require_dependency

# The original report has 1,034 records; these six word numbers are absent.
WORD_IDS = frozenset(range(1, 1041)) - {142, 144, 600, 676, 739, 820}
GROUPS = {"All": "All", "Male": "Men", "Female": "Women"}
RATINGS = ("Valence (Pleasure)", "Arousal", "Dominance")
HEADER = re.compile(r"Affective\s+Norms\s+for\s+English\s+Words\.\s*(All|Male|Female)\s+Subjects")
RATING = r"(\d+\.\d+)\s*\(\s*(\d+\.\d+)\s*\)"
ROW = re.compile(
    r"([A-Za-z][A-Za-z -]*?)\s+(\d+)\s+"
    + RATING
    + r"\s+"
    + RATING
    + r"\s+"
    + RATING
    + r"\s+(\d+|\.)(?=\s|$)"
)


def anew_csv(text: str) -> bytes:
    """Validate all participant tables and join by word number, preserving means."""
    tables: dict[str, dict[int, tuple[str, tuple[str, ...]]]] = {key: {} for key in GROUPS}
    group = None
    for line in text.splitlines():
        if header := HEADER.search(line):
            group = header[1]
            continue
        if group is None or not re.search(r"\d+\.\d+", line):
            continue
        matches = list(ROW.finditer(line))
        if not matches or ROW.sub("", line).strip():
            raise ValueError(f"Unrecognized ANEW {group} table row: {line.strip()}")
        for match in matches:
            word, number, *scores, _frequency = match.groups()
            code = int(number)
            if code in tables[group]:
                raise ValueError(f"Duplicate ANEW {group} word number: {code}")
            if any(not 1 <= float(value) <= 9 for value in scores[::2]) or any(
                not 0 <= float(value) <= 9 for value in scores[1::2]
            ):
                raise ValueError(f"Invalid ANEW {group} rating for word {code}")
            tables[group][code] = (" ".join(word.casefold().split()), tuple(scores[::2]))
    for label, entries in tables.items():
        if entries.keys() != WORD_IDS:
            raise ValueError(
                f"Incomplete ANEW {label} table: expected {len(WORD_IDS)} word numbers, "
                f"found {len(entries)}; missing IDs (first 10) {sorted(WORD_IDS - entries.keys())[:10]}; "
                f"unexpected IDs (first 10) {sorted(entries.keys() - WORD_IDS)[:10]}"
            )
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        ["word", *(f"{rating} ({label})" for label in GROUPS.values() for rating in RATINGS)]
    )
    words = set()
    for code in sorted(WORD_IDS):
        word = tables["All"][code][0]
        if any(entries[code][0] != word for entries in tables.values()) or word in words:
            raise ValueError(f"Inconsistent ANEW word identity for word number {code}")
        words.add(word)
        writer.writerow(
            [word, *(score for entries in tables.values() for score in entries[code][1])]
        )
    return output.getvalue().encode("utf-8")


def pdf_text(raw: bytes, *, backend: str = "auto") -> str:
    """Extract layout text with optional pypdf or an installed pdftotext binary."""
    if backend not in {"auto", "pypdf", "pdftotext"}:
        raise ValueError("ANEW PDF backend must be auto, pypdf or pdftotext")
    executable = shutil.which("pdftotext") if backend != "pypdf" else None
    if backend == "pdftotext" and executable is None:
        raise FileNotFoundError(
            "pdftotext is unavailable; install Poppler/Xpdf or use --backend pypdf"
        )
    if executable is not None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "anew.pdf"
            path.write_bytes(raw)
            try:
                result = subprocess.run(
                    [executable, "-layout", "-enc", "UTF-8", str(path), "-"],
                    check=True,
                    capture_output=True,
                    timeout=90,
                )
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as error:
                raise ValueError("pdftotext could not extract the ANEW report") from error
        return result.stdout.decode("utf-8")
    pypdf = require_dependency("pypdf", "build")
    reader = pypdf.PdfReader(io.BytesIO(raw))
    pages = []
    for page in reader.pages:
        if HEADER.search(page.extract_text() or "") is None:
            continue
        page.transfer_rotation_to_content()
        pages.append(page.extract_text(extraction_mode="layout") or "")
    return "\n".join(pages)


def convert_anew_pdf(raw: bytes, *, backend: str = "auto") -> bytes:
    """Convert a PDF to the deterministic nine-mean-rating GCAM interchange CSV."""
    return anew_csv(pdf_text(raw, backend=backend))


def main(argv: list[str] | None = None) -> None:
    """Acquire the recorded report or convert an explicitly supplied local PDF."""
    from ..cli.sources import download_source, verify_source
    from ..utils import read_resource_json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("downloads/resources/anew.csv"))
    parser.add_argument("--pdf", type=Path, help="Convert a local report instead of downloading")
    parser.add_argument("--backend", choices=("auto", "pypdf", "pdftotext"), default="auto")
    args = parser.parse_args(argv)
    entry = read_resource_json("recipes.json")["sources"]["anew"]
    if args.pdf is None:
        download_source(args.output, {**entry, "pdf_backend": args.backend}, progress=print)
    else:
        raw = args.pdf.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["pdf_sha256"]:
            raise ValueError("ANEW PDF checksum mismatch; supply the recorded report edition")
        converted = convert_anew_pdf(raw, backend=args.backend)
        if hashlib.sha256(converted).hexdigest() != entry["sha256"]:
            raise ValueError("ANEW CSV checksum mismatch; no file was installed")
        if args.output.is_file():
            verify_source(args.output, entry)
        else:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(converted)
    print(f"ANEW CSV: {args.output}")


if __name__ == "__main__":
    main()
