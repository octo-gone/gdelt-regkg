import json
import tempfile
import unittest
import warnings
from pathlib import Path

from gdelt_regkg import IncompleteGKGWarning, ToneLexicon, analyze_tone, generate_gkg
from gdelt_regkg.fields import extract_tone
from gdelt_regkg.tone import default_tone_lexicon, tokenize_tone


class ToneTests(unittest.TestCase):
    def setUp(self):
        self.lexicon = ToneLexicon(
            name="synthetic-test",
            positive={"good", "joy"},
            negative={"bad"},
            activity={"run"},
            self_group={"we", "our"},
        )

    def test_seven_components_and_repeated_matches(self):
        text = "We run good good bad and our plain news today"
        result = analyze_tone(text, lexicon=self.lexicon)
        self.assertEqual(result.to_gkg(), "10,20,10,30,10,20,10")
        self.assertEqual(result.lexicon_name, "synthetic-test")
        self.assertEqual(extract_tone(text, lexicon=self.lexicon), result.to_gkg())

    def test_neutral_tone_can_be_emotionally_charged(self):
        result = analyze_tone("good bad", lexicon=self.lexicon)
        self.assertEqual(result.tone, 0)
        self.assertEqual(result.polarity, 100)

    def test_overlap_counts_once_in_polarity(self):
        lexicon = ToneLexicon("overlap", {"mixed"}, {"mixed"}, set(), set())
        result = analyze_tone("mixed mixed plain", lexicon=lexicon)
        self.assertEqual(result.tone, 0)
        self.assertAlmostEqual(result.polarity, 200 / 3)
        self.assertAlmostEqual(result.positive_score, result.negative_score)

    def test_denominator_keeps_stopwords_numbers_and_no_reasoning(self):
        self.assertEqual(extract_tone("not good", lexicon=self.lexicon), "50,50,0,50,0,0,2")
        self.assertEqual(
            analyze_tone("very good! 2026", lexicon=self.lexicon).positive_score, 100 / 3
        )
        self.assertEqual(analyze_tone("goodness", lexicon=self.lexicon).positive_score, 0)
        self.assertEqual(analyze_tone("bad BAD", lexicon=self.lexicon).tone, -100)

    def test_unicode_and_token_boundaries(self):
        self.assertEqual(
            tokenize_tone("WE’RE well-known; café 42_7 — ＧＯＯＤ"),
            ["we're", "well-known", "café", "42", "7", "good"],
        )
        lexicon = ToneLexicon("casefold", {"ＧＯＯＤ"}, set(), set(), {"WE’RE"})
        self.assertEqual(extract_tone("we're good", lexicon=lexicon), "50,50,0,50,0,50,2")

    def test_empty_and_missing_input_are_different(self):
        for text in ("", " \n\t", "!? —"):
            self.assertEqual(extract_tone(text, lexicon=self.lexicon), "0,0,0,0,0,0,0")
        for value in (None, 123, float("nan")):
            with self.subTest(value=value), self.assertRaises(TypeError):
                analyze_tone(value)

    def test_local_lexicon_is_real_cached_and_immutable(self):
        lexicon = default_tone_lexicon()
        self.assertIs(lexicon, default_tone_lexicon())
        self.assertGreater(len(lexicon.positive), 1000)
        self.assertGreater(len(lexicon.negative), 1000)
        self.assertGreater(len(lexicon.activity), 1000)
        self.assertIn("good", lexicon.positive)
        self.assertIn("war", lexicon.negative)
        self.assertIn("we", lexicon.self_group)
        self.assertGreater(analyze_tone("good excellent joy").positive_score, 0)
        self.assertGreater(analyze_tone("bad evil war").negative_score, 0)

    def test_json_validation_and_frozen_copy(self):
        words = {"good"}
        lexicon = ToneLexicon("copy", words, set(), set(), set())
        words.add("new")
        self.assertNotIn("new", lexicon.positive)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "lexicon.json"
            data = dict(name="json", positive=["good"], negative=[], activity=[], self_group=[])
            path.write_text(json.dumps(data), encoding="utf-8")
            self.assertEqual(ToneLexicon.from_json(path).positive, frozenset({"good"}))
            del data["activity"]
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "activity"):
                ToneLexicon.from_json(path)
        with self.assertRaises(ValueError):
            ToneLexicon("phrase", {"very good"}, set(), set(), set())

    def test_pipeline_uses_same_scorer_and_honors_override(self):
        kwargs = dict(
            identifier="https://example.org",
            published_at=None,
            batch_time="20261001000000",
            sequence=1,
            tone_lexicon=self.lexicon,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", IncompleteGKGWarning)
            record = generate_gkg("good bad", **kwargs)
            overridden = generate_gkg("good bad", field_values={"V1.5TONE": "custom"}, **kwargs)
        self.assertEqual(record["V1.5TONE"], "0,50,50,100,0,0,2")
        self.assertEqual(overridden["V1.5TONE"], "custom")


if __name__ == "__main__":
    unittest.main()
