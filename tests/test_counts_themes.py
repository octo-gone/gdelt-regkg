import csv
import importlib.util
import io
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg import (
    CountLocation,
    IncompleteGKGWarning,
    ThemeLexicon,
    ThemeRule,
    analyze_counts,
    analyze_themes,
    fields,
    generate_gkg,
    serialize_gkg,
)
from gdelt_regkg.config import ExtractionConfig
from gdelt_regkg.themes import default_theme_lexicon

CONSERVATIVE = ExtractionConfig.from_json(
    Path(__file__).resolve().parent / "fixtures/extraction-conservative-v1.json"
)


def conservative_counts(text, **kwargs):
    return analyze_counts(text, rules=CONSERVATIVE.count_rules, **kwargs)


class ThemeTests(unittest.TestCase):
    def test_distinct_legacy_and_repeated_enhanced_mentions(self):
        lexicon = ThemeLexicon.from_mapping(
            {"FLOOD": ["flood", "flood victims"], "HELP": ["victims"]}
        )
        text = "Flood victims; FLOOD. flooded"
        result = analyze_themes(text, lexicon=lexicon)
        self.assertEqual(result.to_gkg(), "FLOOD;HELP;")
        self.assertEqual(result.to_gkg(enhanced=True), "FLOOD,0;FLOOD,0;HELP,6;FLOOD,15;")
        self.assertEqual(
            [(m.start, m.end) for m in result.mentions], [(0, 5), (0, 13), (6, 13), (15, 20)]
        )
        self.assertEqual(fields.extract_themes(text, lexicon=lexicon), result.to_gkg())
        self.assertEqual(
            fields.extract_enhanced_themes(text, lexicon=lexicon), result.to_gkg(enhanced=True)
        )

    def test_unicode_offsets_and_original_slices(self):
        lexicon = ThemeLexicon.from_mapping({"ROAD": ["STRASSE"], "HELP": ["power outage"]})
        text = "😀 Straße: POWER\n\toutage."
        result = analyze_themes(text, lexicon=lexicon)
        self.assertEqual(result.to_gkg(enhanced=True), "ROAD,2;HELP,10;")
        for mention in result.mentions:
            self.assertEqual(text[mention.start : mention.end], mention.text)

    def test_overlaps_multilabel_and_duplicates(self):
        lexicon = ThemeLexicon.from_mapping({"A": ["a a", "a", "A"], "B": ["a a"]})
        result = analyze_themes("a a a", lexicon=lexicon)
        self.assertEqual(result.to_gkg(enhanced=True), "A,0;A,0;B,0;A,2;A,2;B,2;A,4;")

    def test_no_substring_stemming_or_punctuation_deletion(self):
        lexicon = ThemeLexicon.from_mapping({"X": ["aid", "power outage"]})
        self.assertEqual(analyze_themes("paid power-outage", lexicon=lexicon).mentions, ())

    def test_local_profile_and_custom_json(self):
        default = default_theme_lexicon()
        self.assertIs(default, default_theme_lexicon())
        self.assertGreater(len(default.rules), 379)
        self.assertEqual(fields.extract_themes("An explosion occurred."), "CRISISLEX_CRISISLEXREC;")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "themes.v2.json"
            path.write_text('{"name":"test","themes":{"TEST":["news"]}}', encoding="utf-8")
            self.assertEqual(ThemeLexicon.from_json(path).name, "test")

    def test_empty_and_invalid_input(self):
        self.assertEqual(fields.extract_themes(""), "")
        self.assertEqual(
            fields.extract_themes("anything", lexicon=ThemeLexicon.from_mapping({})), ""
        )
        with self.assertRaises(TypeError):
            analyze_themes(None)
        for theme, phrase in (("X;Y", "aid"), ("X", ""), ("X", "{Number}")):
            with self.subTest(theme=theme, phrase=phrase), self.assertRaises(ValueError):
                ThemeRule(theme, phrase)
        with self.assertRaises(TypeError):
            ThemeLexicon.from_mapping({"X": "not a phrase list"})


