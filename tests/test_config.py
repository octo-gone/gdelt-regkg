import json
import tempfile
import unittest
import warnings
from pathlib import Path

from support import compose_resources, make_record, read_resources

from gdelt_regkg import IncompleteGKGWarning, Resources
from gdelt_regkg.fields.counts import analyze_counts, default_count_rules
from gdelt_regkg.fields.themes import ThemeLexicon, analyze_themes


class ConfigTests(unittest.TestCase):
    def data(self):
        return json.loads(
            (Path(__file__).parent / "fixtures/extraction-conservative-v1.json").read_text(
                encoding="utf-8"
            )
        )

    def custom_data(self):
        data = self.data()
        data["name"] = "my-extraction-v1"
        data["theme_lexicon"] = {"name": "my-themes-v1", "themes": {"EVACUATION": ["evacuated"]}}
        data["count_rules"]["name"] = "my-counts-v1"
        data["count_rules"]["triggers"] = {"evacuated": "EVACUATION"}
        data["count_rules"]["active_triggers"] = ["evacuated"]
        return data

    def test_edit_both_sections_load_once_and_use_all_four_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "extraction.json"
            path.write_text(json.dumps(self.custom_data()), encoding="utf-8")
            config = read_resources(path)
        text = "Three people were evacuated."
        self.assertEqual(analyze_themes(text, lexicon=config.theme_lexicon).to_gkg(), "EVACUATION;")
        self.assertEqual(
            analyze_themes(text, lexicon=config.theme_lexicon).to_gkg(enhanced=True),
            "EVACUATION,18;",
        )
        self.assertEqual(
            analyze_counts(text, rules=config.count_rules).to_gkg(), "EVACUATION#3#people#0######;"
        )
        self.assertEqual(
            analyze_counts(text, rules=config.count_rules).to_gkg(enhanced=True),
            "EVACUATION#3#people#0#######0;",
        )
        self.assertEqual(
            analyze_counts(text, rules=config.count_rules).profile_name, "my-counts-v1"
        )
        self.assertEqual(
            analyze_themes(text, lexicon=config.theme_lexicon).lexicon_name, "my-themes-v1"
        )
        self.assertEqual(
            analyze_counts(text).profile_name,
            Resources(count_rules=default_count_rules()).count_rules.name,
        )

    def test_pipeline_config_and_explicit_override_precedence(self):
        config = compose_resources(self.custom_data())
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = make_record(
                "Three people were evacuated.",
                config=config,
                theme_lexicon=ThemeLexicon.from_mapping({"CUSTOM": ["evacuated"]}),
                field_values={"V1COUNTS": "provided"},
                identifier="https://example.org",
                published_at=None,
                batch_time="20261001120000",
                sequence=1,
            )
        self.assertEqual(record["V1COUNTS"], "provided")
        self.assertEqual(record["V2.1COUNTS"], "EVACUATION#3#people#0#######0;")
        self.assertEqual(record["V1THEMES"], "CUSTOM;")
        self.assertEqual(record["V2ENHANCEDTHEMES"], "CUSTOM,18;")

    def test_count_vocabulary_and_guard_settings_are_effective(self):
        data = self.custom_data()
        data["count_rules"]["object_nouns"] = ["engineers"]
        config = compose_resources(data)
        self.assertEqual(
            analyze_counts("Police evacuated two engineers.", rules=config.count_rules)
            .mentions[0]
            .number,
            2,
        )
        self.assertEqual(
            analyze_counts("Police evacuated two people.", rules=config.count_rules).mentions, ()
        )
        self.assertEqual(
            analyze_counts(
                "About two engineers were evacuated.", rules=config.count_rules
            ).mentions,
            (),
        )
        data["count_rules"]["unsafe_phrases"].remove("about")
        relaxed = compose_resources(data)
        self.assertEqual(
            analyze_counts("About two engineers were evacuated.", rules=relaxed.count_rules)
            .mentions[0]
            .number,
            2,
        )

    def test_invalid_configuration_does_not_silently_fall_back(self):
        for edit in (
            lambda d: d["count_rules"].update(active_triggers=["unknown"]),
            lambda d: d["count_rules"].update(object_nouns="people"),
            lambda d: d["count_rules"].update(triggers={"killed.*": "KILL"}),
            lambda d: d["count_rules"].update(context_words=0),
            lambda d: d["count_rules"].update(max_object_modifiers=True),
        ):
            data = self.data()
            edit(data)
            with self.assertRaises((ValueError, TypeError)):
                compose_resources(data)

    def test_profile_is_snapshot_and_empty_lists_disable_matching(self):
        data = self.custom_data()
        config = compose_resources(data)
        data["count_rules"]["triggers"]["evacuated"] = "OTHER"
        self.assertEqual(config.count_rules.triggers["evacuated"], ("EVACUATION",))
        with self.assertRaises(TypeError):
            config.count_rules.triggers["evacuated"] = "OTHER"
        data["count_rules"].update(triggers={}, active_triggers=[])
        data["theme_lexicon"]["themes"] = {}
        empty = compose_resources(data)
        self.assertEqual(analyze_counts("3 evacuated", rules=empty.count_rules).mentions, ())
        self.assertEqual(analyze_themes("evacuated", lexicon=empty.theme_lexicon).mentions, ())
        self.assertIs(Resources().counts(), Resources().counts())


if __name__ == "__main__":
    unittest.main()
