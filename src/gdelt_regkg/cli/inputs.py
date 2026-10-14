"""Resolve build requests into selected targets and local source paths."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any

from gdelt_regkg.utils import read_resource_json

from .gcam import COMPONENT_SOURCES, GCAMOptions
from .progress import Progress, ignore_progress
from .recipes import label_filename, select_recipes, validate_suffix
from .sources import download_source, verify_source

TARGET_SOURCES = {
    "tone": ("general-inquirer",),
    "themes": ("crisislex",),
    "counts": (),
    "ner": (),
    "locations": (),
    "gcam": (),
}
DIRECTORY_SOURCES = {
    "wordnet-31",
    "wordnet-20",
    "wordnet-16",
    "wordnet-annotations",
    "wordnet-affect",
    "wordnet-domains",
    "roget",
    "lexicoder",
}
SOURCE_RECIPES = {"wordnet-affect": "wordnet-annotations", "wordnet-domains": "wordnet-annotations"}
SOURCE_NAMES = tuple(
    dict.fromkeys(
        (
            "wordnet-annotations",
            *(source for sources in TARGET_SOURCES.values() for source in sources),
            *(source for sources in COMPONENT_SOURCES.values() for source in sources),
        )
    )
)


@dataclass(frozen=True)
class BuildInputs:
    output: Path
    targets: tuple[str, ...]
    sources: Mapping[str, Path]
    gazetteer_archives: tuple[Path, ...]
    authored_themes_only: bool
    recipes: Mapping[str, str]
    gcam: GCAMOptions = field(default_factory=GCAMOptions)
    gazetteer_name: str = "gkg-reference-gazetteer-v1"
    gazetteer_filename: str = "locations.v1.json.gz"
    gcam_filename: str | None = None
    suffix: str | None = None

    def filename(self, filename: str) -> str:
        return label_filename(filename, self.suffix)


def required_sources(
    targets: Iterable[str], *, authored_themes_only: bool = False, gcam: GCAMOptions | None = None
) -> tuple[str, ...]:
    targets = tuple(targets)
    if not targets:
        raise ValueError("Select at least one build target")
    if unknown := (set(targets) - TARGET_SOURCES.keys()):
        raise ValueError(f"Unknown build targets: {sorted(unknown)}")
    return tuple(
        dict.fromkeys(
            (
                source
                for target in targets
                for source in (
                    (gcam or GCAMOptions()).required_sources()
                    if target == "gcam"
                    else TARGET_SOURCES[target]
                )
                if not (authored_themes_only and source == "crisislex")
            )
        )
    )


def parse_sources(values: Iterable[str]) -> dict[str, Path]:
    """Parse --source NAME=PATH without treating paths as shell expressions."""
    known = set(SOURCE_NAMES)
    sources = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not path or name not in known:
            raise ValueError(
                f"Expected --source NAME=PATH with NAME in {', '.join(sorted(known))}; got {value!r}"
            )
        if name in sources:
            raise ValueError(f"Source supplied more than once: {name}")
        sources[name] = Path(path).expanduser()
    return sources


@dataclass(frozen=True)
class BuildOptions:
    targets: tuple[str, ...]
    sources: Mapping[str, str | Path] | None = None
    sources_dir: str | Path | None = None
    download_sources: bool = False
    gazetteer_archives: tuple[str | Path, ...] | None = None
    authored_themes_only: bool = False
    gcam: GCAMOptions | None = None
    gazetteer_name: str = "gkg-reference-gazetteer-v1"
    gazetteer_filename: str | None = None
    gcam_filename: str | None = None
    use: str = "best"
    suffix: str | None = None
    recipe: dict | None = None

    def __post_init__(self):
        object.__setattr__(self, "targets", tuple(self.targets))
        if self.sources is not None:
            object.__setattr__(self, "sources", MappingProxyType(dict(self.sources)))
        if self.gazetteer_archives is not None:
            object.__setattr__(self, "gazetteer_archives", tuple(self.gazetteer_archives))


class _InputResolver:
    recipe: Any
    gcam: Any
    selected: Any
    required: Any
    directory: Any
    resolved: Any
    missing: list[str]
    archives: list[Path]

    def __init__(self, output, options, progress):
        self.output = output
        self.progress = progress
        self.targets = options.targets
        self.sources = options.sources
        self.sources_dir = options.sources_dir
        self.download_sources = options.download_sources
        self.gazetteer_archives = options.gazetteer_archives
        self.authored_themes_only = options.authored_themes_only
        self.gcam = options.gcam
        self.gazetteer_name = options.gazetteer_name
        self.gazetteer_filename = options.gazetteer_filename
        self.gcam_filename = options.gcam_filename
        self.use = options.use
        self.suffix = options.suffix
        self.recipe = options.recipe

    def _select(self):
        self.targets = tuple(dict.fromkeys(self.targets))
        if self.targets == ("all",):
            self.targets = tuple(TARGET_SOURCES)
        self.selected = select_recipes(self.targets, self.use)
        validate_suffix(self.suffix)
        if self.suffix is not None and (
            self.gcam_filename is not None or self.gazetteer_filename is not None
        ):
            raise ValueError("Choose --suffix or a complete profile filename")
        if self.gazetteer_filename is None:
            self.gazetteer_filename = "locations.v1.json.gz"
        if self.authored_themes_only:
            if "themes" in self.targets and self.use not in ("best", "authored"):
                raise ValueError(
                    "--authored-themes-only cannot be combined with a versioned --use recipe"
                )
            if "themes" in self.selected:
                self.selected["themes"] = "authored"
        self.authored_themes_only = self.authored_themes_only or self.use == "authored"
        self.gcam = GCAMOptions() if self.gcam is None else self.gcam
        if "gcam" in self.targets and self.use != "best":
            if self.gcam.profile is not None or self.gcam.baseline is not None:
                raise ValueError("Choose --use or --gcam-baseline")
            self.gcam = GCAMOptions(
                profile=self.selected["gcam"],
                additions=self.gcam.additions,
                affect_propagate_hierarchy=self.gcam.affect_propagate_hierarchy,
                affect_nouns_only=self.gcam.affect_nouns_only,
            )
        self.required = required_sources(
            self.targets, authored_themes_only=self.authored_themes_only, gcam=self.gcam
        )
        self.sources = dict(self.sources or {})
        if "wordnet-annotations" in self.sources:
            combined = self.sources.pop("wordnet-annotations")
            used = False
            for name in ("wordnet-affect", "wordnet-domains"):
                if name in self.required:
                    self.sources.setdefault(name, combined)
                    used = True
            if not used:
                raise ValueError("wordnet-annotations is not used by the selected targets")
        if unused := (self.sources.keys() - set(self.required)):
            raise ValueError(f"Sources not used by the selected targets: {sorted(unused)}")

    def _validate_output(self):
        if self.download_sources and self.sources_dir is None:
            raise ValueError("--download-sources requires --sources-dir")
        if "gcam" not in self.targets and (
            self.gcam != GCAMOptions() or self.gcam_filename is not None
        ):
            raise ValueError("GCAM options require the gcam target")
        if "locations" not in self.targets and (
            self.gazetteer_name != "gkg-reference-gazetteer-v1"
            or self.gazetteer_filename != "locations.v1.json.gz"
        ):
            raise ValueError("Gazetteer options require the locations target")
        for filename in (
            self.gazetteer_filename,
            self.gcam.filename if self.gcam_filename is None else self.gcam_filename,
        ):
            if (
                not filename
                or Path(filename).name != filename
                or any((c in filename for c in "/\\:"))
                or (not filename.endswith((".json", ".json.gz")))
            ):
                raise ValueError("Profile filenames must be a basename ending in .json or .json.gz")
        if not self.gazetteer_name.strip():
            raise ValueError("Gazetteer name must not be empty")
        if self.gcam.baseline is not None and (not self.gcam.baseline.is_file()):
            raise ValueError(f"Missing GCAM baseline: {self.gcam.baseline}")

    def _sources(self):
        self.recipe = read_resource_json("recipes.json") if self.recipe is None else self.recipe
        self.directory = None if self.sources_dir is None else Path(self.sources_dir).expanduser()
        self.progress(
            "[inputs] Resolving "
            + ", ".join((f"{target} ({name})" for target, name in self.selected.items()))
        )
        self.resolved = {}
        self.missing = []
        for name in self.required:
            if name in self.sources:
                path = Path(self.sources[name]).expanduser()
                if not path.is_file() and (not (name in DIRECTORY_SOURCES and path.is_dir())):
                    self.missing.append(f"{name} ({path})")
                    continue
                self.progress(f"[inputs] Using provided {name}: {path}")
            elif self.directory is not None:
                entry = self.recipe["sources"][SOURCE_RECIPES.get(name, name)]
                path = self.directory / entry["filename"]
                if path.is_file():
                    self.progress(f"[inputs] Checking {name}: {path}")
                if self.download_sources:
                    download_source(path, entry, progress=self.progress)
                if not path.is_file():
                    self.missing.append(f"{name} ({path})")
                    continue
                verify_source(path, entry)
            else:
                self.missing.append(name)
                continue
            self.resolved[name] = path

    def _archives(self):
        self.archives = []
        if "locations" in self.targets:
            if self.gazetteer_archives is not None:
                self.archives = [Path(path).expanduser() for path in self.gazetteer_archives]
                self.missing.extend(
                    (f"gazetteer archive ({path})" for path in self.archives if not path.is_file())
                )
                for path in self.archives:
                    if path.is_file():
                        self.progress(f"[inputs] Using provided gazetteer archive: {path}")
            elif self.directory is not None:
                for entry in self.recipe["gazetteer_sources"]:
                    path = self.directory / entry["url"].rsplit("/", 1)[-1]
                    if path.is_file():
                        self.progress(f"[inputs] Checking gazetteer archive: {path}")
                    if self.download_sources:
                        download_source(path, entry, progress=self.progress)
                    if not path.is_file():
                        self.missing.append(f"gazetteer archive ({path})")
                        continue
                    verify_source(path, entry)
                    self.archives.append(path)
            if not self.archives:
                self.missing.append("gazetteer archives (--gazetteer-archives or --sources-dir)")
        elif self.gazetteer_archives is not None:
            raise ValueError("--gazetteer-archives requires the locations target")

    def resolve(self):
        self._select()
        self._validate_output()
        self._sources()
        self._archives()
        if self.missing:
            raise ValueError(
                "Missing build inputs: "
                + ", ".join(self.missing)
                + ". Supply --source NAME=PATH or --sources-dir."
            )
        self.progress(
            f"[inputs] Ready: {len(self.resolved)} sources, {len(self.archives)} gazetteer archives"
        )
        return BuildInputs(
            output=Path(self.output).expanduser(),
            targets=self.targets,
            sources=MappingProxyType(self.resolved),
            gazetteer_archives=tuple(self.archives),
            authored_themes_only=self.authored_themes_only,
            recipes=MappingProxyType(self.selected),
            gcam=self.gcam,
            gazetteer_name=self.gazetteer_name,
            gazetteer_filename=self.gazetteer_filename,
            gcam_filename=self.gcam_filename,
            suffix=self.suffix,
        )


def resolve_inputs(
    output: str | Path, options: BuildOptions, *, progress: Progress = ignore_progress
) -> BuildInputs:
    return _InputResolver(output, options, progress).resolve()