class CountTests(unittest.TestCase):
    def test_two_categories_and_wire_components(self):
        text = "Three people were killed and twelve injured."
        result = conservative_counts(text)
        self.assertEqual(
            [(m.count_type, m.number, m.object_type) for m in result.mentions],
            [("KILL", 3, "people"), ("WOUND", 12, "")],
        )
        self.assertEqual(result.issues, ())
        self.assertEqual(
            fields.extract_counts(text, rules=CONSERVATIVE.count_rules), result.to_gkg()
        )
        self.assertEqual(
            fields.extract_enhanced_counts(text, rules=CONSERVATIVE.count_rules),
            result.to_gkg(enhanced=True),
        )
        for legacy, enhanced, mention in zip(
            result.to_gkg().rstrip(";").split(";"),
            result.to_gkg(enhanced=True).rstrip(";").split(";"),
            result.mentions,
        ):
            self.assertEqual(len(legacy.split("#")), 10)
            self.assertEqual(enhanced.split("#")[:-1], legacy.split("#"))
            self.assertEqual(enhanced.split("#")[-1], str(mention.start))
            self.assertEqual(legacy.split("#")[3:], ["0"] + [""] * 6)

    def test_integer_forms_active_and_passive(self):
        for expression, number in (
            ("twenty-one", 21),
            ("two hundred and five", 205),
            ("one thousand and six", 1006),
            ("1,234", 1234),
            ("ten thousand two hundred and three", 10203),
            ("five million", 5_000_000),
            ("2 thousand", 2000),
        ):
            for text in (
                f"Police arrested {expression} suspects.",
                f"{expression} suspects were arrested.",
            ):
                with self.subTest(text=text):
                    result = conservative_counts(text)
                    self.assertEqual(
                        [(m.count_type, m.number, m.object_type) for m in result.mentions],
                        [("ARREST", number, "suspects")],
                    )
                    self.assertEqual(result.mentions[0].start, text.index(expression))

    def test_identifying_object_and_unicode_offsets(self):
        text = "😀 20 Christian missionaries were arrested."
        result = conservative_counts(text)
        self.assertEqual(result.mentions[0].object_type, "Christian missionaries")
        self.assertEqual(result.mentions[0].start, 2)

    def test_conservative_rejections_have_diagnostics(self):
        cases = [
            "No one was injured.",
            "Three people were not killed.",
            "Officials fear hundreds could die.",
            "10-20 killed.",
            "Between ten and twenty people were killed.",
            "ten to twenty killed.",
            "1.5 people died.",
            "-3 people died.",
            "1/2 killed.",
            "At least 10 killed.",
            "About 5 killed.",
            "0 killed.",
            "Three people could be killed.",
            "Three people will be killed.",
            "3 injured people arrived.",
            "Two more people were killed.",
        ]
        cases.extend(["Three people killed a man.", "Three people killed police."])
        for text in cases:
            with self.subTest(text=text):
                result = conservative_counts(text)
                self.assertEqual(result.mentions, ())
                if any(t in text for t in ("killed", "injured", "died")):
                    self.assertTrue(result.issues)

    def test_actor_age_date_and_sentence_boundaries(self):
        text = "The driver, aged 25, was arrested with two passengers."
        self.assertEqual(conservative_counts(text).mentions, ())
        result = conservative_counts("Three people killed five attackers.")
        self.assertEqual([m.number for m in result.mentions], [5])
        self.assertEqual(
            [
                m.number
                for m in conservative_counts("No injuries. In 2025, three people died.").mentions
            ],
            [3],
        )
        self.assertEqual(conservative_counts("Three people. Killed yesterday.").mentions, ())

    def test_locations_and_repeated_mentions(self):
        text = "Alpha: 3 killed. Beta: 3 killed."
        a = CountLocation(0, 5, "1", "Alpha", "AA", latitude="1", longitude="2", feature_id="AA")
        b = CountLocation(17, 21, "1", "Beta", "BB", feature_id="BB")
        result = conservative_counts(text, locations=iter([a, b]))
        self.assertEqual([m.location for m in result.mentions], [a, b])
        self.assertEqual(len(result.to_gkg(enhanced=True).rstrip(";").split(";")), 2)
        self.assertEqual(
            result.to_gkg().split(";")[0].split("#")[3:], ["1", "Alpha", "AA", "", "1", "2", "AA"]
        )

    def test_invalid_input_and_unsupported_categories(self):
        self.assertEqual(fields.extract_counts(""), "")
        self.assertEqual(conservative_counts("200 people were evacuated.").mentions, ())
        with self.assertRaises(TypeError):
            analyze_counts(None)
        self.assertEqual(
            CountLocation(0, 2, full_name="bad#place;\nname").components()[1], "bad place name"
        )
        with self.assertRaises(ValueError):
            CountLocation(0, 2, latitude="nan")
        with self.assertRaises(ValueError):
            analyze_counts("x", locations=[CountLocation(0, 2)])


