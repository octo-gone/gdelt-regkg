"""Command dispatch for gdelt-regkg-cli."""

from __future__ import annotations

import argparse
import zipfile
from collections.abc import Sequence

from .build import add_arguments, run


def main(argv: Sequence[str] | None = None):
    parser = argparse.ArgumentParser(description="GDELT reconstruction tools")
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build", help="Build local extraction resources")
    add_arguments(build)
    args = parser.parse_args(argv)
    try:
        run(args)
    except (OSError, ValueError, zipfile.BadZipFile) as error:
        build.error(str(error))
