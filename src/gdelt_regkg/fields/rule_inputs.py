"""Source-neutral, reviewable inputs for count and theme extraction."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

# Versioned data formats stay stable across package renames.
COUNT_SCHEMA = "reconstruct-gkg/count-rules/v1"
THEME_SCHEMA = "reconstruct-gkg/theme-rules/v1"
_CODE = re.compile(r"[A-Z][A-Z0-9_-]*\Z")
_STATUSES = {"enabled", "needs_review", "disabled"}


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _validate(data, schema, kinds):
    if not isinstance(data, dict) or data.get("schema") != schema:
        raise ValueError(f"Expected schema {schema}")
    if not isinstance(data.get("name"), str) or not data["name"].strip():
        raise ValueError("Rule input requires a nonempty name")
    records = data.get("rules")
    if not isinstance(records, list):
        raise TypeError("rules must be a list")
    ids = set()
    for record in records:
        if (
            not isinstance(record, dict)
            or not {"id", "kind", "expression", "labels", "status"} <= record.keys()
        ):
            raise ValueError("Each rule needs id, kind, expression, labels and status")
        identifier = record["id"]
        if not isinstance(identifier, str) or not identifier or identifier in ids:
            raise ValueError("Rule IDs must be nonempty and unique")
        ids.add(identifier)
        if record["kind"] not in kinds or record["status"] not in _STATUSES:
            raise ValueError(f"Invalid rule kind or status: {identifier}")
        if (
            not isinstance(record["expression"], str)
            or not record["expression"].strip()
            or any(c in record["expression"] for c in "\t\r\n")
        ):
            raise ValueError(f"Rule expression must be a nonempty single line: {identifier}")
        labels = record["labels"]
        if (
            not isinstance(labels, list)
            or not labels
            or any(not isinstance(label, str) or not _CODE.fullmatch(label) for label in labels)
        ):
            raise ValueError(f"Rule labels must be a nonempty list of GKG codes: {identifier}")
        if "provenance" in record and not isinstance(record["provenance"], dict):
            raise TypeError(f"provenance must be an object: {identifier}")
    return records


def count_rules_from_input(data):
    """Compile enabled count records into the reusable count analyzer."""
    from .counts import CountRules

    records = _validate(data, COUNT_SCHEMA, {"predicate", "active_predicate", "template"})
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise TypeError("Count input requires a settings object")
    triggers = defaultdict(set)
    active = set()
    patterns = []
    for record in records:
        if "aliases" in record or "requires_all" in record or "exclude_any" in record:
            raise ValueError("Count rules do not support theme aliases or conditions")
        if record["status"] != "enabled":
            continue
        phrase = record["expression"]
        if record["kind"] == "template":
            patterns.append({"id": record["id"], "template": phrase, "labels": record["labels"]})
        else:
            triggers[phrase].update(record["labels"])
            if record["kind"] == "active_predicate":
                active.add(phrase)
    if {"name", "triggers", "patterns", "active_triggers"} & settings.keys():
        raise ValueError("Count settings cannot override rule records")
    return CountRules.from_dict(
        {
            "name": data["name"],
            **settings,
            "triggers": {phrase: sorted(labels) for phrase, labels in triggers.items()},
            "active_triggers": sorted(active),
            "patterns": patterns,
        }
    )


def theme_lexicon_from_input(data):
    """Compile enabled phrases, aliases and context conditions."""
    from .themes import ThemeLexicon, ThemeRule

    records = _validate(data, THEME_SCHEMA, {"literal"})
    rules = []
    for record in records:
        if record["status"] == "enabled":
            aliases = record.get("aliases", [])
            if not isinstance(aliases, list) or any(not isinstance(p, str) for p in aliases):
                raise TypeError("Theme aliases must be a list of literal phrases")
            for label in record["labels"]:
                for phrase in dict.fromkeys([record["expression"], *aliases]):
                    rules.append(
                        ThemeRule(
                            label,
                            phrase,
                            record.get("requires_all", ()),
                            record.get("exclude_any", ()),
                        )
                    )
    return ThemeLexicon(data["name"], tuple(rules))


def load_count_rules(path):
    return count_rules_from_input(_read(path))


def load_theme_lexicon(path):
    return theme_lexicon_from_input(_read(path))


def theme_input_from_mapping(themes, *, name, sources=()):
    """Create a neutral editable theme file from any source's code/phrase map."""
    from .themes import ThemeLexicon

    ThemeLexicon.from_mapping(themes, name=name)
    phrases = defaultdict(set)
    for label, values in themes.items():
        for value in values:
            phrases[value].add(label)
    rules = []
    for phrase, labels in sorted(phrases.items()):
        identifier = "literal-" + hashlib.sha256(phrase.encode()).hexdigest()[:16]
        rules.append(
            {
                "id": identifier,
                "kind": "literal",
                "expression": phrase,
                "labels": sorted(labels),
                "status": "enabled",
            }
        )
    result = {"schema": THEME_SCHEMA, "name": name, "sources": list(sources), "rules": rules}
    theme_lexicon_from_input(result)
    return result
