"""Command dispatch for gdelt-regkg-cli."""

from __future__ import annotations

import argparse
import zipfile
from collections.abc import Sequence

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
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            build.run(args)
        else:
            benchmark.run(args)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        (build_parser if args.command == "build" else benchmark_parser).error(str(error))
