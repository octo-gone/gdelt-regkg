"""Import theme sources, merge authored rules and replay recorded revisions."""

from __future__ import annotations

import copy
import csv
import hashlib
import io
import json
import zipfile
from pathlib import Path

from gdelt_regkg.rule_inputs import THEME_SCHEMA, theme_lexicon_from_input
from gdelt_regkg.themes import ThemeLexicon
from gdelt_regkg.utils import read_resource_json

EMTERMS_THEMES = dict(
    zip(
        "C01 C02 C03 C04 C05 C06 C07 C08 O01 O02 T01 T02 T03 T04 T05 T06 T07 T08 T09 T11".split(),
        (
            "CHILDREN_AND_EDUCATION NEEDSPROVIDE_FOOD WELLBEING_HEALTH LOGISTICS_TRANSPORT "
            "NEED_OF_SHELTERS WATER_SANITATION SAFETY TELECOM WEATHER RESPONSEAGENCIESATCRISIS "
            "CAUTION_ADVICE INJURED DEAD INFRASTRUCTURE MONEY SUPPLIES SERVICESNEEDEDOFFERED "
            "MISSINGFOUNDTRAPPEDPEOPLE DISPLACEDRELOCATEDEVACUATED UPDATESSYMPATHY"
        ).split(),
        strict=True,
    )
)


def build_profile(*, crisislex: Path | None = None, emterms: Path | None = None, name: str):
    themes: dict[str, set[str]] = {}
    sources = []
    skipped = {"template": 0, "unmapped_category": 0, "empty": 0}
    for path, kind in ((crisislex, "CrisisLexRec"), (emterms, "EMTerms")):
        if path is None:
            continue
        raw = path.read_bytes()
        sources.append(
            {
                "resource": kind,
                "url": (
                    "https://raw.githubusercontent.com/sajao/CrisisLex/master/data/CrisisLexLexicon/CrisisLexRec.txt"
                    if kind == "CrisisLexRec"
                    else "https://crisislex.org/emterms/EMTerms-v1.0.zip"
                ),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
        if kind == "CrisisLexRec":
            rows = (
                (line.strip(), "CRISISLEX_CRISISLEXREC")
                for line in raw.decode("utf-8-sig").splitlines()
            )
        else:
            if zipfile.is_zipfile(io.BytesIO(raw)):
                with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                    raw = archive.read("EMTerms-1.0.csv")
            reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
            if not {"Term", "Category Code"} <= set(reader.fieldnames or []):
                raise ValueError("Expected an EMTerms CSV with Term and Category Code columns")
            rows = ((r["Term"].strip(), r["Category Code"].strip()) for r in reader)
        for phrase, code in rows:
            if not phrase:
                skipped["empty"] += 1
                continue
            if kind == "EMTerms":
                if code not in EMTERMS_THEMES:
                    skipped["unmapped_category"] += 1
                    continue
                code = f"CRISISLEX_{code}_{EMTERMS_THEMES[code]}"
            if "{" in phrase or "}" in phrase:
                skipped["template"] += 1
                continue
            themes.setdefault(code, set()).add(" ".join(phrase.split()))
    if not themes:
        raise ValueError("No supported literal phrases found")
    sorted_themes = {code: sorted(phrases) for code, phrases in sorted(themes.items())}
    ThemeLexicon.from_mapping(sorted_themes, name=name)
    return {"name": name, "sources": sources, "skipped_rows": skipped, "themes": sorted_themes}


def merge_inputs(inputs, *, name):
    records: dict[str, dict] = {}
    sources = {}
    for data in inputs:
        theme_lexicon_from_input(data)
        for rule in data["rules"]:
            identifier = rule["id"]
            if identifier in records and records[identifier] != rule:
                raise ValueError(f"Conflicting rule ID: {identifier}")
            records[identifier] = copy.deepcopy(rule)
        for source in data.get("sources", []):
            sources[json.dumps(source, sort_keys=True)] = copy.deepcopy(source)
    result = {
        "schema": THEME_SCHEMA,
        "name": name,
        "sources": list(sources.values()),
        "rules": list(records.values()),
    }
    theme_lexicon_from_input(result)
    return result


def revise_themes(baseline, revision):
    """Replay validated rule replacements and additions against a fixed baseline."""
    checksum = hashlib.sha256(json.dumps(baseline, sort_keys=True).encode()).hexdigest()
    if checksum != revision.get("base_sha256"):
        raise ValueError("Theme baseline checksum differs from the recorded revision")
    revision = copy.deepcopy(revision)
    originals = {rule["id"]: rule for rule in baseline["rules"]}
    for entry in revision.pop("external_rule_overrides", []):
        patch = entry["rule"]
        if patch["id"] not in originals:
            raise ValueError("External theme override requires a matching source rule")
        revision["rules"].insert(
            entry["position"], {**patch, "expression": originals[patch["id"]]["expression"]}
        )
    theme_lexicon_from_input(revision)
    result = copy.deepcopy(baseline)
    result["name"] = revision["name"]
    result["evaluation"] = copy.deepcopy(revision["evaluation"])
    changes = {rule["id"]: rule for rule in revision["rules"]}
    result["rules"] = [copy.deepcopy(changes.pop(rule["id"], rule)) for rule in baseline["rules"]]
    result["rules"].extend(copy.deepcopy(list(changes.values())))
    theme_lexicon_from_input(result)
    return result


def restore_crisislex(authored, source):
    """Merge external phrases into authored rules without storing the vocabulary."""
    data = copy.deepcopy(authored)
    identifiers = data.pop("external_rule_ids", {})
    profile = build_profile(crisislex=Path(source), name="source")
    if profile["sources"] != data["sources"]:
        raise ValueError("CrisisLex source checksum differs from the recorded recipe")
    rules = {rule["expression"]: rule for rule in data["rules"]}
    for phrase in profile["themes"]["CRISISLEX_CRISISLEXREC"]:
        rule = rules.setdefault(
            phrase,
            {
                "id": identifiers.get(
                    hashlib.sha256(phrase.encode()).hexdigest(),
                    "literal-" + hashlib.sha256(phrase.encode()).hexdigest()[:16],
                ),
                "kind": "literal",
                "expression": phrase,
                "labels": [],
                "status": "enabled",
                "provenance": {"evidence": []},
            },
        )
        rule["labels"] = sorted(set(rule["labels"]) | {"CRISISLEX_CRISISLEXREC"})
    data["rules"] = [rule for _, rule in sorted(rules.items())]
    return data


def authored_theme_input():
    """Independent custom rules; no third-party vocabulary or source checksum."""
    first = read_resource_json("themes", "themes-count-candidates-v2.json")
    seeds = read_resource_json("themes", "theme_seeds.json")
    revision = read_resource_json("themes", "revision.v3.json")
    result = merge_inputs([first, seeds], name="authored-themes-v3")
    changes = {rule["id"]: rule for rule in revision["rules"]}
    result["rules"] = [copy.deepcopy(changes.pop(rule["id"], rule)) for rule in result["rules"]]
    result["rules"].extend(changes.values())
    result["sources"] = []
    result["$schema"] = "../schemas/theme-rules.schema.json"
    theme_lexicon_from_input(result)
    return result
