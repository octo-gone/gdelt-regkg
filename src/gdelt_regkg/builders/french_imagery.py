"""Convert the French imagery paper's appendix to approximate midpoint scores.

Run ``python -m gdelt_regkg.builders.french_imagery --help``. PDFium renders the
scanned appendix; Tesseract recognizes individual text lines using French data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import re
import unicodedata
import warnings
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter
from typing import Any

from ..dependencies import require_dependency
from ..fields.gcam_tokens import tokenize_gcam
from ..fields.tone import _normalize
from ..utils import read_resource_json

CLASSES = {
    "I": (15, 24, 41),
    "II": (25, 34, 260),
    "III": (35, 44, 256),
    "IV": (45, 54, 293),
    "V": (55, 64, 278),
    "VI": (65, 70, 2),
}
APPROXIMATION = "class-midpoint"
OCR_ENGINE = "tesseract"
OCR_TIMEOUT = 120
OCR_CONFIG = "--psm 7 --oem 1"
OCR_DATA_DIR = Path("downloads/resources/models/tesseract")
OCR_RENDER_SCALE = 2
OCR_LINE_SCALE = 1.5
HEADER = re.compile(
    r"(?:^\s*Classe\s+([^\n(]+)\s*\(valences([^\n]*)|^\[([IVX]+)\]\s*$)", re.I | re.M
)


def _ocr_metadata() -> dict[str, Any]:
    entry = read_resource_json("recipes.json")["sources"]["tesseract-french"]
    return {
        "ocr_engine": OCR_ENGINE,
        "ocr_language": "fra",
        "ocr_config": OCR_CONFIG,
        "ocr_language_data_sha256": entry["sha256"],
        "ocr_language_data_url": entry["url"],
        "ocr_renderer": "pypdfium2; grayscale",
        "ocr_render_scale": OCR_RENDER_SCALE,
        "ocr_line_scale": OCR_LINE_SCALE,
    }


def _class_label(match: re.Match[str]) -> str:
    """Recover damaged Roman numerals only from the printed rating interval."""
    label = (match[1] or match[3]).strip().upper()
    if match[3]:
        return label
    values = [
        round(float(value.replace(",", ".")) * 10)
        for value in re.findall(r"\b\d[.,]\d\b", match[2])
    ]
    candidates = [
        name
        for name, (lower, upper, _) in CLASSES.items()
        if values == ([lower] if name == "VI" else [lower, upper])
    ]
    if len(candidates) == 1:
        recovered = candidates[0]
        if label in CLASSES and label != recovered:
            raise ValueError("French imagery class label conflicts with its rating interval")
        return recovered
    return label


def verify_pdf(raw: bytes) -> str:
    """Require the recorded edition before applying its page and class mapping."""
    checksum = hashlib.sha256(raw).hexdigest()
    expected = read_resource_json("recipes.json")["sources"]["french-imagery-report"]["sha256"]
    if checksum != expected:
        raise ValueError("French imagery PDF checksum mismatch; supply the recorded paper")
    return checksum


def _line_bands(image: Any) -> list[tuple[int, int]]:
    """Find text rows from ink projections, excluding margins and thin rules."""
    mask = image.crop((int(image.width * 0.08), 0, int(image.width * 0.93), image.height))
    try:
        binary = mask.point(lambda p: 0 if p < 160 else 255)
        try:
            pixels = binary.tobytes()
        finally:
            binary.close()
        bands: list[tuple[int, int]] = []
        for y in range(mask.height):
            if pixels[y * mask.width : (y + 1) * mask.width].count(0) <= max(8, mask.width * 0.01):
                continue
            if not bands or y > bands[-1][1] + 2:
                bands.append((y, y))
            else:
                bands[-1] = (bands[-1][0], y)
        return [(a, b) for a, b in bands if 5 <= b - a <= 45]
    finally:
        mask.close()


def _ocr_page(image: Any, ocr: Any, pillow: Any, report: Callable[[str], None]) -> str:
    bands = _line_bands(image)
    if not bands:
        raise ValueError("French imagery OCR found no text lines")
    deadline = perf_counter() + OCR_TIMEOUT

    def recognize(band: tuple[int, int]) -> str:
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise TimeoutError("French imagery OCR exceeded its page timeout")
        a, b = band
        crop = image.crop(
            (
                int(image.width * 0.08),
                max(0, a - 4),
                int(image.width * 0.93),
                min(image.height, b + 5),
            )
        )
        try:
            line = crop.resize(
                (round(crop.width * OCR_LINE_SCALE), round(crop.height * OCR_LINE_SCALE)),
                pillow.Resampling.LANCZOS,
            )
        finally:
            crop.close()
        try:
            # A relative cache path avoids quoting problems in pytesseract on Windows.
            config = f"{OCR_CONFIG} --tessdata-dir {OCR_DATA_DIR.as_posix()}"
            return str(
                ocr.image_to_string(line, lang="fra", config=config, timeout=min(15, remaining))
            ).strip()
        finally:
            line.close()

    lines = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for index, text in enumerate(pool.map(recognize, bands), 1):
            lines.append(text)
            if index % 10 == 0 or index == len(bands):
                report(f"[french-imagery] Recognized {index}/{len(bands)} text lines")
    return "\n".join(lines)


def ocr_pdf(raw: bytes, *, progress: Callable[[str], None] | None = None) -> str:
    """Render the recorded PDF and recognize each text line without transcription data."""
    from ..cli.sources import download_source

    verify_pdf(raw)
    report = progress or (lambda _message: None)
    report("[french-imagery] Loading Python OCR dependencies")
    pdfium = require_dependency("pypdfium2", "build")
    ocr = require_dependency("pytesseract", "build")
    pillow = require_dependency("PIL.Image", "build")
    command = os.environ.get("TESSERACT_CMD")
    if command:
        ocr.pytesseract.tesseract_cmd = command
    try:
        ocr.get_tesseract_version()
    except (OSError, ocr.TesseractNotFoundError, ocr.TesseractError) as error:
        raise RuntimeError(
            "French imagery OCR requires Tesseract on PATH (or TESSERACT_CMD) "
            "see docs/guides/dictionary-imports.md#french-imagery-pdf-conversion"
        ) from error
    entry = read_resource_json("recipes.json")["sources"]["tesseract-french"]
    download_source(OCR_DATA_DIR / "fra.traineddata", entry, progress=report)
    report(f"[french-imagery] Tesseract ready; language fra; timeout {OCR_TIMEOUT}s/page")
    pages = []
    document = pdfium.PdfDocument(raw)
    try:
        if len(document) != 10:
            raise ValueError("French imagery requires the original ten-page report")
        for index in range(6, 10):
            page_started = perf_counter()
            report(f"[french-imagery] OCR appendix page {index - 5}/4 (PDF page {index + 1})")
            page = document[index]
            bitmap = None
            image = None
            try:
                bitmap = page.render(scale=OCR_RENDER_SCALE, grayscale=True)
                image = bitmap.to_pil()
                pages.append(_ocr_page(image, ocr, pillow, report))
                report(
                    f"[french-imagery] Finished appendix page {index - 5}/4: "
                    f"{len(pages[-1])} characters ({perf_counter() - page_started:.1f}s)"
                )
            finally:
                if image is not None:
                    image.close()
                if bitmap is not None:
                    bitmap.close()
                page.close()
    finally:
        document.close()
    return "\n".join(pages)


def class_csv(
    text: str, *, pdf_sha256: str, reviewed: bool = False
) -> tuple[bytes, dict[str, Any]]:
    """Parse all six classes, retaining extraction issues and sense conflicts."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n")
    headers = list(HEADER.finditer(text))
    labels = [_class_label(match) for match in headers]
    if labels != list(CLASSES):
        raise ValueError(
            "French imagery requires exactly classes I–VI in order; "
            f"found {', '.join(labels) or 'none'}; inspect the OCR text"
        )
    entries: list[dict[str, Any]] = []
    counts = {}
    for index, match in enumerate(headers):
        group = labels[index]
        lower, upper, expected = CLASSES[group]
        end = headers[index + 1].start() if index + 1 < len(headers) else len(text)
        body = text[match.end() : end]
        body = re.split(r"R[ÉE]F[ÉE]RENCES", body, flags=re.I)[0]
        lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip()
            and not re.fullmatch(r"(?:N\s*=\s*)?\d+", line.strip(), re.I)
            and not re.search(r"Hogenraad|Orianne", line, re.I)
            and (reviewed or not re.fullmatch(r"[\W\d_]+", line.strip()))
        ]
        body = "\n".join(lines)
        for wrapped, joined in (
            ("con-\nnaissance", "connaissance"),
            ("ma-\nnière", "manière"),
            ("schizo-\nphrène", "schizophrène"),
            ("articu-\nlation", "articulation"),
            ("pro-\njection", "projection"),
            ("pro-\npriété", "propriété"),
            ("inter-\nrupteur", "interrupteur"),
            ("secré-\ntaire", "secrétaire"),
        ):
            body = body.replace(wrapped, joined)
        body = re.sub(r"-\s*\n\s*", "-", body)
        body = " ".join(body.split()).strip(" ,;.")
        words = [
            word.strip().rstrip(".")
            for word in re.split(r",(?![^()]*\))" if reviewed else r"[,.](?![^()]*\))", body)
        ]
        if not words or any(not word for word in words):
            raise ValueError(f"Empty French imagery entry in class {group}")
        for word in words:
            term = _normalize(re.sub(r"\s*\([^)]*\)", "", word)).strip()
            if not term or any(not (c.isalpha() or c in " '-") for c in term):
                raise ValueError(
                    f"Unrecognized French imagery entry {word!r}; correct the OCR text"
                )
            entries.append(
                {"label": word, "word": term, "class": group, "lower": lower, "upper": upper}
            )
        counts[group] = {"expected": expected, "extracted": len(words)}
        if not 0.9 * expected <= len(words) <= 1.1 * expected:
            raise ValueError(
                f"French imagery class {group} has {len(words)} entries; expected about {expected}; correct the OCR text"
            )
    senses: dict[str, set[str]] = {}
    for entry in entries:
        senses.setdefault(entry["word"], set()).add(entry["class"])
    conflicts = sorted(term for term, groups in senses.items() if len(groups) > 1)
    skipped = sorted(
        {
            e["label"]
            for e in entries
            if e["word"] in conflicts or tokenize_gcam(e["word"], "fra") != [e["word"]]
        }
    )
    status = "reviewed-text" if reviewed else "unreviewed-ocr"
    output = io.StringIO(newline="")
    writer = csv.writer(output, lineterminator="\n")
    writer.writerow(
        [
            "word",
            "ImageryValence",
            "approximation",
            "class",
            "lower",
            "upper",
            "label",
            "source_pdf_sha256",
            "review_status",
        ]
    )
    seen = set()
    for entry in entries:
        if entry["label"] in skipped or entry["word"] in seen:
            continue
        seen.add(entry["word"])
        writer.writerow(
            [
                entry["word"],
                (entry["lower"] + entry["upper"]) / 2,
                APPROXIMATION,
                entry["class"],
                entry["lower"],
                entry["upper"],
                entry["label"],
                pdf_sha256,
                status,
            ]
        )
    audit = {
        "approximation": APPROXIMATION,
        "review_status": status,
        "source_pdf_sha256": pdf_sha256,
        "extracted_entries": len(entries),
        "scored_terms": len(seen),
        "classes": counts,
        "conflicting_terms": conflicts,
        "skipped_entries": skipped,
    }
    if any(c["expected"] != c["extracted"] for c in counts.values()):
        warnings.warn(
            "French imagery class counts differ from the printed totals; inspect the conversion audit",
            UserWarning,
            stacklevel=2,
        )
    return output.getvalue().encode("utf-8"), audit


