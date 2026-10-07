"""Fetch original GKG article URLs and compare extract_tone with native V1.5TONE.

GDELT archives use HTTP. Article URLs retain their original protocol. This is
an English, live-page benchmark: a page fetched now can differ from the page
GDELT processed. Saved HTML can be rescored offline without downloading again.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import math
import random
import statistics
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from http.client import HTTPException
from importlib import import_module
from importlib.metadata import version
from pathlib import Path
from urllib.request import Request, urlopen

from gdelt_regkg.fields import extract_tone
from gdelt_regkg.tone import ToneLexicon, default_tone_lexicon

FIELDS = (
    "tone",
    "positive",
    "negative",
    "polarity",
    "activity_density",
    "self_group_density",
    "word_count",
)
USER_AGENT = "Mozilla/5.0 (compatible; gdelt-regkg-tone-benchmark/0.1)"


def parse_tone(cell):
    values = [float(value) for value in cell.split(",")]
    if (
        len(values) != 7
        or not all(math.isfinite(v) for v in values)
        or not -100 <= values[0] <= 100
        or not all(0 <= v <= 100 for v in values[1:6])
        or values[6] <= 0
        or not values[6].is_integer()
    ):
        raise ValueError("Invalid seven-component tone cell")
    values[6] = int(values[6])
    return dict(zip(FIELDS, values))


def download(url, *, timeout, max_bytes):
    started = time.monotonic()
    with urlopen(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        content = bytearray()
        while block := response.read(65536):
            content.extend(block)
            if len(content) > max_bytes:
                raise ValueError("Response exceeds byte limit")
            if time.monotonic() - started > timeout * 2:
                raise TimeoutError("Response exceeds time limit")
        return bytes(content), {
            "final_url": response.geturl(),
            "http_status": response.status,
            "content_type": response.headers.get("Content-Type", ""),
            "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        }


def load_originals(paths):
    records, counts, archives = [], Counter[str](), []
    for path in paths:
        archives.append(
            {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if not name.endswith(".csv"):
                    continue
                with archive.open(name) as stream:
                    for raw in stream:
                        counts["original_rows"] += 1
                        try:
                            cells = raw.decode("utf-8").rstrip("\r\n").split("\t")
                            if len(cells) != 27:
                                raise ValueError("Expected 27 cells")
                            tone = parse_tone(cells[15])
                        except (ValueError, UnicodeDecodeError):
                            counts["malformed_original_rows"] += 1
                            continue
                        if (
                            cells[2] != "1"
                            or cells[25]
                            or "-T" in cells[0]
                            or not cells[4].startswith(("http://", "https://"))
                        ):
                            counts["excluded_non_english_or_non_web"] += 1
                            continue
                        records.append(
                            {
                                "record_id": cells[0],
                                "batch": cells[1],
                                "source": cells[3],
                                "url": cells[4],
                                "original_tone_cell": cells[15],
                                "original": tone,
                            }
                        )
    # Do not select arbitrarily between differently scored versions of a URL.
    by_url = defaultdict(list)
    for row in records:
        by_url[row["url"]].append(row)
    unique = []
    for rows in by_url.values():
        signatures = {tuple(r["original"][key] for key in FIELDS) for r in rows}
        if len(signatures) > 1:
            counts["excluded_conflicting_urls"] += 1
        else:
            unique.append(rows[0])
            counts["identical_duplicate_rows"] += len(rows) - 1
    counts["eligible_unique_urls"] = len(unique)
    return unique, dict(counts), archives


def acquire_archive(batch, output, timeout, *, offline=False, translated=False):
    """Retry transient transfers; never leave a partial ZIP in the cache."""
    path = output / (batch + (".translation.gkg.csv.zip" if translated else ".gkg.csv.zip"))
    if path.exists():
        return path
    if offline:
        raise FileNotFoundError(f"Missing cached archive: {path}")
    from io import BytesIO

    for attempt in range(3):
        try:
            print(f"[GKG] Downloading {batch} via HTTP; attempt={attempt + 1}", flush=True)
            content, _ = download(
                f"http://data.gdeltproject.org/gdeltv2/{path.name}",
                timeout=timeout,
                max_bytes=40 * 1024 * 1024,
            )
            with zipfile.ZipFile(BytesIO(content)) as archive:
                if damaged := archive.testzip():
                    raise ValueError(f"Damaged archive member: {damaged}")
            path.write_bytes(content)
            return path
        except (OSError, ValueError, zipfile.BadZipFile, HTTPException) as error:
            if attempt == 2 or getattr(error, "code", None) in (403, 404, 451):
                raise
            time.sleep(attempt + 1)
    raise RuntimeError("Archive download exhausted all attempts")


def sample_records(records, size, per_source, seed):
    """Round-robin shuffled sources; limit concentration without cherry-picking."""
    rng = random.Random(seed)
    sources = defaultdict(list)
    for row in sorted(records, key=lambda r: (r["source"], r["url"])):
        sources[row["source"]].append(row)
    names = sorted(sources)
    rng.shuffle(names)
    for rows in sources.values():
        rng.shuffle(rows)
    selected = []
    for index in range(per_source):
        for source in names:
            if len(sources[source]) > index:
                selected.append(sources[source][index])
                if len(selected) >= size:
                    return selected
    return selected


def correlation(x, y):
    if len(x) < 2:
        return None
    mx, my = statistics.mean(x), statistics.mean(y)
    dx, dy = [v - mx for v in x], [v - my for v in y]
    denom = math.sqrt(sum(v * v for v in dx) * sum(v * v for v in dy))
    return sum(a * b for a, b in zip(dx, dy)) / denom if denom else None


def ranks(values):
    result = [0.0] * len(values)
    ordered = sorted(range(len(values)), key=values.__getitem__)
    index = 0
    while index < len(ordered):
        end = index + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[index]]:
            end += 1
        for pos in ordered[index:end]:
            result[pos] = (index + end - 1) / 2
        index = end
    return result


def summarize(rows):
    if not rows:
        return {"n": 0, "metrics": None}
    metrics = {}
    for key in FIELDS:
        actual = [r["original"][key] for r in rows]
        predicted = [r["predicted"][key] for r in rows]
        errors = [p - a for p, a in zip(predicted, actual)]
        absolute = sorted(abs(e) for e in errors)
        metrics[key] = {
            "mae": statistics.mean(absolute),
            "rmse": math.sqrt(statistics.mean(e * e for e in errors)),
            "bias": statistics.mean(errors),
            "median_absolute_error": statistics.median(absolute),
            "p95_absolute_error": absolute[math.ceil(0.95 * len(absolute)) - 1],
            "pearson": correlation(actual, predicted),
            "spearman": correlation(ranks(actual), ranks(predicted)),
        }
        if key != "word_count":
            metrics[key]["within_1_point"] = sum(v <= 1 for v in absolute) / len(rows)
    sign = lambda v: 1 if v > 0.5 else -1 if v < -0.5 else 0
    return {
        "n": len(rows),
        "sources": len({r["source"] for r in rows}),
        "metrics": metrics,
        "tone_sign_agreement_deadband_0_5": sum(
            sign(r["original"]["tone"]) == sign(r["predicted"]["tone"]) for r in rows
        )
        / len(rows),
        "word_count_median_relative_error": statistics.median(
            abs(r["word_count_ratio"] - 1) for r in rows
        ),
        "word_count_within_10_percent": sum(abs(r["word_count_ratio"] - 1) <= 0.1 for r in rows)
        / len(rows),
    }


def process_article(row, args, lexicon):
    from trafilatura import bare_extraction
    from trafilatura.settings import Document

    result = dict(row)
    key = hashlib.sha256(row["url"].encode()).hexdigest()
    cache = args.output / "html" / (key + ".html.gz")
    metadata = cache.with_suffix(".json")
    stage = "fetch"
    try:
        if cache.exists() and metadata.exists():
            content = gzip.decompress(cache.read_bytes())
            result["fetch"] = {**json.loads(metadata.read_text(encoding="utf-8")), "cached": True}
        elif args.offline:
            raise FileNotFoundError("No cached HTML for selected URL")
        else:
            content, info = download(row["url"], timeout=args.timeout, max_bytes=5 * 1024 * 1024)
            if not any(
                t in info["content_type"].lower() for t in ("text/html", "application/xhtml+xml")
            ):
                raise ValueError("Article response is not HTML")
            cache.write_bytes(gzip.compress(content))
            metadata.write_text(json.dumps(info, indent=2), encoding="utf-8")
            result["fetch"] = {**info, "cached": False}
        stage = "extract"
        doc = bare_extraction(
            content,
            url=row["url"],
            include_comments=False,
            include_tables=False,
            with_metadata=True,
            as_dict=False,
        )
        if not isinstance(doc, Document) or not doc.text:
            raise ValueError("No extracted article body")
        body = doc.text
        result.update(
            title=doc.title, text=body, text_sha256=hashlib.sha256(body.encode()).hexdigest()
        )
        if doc.language and not doc.language.lower().startswith("en") and not row.get("translated"):
            raise ValueError(f"Extracted page language is {doc.language!r}")
        if row.get("translated"):
            if len(body) < 200:
                raise ValueError("Extracted source body is too short")
            result.update(source_text=body, translation_pending=True, status="ok")
            return result
        stage = "tone"
        result["predicted_tone_cell"] = extract_tone(body, lexicon=lexicon)
        result["predicted"] = parse_tone(result["predicted_tone_cell"])
        if result["predicted"]["word_count"] < args.min_words:
            raise ValueError("Extracted body is below minimum word count")
        if len(body) < 2000 and any(
            body.lower().startswith(s)
            for s in (
                "access denied",
                "please enable javascript",
                "verify you are human",
                "just a moment",
            )
        ):
            raise ValueError("Extracted page appears to be a challenge/error response")
        result["word_count_ratio"] = (
            result["predicted"]["word_count"] / row["original"]["word_count"]
        )
        result["status"] = "ok"
    # Retrieval/extraction failures are part of the benchmark's article audit.
    except Exception as error:  # pylint: disable=broad-exception-caught
        result.update(status="failed", stage=stage, error=f"{type(error).__name__}: {error}")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path("local-resources"),
        help="Directory containing prepared profiles and defaults.json",
    )
    parser.add_argument("--archives", type=Path, nargs="*", default=[])
    parser.add_argument(
        "--batches", nargs="*", default=[], help="Download these YYYYMMDDHHMMSS batches via HTTP"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=150)
    parser.add_argument(
        "--per-day",
        type=int,
        help="Sample this many URLs per original date instead of one overall sample",
    )
    parser.add_argument("--per-source", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--min-words", type=int, default=50)
    parser.add_argument("--lexicon", type=Path)
    parser.add_argument("--offline", action="store_true", help="Rescore cached HTML only")
    args = parser.parse_args()
    if not args.archives and not args.batches:
        parser.error("Supply --archives and/or --batches")
    if min(args.sample_size, args.per_source, args.workers, args.timeout, args.min_words) < 1:
        parser.error("Sampling, worker, timeout and word limits must be positive")
    if args.per_day is not None and args.per_day < 1:
        parser.error("--per-day must be positive")
    # Initialize lazy metadata/date imports before threads can enter them together.
    import dateparser

    import_module("trafilatura")

    dateparser.parse("September 30, 2026", languages=["en"])
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "html").mkdir(exist_ok=True)
    paths = list(args.archives)
    archive_failures = []
    for batch in args.batches:
        try:
            datetime.strptime(batch, "%Y%m%d%H%M%S")
            if len(batch) != 14 or not batch.isdigit():
                raise ValueError("Expected 14 digits")
        except ValueError:
            parser.error(f"Invalid batch: {batch}")
        try:
            paths.append(acquire_archive(batch, args.output, args.timeout, offline=args.offline))
        except (OSError, ValueError, zipfile.BadZipFile) as error:
            archive_failures.append({"batch": batch, "error": f"{type(error).__name__}: {error}"})
            print(f"[GKG FAILED] {batch}: {error}", flush=True)
    if not paths:
        parser.error("No original archives available")
    if archive_failures:
        (args.output / "archive_failures.json").write_text(
            json.dumps(archive_failures, indent=2), encoding="utf-8"
        )
    records, counts, archives = load_originals(sorted(set(paths)))
    if args.per_day is None:
        selected = sample_records(records, args.sample_size, args.per_source, args.seed)
    else:
        days = defaultdict(list)
        for row in records:
            days[row["batch"][:8]].append(row)
        selected = [
            row
            for day in sorted(days)
            for row in sample_records(days[day], args.per_day, args.per_source, args.seed)
        ]
    manifest = {
        "archives": archives,
        "original_counts": counts,
        "sampling": {
            k: getattr(args, k) for k in ("sample_size", "per_source", "seed", "min_words")
        },
        "selected": selected,
    }
    if args.per_day is not None:
        manifest["sampling"]["per_day"] = args.per_day
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        parser.error("Output belongs to a different sample; use a new --output directory")
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    lexicon = (
        ToneLexicon.from_json(args.lexicon)
        if args.lexicon
        else default_tone_lexicon(args.resources_dir)
    )
    results = []
    # Offline replay retains the real fetch errors for URLs without cached HTML.
    previous_failures = {}
    result_path = args.output / "results.jsonl"
    if args.offline and result_path.exists():
        for line in result_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["status"] == "failed" and row.get("stage") == "fetch":
                previous_failures[row["url"]] = row
    with (args.output / "results.jsonl").open("w", encoding="utf-8") as stream:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:

            def replay_or_process(row):
                return previous_failures.get(row["url"]) or process_article(row, args, lexicon)

            futures = [executor.submit(replay_or_process, row) for row in selected]
            for future in as_completed(futures):
                row = future.result()
                results.append(row)
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
                stream.flush()
                good = sum(r["status"] == "ok" for r in results)
                if len(results) % 10 == 0 or len(results) == len(selected):
                    print(
                        f"[ARTICLES] {len(results)}/{len(selected)}; scored={good}; failed={len(results) - good}",
                        flush=True,
                    )
    good = [r for r in results if r["status"] == "ok"]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "lexicon": lexicon.name,
        "trafilatura_version": version("trafilatura"),
        "text_policy": "Trafilatura body; comments/tables excluded; title not prepended; no translation",
        "original_counts": counts,
        "selected": len(selected),
        "scored": len(good),
        "archive_failures": archive_failures,
        "failed": len(results) - len(good),
        "failures": dict(Counter(r.get("stage") for r in results if r["status"] != "ok")),
        "all_scored": summarize(good),
        "word_count_within_10_percent": summarize(
            [r for r in good if abs(r["word_count_ratio"] - 1) <= 0.1]
        ),
        "by_source": {
            s: summarize([r for r in good if r["source"] == s])
            for s in sorted({r["source"] for r in good})
        },
        "by_original_date": {
            d: summarize([r for r in good if r["batch"][:8] == d])
            for d in sorted({r["batch"][:8] for r in good})
        },
        "interpretation": "Live-page convenience sample across sources; not verified identical GDELT text. Similar word counts do not prove identical bodies. Failures are excluded from score metrics and counted separately.",
    }
    (args.output / "summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (args.output / "comparison.csv").open("w", encoding="utf-8", newline="") as stream:
        keys = ["record_id", "source", "url", "word_count_ratio"] + [
            f"{kind}_{key}" for key in FIELDS for kind in ("gdelt", "local", "error")
        ]
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for r in sorted(good, key=lambda r: r["record_id"]):
            out = {key: r[key] for key in keys[:4]}
            for key in FIELDS:
                out.update(
                    {
                        f"gdelt_{key}": r["original"][key],
                        f"local_{key}": r["predicted"][key],
                        f"error_{key}": r["predicted"][key] - r["original"][key],
                    }
                )
            writer.writerow(out)
    print(
        json.dumps({k: report[k] for k in ("selected", "scored", "failed", "all_scored")}, indent=2)
    )
    if not good:
        raise SystemExit("No usable articles scored; see results.jsonl for failures")


if __name__ == "__main__":
    main()
