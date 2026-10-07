"""Compile GCAM resources from General Inquirer, VADER and optional licensed input."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any

from gdelt_regkg.gcam import GCAMLexicon, _load
from gdelt_regkg.tone import tokenize_tone

# Verified against GDELT's GCAM Master Codebook. No ambiguous historical aliases.
CATEGORIES = {
    "c2.21": "BodyPt",
    "c2.74": "Goal",
    "c2.79": "Hostile",
    "c2.93": "Know",
    "c2.156": "Power",
    "c2.213": "Vice",
    "c2.214": "Virtue",
    "c2.225": "Weak",
}

LEXICODER_CATEGORIES = {
    "c3.1": "negative",
    "c3.2": "positive",
    "c3.3": "neg_negative",
    "c3.4": "neg_positive",
}


def _parse_lc3(raw):
    """Read Lexicoder section headers, ignoring optional display colors."""
    try:
        text = raw.decode("utf-8-sig")
        encoding = "utf-8"
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
        encoding = "cp1252"
    categories: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("+"):
            header = re.fullmatch(r"\+([a-z_]+)(?:#[0-9a-fA-F]{6})?", line.casefold())
            if header is None or header[1] not in LEXICODER_CATEGORIES.values():
                raise ValueError("Unknown Lexicoder section header")
            current = header[1]
            if current in categories:
                raise ValueError("Duplicate Lexicoder section")
            categories[current] = []
        elif current is None:
            raise ValueError("Lexicoder pattern precedes its category header")
        else:
            categories[current].append(line)
    return categories, encoding


def read_lexicoder_source(input_path):
    """Read user-owned JSON, the original ZIP, or a directory of LC3 files.

    Only the two named dictionaries are read from ZIPs, without extraction or
    execution of the included preprocessing scripts.
    """
    source = Path(input_path)
    filenames = ("LSD2015.lc3", "LSD2015_NEG.lc3")
    metadata: dict[str, Any] = {"preprocessing": "not applied"}
    if source.is_dir():
        documents = [(filename, (source / filename).read_bytes()) for filename in filenames]
        metadata["format"] = "lc3-directory"
        metadata["source_sha256"] = hashlib.sha256(
            b"".join(name.encode() + b"\0" + raw for name, raw in documents)
        ).hexdigest()
    else:
        raw = source.read_bytes()
        metadata["source_sha256"] = hashlib.sha256(raw).hexdigest()
        if source.suffix.casefold() == ".json":
            metadata["format"] = "category-json"
            return json.loads(raw.decode("utf-8-sig")), metadata
        if source.suffix.casefold() != ".zip":
            raise ValueError("Lexicoder source must be a ZIP, four-category JSON or LC3 directory")
        documents = []
        with zipfile.ZipFile(source) as archive:
            for filename in filenames:
                matches = [
                    info
                    for info in archive.infolist()
                    if not info.is_dir()
                    and not info.filename.startswith("__MACOSX/")
                    and info.filename.rsplit("/", 1)[-1] == filename
                ]
                if len(matches) != 1:
                    raise ValueError(f"Lexicoder ZIP requires exactly one {filename}")
                documents.append((matches[0].filename, archive.read(matches[0])))
        metadata["format"] = "original-lc3-zip"
    categories: dict[str, list[str]] = {}
    members = []
    for name, raw in documents:
        parsed, encoding = _parse_lc3(raw)
        if set(categories) & set(parsed):
            raise ValueError("Duplicate Lexicoder categories across dictionary files")
        categories.update(parsed)
        members.append(
            {"name": name, "sha256": hashlib.sha256(raw).hexdigest(), "encoding": encoding}
        )
    metadata["members"] = members
    return categories, metadata


def build_gcam_lexicon(input_path):
    raw = Path(input_path).read_bytes()
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines(), delimiter="\t")
    if not {"Entry", *CATEGORIES.values()}.issubset(reader.fieldnames or []):
        raise ValueError("Expected General Inquirer basic TSV categories")
    words: dict[str, set[str]] = {key: set() for key in CATEGORIES}
    skipped = set()
    for row in reader:
        entry = re.sub(r"#\d+$", "", row["Entry"]).rstrip(">").casefold()
        if tokenize_tone(entry) != [entry]:
            skipped.add(entry)
            continue
        for key, category in CATEGORIES.items():
            if row[category].strip():
                words[key].add(entry)
    GCAMLexicon("general-inquirer-gcam-subset-v1", {k: frozenset(v) for k, v in words.items()})
    return {
        "name": "general-inquirer-gcam-subset-v1",
        "source_url": "https://inquirer.sites.fas.harvard.edu/inqtabs.txt",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "codebook_url": "http://data.gdeltproject.org/documentation/GCAM-MASTER-CODEBOOK.TXT",
        "terms_url": "https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm",
        "skipped_entries": sorted(skipped),
        "dimensions": [
            {"key": key, "category": category, "words": sorted(words[key])}
            for key, category in CATEGORIES.items()
        ],
    }


def extend_gcam_lexicon(baseline, *, vader_source=None, lexicoder_source=None):
    """Add published scores; never retrieve or redistribute licensed Lexicoder data.

    Lexicoder input is a user-provided original ZIP, LC3 directory or UTF-8
    JSON export mapping its four category names to pattern arrays.
    """
    result = copy.deepcopy(baseline)
    additions = ["vader"] if "vader_source" in baseline else []
    if vader_source is not None:
        raw = Path(vader_source).read_bytes()
        scores, skipped, duplicates = {}, [], []
        for line in raw.decode("utf-8-sig").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                raise ValueError("VADER input requires tab-separated term and mean valence")
            term, score = parts[0].casefold(), float(parts[1])
            if not term or any(c.isspace() for c in term):
                skipped.append(parts[0])
                continue
            if term in scores:
                duplicates.append(term)
            scores[term] = score  # Upstream loader also keeps the last duplicate.
        if not scores:
            raise ValueError("VADER input has no usable terms")
        result["dimensions"].append(
            {
                "key": "v26.1",
                "category": "VADER valence",
                "tokenization": "whitespace",
                "scores": dict(sorted(scores.items())),
            }
        )
        result["vader_source"] = {
            "source_url": "https://github.com/cjhutto/vaderSentiment",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "license": "MIT",
            "skipped_multiword_entries": sorted(skipped),
            "duplicate_normalized_entries": sorted(duplicates),
            "mode": "bag-of-words matched-occurrence mean; no sentence heuristics",
        }
        if (
            result["vader_source"]["source_sha256"]
            == "1ec9c6e9ee19aade328f8beb393a6afa71a5bb3acf7d3cc22d4ef568df374bf5"
        ):
            result["vader_source"]["version"] = "3.3.2"
            result["vader_source"]["release_url"] = "https://pypi.org/project/vaderSentiment/3.3.2/"
        additions.append("vader")
    if lexicoder_source is not None:
        categories, metadata = read_lexicoder_source(lexicoder_source)
        if not isinstance(categories, dict) or set(categories) != set(
            LEXICODER_CATEGORIES.values()
        ):
            raise ValueError("Lexicoder input requires exactly its four named category arrays")
        for key, category in LEXICODER_CATEGORIES.items():
            terms = categories[category]
            if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
                raise ValueError("Lexicoder categories require arrays of patterns")
            result["dimensions"].append(
                {
                    "key": key,
                    "category": category,
                    "patterns": sorted({" ".join(term.casefold().split()) for term in terms}),
                }
            )
        result["lexicoder_source"] = {
            **metadata,
            "terms_url": "https://www.snsoroka.com/s/LSDagreement.pdf",
            "bundled_with_package": False,
            "matching": "longest nonoverlapping matches within each category; categories independent",
            "source_entries": {category: len(terms) for category, terms in categories.items()},
            "normalized_unique_patterns": {
                category: len({" ".join(term.casefold().split()) for term in terms})
                for category, terms in categories.items()
            },
        }
        additions.append("lexicoder-custom")
    if not additions:
        return result
    result["name"] = "general-inquirer-" + "-".join(additions) + "-gcam-v2"
    _load(result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--vader-source", type=Path, help="Published vader_lexicon.txt (MIT)")
    parser.add_argument(
        "--lexicoder-source",
        type=Path,
        help="Your licensed original ZIP, LC3 directory or JSON export",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            extend_gcam_lexicon(
                build_gcam_lexicon(args.input),
                vader_source=args.vader_source,
                lexicoder_source=args.lexicoder_source,
            ),
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
