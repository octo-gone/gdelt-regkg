"""Benchmark command: load paired rows or saved bodies, score, and publish tables."""

import hashlib
import logging
import os
import sqlite3
from dataclasses import replace
from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
from importlib.resources import files
from pathlib import Path

from gdelt_regkg.benchmark import BenchmarkOptions, BenchmarkReport, evaluate, write_report
from gdelt_regkg.benchmark.checkpoint import prediction_signature, select_device
from gdelt_regkg.benchmark.corpus import NER_FIELDS, generate_predictions, load_corpus
from gdelt_regkg.benchmark.engine import select_fields
from gdelt_regkg.benchmark.inputs import align_rows, load_rows, resolve_inputs
from gdelt_regkg.benchmark.storage import BenchmarkStore
from gdelt_regkg.fields.gcam import GCAMLexicon, default_gcam_lexicon
from gdelt_regkg.fields.themes import default_theme_lexicon
from gdelt_regkg.utils import ResourceUnavailableError, read_resource_json, resource_path

from .progress import print_progress

LOGGER = logging.getLogger(__name__)


def add_arguments(parser):
    parser.add_argument(
        "--reference",
        nargs="+",
        type=Path,
        required=True,
        help="Native GKG files or directories (searched recursively)",
    )
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--prediction", nargs="+", type=Path, help="Reconstructed GKG files or directories"
    )
    inputs.add_argument(
        "--corpus",
        nargs="+",
        type=Path,
        help="Saved article-body JSONL files or directories; generates predictions locally",
    )
    parser.add_argument("--output", type=Path, default=Path("benchmark-results"))
    parser.add_argument(
        "--fields",
        nargs="+",
        default=["all"],
        help="Fields/groups (space or comma separated); default all",
    )
    parser.add_argument("--exclude", nargs="+", default=[], help="Fields/groups to omit")
    parser.add_argument(
        "--match", choices=("document-date", "document", "record-id"), default="document-date"
    )
    parser.add_argument(
        "--source-collections", nargs="+", default=["1"], help="Collection IDs, or all"
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail on malformed input rows instead of auditing and skipping them",
    )
    parser.add_argument("--offset-tolerance", type=int, default=100)
    parser.add_argument(
        "--relaxed", action="store_true", help="Add explicitly labelled fuzzy/tolerant comparisons"
    )
    parser.add_argument("--number-tolerance", type=float, default=0.1)
    parser.add_argument("--object-similarity", type=float, default=0.6)
    parser.add_argument("--quote-similarity", type=float, default=0.5)
    parser.add_argument("--tone-neutral", type=float, default=0.5)
    parser.add_argument(
        "--diagnostics", action="store_true", help="Add consistency and proximity rows"
    )
    parser.add_argument("--proximity-window", type=int, default=200)
    parser.add_argument("--resources-dir", type=Path, default=Path("local-resources"))
    parser.add_argument(
        "--gcam-lexicon",
        type=Path,
        help="Declare implemented dimensions; also overrides GCAM in corpus mode",
    )
    parser.add_argument("--ner-model", default="en_core_web_sm")
    parser.add_argument(
        "--cache",
        type=Path,
        help="SQLite workspace and prediction cache (default: OUTPUT/benchmark.sqlite3)",
    )
    parser.add_argument(
        "--device",
        choices=("cpu", "cuda", "auto"),
        default="cpu",
        help="spaCy inference device; cuda requires a working CuPy installation",
    )
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument(
        "--batch-size", type=int, default=16, help="Maximum articles per NER/checkpoint batch"
    )
    parser.add_argument(
        "--batch-chars",
        type=int,
        default=100000,
        help="Target maximum characters per batch; longer single articles are kept intact",
    )
    parser.add_argument(
        "--ner-cache", type=Path, help="Saved JSONL entity_mentions matching the corpus text hashes"
    )
    parser.add_argument(
        "--include-translated",
        action="store_true",
        help="Accept already translated saved bodies; does not translate",
    )
    parser.add_argument("--numeric-date-order", choices=("mdy", "dmy"))
    parser.add_argument(
        "--stratify",
        nargs="*",
        choices=("month", "source", "translation", "word_count"),
        default=[],
    )
    parser.add_argument("--min-stratum", type=int, default=10)
    parser.add_argument("--max-strata", type=int, default=20)


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def strata(pairs, names):
    from collections import defaultdict

    from gdelt_regkg.benchmark.parsers import tone

    grouped = defaultdict(list)
    for pair in pairs:
        row = pair[0]
        for name in names:
            if name == "month":
                value = (row.get("date") or "unknown")[:6]
            elif name == "source":
                value = row.get("source") or "unknown"
            elif name == "translation":
                value = (
                    "translated"
                    if row.get("translation") or "-T" in (row.get("recordid") or "")
                    else "native"
                )
            else:
                try:
                    words = tone(row.get("tone") or "")
                except ValueError:
                    words = None
                count = words[6] if words else None
                value = (
                    "unknown"
                    if count is None
                    else "0–199"
                    if count < 200
                    else "200–499"
                    if count < 500
                    else "500–999"
                    if count < 1000
                    else "1000+"
                )
            grouped[name + "/" + value].append(pair)
    return grouped


