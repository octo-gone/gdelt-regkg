import copy
import importlib.util
import json
import unittest
from importlib.resources import files
from pathlib import Path

from jsonschema import Draft202012Validator

from gdelt_regkg.rule_inputs import count_rules_from_input, theme_lexicon_from_input
from gdelt_regkg.utils import read_resource_json, resource_path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = files("gdelt_regkg")


def read_resource(directory, name):
    return read_resource_json(directory, name)


class SchemaTests(unittest.TestCase):
    def validator(self, name):
        schema = read_resource("schemas", name + ".schema.json")
        Draft202012Validator.check_schema(schema)
        return Draft202012Validator(schema)

    def test_prepared_profiles_and_authored_inputs_validate(self):
        for name, schema in (
            ("counts.v1", "count-rules"),
            ("counts.v2", "count-rules"),
            ("themes.v2", "theme-rules"),
            ("themes.v3", "theme-rules"),
            ("tone.v1", "tone-lexicon"),
            ("tone.v2", "tone-lexicon"),
        ):
            with self.subTest(resource=name):
                payload = read_resource("lexicons", name + ".json")
                self.validator(schema).validate(payload)
                reference = resource_path("lexicons", name + ".json").parent / payload["$schema"]
                self.assertTrue(reference.is_file())
        for path in (ROOT / "src/gdelt_regkg/resources/themes").glob("*.json"):
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.validator("theme-rules").validate(payload)
            self.assertTrue((path.parent / payload["$schema"]).is_file())

    def test_invalid_count_settings_labels_and_enabled_templates(self):
        data = read_resource("lexicons", "counts.v1.json")
        validator = self.validator("count-rules")
        for key, value in (
            ("context_words", 0),
            ("max_object_modifiers", 21),
            ("allow_bare_active", "yes"),
            ("triggers", {}),
        ):
            broken = copy.deepcopy(data)
            broken["settings"][key] = value
            self.assertFalse(validator.is_valid(broken), key)
        for expression in ("{number} killed {number}", "{Number} deaths", "{number}; deaths"):
            broken = copy.deepcopy(data)
            broken["rules"] = [
                {
                    "id": "bad",
                    "kind": "template",
                    "status": "enabled",
                    "expression": expression,
                    "labels": ["KILL"],
                }
            ]
            self.assertFalse(validator.is_valid(broken), expression)
        data["rules"][0]["labels"] = ["bad#label"]
        self.assertFalse(validator.is_valid(data))

    def test_theme_conditions_and_review_only_expressions(self):
        data = read_resource("lexicons", "themes.v2.json")
        data["rules"] = [
            {
                "id": "water",
                "kind": "literal",
                "status": "enabled",
                "expression": "water",
                "labels": ["WATER"],
            }
        ]
        validator = self.validator("theme-rules")
        for conditions in ([[]], ["water"], [["{template}"]]):
            data["rules"][0]["requires_all"] = conditions
            self.assertFalse(validator.is_valid(data))
        data["rules"][0] = {
            "id": "review",
            "kind": "literal",
            "status": "needs_review",
            "expression": "{unreviewed template}",
            "labels": ["WATER"],
        }
        validator.validate(data)
        self.assertEqual(theme_lexicon_from_input(data).rules, ())

    def test_semantic_validation_still_checks_duplicate_rule_ids(self):
        data = read_resource("lexicons", "counts.v1.json")
        data["rules"][1]["id"] = data["rules"][0]["id"]
        self.validator("count-rules").validate(data)
        with self.assertRaises(ValueError):
            count_rules_from_input(data)

    def test_tone_requires_all_four_arrays(self):
        data = {"name": "test", "positive": [], "negative": [], "activity": [], "self_group": []}
        validator = self.validator("tone-lexicon")
        validator.validate(data)
        data["positive"] = "hope"
        self.assertFalse(validator.is_valid(data))
        del data["positive"]
        self.assertFalse(validator.is_valid(data))

    def test_theme_sources_reproduce_shipped_rules(self):
        spec = importlib.util.spec_from_file_location(
            "build_theme_profile", ROOT / "src/gdelt_regkg/scripts/build_theme_profile.py"
        )
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)

        from gdelt_regkg.scripts.build_resources import restore_crisislex

        source = Path("downloads/resources")
        if not (source / "CrisisLexRec.txt").is_file():
            self.skipTest("Requires source inputs from the resource setup")
        sources = [
            json.loads(
                (ROOT / "src/gdelt_regkg/resources/themes" / name).read_text(encoding="utf-8")
            )
            for name in ("themes-count-candidates-v2.json", "theme_seeds.json")
        ]
        sources[0] = restore_crisislex(sources[0], Path(source) / "CrisisLexRec.txt")
        shipped = read_resource("lexicons", "themes.v2.json")
        merged = builder.merge_inputs(sources, name=shipped["name"])
        self.assertEqual(merged["rules"], shipped["rules"])
        self.assertEqual(merged["sources"], shipped["sources"])