class IntegrationTests(unittest.TestCase):
    def make_record(self, **kwargs):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            return generate_gkg(
                "Three people killed in a flood.",
                identifier="https://example.org/a",
                published_at=None,
                batch_time="20261001120000",
                sequence=1,
                **kwargs,
            )

    def test_pairs_analyzed_once_and_overrides_stay_independent(self):
        lexicon = ThemeLexicon.from_mapping({"FLOOD": ["flood"]})
        with (
            patch("gdelt_regkg.pipeline.analyze_counts", wraps=analyze_counts) as counts,
            patch("gdelt_regkg.pipeline.analyze_themes", wraps=analyze_themes) as themes,
        ):
            record = self.make_record(theme_lexicon=lexicon, field_values={"V1THEMES": "CUSTOM"})
            self.assertEqual(counts.call_count, 1)
            self.assertEqual(themes.call_count, 1)
        self.assertEqual(record["V1THEMES"], "CUSTOM")
        self.assertEqual(record["V2ENHANCEDTHEMES"], "FLOOD,25;")
        self.assertEqual(
            len(serialize_gkg(record, allow_incomplete=True).rstrip("\n").split("\t")), 27
        )
        with (
            patch("gdelt_regkg.pipeline.analyze_counts", side_effect=AssertionError("must skip")),
            patch("gdelt_regkg.pipeline.analyze_themes", side_effect=AssertionError("must skip")),
        ):
            self.make_record(
                field_values={
                    c: "" for c in ("V1COUNTS", "V2.1COUNTS", "V1THEMES", "V2ENHANCEDTHEMES")
                }
            )

    def test_importer_excludes_templates_and_unmapped_codes(self):
        path = (
            Path(__file__).resolve().parents[1] / "src/gdelt_regkg/scripts/build_theme_lexicon.py"
        )
        spec = importlib.util.spec_from_file_location("build_theme_lexicon", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        stream = io.StringIO()
        writer = csv.writer(stream)
        writer.writerow(["Term", "Category Code"])
        writer.writerows(
            [
                ("injured", "T02"),
                ("injured", "T02"),
                ("injured", "T03"),
                ("{Number}", "T03"),
                ("unknown", "O04"),
            ]
        )
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "terms.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("EMTerms-1.0.csv", stream.getvalue())
            result = module.build_profile(emterms=archive, name="test")
        self.assertEqual(
            result["themes"],
            {"CRISISLEX_T02_INJURED": ["injured"], "CRISISLEX_T03_DEAD": ["injured"]},
        )
        self.assertEqual(
            result["skipped_rows"], {"template": 1, "unmapped_category": 1, "empty": 0}
        )


if __name__ == "__main__":
    unittest.main()
