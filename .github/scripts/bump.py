"""Bump project, CFF and docs citation versions: bump.py --patch | --minor | --major."""

from __future__ import annotations

import argparse
import re
import tomllib
from pathlib import Path


def replace_version(text: str, pattern: str, version: str, filename: str) -> str:
    updated, count = re.subn(pattern, lambda match: match[1] + version, text)
    if count != 1:
        raise ValueError(f"Expected exactly one version field in {filename}; found {count}")
    return updated


def update_software_citation(text: str, version: str) -> str:
    """Update the software citation while preserving other citations and formatting."""
    pattern = r"(?ms)^## Citing the software\r?\n.*?(?=^## |\Z)"
    sections = list(re.finditer(pattern, text))
    if len(sections) != 1:
        raise ValueError("Expected exactly one 'Citing the software' section in docs/README.md")
    section = sections[0]
    updated = section[0]
    for field_pattern in (
        r"(?m)^(Cite the release used in your work\. The citation for version )\d+\.\d+\.\d+(?= is:)",
        r"(?m)^(  version = \{)\d+\.\d+\.\d+(?=\},\r?$)",
        r"(?m)^(  note = \{Version )\d+\.\d+\.\d+(?=\},\r?$)",
    ):
        updated = replace_version(updated, field_pattern, version, "docs/README.md")
    return text[: section.start()] + updated + text[section.end() :]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    for part in ("patch", "minor", "major"):
        group.add_argument(f"--{part}", dest="part", action="store_const", const=part)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[2]
    pyproject_path = root / "pyproject.toml"
    citation_path = root / "CITATION.cff"
    docs_path = root / "docs" / "README.md"
    try:
        # Read/write bytes to preserve line endings and unrelated formatting.
        pyproject = pyproject_path.read_bytes().decode("utf-8")
        citation = citation_path.read_bytes().decode("utf-8")
        docs = docs_path.read_bytes().decode("utf-8")
        current = tomllib.loads(pyproject)["project"]["version"]
        if not re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", current):
            raise ValueError(f"Expected a major.minor.patch version; found {current!r}")
        major, minor, patch = map(int, current.split("."))
        if args.part == "major":
            major, minor, patch = major + 1, 0, 0
        elif args.part == "minor":
            minor, patch = minor + 1, 0
        else:
            patch += 1
        version = f"{major}.{minor}.{patch}"

        pyproject = replace_version(
            pyproject,
            r"(?ms)(^\[project\][^\S\r\n]*\r?\n(?:(?!^\[).)*?"
            r"^version[^\S\r\n]*=[^\S\r\n]*[\"'])[^\"'\r\n]+",
            version,
            pyproject_path.name,
        )
        citation = replace_version(
            citation,
            r"(?m)^(version:[^\S\r\n]*[\"']?)\d+\.\d+\.\d+(?=[\"']?[^\S\r\n]*(?:#|\r?$))",
            version,
            citation_path.name,
        )
        docs = update_software_citation(docs, version)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))

    pyproject_path.write_bytes(pyproject.encode("utf-8"))
    citation_path.write_bytes(citation.encode("utf-8"))
    docs_path.write_bytes(docs.encode("utf-8"))
    print(f"Updated pyproject.toml, CITATION.cff and docs/README.md: {current} -> {version}")


if __name__ == "__main__":
    main()