def convert_pdf(
    raw: bytes,
    *,
    progress: Callable[[str], None] | None = None,
    draft_path: Path | None = None,
) -> tuple[bytes, dict[str, Any]]:
    """Convert the recorded PDF with explicit approximation and OCR status."""
    text = ocr_pdf(raw, progress=progress)
    if draft_path is not None:
        draft_path.write_text(text, encoding="utf-8")
    try:
        converted, audit = class_csv(text, pdf_sha256=verify_pdf(raw))
    except ValueError as error:
        if draft_path is None:
            raise
        raise ValueError(
            f"{error}. OCR draft saved to {draft_path}; correct it against the PDF, then use "
            "python -m gdelt_regkg.builders.french_imagery --pdf <paper.pdf> "
            "--reviewed-text <corrected.txt> --output <imagery.csv>, and build with "
            "--source french-imagery=<imagery.csv>"
        ) from error
    audit.update(_ocr_metadata())
    return converted, audit


def main(argv: list[str] | None = None) -> None:
    """Download the paper, OCR its appendix, and save CSV plus conversion audit."""
    from ..cli.progress import print_progress
    from ..cli.sources import download_source

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pdf", type=Path, default=Path("downloads/resources/hogenraad-orianne-1981.pdf")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("downloads/resources/french-imagery.csv")
    )
    parser.add_argument(
        "--reviewed-text",
        type=Path,
        help="Use a corrected appendix transcription instead of OCR; retains approximate scores",
    )
    args = parser.parse_args(argv)
    entry = read_resource_json("recipes.json")["sources"]["french-imagery-report"]
    download_source(args.pdf, entry, progress=print)
    raw = args.pdf.read_bytes()
    checksum = verify_pdf(raw)
    text = (
        args.reviewed_text.read_text(encoding="utf-8-sig")
        if args.reviewed_text
        else ocr_pdf(raw, progress=print_progress)
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Save the draft even when parsing fails, allowing correction without rerunning OCR.
    args.output.with_suffix(".ocr.txt").write_text(text, encoding="utf-8")
    converted, audit = class_csv(text, pdf_sha256=checksum, reviewed=args.reviewed_text is not None)
    if args.reviewed_text is None:
        audit.update(_ocr_metadata())
    args.output.write_bytes(converted)
    args.output.with_suffix(".audit.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"French imagery: {args.output}; approximate class midpoints ({audit['review_status']})")


if __name__ == "__main__":
    main()
