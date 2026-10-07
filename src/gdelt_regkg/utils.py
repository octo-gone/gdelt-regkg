"""GKG columns, packaged rules, and explicitly prepared local resources."""

from __future__ import annotations

import gzip
import json
from importlib.resources import files
from pathlib import Path

_EXTERNAL_RESOURCES = {
    *(
        f"lexicons/{kind}.v{version}.json"
        for kind in ("tone", "themes", "gcam")
        for version in (1, 2, 3)
    ),
    "lexicons/gcam.v3.json.gz",
    "lexicons/locations.v1.json.gz",
    "gcam/codebook.v1.json",
}


class ResourceUnavailableError(FileNotFoundError):
    """A required local vocabulary has not been prepared."""


def resource_directory(resources_dir=None):
    """Resolve the supplied root, or local-resources under the working directory."""
    return (
        Path("local-resources" if resources_dir is None else resources_dir).expanduser().resolve()
    )


def packaged_resource_path(*parts):
    """Read schemas, authored rules and build recipes from the distribution."""
    return files("gdelt_regkg").joinpath("resources", *parts)


def resource_path(*parts, resources_dir=None):
    """Resolve generated profiles locally and authored rules in the package.

    Local profiles may override count/name defaults too. External dictionaries
    never fall back to a packaged copy and extraction never accesses a network.
    """
    relative = "/".join(parts)
    if parts and parts[0] in {"lexicons", "gcam"}:
        local = resource_directory(resources_dir).joinpath(*parts)
        if local.is_file():
            return local
        external_profile = (
            parts[0] == "lexicons"
            and parts[-1].endswith((".json", ".json.gz"))
            and not parts[-1].startswith(("counts.", "names."))
        )
        if relative in _EXTERNAL_RESOURCES or external_profile:
            raise ResourceUnavailableError(
                f"Missing local resource {local}. Run gdelt-regkg-build-resources "
                "with the source inputs described in docs/installation.md, or supply "
                "an explicit lexicon/gazetteer. Pass resources_dir= in Python or "
                "--resources-dir in the CLI to select the resource root."
            )
    return packaged_resource_path(*parts)


def read_resource_json(*parts, resources_dir=None):
    resource = resource_path(*parts, resources_dir=resources_dir)
    if parts[-1].endswith(".gz"):
        return json.loads(gzip.decompress(resource.read_bytes()).decode("utf-8"))
    payload = json.loads(resource.read_text(encoding="utf-8"))
    if parts == ("defaults.json",):
        local = resource_directory(resources_dir) / "defaults.json"
        if local.is_file():
            payload.update(json.loads(local.read_text(encoding="utf-8")))
    return payload


# https://data.gdeltproject.org/documentation/GDELT-Global_Knowledge_Graph_Codebook-V2.1.pdf
GKG_COLUMNS = [
    "GKGRECORDID",
    "V2.1DATE",
    "V2SOURCECOLLECTIONIDENTIFIER",
    "V2SOURCECOMMONNAME",
    "V2DOCUMENTIDENTIFIER",
    "V1COUNTS",
    "V2.1COUNTS",
    "V1THEMES",
    "V2ENHANCEDTHEMES",
    "V1LOCATIONS",
    "V2ENHANCEDLOCATIONS",
    "V1PERSONS",
    "V2ENHANCEDPERSONS",
    "V1ORGANIZATIONS",
    "V2ENHANCEDORGANIZATIONS",
    "V1.5TONE",
    "V2.1ENHANCEDDATES",
    "V2GCAM",
    "V2.1SHARINGIMAGE",
    "V2.1RELATEDIMAGES",
    "V2.1SOCIALIMAGEEMBEDS",
    "V2.1SOCIALVIDEOEMBEDS",
    "V2.1QUOTATIONS",
    "V2.1ALLNAMES",
    "V2.1AMOUNTS",
    "V2.1TRANSLATIONINFO",
    "V2EXTRASXML",
]
