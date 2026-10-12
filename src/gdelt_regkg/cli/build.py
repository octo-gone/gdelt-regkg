"""Build command: parse the request, resolve inputs, compile, and publish."""

from __future__ import annotations

import argparse
import gzip
import json
import tempfile
from pathlib import Path

from .gcam import COMPONENT_SOURCES, GCAMOptions
from .inputs import SOURCE_NAMES, TARGET_SOURCES, parse_sources, resolve_inputs
from .profiles import Artifact, compile_profiles
from .progress import Progress, ignore_progress, print_progress


def add_arguments(parser: argparse.ArgumentParser):
    parser.add_argument(
        "targets",
        nargs="+",
        metavar="TARGET",
        help="Targets: " + ", ".join(TARGET_SOURCES) + "; use all to select every target",
    )
    parser.add_argument("--output", type=Path, default=Path("local-resources"))
    parser.add_argument(
        "--use",
        default="best",
        metavar="RECIPE",
        help="Recipe to build: best (default), v1, v2, v3; also themes: authored, gcam: full",
    )
    parser.add_argument(
        "--suffix", metavar="LABEL", help="Output label only, e.g. tone.experiment.json"
    )
    parser.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Explicit input; repeat as needed. Names: " + ", ".join(SOURCE_NAMES),
    )
    parser.add_argument(
        "--sources-dir", type=Path, help="Find the recipe's recorded source files here"
    )
    parser.add_argument(
        "--download-sources",
        action="store_true",
        help="Fetch required recorded inputs into --sources-dir",
    )
    parser.add_argument(
        "--authored-themes-only", action="store_true", help="Use authored themes without CrisisLex"
    )
    locations = parser.add_argument_group("locations")
    locations.add_argument(
        "--gazetteer-archives",
        nargs="+",
        type=Path,
        help="Explicit GKG reference ZIP files for locations",
    )
    locations.add_argument("--gazetteer-name", default="gkg-reference-gazetteer-v1")
    locations.add_argument(
        "--gazetteer-filename", help="Complete JSON/gzip basename; replaces --suffix"
    )
    gcam = parser.add_argument_group("GCAM")
    gcam.add_argument("--gcam-baseline", type=Path, help="Expand an existing GCAM JSON/gzip file")
    gcam.add_argument(
        "--gcam-add",
        choices=COMPONENT_SOURCES,
        nargs="+",
        default=(),
        help="Add or replace these components in the starting profile",
    )
    gcam.add_argument("--gcam-filename", help="Output basename ending in .json or .json.gz")
    gcam.add_argument("--affect-propagate-hierarchy", action="store_true")
    gcam.add_argument("--affect-nouns-only", action="store_true")


def publish(
    output: Path,
    artifacts: tuple[Artifact, ...],
    selections: dict[str, str],
    *,
    progress: Progress = ignore_progress,
):
    """Stage complete files and preserve unrelated selections on partial builds."""
    defaults_path = output / "defaults.json"
    defaults = (
        json.loads(defaults_path.read_text(encoding="utf-8")) if defaults_path.is_file() else {}
    )
    if not isinstance(defaults, dict) or any(
        not isinstance(value, str) for value in defaults.values()
    ):
        raise ValueError(f"Expected a field-to-filename object in {defaults_path}")
    defaults.update(selections)
    artifacts = (*artifacts, Artifact("defaults.json", defaults))
    progress(f"[write] Preparing {len(artifacts)} files for {output}")
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=output) as directory:
        staging = Path(directory)
        for artifact in artifacts:
            if not artifact.path.startswith("schemas/"):
                progress(f"[write] Preparing {artifact.path}")
            raw = (json.dumps(artifact.payload, ensure_ascii=False, indent=2) + "\n").encode(
                "utf-8"
            )
            path = staging / artifact.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(gzip.compress(raw, mtime=0) if path.suffix == ".gz" else raw)
        # Defaults are installed last, after the selected profiles exist.
        for artifact in artifacts:
            destination = output / artifact.path
            destination.parent.mkdir(parents=True, exist_ok=True)
            (staging / artifact.path).replace(destination)
    progress(f"[write] Published {len(artifacts)} files to {output}")


def run(args: argparse.Namespace):
    inputs = resolve_inputs(
        args.output,
        targets=args.targets,
        sources=parse_sources(args.source),
        sources_dir=args.sources_dir,
        download_sources=args.download_sources,
        authored_themes_only=args.authored_themes_only,
        gazetteer_archives=args.gazetteer_archives,
        gazetteer_name=args.gazetteer_name,
        gazetteer_filename=args.gazetteer_filename,
        gcam=GCAMOptions(
            baseline=None if args.gcam_baseline is None else args.gcam_baseline.expanduser(),
            additions=tuple(args.gcam_add),
            affect_propagate_hierarchy=args.affect_propagate_hierarchy,
            affect_nouns_only=args.affect_nouns_only,
        ),
        gcam_filename=args.gcam_filename,
        use=args.use,
        suffix=args.suffix,
        progress=print_progress,
    )
    artifacts, selections = compile_profiles(inputs, progress=print_progress)
    publish(inputs.output, artifacts, selections, progress=print_progress)
    print(
        "Built " + ", ".join(f"{name}: {filename}" for name, filename in selections.items()),
        flush=True,
    )