def run(args):
    if args.batch_size < 1 or args.batch_chars < 1 or args.gpu_id < 0:
        raise ValueError(
            "Batch size and character limit must be positive; GPU ID must be nonnegative"
        )
    fields = select_fields(args.fields)
    if args.exclude:
        excluded = set(select_fields(args.exclude))
        fields = tuple(name for name in fields if name not in excluded)
    if not fields:
        raise ValueError("No benchmark fields remain after exclusions")
    if args.min_stratum < 1 or args.max_strata < 1:
        raise ValueError("Stratum limits must be positive")
    if "all" in args.source_collections and args.source_collections != ["all"]:
        raise ValueError("Choose source collection IDs or all, not both")
    if args.corpus is None and (
        args.ner_cache is not None or args.include_translated or args.numeric_date_order is not None
    ):
        raise ValueError("NER cache, translated bodies and numeric-date-order require --corpus")
    options = BenchmarkOptions(
        offset_tolerance=args.offset_tolerance,
        relaxed=args.relaxed,
        number_tolerance=args.number_tolerance,
        object_similarity=args.object_similarity,
        quote_similarity=args.quote_similarity,
        tone_neutral=args.tone_neutral,
        diagnostics=args.diagnostics,
        proximity_window=args.proximity_window,
    )
    try:
        for dependency in ("scipy", "sklearn"):
            import_module(dependency)
    except ModuleNotFoundError as error:
        raise ValueError(
            'Install benchmark dependencies with pip install "gdelt-regkg[benchmark]" '
            "or uv sync --extra benchmark"
        ) from error
    args.reference = resolve_inputs(args.reference)
    if args.prediction is not None:
        args.prediction = resolve_inputs(args.prediction)
    if args.corpus is not None:
        args.corpus = resolve_inputs(args.corpus, corpus=True)
    path = args.cache or args.output / "benchmark.sqlite3"
    try:
        with BenchmarkStore(path) as store:
            return run_with_store(args, fields, options, store)
    except sqlite3.Error as error:
        raise ValueError(f"Benchmark cache {path}: {error}") from error


