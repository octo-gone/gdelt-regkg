"""Fetch native GCAM corpus bodies from supplied GDELT archives; requires benchmark and lang extras."""

import argparse
import hashlib
import ipaddress
import json
import math
import random
import re
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from ..dependencies import require_dependency
from ..fields.language import default_language_detector, detect_language
from ..fields.translation import normalize_language
from .inputs import iter_lines, resolve_inputs
from .model import FIELD_NAMES
from .prepare import prepared_article


def native_language(cells):
    if len(cells) != 27 or cells[FIELD_NAMES.index("source_collection")] != "1":
        return None
    match = re.search(r"(?:^|;)srclc:([a-z]{3})(?:;|$)", cells[FIELD_NAMES.index("translation")])
    try:
        return normalize_language(match[1]) if match else None
    except ValueError:
        return None


def _public_url(url):
    parsed = urlsplit(url)
    if (
        parsed.scheme not in ("http", "https")
        or not parsed.hostname
        or parsed.hostname == "localhost"
    ):
        raise ValueError("Expected a public HTTP article URL")
    try:
        address = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        return
    if not address.is_global:
        raise ValueError("Private-network article URLs are excluded")


def fetch_body(url):
    _public_url(url)
    with urlopen(
        Request(url, headers={"User-Agent": "gdelt-regkg benchmark corpus acquisition"}), timeout=12
    ) as response:
        _public_url(response.url)
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Article response exceeds 2 MB")
        final_url = response.url
    text = require_dependency("trafilatura", "benchmark").extract(
        raw, url=final_url, include_comments=False, include_tables=False
    )
    if not text or sum(char.isalpha() for char in text) < 250:
        raise ValueError("No substantive article body extracted")
    return text, final_url


def _language_audit(text, code):
    if not hasattr(require_dependency("lingua", "lang").IsoCode639_3, code.upper()):
        return {"language_check": "detector-unavailable", "supplied_language": code}
    detection = detect_language(text)
    if detection.language != code:
        raise ValueError("Fetched article language differs from GDELT's source label")
    return {
        "language_check": "detected",
        "detected_language": detection.language,
        "language_confidence": detection.confidence,
        "language_margin": detection.margin,
    }


def _fetch(item):
    code, cells = item
    url = cells[FIELD_NAMES.index("document")]
    try:
        text, final = fetch_body(url)
        language_audit = _language_audit(text, code)
        body = {
            "record_id": cells[FIELD_NAMES.index("recordid")],
            "url": url,
            "text": "",
            "translated": True,
            "gcam_native_only": True,
            "original_text": text,
            "original_language": code,
            "original_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text_sha256": hashlib.sha256(b"").hexdigest(),
            "status": "ok",
            "retrieval": {"final_url": final, **language_audit},
        }
        return code, body, cells, None
    except (OSError, ValueError, RuntimeError) as error:
        return code, None, cells, type(error).__name__ + ": " + str(error)[:160]


