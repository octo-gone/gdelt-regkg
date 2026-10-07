"""Compare entities, count tuples and themes with original GKG article records.

Samples are fixed before retrieval. Live bodies are not verified GDELT snapshots;
enhanced offsets and location geocoding are not scored. Translation is opt-in through --include-translated and processes complete bodies before English NLP.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import statistics
import unicodedata
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

from gdelt_regkg.counts import CountRules, analyze_counts, default_count_rules
from gdelt_regkg.language import detect_language
from gdelt_regkg.ner import NameRules, SpacyNER
from gdelt_regkg.themes import ThemeLexicon, analyze_themes, default_theme_lexicon
from gdelt_regkg.tone import ToneLexicon, default_tone_lexicon, tokenize_tone
from gdelt_regkg.utils import read_resource_json

from .benchmark_tone import acquire_archive, parse_tone, process_article, sample_records, summarize


def normalize_name(value):
    """NFKC, casefold, apostrophe normalization and collapsed whitespace only."""
    value = unicodedata.normalize("NFKC", value).casefold().replace("\u2019", "'")
    return " ".join(value.split())


def parse_counts(cell):
    result = []
    for entry in filter(None, cell.split(";")):
        parts = entry.split("#")
        if len(parts) != 10 or not re.fullmatch(r"[A-Z][A-Z0-9_-]*", parts[0]):
            raise ValueError("Invalid legacy count tuple")
        try:
            number = Decimal(parts[1])
        except InvalidOperation as error:
            raise ValueError("Invalid count quantity") from error
        if not number.is_finite() or number < 0:
            raise ValueError("Count quantity must be finite and nonnegative")
        parts[1] = format(number.normalize(), "f")
        result.append(parts)
    return result


def reference(cells):
    return {
        "counts": parse_counts(cells[5]),
        "themes": sorted(set(filter(None, cells[7].split(";")))),
        "persons": list(filter(None, cells[11].split(";"))),
        "organizations": list(filter(None, cells[13].split(";"))),
    }


def load_originals(paths, *, include_translated=False):
    """Require unambiguous reference outputs per URL; keep malformed-row counts."""
    by_url, counts, archives = defaultdict(list), Counter[str](), []
    for path in sorted(set(paths)):
        archives.append(
            {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        with zipfile.ZipFile(path) as archive:
            for member in archive.namelist():
                if not member.endswith(".csv"):
                    continue
                with archive.open(member) as stream:
                    for raw in stream:
                        counts["original_rows"] += 1
                        try:
                            cells = raw.decode("utf-8").rstrip("\r\n").split("\t")
                            if len(cells) != 27:
                                raise ValueError("Expected 27 cells")
                            translated = bool(cells[25] or "-T" in cells[0])
                            if (
                                cells[2] != "1"
                                or not cells[4].startswith(("http://", "https://"))
                                or (translated and not include_translated)
                            ):
                                counts["excluded_translated_or_non_web"] += 1
                                continue
                            row = {
                                "record_id": cells[0],
                                "batch": cells[1],
                                "source": cells[3],
                                "url": cells[4],
                                "original": parse_tone(cells[15]),
                                "reference": reference(cells),
                                "translated": translated,
                                "translation_info": cells[25],
                                "original_tone_cell": cells[15],
                            }
                        except (ValueError, UnicodeError):
                            counts["malformed_original_rows"] += 1
                            continue
                        by_url[row["url"]].append(row)
    records = []
    for rows in by_url.values():
        signatures = {
            json.dumps(
                {
                    "reference": {
                        **r["reference"],
                        "counts": sorted(r["reference"]["counts"]),
                        "persons": sorted(set(r["reference"]["persons"])),
                        "organizations": sorted(set(r["reference"]["organizations"])),
                    },
                    "word_count": r["original"]["word_count"],
                },
                sort_keys=True,
            )
            for r in rows
        }
        if len(signatures) > 1:
            counts["excluded_conflicting_urls"] += 1
            continue
        records.append(rows[0])
        counts["identical_duplicate_rows"] += len(rows) - 1
    counts["eligible_unique_urls"] = len(records)
    return records, dict(counts), archives


def prepare_translation(row, translator, *, min_words=50):
    """Translate the complete retrieved body before any English field extraction."""
    if row.get("status") != "ok" or not row.get("translated") or not row.get("translation_pending"):
        return row
    from gdelt_regkg.fields import extract_tone
    from gdelt_regkg.translation import normalize_language, translate_text

    try:
        match = re.search(r"(?:^|;)srclc:([^;]+)", row.get("translation_info", ""))
        language = match[1] if match else None
        if language:
            try:
                normalize_language(language)
            except ValueError:
                row = {**row, "source_language_hint_error": language}
                language = None
        result = translate_text(
            row["text"],
            language=language,
            translator=translator,
            language_check="all",
        )
        row = {
            **row,
            "source_text": row["text"],
            "text": result.text,
            "source_language": result.source_language,
            "translation_engine": result.engine,
            "translation_pending": False,
        }
        row["text_sha256"] = hashlib.sha256(result.text.encode()).hexdigest()
        row["predicted_tone_cell"] = extract_tone(result.text)
        row["predicted"] = parse_tone(row["predicted_tone_cell"])
        if row["predicted"]["word_count"] < min_words:
            raise ValueError("Translated body is below minimum word count")
        row["word_count_ratio"] = row["predicted"]["word_count"] / row["original"]["word_count"]
    # Record individual article failures while allowing the batch to continue.
    except Exception as error:  # pylint: disable=broad-exception-caught
        row = {
            **row,
            "status": "failed",
            "stage": "translation",
            "error": f"{type(error).__name__}: {error}",
        }
    return row


def tally(expected, predicted):
    """Multiset matches; callers use sets when occurrence multiplicity is irrelevant."""
    gold, local = Counter(expected), Counter(predicted)
    return {
        "tp": sum((gold & local).values()),
        "fp": sum((local - gold).values()),
        "fn": sum((gold - local).values()),
        "reference": sum(gold.values()),
        "predicted": sum(local.values()),
        "exact": gold == local,
    }


def ratios(tp, fp, fn):
    return {
        "precision": tp / (tp + fp) if tp + fp else None,
        "recall": tp / (tp + fn) if tp + fn else None,
        "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None,
    }


def compare(expected, predicted, *, unique=False):
    if unique:
        expected, predicted = set(expected), set(predicted)
    result = tally(expected, predicted)
    return {**result, **ratios(result["tp"], result["fp"], result["fn"])}


def score(reference, predicted, fields, supported_themes):
    results, labels = {}, {}
    if "themes" in fields:
        gold, local = set(reference["themes"]), set(predicted["themes"])
        results["themes.all_labels"] = compare(gold, local)
        results["themes.supported_labels"] = compare(
            gold & supported_themes, local & supported_themes
        )
        labels["themes"] = {
            l: tally([l] if l in gold else [], [l] if l in local else [])
            for l in sorted(gold | local)
        }
    if "counts" in fields:
        gold, local = reference["counts"], predicted["counts"]
        core = lambda rows: [tuple(row[:2]) for row in rows]
        results["counts.labels"] = compare([r[0] for r in gold], [r[0] for r in local], unique=True)
        results["counts.label_quantity"] = compare(core(gold), core(local))
        results["counts.unique_label_quantity"] = compare(core(gold), core(local), unique=True)
        objects = lambda rows: [(r[0], r[1], normalize_name(r[2])) for r in rows]
        results["counts.with_object"] = compare(objects(gold), objects(local))
        results["counts.full_tuple"] = compare([tuple(r) for r in gold], [tuple(r) for r in local])
        labels["counts"] = {
            l: tally(
                [tuple(r[:2]) for r in gold if r[0] == l],
                [tuple(r[:2]) for r in local if r[0] == l],
            )
            for l in sorted({r[0] for r in gold + local})
        }
    if "ner" in fields:
        for kind in ("persons", "organizations"):
            gold, local = reference[kind], predicted[kind]
            results[f"ner.{kind}.raw"] = compare(gold, local, unique=True)
            results[f"ner.{kind}.normalized"] = compare(
                map(normalize_name, gold), map(normalize_name, local), unique=True
            )
    return results, labels


def aggregate(rows):
    if not rows:
        return {"n": 0, "metrics": {}, "per_label": {}}
    metrics = {}
    for key in rows[0]["scores"]:
        values = [r["scores"][key] for r in rows]
        total = {
            name: sum(v[name] for v in values)
            for name in ("tp", "fp", "fn", "reference", "predicted")
        }
        f1 = [v["f1"] for v in values if v["f1"] is not None]
        metrics[key] = {
            **total,
            **ratios(total["tp"], total["fp"], total["fn"]),
            "document_f1_mean_nonempty": statistics.mean(f1) if f1 else None,
            "documents_either_nonempty": len(f1),
            "documents_reference_nonempty": sum(v["reference"] > 0 for v in values),
            "documents_both_empty": sum(v["reference"] == v["predicted"] == 0 for v in values),
            "exact_document_agreement": sum(v["exact"] for v in values) / len(values),
        }
    per_label = {}
    for field in rows[0]["label_scores"]:
        totals: defaultdict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            for label, values in row["label_scores"][field].items():
                totals[label].update(
                    {k: values[k] for k in ("tp", "fp", "fn", "reference", "predicted")}
                )
        per_label[field] = {
            l: {**dict(v), **ratios(v["tp"], v["fp"], v["fn"])} for l, v in sorted(totals.items())
        }
        f1s = [v["f1"] for v in per_label[field].values() if v["f1"] is not None]
        key = "themes.all_labels" if field == "themes" else "counts.label_quantity"
        metrics[key]["label_macro_f1"] = statistics.mean(f1s) if f1s else None
    return {
        "n": len(rows),
        "sources": len({r["source"] for r in rows}),
        "metrics": metrics,
        "per_label": per_label,
    }


def load_corpus(path):
    if path is None:
        return None
    by_url = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["url"] in by_url:
            raise ValueError(f"Duplicate URL in supplied corpus: {row['url']}")
        by_url[row["url"]] = row
    return by_url


def retrieve(row, args, corpus):
    if corpus is not None:
        saved = corpus[row["url"]]
        if saved.get("status") != "ok" or not saved.get("text"):
            return {
                **row,
                "status": "failed",
                "stage": "corpus",
                "error": saved.get("error", "Corpus body is unavailable"),
                "corpus_stage": saved.get("stage"),
            }
        body = saved["text"]
        if saved.get("translation_pending"):
            return {**saved, **row}
        n = len(tokenize_tone(body))
        if n < args.min_words:
            return {
                **row,
                "status": "failed",
                "stage": "extract",
                "error": "Body below minimum word count",
            }
        return {
            **saved,
            **row,
            "status": "ok",
            "text": body,
            "text_sha256": hashlib.sha256(body.encode()).hexdigest(),
            "fetch": saved.get("fetch"),
            "body_origin": "supplied_corpus",
            "word_count_ratio": n / row["original"]["word_count"],
        }
    fetch_args = SimpleNamespace(
        output=args.cache_dir or args.output,
        timeout=args.timeout,
        offline=args.offline,
        min_words=args.min_words,
    )
    return process_article(
        row, fetch_args, default_tone_lexicon(getattr(args, "resources_dir", None))
    )


def predict(row, fields, recognizer, count_rules, theme_lexicon, check_language):
    if row["status"] != "ok":
        return row
    stage = "language"
    try:
        if check_language:
            detection = detect_language(row["text"])
            row["language_detection"] = asdict(detection)
            if detection.language != "eng":
                raise ValueError(f"Body detected as {detection.language}")
        stage = "nlp"
        predicted = {}
        if "counts" in fields:
            result = analyze_counts(row["text"], rules=count_rules)
            predicted["counts"] = parse_counts(result.to_gkg())
            row["count_issues"] = [asdict(i) for i in result.issues]
        if "themes" in fields:
            predicted["themes"] = sorted(
                {m.theme for m in analyze_themes(row["text"], lexicon=theme_lexicon).mentions}
            )
        if "ner" in fields:
            result = recognizer.analyze(row["text"])
            predicted["persons"] = (
                result.to_gkg("PERSON").split(";") if result.to_gkg("PERSON") else []
            )
            predicted["organizations"] = (
                result.to_gkg("ORG").split(";") if result.to_gkg("ORG") else []
            )
            row["entity_mentions"] = [asdict(m) for m in result.mentions]
        row["predicted_fields"] = predicted
        supported = {r.theme for r in theme_lexicon.rules}
        row["scores"], row["label_scores"] = score(row["reference"], predicted, fields, supported)
    # Include backend failures in the report rather than dropping the article.
    except Exception as error:  # pylint: disable=broad-exception-caught
        row.update(status="failed", stage=stage, error=f"{type(error).__name__}: {error}")
    return row


def main(default_fields=("ner", "counts", "themes")):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources-dir",
        type=Path,
        default=Path("local-resources"),
        help="Directory containing prepared profiles and defaults.json",
    )
    parser.add_argument(
        "--fields", nargs="+", choices=("ner", "counts", "themes"), default=default_fields
    )
    parser.add_argument("--archives", nargs="*", type=Path, default=[])
    parser.add_argument("--batches", nargs="*", default=[])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--corpus",
        type=Path,
        help="Reuse benchmark results.jsonl texts and failures; no article fetches",
    )
    parser.add_argument(
        "--cache-dir", type=Path, help="Existing benchmark directory containing html/"
    )
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--per-day", type=int)
    parser.add_argument("--per-source", type=int, default=2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--workers",
        type=int,
        default=6,
        help="Article retrieval threads; NLP model is reused sequentially",
    )
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--min-words", type=int, default=50)
    parser.add_argument("--ner-model", default="en_core_web_sm")
    parser.add_argument(
        "--ner-name-rules",
        type=Path,
        help="Optional calibrated name aliases and organization exclusions",
    )
    parser.add_argument(
        "--ner-name-policy",
        choices=("surface", "gdelt", "gdelt-full-names"),
        default="gdelt-full-names",
        help="Serialization and full-name policy; source spans are retained",
    )
    parser.add_argument("--count-rules", type=Path)
    parser.add_argument("--theme-lexicon", type=Path)
    parser.add_argument("--tone-lexicon", type=Path)
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Include native translated records and translate their retrieved bodies locally",
    )
    parser.add_argument("--translation-model", default="facebook/m2m100_418M")
    parser.add_argument("--translation-device", default="cuda")
    parser.add_argument("--translation-cache", type=Path)
    parser.add_argument("--translation-batch-size", type=int, default=8)
    parser.add_argument("--translation-beams", type=int, default=1)
    parser.add_argument(
        "--no-language-check",
        action="store_true",
        help="Skip independent English screening; record this in configuration",
    )
    args = parser.parse_args()
    if not args.archives and not args.batches:
        parser.error("Supply --archives and/or --batches for the original reference fields")
    if min(args.sample_size, args.per_source, args.workers, args.timeout, args.min_words) < 1 or (
        args.per_day is not None and args.per_day < 1
    ):
        parser.error("Sampling and processing limits must be positive")
    fields = tuple(sorted(set(args.fields)))
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "html").mkdir(exist_ok=True)
    paths, failures = list(args.archives), []
    for batch in args.batches:
        try:
            if len(batch) != 14 or not batch.isdigit():
                raise ValueError("Expected 14 digits")
            datetime.strptime(batch, "%Y%m%d%H%M%S")
        except ValueError as error:
            parser.error(f"Invalid batch: {batch}: {error}")
        for translated in (False, True) if args.include_translated else (False,):
            try:
                paths.append(
                    acquire_archive(
                        batch,
                        args.output,
                        max(args.timeout, 60),
                        offline=args.offline,
                        translated=translated,
                    )
                )
            except (OSError, ValueError, zipfile.BadZipFile) as error:
                failures.append(
                    {
                        "batch": batch,
                        "translated": translated,
                        "error": f"{type(error).__name__}: {error}",
                    }
                )
    if not paths:
        parser.error("No original archives available")
    try:
        corpus = load_corpus(args.corpus)
        records, original_counts, archives = load_originals(
            paths, include_translated=args.include_translated
        )
        if corpus is not None:
            records = [r for r in records if r["url"] in corpus]
        if args.per_day:
            days = sorted({r["batch"][:8] for r in records})
            selected = [
                r
                for d in days
                for r in sample_records(
                    [r for r in records if r["batch"].startswith(d)],
                    args.per_day,
                    args.per_source,
                    args.seed,
                )
            ]
        else:
            selected = sample_records(records, args.sample_size, args.per_source, args.seed)
        if not selected:
            parser.error("No eligible records in the requested archive/corpus intersection")
        count_rules = (
            CountRules.from_json(args.count_rules)
            if args.count_rules
            else default_count_rules(args.resources_dir)
        )
        theme_lexicon = (
            ThemeLexicon.from_json(args.theme_lexicon)
            if args.theme_lexicon
            else default_theme_lexicon(args.resources_dir)
        )
        tone_lexicon = (
            ToneLexicon.from_json(args.tone_lexicon)
            if args.tone_lexicon
            else default_tone_lexicon(args.resources_dir)
        )
    except (OSError, ValueError) as error:
        parser.error(str(error))
    resource_hash = lambda name: hashlib.sha256(
        json.dumps(
            read_resource_json("lexicons", name, resources_dir=args.resources_dir), sort_keys=True
        ).encode()
    ).hexdigest()
    defaults = read_resource_json("defaults.json", resources_dir=args.resources_dir)
    configuration = {
        "fields": fields,
        "ner_model": args.ner_model if "ner" in fields else None,
        "ner_name_policy": args.ner_name_policy if "ner" in fields else None,
        "ner_name_rules_sha256": hashlib.sha256(args.ner_name_rules.read_bytes()).hexdigest()
        if args.ner_name_rules
        else resource_hash(defaults["ner"])
        if "ner" in fields and args.ner_name_policy == "gdelt-full-names"
        else None,
        "count_rules": count_rules.name,
        "theme_lexicon": theme_lexicon.name,
        "count_sha256": hashlib.sha256(args.count_rules.read_bytes()).hexdigest()
        if args.count_rules
        else resource_hash(defaults["counts"]),
        "theme_sha256": hashlib.sha256(args.theme_lexicon.read_bytes()).hexdigest()
        if args.theme_lexicon
        else resource_hash(defaults["themes"]),
        "tone_sha256": hashlib.sha256(args.tone_lexicon.read_bytes()).hexdigest()
        if args.tone_lexicon
        else resource_hash(defaults["tone"]),
        "corpus_sha256": hashlib.sha256(args.corpus.read_bytes()).hexdigest()
        if args.corpus
        else None,
        "sampling": {
            k: getattr(args, k)
            for k in ("sample_size", "per_day", "per_source", "seed", "min_words")
        },
        "independent_language_check": not args.no_language_check,
        "include_translated": args.include_translated,
        "translation": {
            "model": args.translation_model,
            "device": args.translation_device,
            "batch_size": args.translation_batch_size,
            "beams": args.translation_beams,
        }
        if args.include_translated
        else None,
        "implementation_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "extraction_sha256": hashlib.sha256(
            b"".join(
                (Path(__file__).parents[1] / name).read_bytes()
                for name in (
                    "ner.py",
                    "counts.py",
                    "tone.py",
                    "translation.py",
                    "themes.py",
                    "language.py",
                    "wire.py",
                    "rule_inputs.py",
                )
            )
        ).hexdigest(),
    }
    manifest = {
        "configuration": configuration,
        "archives": archives,
        "archive_failures": failures,
        "selected": selected,
    }
    manifest_path = args.output / "manifest.json"
    # Compare the JSON form so tuple/list encoding is stable on replay.
    manifest = json.loads(json.dumps(manifest))
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        parser.error("Output contains a different sample/configuration; choose a new --output")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    recognizer = (
        SpacyNER.from_model(
            args.ner_model,
            resources_dir=args.resources_dir,
            name_policy=args.ner_name_policy,
            name_rules=NameRules.from_json(args.ner_name_rules) if args.ner_name_rules else None,
        )
        if "ner" in fields
        else None
    )
    translator = None
    if args.include_translated:
        from gdelt_regkg.translation import CachedTranslator, M2M100Translator

        translator = CachedTranslator(
            M2M100Translator.from_model(
                args.translation_model,
                device=args.translation_device,
                batch_size=args.translation_batch_size,
                num_beams=args.translation_beams,
            ),
            args.translation_cache or args.output / "translations.sqlite",
        )
    if corpus is None:
        import dateparser

        import_module("trafilatura")

        dateparser.parse("September 30, 2026", languages=["en"])
    rows = []
    # Failure decisions in a cached offline run are retained, not silently replaced.
    previous = {}
    if args.offline and corpus is None and (args.output / "results.jsonl").exists():
        previous = {
            r["url"]: r
            for r in load_corpus(args.output / "results.jsonl").values()
            if r.get("stage") == "fetch" and r["status"] == "failed"
        }
    with (
        (args.output / "results.jsonl").open("w", encoding="utf-8") as stream,
        ThreadPoolExecutor(max_workers=args.workers) as pool,
    ):
        retrieved = pool.map(
            lambda r: previous.get(r["url"]) or retrieve(r, args, corpus), selected
        )
        for row in retrieved:
            row = prepare_translation(row, translator, min_words=args.min_words)
            if row.get("status") == "ok":
                from gdelt_regkg.fields import extract_tone

                row["predicted_tone_cell"] = extract_tone(row["text"], lexicon=tone_lexicon)
                row["predicted"] = parse_tone(row["predicted_tone_cell"])
            result = predict(
                row, fields, recognizer, count_rules, theme_lexicon, not args.no_language_check
            )
            rows.append(result)
            stream.write(json.dumps(result, ensure_ascii=False) + "\n")
            stream.flush()
            if len(rows) % 25 == 0 or len(rows) == len(selected):
                print(
                    f"[ARTICLES] {len(rows)}/{len(selected)}; scored={sum(r['status'] == 'ok' for r in rows)}",
                    flush=True,
                )
    good = [r for r in rows if r["status"] == "ok"]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": configuration,
        "ner_backend": recognizer.name if recognizer else None,
        "original_counts": original_counts,
        "corpus_intersection_records": len(records),
        "selected": len(selected),
        "scored": len(good),
        "failed": len(rows) - len(good),
        "archive_failures": failures,
        "failures_by_stage": dict(Counter(r.get("stage") for r in rows if r["status"] != "ok")),
        "all_scored": aggregate(good),
        "tone": summarize(good),
        "tone_by_translation": {
            name: summarize([r for r in good if bool(r.get("translated")) == translated])
            for name, translated in (("english", False), ("translated", True))
        },
        "word_count_within_10_percent": aggregate(
            [r for r in good if abs(r["word_count_ratio"] - 1) <= 0.1]
        ),
        "by_original_date": {
            d: aggregate([r for r in good if r["batch"].startswith(d)])
            for d in sorted({r["batch"][:8] for r in good})
        },
        "by_translation": {
            name: aggregate([r for r in good if bool(r.get("translated")) == translated])
            for name, translated in (("english", False), ("translated", True))
        },
        "by_source": {
            s: aggregate([r for r in good if r["source"] == s])
            for s in sorted({r["source"] for r in good})
        },
        "text_policy": "Supplied corpus text verbatim or Trafilatura body, no titles/comments/tables; translated originals use explicit local M2M100 before English NLP; independent English screening by default",
        "normalization": "NER raw names and NFKC/casefold/whitespace/apostrophe normalized names; no alias resolution",
        "metric_policy": "Micro multiset label+quantity count scoring plus unique pairs, objects and full tuples; per-article theme/name sets; undefined ratios are null and both-empty documents excluded from document F1 means",
        "interpretation": "Agreement against original records on retrieved bodies; not a gold-standard accuracy claim or verified identical GDELT text. Failures excluded from metrics and counted separately. Enhanced offsets and geographic NER accuracy are not scored.",
    }
    (args.output / "summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (args.output / "comparison.csv").open("w", newline="", encoding="utf-8") as stream:
        names = sorted(report["all_scored"]["metrics"])
        keys = ["record_id", "source", "url", "word_count_ratio", "text_sha256"] + [
            f"{k}.{v}" for k in names for v in ("tp", "fp", "fn", "precision", "recall", "f1")
        ]
        writer = csv.DictWriter(stream, fieldnames=keys)
        writer.writeheader()
        for r in good:
            writer.writerow(
                {
                    **{k: r[k] for k in keys[:5]},
                    **{
                        f"{k}.{v}": r["scores"][k][v]
                        for k in names
                        for v in ("tp", "fp", "fn", "precision", "recall", "f1")
                    },
                }
            )
    print(
        json.dumps(
            {
                "selected": len(selected),
                "scored": len(good),
                "failed": len(rows) - len(good),
                "metrics": report["all_scored"]["metrics"],
            },
            indent=2,
        )
    )
    if not good:
        raise SystemExit("No usable articles scored; inspect results.jsonl")
    if translator is not None:
        translator.close()


def main_ner():
    main(("ner",))


def main_counts():
    main(("counts",))


def main_themes():
    main(("themes",))


if __name__ == "__main__":
    main()
