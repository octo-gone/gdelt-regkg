import copy
import json
import tempfile
import unittest
from pathlib import Path

from gdelt_regkg import (
    ExtractionConfig,
    analyze_counts,
    analyze_themes,
    default_extraction_config,
    load_count_rules,
    load_theme_lexicon,
    parse_counts_cell,
    parse_themes_cell,
    serialize_counts_cell,
    serialize_themes_cell,
)
from gdelt_regkg.rule_inputs import (
    count_rules_from_input,
    theme_input_from_mapping,
    theme_lexicon_from_input,
)
from gdelt_regkg.utils import read_resource_json, resource_path

ROOT = Path(__file__).resolve().parents[1]
LEXICONS = ROOT / "src/gdelt_regkg/resources/lexicons"


class RuleInputTests(unittest.TestCase):
    def test_local_separate_inputs_match_combined_profile(self):
        standalone = default_extraction_config()
        payload = {
            "name": "combined-test",
            "count_rules": json.loads(
                (LEXICONS / read_resource_json("defaults.json")["counts"]).read_text(
                    encoding="utf-8"
                )
            ),
            "theme_lexicon": json.loads(
                (
                    resource_path("lexicons", read_resource_json("defaults.json")["themes"])
                ).read_text(encoding="utf-8")
            ),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "combined.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            combined = ExtractionConfig.from_json(path)
        for text in (
            "Nearly 460 deaths",
            "11 people arrested; 5 injured.",
            "500 protesters gathered",
        ):
            self.assertEqual(
                analyze_counts(text, rules=standalone.count_rules).to_gkg(enhanced=True),
                analyze_counts(text, rules=combined.count_rules).to_gkg(enhanced=True),
            )
            self.assertEqual(
                analyze_themes(text, lexicon=standalone.theme_lexicon).to_gkg(enhanced=True),
                analyze_themes(text, lexicon=combined.theme_lexicon).to_gkg(enhanced=True),
            )

    def test_separate_inputs_support_independent_editing_and_review_status(self):
        count_data = json.loads((LEXICONS / "counts.v1.json").read_text(encoding="utf-8"))
        theme_data = json.loads(
            (resource_path("lexicons", "themes.v2.json")).read_text(encoding="utf-8")
        )
        count_data["rules"] = [
            {
                "id": "count-reviewed",
                "kind": "active_predicate",
                "expression": "rescued",
                "labels": ["RESCUE", "CRISISLEX_C07_SAFETY"],
                "status": "enabled",
                "provenance": {"source": "manual"},
            },
            {
                "id": "pending",
                "kind": "template",
                "expression": "{Number} unknown {Bad}",
                "labels": ["OTHER"],
                "status": "needs_review",
            },
        ]
        theme_data["rules"] = [
            {
                "id": "theme-reviewed",
                "kind": "literal",
                "expression": "rescued",
                "labels": ["RESCUE_TOPIC"],
                "status": "enabled",
            },
            {
                "id": "disabled",
                "kind": "literal",
                "expression": "other",
                "labels": ["OTHER_TOPIC"],
                "status": "disabled",
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            counts = Path(directory) / "counts.v1.json"
            themes = Path(directory) / "themes.v2.json"
            counts.write_text(json.dumps(count_data), encoding="utf-8")
            themes.write_text(json.dumps(theme_data), encoding="utf-8")
            config = ExtractionConfig.from_rule_inputs(counts, themes)
            self.assertEqual(load_count_rules(counts).name, config.count_rules.name)
            self.assertEqual(load_theme_lexicon(themes).name, config.theme_lexicon.name)
        result = analyze_counts("Police rescued 3 people.", rules=config.count_rules)
        self.assertEqual(
            {m.count_type for m in result.mentions}, {"RESCUE", "CRISISLEX_C07_SAFETY"}
        )
        self.assertEqual(
            analyze_themes("Rescued other", lexicon=config.theme_lexicon).to_gkg(), "RESCUE_TOPIC;"
        )
        self.assertEqual(analyze_counts("9 unknown", rules=config.count_rules).mentions, ())
        self.assertEqual(analyze_themes("Rescued other").to_gkg().count("RESCUE_TOPIC"), 0)

    def test_enabled_template_and_validation(self):
        data = json.loads((LEXICONS / "counts.v1.json").read_text(encoding="utf-8"))
        self.assertEqual(
            {
                m.count_type
                for m in analyze_counts(
                    "Death toll rose to 12.", rules=count_rules_from_input(data)
                ).mentions
            },
            {"KILL"},
        )
        broken = copy.deepcopy(data)
        broken["rules"][0]["id"] = broken["rules"][1]["id"]
        with self.assertRaises(ValueError):
            count_rules_from_input(broken)
        broken = copy.deepcopy(data)
        broken["rules"][0]["labels"] = ["bad#code"]
        with self.assertRaises(ValueError):
            count_rules_from_input(broken)
        theme_data = json.loads(
            (resource_path("lexicons", "themes.v2.json")).read_text(encoding="utf-8")
        )
        theme_data["rules"][0]["kind"] = "template"
        with self.assertRaises(ValueError):
            theme_lexicon_from_input(theme_data)

    def test_external_theme_mapping_converts_without_source_format_dependency(self):
        data = theme_input_from_mapping(
            {"TOPIC_A": ["hurricane"], "TOPIC_B": ["hurricane"]},
            name="neutral-import",
            sources=[{"resource": "any-csv"}],
        )
        self.assertEqual(len(data["rules"]), 1)
        self.assertEqual(data["rules"][0]["labels"], ["TOPIC_A", "TOPIC_B"])
        self.assertEqual(
            analyze_themes("Hurricane", lexicon=theme_lexicon_from_input(data)).to_gkg(),
            "TOPIC_A;TOPIC_B;",
        )

    def test_v2_multilabel_counts_and_native_wire(self):
        mentions = analyze_counts("Three people were killed; 11 arrested.").mentions
        self.assertIn("KILL", {m.count_type for m in mentions})
        self.assertIn("CRISISLEX_T03_DEAD", {m.count_type for m in mentions})
        self.assertIn("CRISISLEX_C07_SAFETY", {m.count_type for m in mentions})
        self.assertEqual(analyze_counts("Police arrested 1.5 suspects.").mentions, ())
        original = (
            "ARREST#11##0#######1992;CRISISLEX_C07_SAFETY#11##0#######1992;ARREST#11##0#######1992;"
        )
        self.assertEqual(
            serialize_counts_cell(parse_counts_cell(original, enhanced=True), enhanced=True),
            original,
        )
        theme = "KILL,2;KILL,2;CRISISLEX_T03_DEAD,2;"
        self.assertEqual(
            serialize_themes_cell(parse_themes_cell(theme, enhanced=True), enhanced=True), theme
        )
        native_hyphen = "TAX_DISEASE_COVID-19;GENERAL_HEALTH;"
        self.assertEqual(serialize_themes_cell(parse_themes_cell(native_hyphen)), native_hyphen)


if __name__ == "__main__":
    unittest.main()
