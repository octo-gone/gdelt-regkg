"""Disk-backed benchmark inputs and transactional prediction checkpoints."""

import hashlib
import json
import os
import sqlite3
import sys
from collections.abc import MutableMapping, Sequence
from pathlib import Path

from .model import FIELD_NAMES

APPLICATION_ID = int.from_bytes(b"GKGB", "big")
CACHE_SCHEMA_VERSION = 1


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


class StoredRow:
    """A small handle; encoded field contents stay in SQLite until requested."""

    def __init__(self, store, identifier):
        self.store = store
        self.identifier = identifier

    def get(self, name):
        if name not in FIELD_NAMES:
            return None
        return self.store.db.execute(
            f'SELECT "{name}" FROM rows WHERE id=?', (self.identifier,)
        ).fetchone()[0]

    @property
    def values(self):
        row = self.store.db.execute(
            "SELECT present," + ",".join(f'"{n}"' for n in FIELD_NAMES) + " FROM rows WHERE id=?",
            (self.identifier,),
        ).fetchone()
        present = set(json.loads(row[0]))
        return {key: value for key, value in zip(FIELD_NAMES, row[1:]) if key in present}

    @property
    def origin(self):
        return self.store.db.execute(
            "SELECT origin FROM rows WHERE id=?", (self.identifier,)
        ).fetchone()[0]


class StoredRows(Sequence):
    def __init__(self, store, scope):
        self.store, self.scope = store, scope
        self.identifiers = []

    def append(self, row):
        self.identifiers.append(self.store.put(row, scope=self.scope).identifier)
        if len(self.identifiers) % 1000 == 0:
            self.store.db.commit()

    def __len__(self):
        return len(self.identifiers)

    def __getitem__(self, index):
        if isinstance(index, slice):
            return [StoredRow(self.store, i) for i in self.identifiers[index]]
        return StoredRow(self.store, self.identifiers[index])


class StoredCorpus(MutableMapping):
    def __init__(self, store, table="bodies"):
        if table not in {"bodies", "ner"}:
            raise ValueError("Unknown benchmark mapping")
        self.store = store
        self.table = table
        self.written = 0

    def __getitem__(self, key):
        found = self.store.db.execute(
            f"SELECT payload FROM {self.table} WHERE identity=?", (json.dumps(key),)
        ).fetchone()
        if found is None:
            raise KeyError(key)
        return json.loads(found[0])

    def __setitem__(self, key, value):
        self.store.db.execute(
            f"INSERT OR REPLACE INTO {self.table} VALUES (?,?)",
            (json.dumps(key), json.dumps(value, ensure_ascii=False)),
        )
        self.written += 1
        if self.written % 1000 == 0:
            self.store.db.commit()

    def __delitem__(self, key):
        if (
            self.store.db.execute(
                f"DELETE FROM {self.table} WHERE identity=?", (json.dumps(key),)
            ).rowcount
            == 0
        ):
            raise KeyError(key)

    def __iter__(self):
        for (key,) in self.store.db.execute(f"SELECT identity FROM {self.table}"):
            yield tuple(json.loads(key))

    def __len__(self):
        return self.store.db.execute(f"SELECT COUNT(*) FROM {self.table}").fetchone()[0]


class BenchmarkStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = None
        self._db = None

    @property
    def db(self) -> sqlite3.Connection:
        if self._db is None:
            raise RuntimeError("Benchmark store is not open")
        return self._db

    def __enter__(self):
        # Hold an OS lock across batch commits, so two runs cannot reset each
        # other's staged inputs. The OS releases it even after a killed process.
        self.lock = self.path.with_suffix(self.path.suffix + ".lock").open("a+b")
        if os.fstat(self.lock.fileno()).st_size == 0:
            self.lock.write(b"0")
            self.lock.flush()
        self.lock.seek(0)
        try:
            if sys.platform == "win32":
                import msvcrt

                msvcrt.locking(self.lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl  # pylint: disable=import-error

                fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            self.lock.close()
            raise ValueError(f"Benchmark cache is in use: {self.path}") from error
        try:
            self._db = sqlite3.connect(self.path)
            application = self.db.execute("PRAGMA application_id").fetchone()[0]
            tables = self.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            if tables and application != APPLICATION_ID:
                raise ValueError(f"Not a benchmark cache database: {self.path}")
            if (
                application
                and self.db.execute("PRAGMA user_version").fetchone()[0] != CACHE_SCHEMA_VERSION
            ):
                raise ValueError("Unsupported benchmark cache version; choose a new --cache path")
            self.db.execute(f"PRAGMA application_id={APPLICATION_ID}")
            self.db.execute(f"PRAGMA user_version={CACHE_SCHEMA_VERSION}")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
            self.db.execute("PRAGMA cache_size=-16384")
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS bodies (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            self.db.execute(
                "CREATE TABLE IF NOT EXISTS ner (identity TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            columns = ",".join(f'"{name}" TEXT' for name in FIELD_NAMES)
            self.db.execute(
                f"CREATE TABLE IF NOT EXISTS rows (id INTEGER PRIMARY KEY, scope TEXT, signature TEXT UNIQUE, origin TEXT, present TEXT, {columns})"
            )
            self.db.execute("DELETE FROM rows WHERE scope != 'cache'")
            self.db.execute("DELETE FROM bodies")
            self.db.execute("DELETE FROM ner")
            self.db.commit()
        except BaseException:
            self.__exit__(None, None, None)
            raise
        return self

    def __exit__(self, *_):
        if self._db is not None:
            self._db.close()
            self._db = None
        if self.lock is not None:
            self.lock.close()

    def put(self, row, *, scope="cache", signature=None):
        values = row.values
        columns = ["scope", "signature", "origin", "present", *FIELD_NAMES]
        sql = (
            "INSERT OR IGNORE INTO rows ("
            + ",".join(f'"{n}"' for n in columns)
            + ") VALUES ("
            + ",".join("?" for _ in columns)
            + ")"
        )
        cursor = self.db.execute(
            sql,
            (
                scope,
                signature,
                row.origin,
                json.dumps(list(values)),
                *(values.get(n) for n in FIELD_NAMES),
            ),
        )
        return StoredRow(self, cursor.lastrowid) if cursor.rowcount else self.cached(signature)

    def cached(self, signature):
        found = self.db.execute("SELECT id FROM rows WHERE signature=?", (signature,)).fetchone()
        return None if found is None else StoredRow(self, found[0])

    def rows(self, scope):
        return StoredRows(self, scope)

    def corpus(self, table="bodies"):
        return StoredCorpus(self, table)

    def commit(self):
        self.db.commit()
