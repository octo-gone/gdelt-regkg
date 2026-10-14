"""Explicit SQLite translation caching, independent of language verification."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from typing import Self

from .fields.translation import Translator, normalize_language
from .storage import close_database, open_database
from .types import StrPath


class CachedTranslator:
    """Owned thread-affine cache; closing it does not close the translator.

    Create one instance per worker. Independent instances may share a WAL file.
    Successful translation operations commit; pending work is rolled back on close.
    """

    def __init__(self, translator: Translator, path: StrPath, *, timeout: float = 60):
        self.translator = translator
        self.engine = translator.engine
        if not isinstance(self.engine, str) or not self.engine.strip():
            raise ValueError("Translator must identify its engine")
        self._connection: sqlite3.Connection | None = open_database(path, timeout=timeout)
        try:
            self.connection.execute(
                "CREATE TABLE IF NOT EXISTS translations (key TEXT PRIMARY KEY, body TEXT NOT NULL)"
            )
            self.connection.commit()
        except BaseException:
            self.close()
            raise

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Translation cache is closed")
        return self._connection

    def __enter__(self) -> Self:
        _ = self.connection
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        connection, self._connection = self._connection, None
        close_database(connection)

    def _key(self, text: str, source: str) -> str:
        return hashlib.sha256(
            ("translation-v2\0" + self.engine + "\0" + source + "\0" + text).encode("utf-8")
        ).hexdigest()

    def translate(self, text: str, source_language: str) -> str:
        return self.translate_many([text], source_language)[0]

    def translate_many(self, texts: Iterable[str], source_language: str) -> list[str]:
        source = normalize_language(source_language)
        texts = list(texts)
        if any(not isinstance(text, str) for text in texts):
            raise TypeError("texts must contain strings")
        connection = self.connection
        if source == "eng":
            return texts
        if any(not text.strip() for text in texts):
            raise ValueError("Cannot translate a blank body")
        keys = [self._key(text, source) for text in texts]
        outputs = {}
        missing: dict[str, str] = {}
        for key, text in zip(keys, texts, strict=True):
            cached = connection.execute(
                "SELECT body FROM translations WHERE key = ?", (key,)
            ).fetchone()
            if cached is not None:
                outputs[key] = cached[0]
            else:
                missing.setdefault(key, text)
        if missing:
            bodies = list(missing.values())
            method = getattr(self.translator, "translate_many", None)
            translated = (
                method(bodies, source)
                if callable(method)
                else [self.translator.translate(text, source) for text in bodies]
            )
            if isinstance(translated, (str, bytes)):
                raise ValueError("Translator returned an invalid batch")
            try:
                translated = list(translated)
            except TypeError as error:
                raise ValueError("Translator returned an invalid batch") from error
            if len(translated) != len(bodies) or any(
                not isinstance(text, str) or not text.strip() for text in translated
            ):
                raise ValueError("Translator returned an invalid batch")
            entries = list(zip(missing, translated, strict=True))
            try:
                connection.executemany("INSERT OR REPLACE INTO translations VALUES (?, ?)", entries)
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            outputs.update(entries)
        return [outputs[key] for key in keys]
