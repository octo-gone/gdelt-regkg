"""Persistent SQLite caching for English translations."""

from __future__ import annotations

import hashlib
import sqlite3
from collections.abc import Iterable
from typing import Any, Self

from .fields.translation import Translator, normalize_language
from .storage import close_database, open_database
from .types import StrPath


class CachedTranslator:
    """Cache translations by full identity, source language, and input text.

    Create one instance per worker; instances may share a database file.
    Use as a context manager to close the cache automatically.

    Args:
        translator: Translation backend with a nonempty engine identifier.
        path: SQLite database path, or `:memory:` for an in-memory cache.
        timeout: SQLite lock timeout in seconds.

    Raises:
        ValueError: If the engine identifier or timeout is invalid.
        sqlite3.Error: If the cache cannot be opened or initialized.
    """

    def __init__(self, translator: Translator, path: StrPath, *, timeout: float = 60):
        self.translator = translator
        """Wrapped translation backend."""
        self.engine = translator.engine
        """Public citation used by translated metadata."""
        if not isinstance(self.engine, str) or not self.engine.strip():
            raise ValueError("Translator must identify its engine")
        identity = getattr(translator, "cache_identity", None)
        self.cache_identity = self.engine if identity is None else identity
        if not isinstance(self.cache_identity, str) or not self.cache_identity.strip():
            raise ValueError("cache_identity must be a nonempty string")
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
    def translation_profile(self) -> dict[str, Any] | None:
        """Full provenance, when exposed by the wrapped backend."""
        return getattr(self.translator, "translation_profile", None)

    @property
    def connection(self) -> sqlite3.Connection:
        """Return the cache's open SQLite connection.

        Raises:
            RuntimeError: If the cache is closed.
        """
        if self._connection is None:
            raise RuntimeError("Translation cache is closed")
        return self._connection

    def __enter__(self) -> Self:
        _ = self.connection
        return self

    def __exit__(self, *_):
        self.close()

    def close(self) -> None:
        """Roll back pending work and close the cache connection.

        Repeated calls are safe. The wrapped translator remains available.
        """
        connection, self._connection = self._connection, None
        close_database(connection)

    def _key(self, text: str, source: str) -> str:
        return hashlib.sha256(
            ("translation-v2\0" + self.cache_identity + "\0" + source + "\0" + text).encode("utf-8")
        ).hexdigest()

    def translate(self, text: str, source_language: str) -> str:
        """Translate one body into English, reusing cached results.

        Args:
            text: Source body to translate.
            source_language: Supported language code, name, or regional tag.

        Returns:
            The English translation. English input is returned unchanged.

        Raises:
            TypeError: If `text` is not a string.
            ValueError: If the language is invalid, a non-English body is blank,
                or the backend returns invalid output.
            RuntimeError: If the cache is closed.
            sqlite3.Error: If reading or saving cached results fails.
        """
        return self.translate_many([text], source_language)[0]

    def translate_many(self, texts: Iterable[str], source_language: str) -> list[str]:
        """Translate bodies into English, batching unique cache misses.

        Uses the backend's batch method when available. New results are committed
        after validation.

        Args:
            texts: Source bodies to translate.
            source_language: Supported language code, name, or regional tag.

        Returns:
            Translations in input order, preserving duplicates. English input
            is returned unchanged.

        Raises:
            TypeError: If `texts` is not iterable or contains non-string values.
            ValueError: If the language is invalid, a non-English body is blank,
                or the backend returns invalid output.
            RuntimeError: If the cache is closed.
            sqlite3.Error: If reading or saving cached results fails.
        """
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
