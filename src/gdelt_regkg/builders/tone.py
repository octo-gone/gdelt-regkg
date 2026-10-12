"""Compile General Inquirer tone profiles and replay recorded revisions."""

from __future__ import annotations

import copy
import csv
import hashlib
import json
import re

from gdelt_regkg.tone import ToneLexicon, _parse_lexicon, tokenize_tone


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


def revise_tone(baseline, edits):
    """Replay the recorded revision without fitting against benchmark bodies."""
    if baseline.get("source_sha256") != edits["base_source_sha256"]:
        raise ValueError("Tone source checksum differs from the recorded revision")
    if (
        "base_dictionary_sha256" in edits
        and hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
        != edits["base_dictionary_sha256"]
    ):
        raise ValueError("Tone dictionary checksum differs from the recorded revision")
    result = copy.deepcopy(edits["metadata"])
    for category, changes in edits["changes"].items():
        words = set(baseline[category])
        removals = set(changes.get("remove", ()))
        by_hash = {hashlib.sha256(word.encode()).hexdigest(): word for word in words}
        for digest in changes.get("remove_sha256", ()):
            if digest not in by_hash:
                raise ValueError(f"Revision removes unknown {category} term hash")
            removals.add(by_hash[digest])
        if not removals <= words:
            raise ValueError(f"Revision removes unknown {category} terms")
        result[category] = sorted((words - removals) | set(changes["add"]))
    _parse_lexicon(json.dumps(result))
    return result
