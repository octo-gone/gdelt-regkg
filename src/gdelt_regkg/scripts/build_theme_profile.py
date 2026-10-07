"""Merge source-neutral theme inputs and optionally update a combined profile.

Records keep their review status, aliases, conditions and provenance. A merge
adds only explicitly supplied mappings; it never guesses phrases from codes.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from importlib.resources import files
from pathlib import Path

from gdelt_regkg import ExtractionConfig
from gdelt_regkg.rule_inputs import THEME_SCHEMA, theme_lexicon_from_input


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--name", default="gdelt-theme-candidates-v3")
    parser.add_argument("--counts-input", type=Path)
    parser.add_argument("--combined-output", type=Path)
    args = parser.parse_args()
    if bool(args.counts_input) != bool(args.combined_output):
        parser.error("--counts-input and --combined-output must be supplied together")
    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
    result = merge_inputs(inputs, name=args.name)
    schema_path = Path(
        str(files("gdelt_regkg").joinpath("resources/schemas/theme-rules.schema.json"))
    )
    result["$schema"] = os.path.relpath(schema_path, args.output.resolve().parent).replace(
        os.sep, "/"
    )
    result["input_versions"] = [
        {
            "name": data["name"],
            "file": path.name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path, data in zip(args.inputs, inputs)
    ]
    combined = None
    if args.counts_input:
        combined = {
            "name": args.name,
            "count_rules": json.loads(args.counts_input.read_text(encoding="utf-8")),
            "theme_lexicon": result,
        }
        ExtractionConfig.from_dict(combined)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if combined:
        args.combined_output.parent.mkdir(parents=True, exist_ok=True)
        args.combined_output.write_text(
            json.dumps(combined, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
    lexicon = theme_lexicon_from_input(result)
    print(
        f"{len(result['rules'])} rule groups, {len(lexicon.rules)} phrase/label rules, "
        f"{len({rule.theme for rule in lexicon.rules})} enabled theme labels"
    )


if __name__ == "__main__":
    main()
