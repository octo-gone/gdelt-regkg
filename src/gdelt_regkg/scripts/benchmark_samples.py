"""Collect fixed seasonal article samples without evaluating the held-out sample."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.client import HTTPException
from pathlib import Path
from types import SimpleNamespace

from gdelt_regkg.tone import default_tone_lexicon

from .benchmark_extraction import load_originals
from .benchmark_tone import acquire_archive, process_article, sample_records


def read_jsonl(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream if line.strip()]


def sample_windows(records, plan, split, excluded_urls=(), *, cohort="both", prior_sources=()):
    """Apply fixed day/hour/language quotas, without inspecting extraction scores."""
    seen = set(excluded_urls)
    sources = Counter((r["batch"][:8], r["source"]) for r in prior_sources)
    result = []
    windows = {}
    for day in plan[split]["days"]:
        for time in plan["utc_windows"]:
            batch = day + time
            for translated, quota in (
                (False, plan["english_per_window"]),
                (True, plan["translated_per_window"]),
            ):
                if cohort != "both" and translated != (cohort == "translated"):
                    continue
                eligible = [
                    r
                    for r in records
                    if r["batch"] == batch
                    and bool(r.get("translated")) == translated
                    and r["url"] not in seen
                    and sources[(day, r["source"])] < plan["per_source_per_day"]
                ]
                selected = sample_records(eligible, quota, 1, plan["seed"])
                windows[batch + ("/translated" if translated else "/english")] = {
                    "eligible": len(eligible),
                    "selected": len(selected),
                    "requested": quota,
                }
                for row in selected:
                    result.append(
                        {**row, "sample_split": split, "sample_month": day[:6], "utc_window": time}
                    )
                    seen.add(row["url"])
                    sources[(day, row["source"])] += 1
    return result, windows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path("local-resources"),
        help="Directory containing prepared profiles and defaults.json",
    )
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--split", choices=("development", "benchmark"), required=True)
    parser.add_argument("--cohort", choices=("english", "translated", "both"), default="both")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--exclude-corpus", type=Path, nargs="*", default=[])
    parser.add_argument("--exclude-manifest", type=Path, nargs="*", default=[])
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--archive-timeout", type=int, default=60)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if args.workers < 1 or args.timeout < 1:
        parser.error("Workers and timeout must be positive")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    if set(plan["development"]["days"]) & set(plan["benchmark"]["days"]):
        parser.error("Development and benchmark dates must be disjoint")
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "html").mkdir(exist_ok=True)
    batches = [
        (day + window, translated)
        for day in plan[args.split]["days"]
        for window in plan["utc_windows"]
        for translated in (False, True)
        if args.cohort == "both" or translated == (args.cohort == "translated")
    ]
    paths, failures = [], []

    def get(item):
        batch, translated = item
        try:
            return acquire_archive(
                batch, args.output, args.archive_timeout, translated=translated
            ), None
        except (OSError, ValueError, zipfile.BadZipFile, HTTPException) as error:
            return None, {
                "batch": batch,
                "translated": translated,
                "error": f"{type(error).__name__}: {error}",
            }

    with ThreadPoolExecutor(max_workers=6) as pool:
        for path, failure in pool.map(get, batches):
            if path is not None:
                paths.append(path)
            else:
                failures.append(failure)
    records, counts, archives = load_originals(paths, include_translated=True)
    excluded: set[str] = set()
    for path in args.exclude_corpus:
        excluded.update(r["url"] for r in read_jsonl(path))
    prior_sources = []
    for path in args.exclude_manifest:
        prior = json.loads(path.read_text(encoding="utf-8"))["selected"]
        excluded.update(r["url"] for r in prior)
        prior_sources.extend(prior)
    selected, windows = sample_windows(
        records, plan, args.split, excluded, cohort=args.cohort, prior_sources=prior_sources
    )
    manifest = {
        "plan": plan,
        "split": args.split,
        "archives": archives,
        "archive_failures": failures,
        "original_counts": counts,
        "windows": windows,
        "selected": selected,
        "excluded_url_count": len(excluded),
    }
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding="utf-8")) != manifest:
        parser.error("Existing manifest differs; choose another output directory")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    destination = args.output / "results.jsonl"
    previous = (
        {r["url"]: r for r in read_jsonl(destination)}
        if args.resume and destination.exists()
        else {}
    )
    fetch_args = SimpleNamespace(
        output=args.output, timeout=args.timeout, offline=False, min_words=50
    )
    lexicon = default_tone_lexicon(args.resources_dir)
    statuses = Counter[str]()
    import dateparser

    dateparser.parse("January 1, 2026", languages=["en"])

    def fetch(row):
        return previous.get(row["url"]) or process_article(row, fetch_args, lexicon)

    with (
        destination.open("w", encoding="utf-8") as stream,
        ThreadPoolExecutor(max_workers=args.workers) as pool,
    ):
        for index, row in enumerate(pool.map(fetch, selected), 1):
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
            stream.flush()
            statuses["available" if row["status"] == "ok" else row.get("stage", "failed")] += 1
            if index % 100 == 0 or index == len(selected):
                print(f"[{args.split}] {index}/{len(selected)} {dict(statuses)}", flush=True)
    report = {
        "selected": len(selected),
        "statuses": dict(statuses),
        "archives": len(paths),
        "archive_failures": failures,
        "plan_sha256": hashlib.sha256(args.plan.read_bytes()).hexdigest(),
        "windows": windows,
        "policy": "Selection fixed before retrieval; all failures retained, no replacements; no held-out scores calculated.",
    }
    (args.output / "collection.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "windows"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
