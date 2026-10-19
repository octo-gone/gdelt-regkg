"""Access local and packaged resources for GKG extraction."""

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
    """Required local resource is missing.

    Prepare the resource in the selected resource directory or supply an explicit
    lexicon or gazetteer to the extraction function. The exception message
    identifies the missing path and provides setup guidance.
    """


def resource_directory(resources_dir: StrPath | None = None) -> Path:
    """Resolve the directory used for locally prepared resources.

    Args:
        resources_dir: Resource directory to use. Defaults to `local-resources`
            under the current working directory. A leading `~` is expanded to
            the user's home directory.

    Returns:
        The absolute resource directory path. Relative paths are resolved against
        the current working directory.
    """
    return (
        Path("local-resources" if resources_dir is None else resources_dir).expanduser().resolve()
    )


def packaged_resource_path(*parts: str) -> ResourcePath:
    """Return a reference to a resource shipped with the package.

    Args:
        *parts: Path components relative to the package's `resources` directory.
            Omit components to refer to that directory itself.

    Returns:
        A resource reference supporting file. The referenced path may be a file,
        a directory, or a path that does not exist.
    """
    return cast(ResourcePath, files("gdelt_regkg").joinpath("resources", *parts))


def _missing(path: Path) -> ResourceUnavailableError:
    return ResourceUnavailableError(
        f"Missing local resource {path}. Run gdelt-regkg-cli build all with the source inputs "
        "described in docs/installation.md, or supply an explicit lexicon/gazetteer. "
        "Pass resources_dir= in Python or --resources-dir in the CLI to select the resource root."
    )


@dataclass(frozen=True)
class ResourceStore:
    """Resolve and read resources using a selected local resource directory.

    Prepared lexicons and GCAM data are loaded from the local directory. Packaged
    count and name rules provide fallbacks, and other resource paths refer to
    packaged files. Local `defaults.json` entries override packaged profile names.

    Args:
        resources_dir: Root directory for locally prepared resources. Defaults to
            `local-resources` under the current working directory.
    """

    resources_dir: StrPath | None = None
    """Root directory used to look up prepared resources and local defaults."""

    def path(self, *parts: str) -> ResourcePath:
        """Select a local or packaged resource by its relative path.

        Paths under `lexicons` and `gcam` use local files when available. Missing
        lexicon files whose names start with `counts.` or `names.` fall back to
        packaged resources. Other paths refer directly to packaged resources.

        Args:
            *parts: Path components relative to the resource root. Omit components
                to refer to the packaged resource directory.

        Returns:
            A local file path or packaged resource reference. Packaged references
            are returned before their existence is checked.

        Raises:
            ResourceUnavailableError: If a requested local lexicon or GCAM file
                is missing and has no packaged fallback.
        """
        if parts and parts[0] in {"lexicons", "gcam"}:
            local = resource_directory(self.resources_dir).joinpath(*parts)
            if local.is_file():
                return local
            authored = parts[0] == "lexicons" and parts[-1].startswith(("counts.", "names."))
            if not authored:
                raise _missing(local)
        return packaged_resource_path(*parts)

    def read_json(self, *parts: str) -> dict[str, Any]:
        """Read a UTF-8 JSON resource, decompressing files ending in `.gz`.

        Reading `defaults.json` merges the packaged mapping with entries from
        the local resource directory. Local entries take precedence.

        Args:
            *parts: Path components identifying a JSON file relative to the
                resource root.

        Returns:
            The decoded JSON data. For `defaults.json`, returns the merged
            field-to-filename mapping.

        Raises:
            ResourceUnavailableError: If a required local resource is missing.
            OSError: If the selected file cannot be read or its gzip header is
                invalid.
            UnicodeDecodeError: If resource data or local defaults are not UTF-8.
            json.JSONDecodeError: If resource data or local defaults are invalid
                JSON.
            ValueError: If packaged or local `defaults.json` data is not a JSON
                object.
        """
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
        """Locate the default extraction profile for a field.

        The filename comes from the merged `defaults.json` mapping. Local files
        under `lexicons` take precedence. The `counts` and `ner` profiles can
        fall back to packaged files when those files exist.

        Args:
            kind: Profile key in `defaults.json`, such as `tone`, `themes`,
                `counts`, `ner`, `locations`, or `gcam`.

        Returns:
            A reference to an existing local or packaged profile file.

        Raises:
            KeyError: If `kind` is absent from the merged defaults.
            ValueError: If the selected filename is empty, is not a string, or
                contains a slash, backslash, or colon; or defaults data is not a
                JSON object.
            ResourceUnavailableError: If the profile is missing locally and no
                packaged fallback exists.
            OSError: If a defaults file cannot be read.
            UnicodeDecodeError: If a defaults file is not valid UTF-8.
            json.JSONDecodeError: If a defaults file contains invalid JSON.
        """
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
    """Select a resource using the local directory and packaged fallbacks.

    Uses the lookup rules of `ResourceStore.path`. Prepared lexicons and GCAM
    files are selected locally, with packaged fallbacks for count and name rules.
    Other resource paths refer to packaged files.

    Args:
        *parts: Path components relative to the resource root. Omit components to
            refer to the packaged resource directory.
        resources_dir: Root directory for locally prepared resources. Defaults to
            `local-resources` under the current working directory.

    Returns:
        A local file path or packaged resource reference. Packaged references
        are returned before their existence is checked.

    Raises:
        ResourceUnavailableError: If a requested local lexicon or GCAM file is
            missing and has no packaged fallback.
    """
    return ResourceStore(resources_dir).path(*parts)


def read_resource_json(*parts: str, resources_dir: StrPath | None = None) -> dict[str, Any]:
    """Load a JSON resource using the selected resource directory.

    Uses `ResourceStore.read_json` to select the resource, decode UTF-8 JSON,
    decompress files ending in `.gz`, and merge local `defaults.json` overrides.

    Args:
        *parts: Path components identifying a JSON file relative to the resource
            root.
        resources_dir: Root directory for locally prepared resources. Defaults to
            `local-resources` under the current working directory.

    Returns:
        The decoded JSON data. For `defaults.json`, returns the packaged
        field-to-filename mapping updated with local entries.

    Raises:
        ResourceUnavailableError: If a required local resource is missing.
        OSError: If the selected file cannot be read or its gzip header is invalid.
        UnicodeDecodeError: If resource data or local defaults are not UTF-8.
        json.JSONDecodeError: If resource data or local defaults are invalid JSON.
        ValueError: If packaged or local `defaults.json` data is not a JSON object.
    """
    return ResourceStore(resources_dir).read_json(*parts)
