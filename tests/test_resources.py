import json
import tempfile
import unittest
from pathlib import Path

from gdelt_regkg.ner import NameRules, default_name_rules
from gdelt_regkg.scripts.build_resources import build_resources, revise_themes, revise_tone
from gdelt_regkg.tone import benchmark_tone_lexicon, default_tone_lexicon
from gdelt_regkg.utils import read_resource_json


class ResourceTests(unittest.TestCase):
    def test_name_profile_schema_and_fixed_runtime_coefficients(self):
        from jsonschema import Draft202012Validator

        profile = read_resource_json("lexicons", "names.v1.json")
        Draft202012Validator(read_resource_json("schemas", "name-rules.schema.json")).validate(
            profile
        )
        rules = default_name_rules()
        self.assertIs(rules, default_name_rules())
        self.assertEqual(rules.name, profile["name"])
        self.assertEqual(rules.apply("president jane smith", "PERSON"), "jane smith")
        self.assertEqual(
            NameRules().apply("president jane smith", "PERSON"), "president jane smith"
        )
        with self.assertRaises(TypeError):
            rules.organization_weights["w:test"] = 1

    def test_recorded_tone_revision_reproduces_local_default(self):
        baseline = read_resource_json("lexicons", "tone.v1.json")
        edits = read_resource_json("tone", "v2-edits.json")
        self.assertEqual(
            revise_tone(baseline, edits), read_resource_json("lexicons", "tone.v2.json")
        )
        baseline_v2 = read_resource_json("lexicons", "tone.v2.json")
        edits_v3 = read_resource_json("tone", "v3-edits.json")
        self.assertEqual(
            revise_tone(baseline_v2, edits_v3), read_resource_json("lexicons", "tone.v3.json")
        )
        self.assertEqual(default_tone_lexicon().name, edits_v3["name"])
        baseline_v2["name"] = "modified baseline"
        with self.assertRaisesRegex(ValueError, "dictionary checksum"):
            revise_tone(baseline_v2, edits_v3)
        self.assertIs(benchmark_tone_lexicon(), default_tone_lexicon())
        baseline["source_sha256"] = "different source"
        with self.assertRaisesRegex(ValueError, "checksum"):
            revise_tone(baseline, edits)

    def test_builds_reproduce_count_and_theme_rules_and_portable_schemas(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = Path("downloads/resources")
            if not (source / "CrisisLexRec.txt").is_file():
                self.skipTest("Requires source inputs from the resource setup")
            built = build_resources(
                root,
                fields=("themes", "counts", "ner"),
                crisislex_source=Path(source) / "CrisisLexRec.txt",
            )
            for name in (
                "themes.v2.json",
                "themes.v3.json",
                "counts.v1.json",
                "counts.v2.json",
                "counts.v3.json",
                "names.v1.json",
            ):
                shipped = read_resource_json("lexicons", name)
                self.assertEqual(built[name], shipped)
                payload = json.loads((root / "lexicons" / name).read_text(encoding="utf-8"))
                self.assertTrue((root / "lexicons" / payload["$schema"]).is_file())
            self.assertEqual(
                json.loads((root / "defaults.json").read_text()),
                {
                    key: read_resource_json("defaults.json")[key]
                    for key in ("themes", "counts", "ner")
                },
            )
            self.assertIn("themes.v1.json", built)

    def test_theme_revision_checks_baseline_and_preserves_older_snapshot(self):
        baseline = read_resource_json("lexicons", "themes.v2.json")
        revision = read_resource_json("themes", "revision.v3.json")
        result = revise_themes(baseline, revision)
        self.assertEqual(result, read_resource_json("lexicons", "themes.v3.json"))
        self.assertNotEqual(baseline["name"], result["name"])
        baseline["name"] = "different baseline"
        with self.assertRaisesRegex(ValueError, "checksum"):
            revise_themes(baseline, revision)


if __name__ == "__main__":
    unittest.main()