class _Acquisition:
    def __init__(self, languages, target, candidates_per_language, seed):
        self.languages = languages
        self.target, self.limit = target, candidates_per_language
        self.rng = random.Random(seed)
        self.existing: dict[str, dict] = {code: {} for code in languages}
        self.candidates: dict[str, list] = {code: [] for code in languages}
        self.retained: dict[str, list] = {code: [] for code in languages}
        self.totals: Counter = Counter()
        self.failures: Counter = Counter()
        self.attempted: Counter = Counter()
        self.sources: dict[str, Counter] = {code: Counter() for code in languages}
        self.seen: set[tuple] = set()

    def seed_bodies(self, paths):
        for path in resolve_inputs(paths, corpus=True) if paths else ():
            for _, line, _ in iter_lines(path):
                if line.strip():
                    body = prepared_article(json.loads(line))
                    if body and body.get("original_language") in self.existing:
                        code = body["original_language"]
                        self.existing[code][
                            (body.get("record_id", body.get("recordid")), body["url"])
                        ] = body

    def observe(self, cells):
        code = native_language(cells)
        if code not in self.candidates:
            return
        url, recordid = (cells[FIELD_NAMES.index(name)] for name in ("document", "recordid"))
        if (code, url) in self.seen:
            return
        self.seen.add((code, url))
        body = self.existing[code].get((recordid, url))
        if body is not None:
            self.retained[code].append((body, cells))
            self.sources[code][urlsplit(url).hostname] += 1
            return
        self.totals[code] += 1
        if len(self.candidates[code]) < self.limit:
            self.candidates[code].append(cells)
        elif (index := self.rng.randrange(self.totals[code])) < self.limit:
            self.candidates[code][index] = cells

    def scan(self, references):
        for path in resolve_inputs(references):
            for _, line, is_json in iter_lines(path):
                if line.strip():
                    cells = (
                        json.loads(line).get("native_cells", [])
                        if is_json
                        else line.rstrip("\r\n").split("\t")
                    )
                    self.observe(cells)
            print(f"[acquire] Scanned {path.name}", flush=True)

    def fetch(self, max_seconds):
        started = time.monotonic()
        queues = [
            (code, self.candidates[code][index])
            for index in range(self.limit)
            for code in self.languages
            if index < len(self.candidates[code])
        ]
        with ThreadPoolExecutor(max_workers=3) as pool:
            for offset in range(0, len(queues), 3):
                batch = [
                    (code, cells)
                    for code, cells in queues[offset : offset + 3]
                    if len(self.retained[code]) < self.target
                    and self.sources[code][urlsplit(cells[FIELD_NAMES.index("document")]).hostname]
                    < 5
                ]
                for code, body, cells, error in pool.map(_fetch, batch):
                    self.attempted[code] += 1
                    if body:
                        self.retained[code].append((body, cells))
                        self.sources[code][urlsplit(body["url"]).hostname] += 1
                        print(
                            f"[acquire] {code}: {len(self.retained[code])}/{self.target}",
                            flush=True,
                        )
                    else:
                        self.failures[error] += 1
                if time.monotonic() - started >= max_seconds:
                    break

    def save(self, output):
        summary = {}
        for code, rows in self.retained.items():
            if rows:
                with (
                    (output / (code + ".jsonl")).open("w", encoding="utf-8") as corpus,
                    (output / (code + ".reference.jsonl")).open("w", encoding="utf-8") as reference,
                ):
                    for body, cells in rows:
                        corpus.write(json.dumps(body, ensure_ascii=False) + "\n")
                        reference.write(
                            json.dumps({"native_cells": cells}, ensure_ascii=False) + "\n"
                        )
            summary[code] = {
                "articles": len(rows),
                "publishers": len(self.sources[code]),
                "attempted": self.attempted[code],
                "candidate_urls": self.totals[code],
                "native_only_articles": sum(bool(body.get("gcam_native_only")) for body, _ in rows),
                "unverified_language_articles": sum(
                    body.get("retrieval", {}).get("language_check") == "detector-unavailable"
                    for body, _ in rows
                ),
            }
        return summary


def acquire(
    references,
    output,
    languages,
    *,
    seed_corpus=(),
    target=20,
    candidates_per_language=80,
    seed=17,
    max_seconds=300,
):
    languages = sorted({normalize_language(code) for code in languages} - {"eng"})
    if (
        not languages
        or target < 1
        or candidates_per_language < 1
        or not math.isfinite(max_seconds)
        or max_seconds <= 0
    ):
        raise ValueError("Native languages and positive finite acquisition limits are required")
    require_dependency("trafilatura", "benchmark")
    default_language_detector()
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    run = _Acquisition(languages, target, candidates_per_language, seed)
    run.seed_bodies(seed_corpus)
    run.scan(references)
    run.fetch(max_seconds)
    summary = run.save(output)
    manifest = {
        "languages": summary,
        "target_per_language": target,
        "seed": seed,
        "failures": dict(run.failures),
        "references": [str(path) for path in references],
        "note": "Newly fetched bodies may differ from GDELT snapshots. Native-only rows have no English translation and must use native-language GCAM evaluation. Lingua screens supported languages; unsupported detection languages retain GDELT labels and are marked unverified. Saved seed bodies retain supplied labels. Retrieval success sampling is not representative of GDELT.",
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=True), flush=True)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--languages", nargs="+", required=True)
    parser.add_argument("--seed-corpus", nargs="+", type=Path, default=[])
    parser.add_argument("--target-per-language", type=int, default=20)
    parser.add_argument("--candidates-per-language", type=int, default=80)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--max-seconds", type=float, default=300)
    args = parser.parse_args(argv)
    try:
        acquire(
            args.reference,
            args.output,
            args.languages,
            seed_corpus=args.seed_corpus,
            target=args.target_per_language,
            candidates_per_language=args.candidates_per_language,
            seed=args.seed,
            max_seconds=args.max_seconds,
        )
    except (OSError, ValueError, RuntimeError) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
