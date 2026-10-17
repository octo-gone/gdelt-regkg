"""Prepare reproducible GCAM samples and native-language corpus inputs.

Run ``python -m gdelt_regkg.benchmark.prepare --help``. Inputs are read-only.
"""

import argparse
import hashlib
import json
import math
import random
import re
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

from ..fields.gcam_tokens import tokenize_gcam
from ..fields.translation import normalize_language
from . import parsers
from .inputs import iter_lines, resolve_inputs
from .model import FIELD_NAMES


def prepared_article(row):
    """Normalize saved source_text/translation pairs without generating translations."""
    if not isinstance(row, dict):
        raise ValueError("Saved article must be an object")
    if row.get("status", "ok") != "ok" or row.get("translation_pending"):
        return None
    text = row.get("text")
    if not isinstance(text, str):
        return None
    document = row.get("url", row.get("document"))
    if not document:
        raise ValueError("Saved article requires url or document")
    checksum = hashlib.sha256(text.encode()).hexdigest()
    if row.get("text_sha256", checksum) != checksum:
        raise ValueError("Saved body checksum mismatch")
    body = {
        key: row[key]
        for key in ("record_id", "recordid", "translated", "translation_info", "gcam_native_only")
        if key in row
    }
    body.update(url=document, text=text, text_sha256=checksum, status="ok")
    language = row.get("original_language", row.get("source_language"))
    if language is None and row.get("translated"):
        match = re.search(r"(?:^|;)srclc:([a-z]{3})(?:;|$)", row.get("translation_info", ""))
        language = match[1] if match else None
    original = row.get("original_text", row.get("source_text") if row.get("translated") else None)
    if original is not None:
        if not isinstance(original, str) or not language:
            raise ValueError("Original text requires a source language")
        language = normalize_language(language)
        if language == "eng":
            raise ValueError("Original text must be non-English")
        original_hash = hashlib.sha256(original.encode()).hexdigest()
        if row.get("original_text_sha256", original_hash) != original_hash:
            raise ValueError("Original body checksum mismatch")
        body.update(
            original_text=original,
            original_language=language,
            original_text_sha256=original_hash,
            translated=True,
        )
    elif row.get("translated"):
        return None
    return body


def _eligible(row, body, counts, *, language, reference_output, difference):
    if body is None:
        counts["unusable_body"] += 1
        return False
    if language and body.get("original_language", "eng") != language:
        counts["other_language"] += 1
        return False
    native = row.get("native_cells")
    has_native = isinstance(native, list) and len(native) == 27
    if reference_output is not None and not has_native:
        counts["missing_native_cells"] += 1
        return False
    if difference is not None:
        if body.get("original_language", "eng") != "eng":
            raise ValueError("Preparation body-size matching requires English bodies")
        if not has_native:
            counts["missing_reference_word_count"] += 1
            return False
        try:
            expected = parsers.gcam(native[FIELD_NAMES.index("gcam")]).get("wc", 0)
        except (ValueError, ArithmeticError):
            counts["invalid_reference_word_count"] += 1
            return False
        actual = len(tokenize_gcam(body["text"], "eng"))
        if expected <= 0 or abs(actual - expected) / expected > difference:
            counts["body_size_excluded"] += 1
            return False
    return True


def _write_selection(selected, output, reference_output, split_languages):
    languages: Counter = Counter()
    months: Counter = Counter()
    streams = {}
    with ExitStack() as stack:
        reference = None
        if reference_output is not None:
            Path(reference_output).parent.mkdir(parents=True, exist_ok=True)
            reference = stack.enter_context(Path(reference_output).open("w", encoding="utf-8"))
        for body, native in selected:
            code = body.get("original_language", "eng")
            path = output / (code + ".jsonl") if split_languages else output
            if path not in streams:
                path.parent.mkdir(parents=True, exist_ok=True)
                streams[path] = stack.enter_context(path.open("w", encoding="utf-8"))
            streams[path].write(json.dumps(body, ensure_ascii=False) + "\n")
            if reference is not None:
                reference.write(json.dumps({"native_cells": native}, ensure_ascii=False) + "\n")
            languages[code] += 1
            months[str(body.get("record_id", body.get("recordid", "unknown")))[:6]] += 1
    return languages, months


