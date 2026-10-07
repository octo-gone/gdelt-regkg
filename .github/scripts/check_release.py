"""Validate release metadata and archives without installing the project."""

from __future__ import annotations

import argparse
import re
import tarfile
import tomllib
import zipfile
from email.parser import BytesParser
from pathlib import Path, PurePosixPath


def check_metadata(project, tag=""):
    """Reject mismatched tags and dependencies that PyPI cannot accept."""
    if project["name"] != "gdelt-regkg":
        raise ValueError("Unexpected package name")
    if tag and tag != f"v{project['version']}":
        raise ValueError(f"Tag {tag!r} must match v{project['version']}")
    requirements = list(project.get("dependencies", ()))
    for extra in project.get("optional-dependencies", {}).values():
        requirements.extend(extra)
    if any("@" in requirement for requirement in requirements):
        raise ValueError("PyPI rejects direct URL dependencies; install models separately")


def check_archive(path, project):
    """Check identity, license and absence of external data in either archive."""
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            members = {
                name: archive.read(name) for name in archive.namelist() if not name.endswith("/")
            }
        metadata_name = next(name for name in members if name.endswith(".dist-info/METADATA"))
        metadata = members[metadata_name]
    else:
        with tarfile.open(path, "r:gz") as archive:
            members = {}
            for member in archive.getmembers():
                if member.isfile():
                    stream = archive.extractfile(member)
                    if stream is None:
                        raise ValueError(f"Cannot read archive member {member.name}")
                    name = str(
                        PurePosixPath(member.name).relative_to(PurePosixPath(member.name).parts[0])
                    )
                    members[name] = stream.read()
        metadata = members["PKG-INFO"]
        for required in ("CONTRIBUTING.md",):
            if required not in members:
                raise ValueError(f"Missing {required} in {path.name}")
    headers = BytesParser().parsebytes(metadata)
    if headers["Name"] != project["name"] or headers["Version"] != project["version"]:
        raise ValueError(f"Distribution identity differs from pyproject.toml in {path.name}")
    if headers["License-Expression"] != "MIT" or "LICENSE" not in headers.get_all(
        "License-File", []
    ):
        raise ValueError(f"Missing MIT license metadata in {path.name}")
    if not any(PurePosixPath(name).name == "LICENSE" for name in members):
        raise ValueError(f"Missing LICENSE in {path.name}")
    if any("@" in value for value in headers.get_all("Requires-Dist", [])):
        raise ValueError(f"Direct URL requirement in {path.name}")
    for name in members:
        parts = PurePosixPath(name).parts
        if any(
            part in {"tmp", "data", "data2", "downloads", "local-resources", ".venv"}
            for part in parts
        ):
            raise ValueError(f"Local data leaked into {path.name}: {name}")
        if "docs/reports/" in name:
            raise ValueError(f"Research report leaked into {path.name}: {name}")
        if re.search(r"resources/(?:lexicons/(?:tone|themes|gcam|locations)\.|gcam/)", name):
            raise ValueError(f"External resource leaked into {path.name}: {name}")
    print(f"Checked {path.name}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="")
    parser.add_argument("--dist", type=Path)
    args = parser.parse_args()
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]
    check_metadata(project, args.tag)
    if args.dist:
        expected = {
            f"gdelt_regkg-{project['version']}-py3-none-any.whl",
            f"gdelt_regkg-{project['version']}.tar.gz",
        }
        paths = list(args.dist.iterdir())
        if {path.name for path in paths} != expected:
            raise ValueError(f"Expected only {sorted(expected)} in {args.dist}")
        for path in sorted(paths):
            check_archive(path, project)
    print(f"Release metadata OK for {project['name']} {project['version']}")


if __name__ == "__main__":
    main()
