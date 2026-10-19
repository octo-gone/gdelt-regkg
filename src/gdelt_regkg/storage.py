"""SQLite connection lifecycle for persistent caches and benchmarks."""

from __future__ import annotations

import math
import sqlite3
from collections.abc import Callable

from .types import StrPath


def open_database(
    path: StrPath, *, timeout: float, validate: Callable[[sqlite3.Connection], None] | None = None
) -> sqlite3.Connection:
    """Open a SQLite connection with WAL enabled for file databases.

    Use the connection in its creating thread and commit successful writes
    explicitly. Validation failures close the connection and propagate to callers.

    Args:
        path: Database path, or `:memory:` for an in-memory database.
        timeout: Finite, nonnegative lock timeout in seconds.
        validate: Optional connection check run before journal setup.

    Returns:
        An open connection owned by the caller.

    Raises:
        ValueError: If `timeout` is invalid.
        sqlite3.Error: If opening the database or configuring its journal fails.
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
    """Roll back pending work and close a SQLite connection.

    The connection is closed even if rollback fails.

    Args:
        connection: Connection to close. Passing `None` has no effect.

    Raises:
        sqlite3.Error: If rollback or closure fails.
    """
    if connection is not None:
        try:
            connection.rollback()
        finally:
            connection.close()
