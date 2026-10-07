import importlib.util
import json
import unittest
from pathlib import Path

from gdelt_regkg import ExtractionConfig, analyze_counts, analyze_themes, load_theme_lexicon
from gdelt_regkg.rule_inputs import THEME_SCHEMA, theme_lexicon_from_input
from gdelt_regkg.themes import ThemeRule
from gdelt_regkg.utils import read_resource_json, resource_path

ROOT = Path(__file__).resolve().parents[1]
LEXICONS = ROOT / "src/gdelt_regkg/resources/lexicons"
spec = importlib.util.spec_from_file_location(
    "build_theme_profile", ROOT / "src/gdelt_regkg/scripts/build_theme_profile.py"
)
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ThemeExpansionTests(unittest.TestCase):
    def test_aliases_and_document_conditions_keep_original_offsets(self):
        data = {
            "schema": THEME_SCHEMA,
            "name": "condition-test",
            "rules": [
                {
                    "id": "water-context",
                    "kind": "literal",
                    "expression": "access",
                    "aliases": ["supply"],
                    "labels": ["WATER"],
                    "status": "enabled",
                    "requires_all": [["clean water", "drinking water"], ["residents"]],
                    "exclude_any": ["fictional"],
                }
            ],
        }
        lexicon = theme_lexicon_from_input(data)
        text = "😀 Residents need SUPPLY of drinking water."
        result = analyze_themes(text, lexicon=lexicon)
        self.assertEqual(result.to_gkg(), "WATER;")
        self.assertEqual(result.to_gkg(enhanced=True), f"WATER,{text.index('SUPPLY')};")
        for text in (
            "residents need supply",
            "supply of drinking water",
            "fictional residents need supply of drinking water",
        ):
            self.assertEqual(analyze_themes(text, lexicon=lexicon).mentions, ())

    def test_common_roles_policy_and_world_bank_topics(self):
        codes = {
            m.theme
            for m in analyze_themes(
                "The minister proposed a budget for public health and education."
            ).mentions
        }
        self.assertTrue(
            {
                "TAX_FNCACT",
                "TAX_FNCACT_MINISTER",
                "EPU_POLICY",
                "EPU_POLICY_BUDGET",
                "GENERAL_HEALTH",
                "WB_635_PUBLIC_HEALTH",
                "WB_470_EDUCATION",
            }
            <= codes
        )
        codes = {m.theme for m in analyze_themes("Students attended schools.").mentions}
        self.assertTrue({"TAX_FNCACT_STUDENTS", "SOC_POINTSOFINTEREST_SCHOOLS"} <= codes)
        self.assertFalse({"TAX_FNCACT_STUDENT", "SOC_POINTSOFINTEREST_SCHOOL"} & codes)
        self.assertEqual(analyze_themes("ministerial schooling budgetary").mentions, ())

    def test_ambiguous_and_review_only_rules_do_not_fire(self):
        self.assertNotIn(
            "TRIAL",
            {m.theme for m in analyze_themes("The clinical trial enrolled patients.").mentions},
        )
        self.assertIn(
            "TRIAL", {m.theme for m in analyze_themes("The criminal trial began.").mentions}
        )
        self.assertNotIn(
            "EPU_POLICY_BLUE_HOUSE",
            {m.theme for m in analyze_themes("They repainted the blue house.").mentions},
        )
        self.assertIn(
            "EPU_POLICY_BLUE_HOUSE",
            {m.theme for m in analyze_themes("Korea's Blue House issued a statement.").mentions},
        )
        self.assertNotIn(
            "EPU_POLICY_DEFICIT",
            {m.theme for m in analyze_themes("An attention deficit was diagnosed.").mentions},
        )
        self.assertIn(
            "EPU_POLICY_DEFICIT",
            {m.theme for m in analyze_themes("The fiscal deficit grew.").mentions},
        )
        self.assertNotIn(
            "EPU_ECONOMY_HISTORIC",
            {m.theme for m in analyze_themes("The economy is growing.").mentions},
        )

    def test_neutral_combined_snapshot_retains_conditions_and_counts(self):
        combined = ExtractionConfig.from_dict(
            {
                "name": "combined-test",
                "count_rules": json.loads(
                    (LEXICONS / "counts.v1.json").read_text(encoding="utf-8")
                ),
                "theme_lexicon": json.loads(
                    (
                        resource_path("lexicons", read_resource_json("defaults.json")["themes"])
                    ).read_text(encoding="utf-8")
                ),
            }
        )
        for text in (
            "The budget deficit grew.",
            "The blue house was painted.",
            "A criminal trial began.",
        ):
            self.assertEqual(
                analyze_themes(text).to_gkg(enhanced=True),
                analyze_themes(text, lexicon=combined.theme_lexicon).to_gkg(enhanced=True),
            )
        self.assertEqual(
            analyze_counts("3 killed").to_gkg(),
            analyze_counts("3 killed", rules=combined.count_rules).to_gkg(),
        )

    def test_merge_conflicts_fail_and_guard_snapshots_are_validated(self):
        first = {
            "schema": THEME_SCHEMA,
            "name": "first",
            "rules": [
                {
                    "id": "same",
                    "kind": "literal",
                    "expression": "school",
                    "labels": ["EDUCATION"],
                    "status": "enabled",
                }
            ],
        }
        merged = builder.merge_inputs([first, first], name="merged")
        self.assertEqual(len(merged["rules"]), 1)
        second = json.loads(json.dumps(first))
        second["rules"][0]["expression"] = "hospital"
        with self.assertRaises(ValueError):
            builder.merge_inputs([first, second], name="merged")
        for groups in (["water"], [[]]):
            with self.assertRaises(ValueError):
                ThemeRule("WATER", "supply", requires_all=groups)
        groups = [["water"]]
        rule = ThemeRule("WATER", "supply", requires_all=groups)
        groups[0].append("oil")
        self.assertEqual(rule.requires_all, (("water",),))


if __name__ == "__main__":
    unittest.main()
