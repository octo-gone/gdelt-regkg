"""Progress callbacks for builds, with terminal output owned by the CLI."""

import sys
from collections.abc import Callable

Progress = Callable[[str], None]


def ignore_progress(_message: str) -> None:
    """Keep programmatic builds silent unless a reporter is supplied."""


def print_progress(message: str) -> None:
    """Flush each update so redirected output also shows ongoing work."""
    print(message, file=sys.stderr, flush=True)
