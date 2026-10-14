"""Connection lifecycle shared by persistent translation and benchmark tools."""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable

from .types import StrPath


def open_database(
    path: StrPath, *, timeout: float, validate: Callable[[sqlite3.Connection], None] | None = None
) -> sqlite3.Connection:
    """Open an owned, thread-affine connection; file databases use WAL.

    Every thread/process must create its own owner and connection. The caller
    closes the connection and explicitly commits successful transactions.
    """
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not math.isfinite(timeout)
        or timeout < 0
    ):
        raise ValueError("SQLite timeout must be a finite nonnegative number")
    connection = sqlite3.connect(path, timeout=timeout)
    try:
        if validate is not None:
            validate(connection)
        mode = connection.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        if mode not in {"wal", "memory"}:
            raise sqlite3.OperationalError(f"SQLite WAL unavailable: {mode}")
    except BaseException:
        connection.close()
        raise
    return connection


def close_database(connection: sqlite3.Connection | None) -> None:
    """Discard uncommitted work and always close an owned connection."""
    if connection is not None:
        try:
            connection.rollback()
        finally:
            connection.close()
