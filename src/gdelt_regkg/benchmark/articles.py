"""Atomic, optionally compressed article-level benchmark statistics."""

import gzip
import io
import json
from pathlib import Path


class ArticleMetrics:
    """A callable JSONL sink; publish only when all scoring finishes successfully."""

    def __init__(self, path):
        self.path = Path(path) if path is not None else None
        self.partial: Path | None = None
        self.stream: io.TextIOWrapper | None = None
        self.raw: io.BufferedWriter | None = None

    def __enter__(self):
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.partial = self.path.with_name(self.path.name + ".partial")
            raw = self.partial.open("wb")
            binary: io.BufferedIOBase
            if self.path.suffix == ".gz":
                self.raw = raw
                binary = gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0)
            else:
                self.raw = None
                binary = raw
            self.stream = io.TextIOWrapper(binary, encoding="utf-8", newline="\n")
        return self if self.stream is not None else None

    def __call__(self, row):
        if self.stream is None:
            raise RuntimeError("Article metrics sink is not open")
        self.stream.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n")

    def __exit__(self, error_type, *_):
        if self.stream is not None:
            self.stream.close()
            if self.raw is not None:
                self.raw.close()
            if error_type is None:
                assert self.path is not None and self.partial is not None
                self.partial.replace(self.path)
