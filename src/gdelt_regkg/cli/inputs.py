"""Resolve build requests into selected targets and local source paths."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

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
    "locations": (),  # Keep the existing gazetteer_sources recipe for now.
    "gcam": (),  # Dependencies follow the selected GCAM components.
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
    if unknown := set(targets) - TARGET_SOURCES.keys():
        raise ValueError(f"Unknown build targets: {sorted(unknown)}")
    return tuple(
        dict.fromkeys(
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


def resolve_inputs(
    output: str | Path,
    *,
    targets: Iterable[str],
    sources: Mapping[str, str | Path] | None = None,
    sources_dir: str | Path | None = None,
    download_sources: bool = False,
    gazetteer_archives: Iterable[str | Path] | None = None,
    authored_themes_only: bool = False,
    gcam: GCAMOptions | None = None,
    gazetteer_name: str = "gkg-reference-gazetteer-v1",
    gazetteer_filename: str | None = None,
    gcam_filename: str | None = None,
    use: str = "best",
    suffix: str | None = None,
    recipe: dict | None = None,
    progress: Progress = ignore_progress,
) -> BuildInputs:
    """Explicit sources win over checksum-verified recipe files in sources_dir.

    Resolution does not build profiles or modify their output directory.
    Downloads occur only when requested. Explicit paths may be custom inputs;
    each converter remains responsible for validating its supported format.
    """
    targets = tuple(dict.fromkeys(targets))
    if targets == ("all",):
        targets = tuple(TARGET_SOURCES)
    selected = select_recipes(targets, use)
    validate_suffix(suffix)
    if suffix is not None and (gcam_filename is not None or gazetteer_filename is not None):
        raise ValueError("Choose --suffix or a complete profile filename")
    if gazetteer_filename is None:
        gazetteer_filename = "locations.v1.json.gz"
    if authored_themes_only:
        if "themes" in targets and use not in ("best", "authored"):
            raise ValueError(
                "--authored-themes-only cannot be combined with a versioned --use recipe"
            )
        if "themes" in selected:
            selected["themes"] = "authored"
    authored_themes_only = authored_themes_only or use == "authored"
    gcam = GCAMOptions() if gcam is None else gcam
    if "gcam" in targets and use != "best":
        if gcam.profile is not None or gcam.baseline is not None:
            raise ValueError("Choose --use or --gcam-baseline")
        gcam = GCAMOptions(
            profile=selected["gcam"],
            additions=gcam.additions,
            affect_propagate_hierarchy=gcam.affect_propagate_hierarchy,
            affect_nouns_only=gcam.affect_nouns_only,
        )
    required = required_sources(targets, authored_themes_only=authored_themes_only, gcam=gcam)
    sources = dict(sources or {})
    if "wordnet-annotations" in sources:
        combined = sources.pop("wordnet-annotations")
        used = False
        for name in ("wordnet-affect", "wordnet-domains"):
            if name in required:
                sources.setdefault(name, combined)
                used = True
        if not used:
            raise ValueError("wordnet-annotations is not used by the selected targets")
    if unused := sources.keys() - set(required):
        raise ValueError(f"Sources not used by the selected targets: {sorted(unused)}")
    if download_sources and sources_dir is None:
        raise ValueError("--download-sources requires --sources-dir")
    if "gcam" not in targets and (gcam != GCAMOptions() or gcam_filename is not None):
        raise ValueError("GCAM options require the gcam target")
    if "locations" not in targets and (
        gazetteer_name != "gkg-reference-gazetteer-v1"
        or gazetteer_filename != "locations.v1.json.gz"
    ):
        raise ValueError("Gazetteer options require the locations target")
    for filename in (gazetteer_filename, gcam.filename if gcam_filename is None else gcam_filename):
        if (
            not filename
            or Path(filename).name != filename
            or any(c in filename for c in "/\\:")
            or not filename.endswith((".json", ".json.gz"))
        ):
            raise ValueError("Profile filenames must be a basename ending in .json or .json.gz")
    if not gazetteer_name.strip():
        raise ValueError("Gazetteer name must not be empty")
    if gcam.baseline is not None and not gcam.baseline.is_file():
        raise ValueError(f"Missing GCAM baseline: {gcam.baseline}")
    recipe = read_resource_json("recipes.json") if recipe is None else recipe
    directory = None if sources_dir is None else Path(sources_dir).expanduser()
    progress(
        "[inputs] Resolving " + ", ".join(f"{target} ({name})" for target, name in selected.items())
    )
    resolved = {}
    missing = []
    for name in required:
        if name in sources:
            path = Path(sources[name]).expanduser()
            if not path.is_file() and not (name in DIRECTORY_SOURCES and path.is_dir()):
                missing.append(f"{name} ({path})")
                continue
            progress(f"[inputs] Using provided {name}: {path}")
        elif directory is not None:
            entry = recipe["sources"][SOURCE_RECIPES.get(name, name)]
            path = directory / entry["filename"]
            if path.is_file():
                progress(f"[inputs] Checking {name}: {path}")
            if download_sources:
                download_source(path, entry, progress=progress)
            if not path.is_file():
                missing.append(f"{name} ({path})")
                continue
            verify_source(path, entry)
        else:
            missing.append(name)
            continue
        resolved[name] = path
    archives = []
    if "locations" in targets:
        if gazetteer_archives is not None:
            archives = [Path(path).expanduser() for path in gazetteer_archives]
            missing.extend(f"gazetteer archive ({path})" for path in archives if not path.is_file())
            for path in archives:
                if path.is_file():
                    progress(f"[inputs] Using provided gazetteer archive: {path}")
        elif directory is not None:
            for entry in recipe["gazetteer_sources"]:
                path = directory / entry["url"].rsplit("/", 1)[-1]
                if path.is_file():
                    progress(f"[inputs] Checking gazetteer archive: {path}")
                if download_sources:
                    download_source(path, entry, progress=progress)
                if not path.is_file():
                    missing.append(f"gazetteer archive ({path})")
                    continue
                verify_source(path, entry)
                archives.append(path)
        if not archives:
            missing.append("gazetteer archives (--gazetteer-archives or --sources-dir)")
    elif gazetteer_archives is not None:
        raise ValueError("--gazetteer-archives requires the locations target")
    if missing:
        raise ValueError(
            "Missing build inputs: "
            + ", ".join(missing)
            + ". Supply --source NAME=PATH or --sources-dir."
        )
    progress(f"[inputs] Ready: {len(resolved)} sources, {len(archives)} gazetteer archives")
    return BuildInputs(
        output=Path(output).expanduser(),
        targets=targets,
        sources=MappingProxyType(resolved),
        gazetteer_archives=tuple(archives),
        authored_themes_only=authored_themes_only,
        recipes=MappingProxyType(selected),
        gcam=gcam,
        gazetteer_name=gazetteer_name,
        gazetteer_filename=gazetteer_filename,
        gcam_filename=gcam_filename,
        suffix=suffix,
    )