def prepare(
    paths,
    output,
    *,
    sample_size=None,
    max_word_count_difference=None,
    language=None,
    seed=0,
    split_languages=False,
    reference_output=None,
):
    if sample_size is not None and (type(sample_size) is not int or sample_size < 1):
        raise ValueError("Sample size must be positive")
    if max_word_count_difference is not None and (
        not math.isfinite(max_word_count_difference) or max_word_count_difference < 0
    ):
        raise ValueError("Word-count difference must be finite and nonnegative")
    language = normalize_language(language) if language else None
    files = resolve_inputs(paths, corpus=True)
    output = Path(output)
    if output.resolve() in files or reference_output and Path(reference_output).resolve() in files:
        raise ValueError("Output must differ from input files")
    if reference_output is not None and Path(reference_output).resolve() == output.resolve():
        raise ValueError("Corpus and reference outputs must differ")
    rng = random.Random(seed)
    selected: list[tuple[dict, list | None]] = []
    counts: Counter = Counter()
    eligible = 0
    for path in files:
        for _, line, _ in iter_lines(path):
            if not line.strip():
                continue
            row = json.loads(line)
            counts["input_rows"] += 1
            if counts["input_rows"] % 10000 == 0:
                print(
                    f"[prepare] Read {counts['input_rows']} rows; eligible {eligible}", flush=True
                )
            body = prepared_article(row)
            if not _eligible(
                row,
                body,
                counts,
                language=language,
                reference_output=reference_output,
                difference=max_word_count_difference,
            ):
                continue
            eligible += 1
            item = (body, row.get("native_cells"))
            if sample_size is None or len(selected) < sample_size:
                selected.append(item)
            elif (index := rng.randrange(eligible)) < sample_size:
                selected[index] = item
    if not selected:
        raise ValueError("No articles satisfy the requested cohort")
    selected.sort(
        key=lambda item: (item[0].get("record_id", item[0].get("recordid", "")), item[0]["url"])
    )
    languages, months = _write_selection(selected, output, reference_output, split_languages)
    manifest = {
        "inputs": [str(path) for path in files],
        "audit": dict(counts),
        "eligible": eligible,
        "selected": len(selected),
        "languages": dict(languages),
        "months": dict(months),
        "sample_size": sample_size,
        "max_word_count_difference": max_word_count_difference,
        "seed": seed,
        "selection_sha256": hashlib.sha256(
            "\n".join(body["url"] for body, _ in selected).encode()
        ).hexdigest(),
        "selection_note": "Similar body length does not establish identical text. Corpus files are external inputs, not independently verified GDELT body snapshots.",
    }
    manifest_path = (
        output / "manifest.json" if split_languages else output.with_suffix(".manifest.json")
    )
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[prepare] Saved {len(selected)} articles; languages {dict(languages)}", flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference-output",
        type=Path,
        help="Export the selected embedded native_cells as benchmark reference JSONL",
    )
    parser.add_argument(
        "--sample-size",
        type=int,
        default=10000,
        help="Maximum retained articles (default: 10000); sampled uniformly over eligible rows",
    )
    parser.add_argument("--max-word-count-difference", type=float)
    parser.add_argument("--language")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--split-languages", action="store_true")
    args = parser.parse_args(argv)
    try:
        prepare(
            args.corpus,
            args.output,
            sample_size=args.sample_size,
            max_word_count_difference=args.max_word_count_difference,
            language=args.language,
            seed=args.seed,
            split_languages=args.split_languages,
            reference_output=args.reference_output,
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