def run_with_store(args, fields, options, store):
    report = BenchmarkReport()
    source_collections = (
        None if args.source_collections == ["all"] else tuple(args.source_collections)
    )
    print_progress(
        f"[benchmark] Reading {len(args.reference)} reference files and "
        f"{len(args.prediction or args.corpus or [])} {'prediction' if args.prediction else 'corpus'} files"
    )
    corpus = None
    device = "not used"
    signature = None
    if args.corpus:
        if set(fields) & NER_FIELDS and args.ner_cache is None:
            os.environ.setdefault(
                "CUPY_CACHE_DIR", str(store.path.parent.resolve() / "cupy-kernels")
            )
            device = select_device(args.device, args.gpu_id, print_progress)
        signature = prediction_signature(args, fields, device)
        print_progress(f"[benchmark] Checkpoints: {store.path}")
        corpus = load_corpus(
            args.corpus,
            report=report,
            include_translated=args.include_translated,
            destination=store.corpus(),
        )
    reference = load_rows(
        args.reference,
        report=report,
        side="reference",
        strict=args.strict,
        source_collections=source_collections,
        wanted_documents={key[1] for key in corpus} if corpus else None,
        destination=store.rows("reference"),
    )
    gcam = None
    if "gcam" in fields:
        try:
            gcam = (
                GCAMLexicon.from_json(args.gcam_lexicon)
                if args.gcam_lexicon
                else default_gcam_lexicon(args.resources_dir)
            )
        except ResourceUnavailableError:
            if args.gcam_lexicon or corpus:
                raise
        if gcam:
            options = replace(options, gcam_keys=frozenset(gcam.dimensions))
    if "themes" in fields:
        try:
            themes = default_theme_lexicon(args.resources_dir)
        except ResourceUnavailableError:
            if corpus:
                raise
        else:
            options = replace(options, theme_labels=frozenset(rule.theme for rule in themes.rules))
    if corpus is None:
        prediction = load_rows(
            args.prediction,
            report=report,
            side="prediction",
            strict=args.strict,
            source_collections=source_collections,
            destination=store.rows("prediction"),
        )
    else:
        prediction = generate_predictions(
            corpus,
            reference,
            fields=fields,
            report=report,
            resources_dir=args.resources_dir,
            ner_model=args.ner_model,
            ner_cache=args.ner_cache,
            gcam_lexicon=gcam,
            numeric_date_order=args.numeric_date_order,
            progress=print_progress,
            store=store,
            signature=signature,
            batch_size=args.batch_size,
            batch_chars=args.batch_chars,
        )
    store.commit()
    pairs = align_rows(reference, prediction, report=report, match=args.match)
    print_progress(
        f"[benchmark] Scoring {len(pairs)} matched documents across {len(fields)} fields"
    )
    evaluate(pairs, fields=fields, options=options, report=report, progress=print_progress)
    for name, subset in sorted(
        strata(pairs, args.stratify).items(), key=lambda item: (-len(item[1]), item[0])
    )[: args.max_strata]:
        if len(subset) >= args.min_stratum:
            print_progress(f"[benchmark] Scoring {name}: {len(subset)} documents")
            evaluate(
                subset,
                fields=fields,
                options=options,
                report=report,
                subset=name,
                progress=print_progress,
            )
    report.configuration = {
        "mode": "saved bodies" if corpus else "prepared GKG rows",
        "prediction_cache": str(store.path.resolve()),
        "prediction_signature": signature or "prepared predictions",
        "ner_device": device,
        "ner_batch_size": str(args.batch_size),
        "ner_batch_chars": str(args.batch_chars),
        "fields": ", ".join(fields),
        "match": args.match,
        "matched_documents": str(len(pairs)),
        "source_collections": ", ".join(args.source_collections),
        "offset_tolerance_chars": str(options.offset_tolerance),
        "relaxed": str(options.relaxed),
        "relative_number_tolerance": str(options.number_tolerance),
        "object_similarity": str(options.object_similarity),
        "quote_similarity": str(options.quote_similarity),
        "tone_neutral": str(options.tone_neutral),
        "resources_dir": str(args.resources_dir.resolve()),
        "gcam_profile": gcam.name if gcam else "inventory unavailable",
        "corpus_metadata": "alignment metadata supplied from native rows"
        if corpus
        else "supplied prediction values",
        "ner": str(args.ner_cache)
        if args.ner_cache
        else args.ner_model
        if corpus
        else "prepared predictions",
        "numeric_date_order": args.numeric_date_order or "ambiguous dates skipped",
        "include_translated": str(args.include_translated),
        "diagnostics": str(args.diagnostics),
        "proximity_window_chars": str(args.proximity_window),
        "stratify": ", ".join(args.stratify),
        "min_stratum": str(args.min_stratum),
        "max_strata": str(args.max_strata),
    }
    try:
        report.configuration["package_version"] = version("gdelt-regkg")
    except PackageNotFoundError:
        report.configuration["package_version"] = "source checkout"
    for dependency in ("numpy", "scipy", "scikit-learn"):
        report.configuration[dependency + "_version"] = version(dependency)
    for module in sorted(
        files("gdelt_regkg").joinpath("benchmark").iterdir(), key=lambda path: path.name
    ):
        if module.name.endswith(".py"):
            report.configuration["code SHA256 benchmark/" + module.name] = hashlib.sha256(
                module.read_bytes()
            ).hexdigest()
    command_code = files("gdelt_regkg").joinpath("cli", "benchmark.py")
    report.configuration["code SHA256 cli/benchmark.py"] = hashlib.sha256(
        command_code.read_bytes()
    ).hexdigest()
    defaults = read_resource_json("defaults.json", resources_dir=args.resources_dir)
    needed = set()
    if options.theme_labels is not None:
        needed.add("themes")
    if gcam is not None and args.gcam_lexicon is None:
        needed.add("gcam")
    if corpus:
        if set(fields) & {"counts", "enhanced_counts"}:
            needed.update(("counts", "ner", "locations"))
        if set(fields) & {
            "persons",
            "enhanced_persons",
            "organizations",
            "enhanced_organizations",
            "locations",
            "enhanced_locations",
            "all_names",
        }:
            needed.add("ner")
        if set(fields) & {"locations", "enhanced_locations"}:
            needed.add("locations")
        if "tone" in fields:
            needed.add("tone")
    for name in sorted(needed):
        resource = resource_path("lexicons", defaults[name], resources_dir=args.resources_dir)
        report.configuration["resource SHA256 " + name] = hashlib.sha256(
            resource.read_bytes()
        ).hexdigest()
    for path in [
        *args.reference,
        *(args.prediction or []),
        *(args.corpus or []),
        *([args.ner_cache] if args.ner_cache else []),
        *([args.gcam_lexicon] if args.gcam_lexicon else []),
    ]:
        report.configuration["SHA256 " + str(path)] = sha256(path)
    path = write_report(report, args.output)
    warnings_count = sum(
        count
        for (_, _, issue, _, subset), count in report.audit.items()
        if subset == "all"
        and issue
        in {
            "malformed",
            "malformed_row",
            "conflicting_key",
            "unavailable",
            "outside_inventory",
            "missing_inventory",
        }
    )
    if warnings_count:
        LOGGER.warning(
            "[warning] %s invalid, ambiguous or unavailable values; see %s",
            warnings_count,
            args.output / "audit.csv",
        )
    print(
        f"Benchmarked {len(pairs)} documents; {len(report.rows)} result rows. Reports: {path}, {args.output / 'metrics.csv'}",
        flush=True,
    )
