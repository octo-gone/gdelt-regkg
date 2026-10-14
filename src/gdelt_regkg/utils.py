"""Offline resource selection, authored fallback and packaged schemas."""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, Protocol, cast

from .record import GKG_COLUMNS
from .types import StrPath

__all__ = [
    "GKG_COLUMNS",
    "ResourceUnavailableError",
    "ResourceStore",
    "resource_directory",
    "packaged_resource_path",
    "resource_path",
    "read_resource_json",
]


class ResourcePath(Traversable, Protocol):
    def __hash__(self) -> int: ...


class ResourceUnavailableError(FileNotFoundError):
    """A required local vocabulary has not been prepared."""


def resource_directory(resources_dir: StrPath | None = None) -> Path:
    return (
        Path("local-resources" if resources_dir is None else resources_dir).expanduser().resolve()
    )


def packaged_resource_path(*parts: str) -> ResourcePath:
    return cast(ResourcePath, files("gdelt_regkg").joinpath("resources", *parts))


def _missing(path: Path) -> ResourceUnavailableError:
    return ResourceUnavailableError(
        f"Missing local resource {path}. Run gdelt-regkg-cli build all with the source inputs "
        "described in docs/installation.md, or supply an explicit lexicon/gazetteer. "
        "Pass resources_dir= in Python or --resources-dir in the CLI to select the resource root."
    )


@dataclass(frozen=True)
class ResourceStore:
    resources_dir: StrPath | None = None

    def path(self, *parts: str) -> ResourcePath:
        if parts and parts[0] in {"lexicons", "gcam"}:
            local = resource_directory(self.resources_dir).joinpath(*parts)
            if local.is_file():
                return local
            authored = parts[0] == "lexicons" and parts[-1].startswith(("counts.", "names."))
            if not authored:
                raise _missing(local)
        return packaged_resource_path(*parts)

    def read_json(self, *parts: str) -> dict[str, Any]:
        resource = self.path(*parts)
        raw = resource.read_bytes()
        if parts[-1].endswith(".gz"):
            raw = gzip.decompress(raw)
        payload = json.loads(raw.decode("utf-8"))
        if parts == ("defaults.json",):
            local = resource_directory(self.resources_dir) / "defaults.json"
            override = json.loads(local.read_text(encoding="utf-8")) if local.is_file() else {}
            if not isinstance(payload, dict) or not isinstance(override, dict):
                raise ValueError("defaults.json must be a field-to-filename object")
            payload.update(override)
        return payload

    def profile(self, kind: str) -> ResourcePath:
        filename = self.read_json("defaults.json")[kind]
        if not isinstance(filename, str) or not filename or any(c in filename for c in "/\\:"):
            raise ValueError(f"Invalid {kind} profile filename")
        local = resource_directory(self.resources_dir) / "lexicons" / filename
        if local.is_file():
            return local
        if kind in {"counts", "ner"}:
            authored = packaged_resource_path("lexicons", filename)
            if authored.is_file():
                return authored
        raise _missing(local)


def resource_path(*parts: str, resources_dir: StrPath | None = None) -> ResourcePath:
    return ResourceStore(resources_dir).path(*parts)


def read_resource_json(*parts: str, resources_dir: StrPath | None = None) -> dict[str, Any]:
    return ResourceStore(resources_dir).read_json(*parts)
