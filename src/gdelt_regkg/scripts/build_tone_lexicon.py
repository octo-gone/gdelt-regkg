"""Build the local approximation from the General Inquirer basic TSV.

Download https://inquirer.sites.fas.harvard.edu/inqtabs.txt separately, then run:
    gdelt-regkg-build-resources --fields tone --tone-source inqtabs.txt --output ./local-resources

Source terms: https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm
See docs/installation.md#source-terms before using the categories.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from pathlib import Path

from gdelt_regkg.tone import ToneLexicon, tokenize_tone


def build_lexicon(input_path):
    """Compile version 1 from the General Inquirer basic TSV."""
    raw = input_path.read_bytes()
    categories: dict[str, set[str]] = {
        key: set() for key in ("positive", "negative", "activity", "self_group")
    }
    skipped = set()
    reader = csv.DictReader(raw.decode("utf-8-sig").splitlines(), delimiter="\t")
    required = {"Entry", "Positiv", "Negativ", "Active", "Self", "Our", "You", "Othtags"}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("Expected the General Inquirer basic tab-delimited spreadsheet")
    for row in reader:
        # Collapse sense numbers; '>' is present in the source MYSELF entry.
        entry = re.sub(r"#\d+$", "", row["Entry"]).rstrip(">").casefold()
        if tokenize_tone(entry) != [entry]:
            skipped.add(entry)
            continue
        for category, source in (
            ("positive", "Positiv"),
            ("negative", "Negativ"),
            ("activity", "Active"),
        ):
            if row[source].strip():
                categories[category].add(entry)
        tags = set(row["Othtags"].split())
        # Pronoun senses plus personal/possessive references, without POS tagging.
        if (
            "PRON" in tags
            or any(row[tag].strip() for tag in ("Self", "Our", "You"))
            or ("GEN" in tags and tags & {"Singp", "Plrlp", "Scndp", "Thrdp"})
        ):
            categories["self_group"].add(entry)
    ToneLexicon(name="general-inquirer-bow-v1", **{k: frozenset(v) for k, v in categories.items()})
    if any(not values for values in categories.values()):
        raise ValueError("Source produced an empty category")
    payload = {
        "$schema": "../schemas/tone-lexicon.schema.json",
        "name": "general-inquirer-bow-v1",
        "source_url": "https://inquirer.sites.fas.harvard.edu/inqtabs.txt",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "terms_url": "https://inquirer.sites.fas.harvard.edu/spreadsheet_guide.htm",
        "skipped_entries": sorted(skipped),
        **{key: sorted(values) for key, values in categories.items()},
    }
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = build_lexicon(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
