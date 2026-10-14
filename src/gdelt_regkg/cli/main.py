"""Command dispatch for gdelt-regkg-cli."""

from __future__ import annotations

import argparse
import zipfile
from collections.abc import Sequence

from ..dependencies import OptionalDependencyError
from ..scripts import refine_tone_lexicon
from . import benchmark, build


def main(argv: Sequence[str] | None = None):
    parser = argparse.ArgumentParser(description="GDELT reconstruction tools")
    commands = parser.add_subparsers(dest="command", required=True)
    build_parser = commands.add_parser("build", help="Build local extraction resources")
    build.add_arguments(build_parser)
    benchmark_parser = commands.add_parser(
        "benchmark", help="Compare GKG fields and write Markdown/CSV tables"
    )
    benchmark.add_arguments(benchmark_parser)
    refine_parser = commands.add_parser(
        "refine-tone", help="Refine tone rules on separated development splits"
    )
    refine_tone_lexicon.add_arguments(refine_parser)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build.run(args)
        elif args.command == "benchmark":
            benchmark.run(args)
        else:
            refine_tone_lexicon.run(args, parser=refine_parser)
    except (OSError, ValueError, OptionalDependencyError, zipfile.BadZipFile) as error:
        {"build": build_parser, "benchmark": benchmark_parser, "refine-tone": refine_parser}[
            args.command
        ].error(str(error))
