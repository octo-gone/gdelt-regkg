"""Configuration for theme phrases and count trigger rules."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .counts import CountRules
from .themes import ThemeLexicon
from .utils import read_resource_json, resource_path


@dataclass(frozen=True)
class ExtractionConfig:
    name: str
    theme_lexicon: ThemeLexicon
    count_rules: CountRules

    @classmethod
    def from_dict(cls, data: dict):
        required = {"name", "theme_lexicon", "count_rules"}
        if not isinstance(data, dict) or set(data) != required:
            raise ValueError("Configuration requires exactly name, theme_lexicon, and count_rules")
        if not isinstance(data["name"], str) or not data["name"].strip():
            raise ValueError("Configuration name must be a nonempty string")
        themes = data["theme_lexicon"]
        from .rule_inputs import count_rules_from_input, theme_lexicon_from_input

        if not isinstance(themes, dict):
            raise ValueError("theme_lexicon must be an object")
        if "schema" in themes:
            lexicon = theme_lexicon_from_input(themes)
        elif {"name", "themes"} <= themes.keys():
            lexicon = ThemeLexicon.from_mapping(themes["themes"], name=themes["name"])
        else:
            raise ValueError("theme_lexicon requires neutral rules or name and themes")
        counts = data["count_rules"]
        rules = (
            count_rules_from_input(counts)
            if isinstance(counts, dict) and "schema" in counts
            else CountRules.from_dict(counts)
        )
        return cls(data["name"], lexicon, rules)

    @classmethod
    def from_json(cls, path: str | Path):
        """Load and compile a snapshot. Call again after editing to reload it."""
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))

    @classmethod
    def from_rule_inputs(
        cls, count_path: str | Path, theme_path: str | Path, *, name: str = "custom-rules"
    ):
        """Compose independent source-neutral count and theme JSON inputs."""
        from .rule_inputs import load_count_rules, load_theme_lexicon

        return cls(name, load_theme_lexicon(theme_path), load_count_rules(count_path))


def default_extraction_config(resources_dir=None) -> ExtractionConfig:
    """Load selected local themes and independently available authored counts."""
    defaults = read_resource_json("defaults.json", resources_dir=resources_dir)
    return _cached_config(
        resource_path("lexicons", defaults["themes"], resources_dir=resources_dir),
        resource_path("lexicons", defaults["counts"], resources_dir=resources_dir),
    )


@lru_cache(maxsize=8)
def _cached_config(theme_path, count_path):
    from .rule_inputs import count_rules_from_input, theme_lexicon_from_input

    counts = json.loads(count_path.read_text(encoding="utf-8"))
    themes = json.loads(theme_path.read_text(encoding="utf-8"))
    return ExtractionConfig(
        themes["name"],
        theme_lexicon_from_input(themes),
        count_rules_from_input(counts),
    )
