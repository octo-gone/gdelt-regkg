"""Dictionary selection, native key inventory and source exclusion semantics."""

import argparse
import gzip
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator

from gdelt_regkg import RecordMetadata, Resources, generate_gkg
from gdelt_regkg.benchmark import BenchmarkOptions, evaluate
from gdelt_regkg.benchmark.model import GKGRow
from gdelt_regkg.cli import benchmark as benchmark_cli
from gdelt_regkg.fields.gcam import GCAMLexicon, _load, analyze_gcam
from gdelt_regkg.fields.themes import ThemeLexicon, ThemeRule
from gdelt_regkg.pipeline import OVERRIDABLE_COLUMNS
from gdelt_regkg.utils import read_resource_json


class GCAMSelectionTests(unittest.TestCase):
    def fixture(self):
        return GCAMLexicon(
            "selection",
            {"c2.1": frozenset({"child"})},
            weighted_dimensions={"v26.1": {"good": 2}},
            patterns={"c9.1": ("child care",), "c3.1": ("bad*",)},
            lemmatization={"c9.1": "wordnet"},
            exceptions={"children": ("child",)},
            theme_dimensions={"c18.1": "HEALTH"},
            theme_lexicon=ThemeLexicon("themes", (ThemeRule("HEALTH", "hospital"),)),
        )

    def test_names_ids_and_cached_selection_remove_all_matcher_types(self):
        lexicon = self.fixture()
        text = "child children care badly good hospital"
        disabled = ("roget", "3", "themes", 26, 9)
        result = analyze_gcam(text, lexicon=lexicon, disabled_dictionaries=disabled)
        self.assertEqual(result.to_gkg(), "wc:6,c2.1:1")
        self.assertEqual(result.implemented_dimensions, ("c2.1",))
        selected = lexicon.without_dictionaries(disabled)
        self.assertIs(selected, lexicon.without_dictionaries((26, 18, 9, 3)))
        self.assertFalse(selected.patterns)
        self.assertFalse(selected.lemmatization)
        self.assertFalse(selected.theme_dimensions)
        self.assertFalse(selected.weighted_dimensions)
        self.assertIn("v26.1", lexicon.implemented_dimensions)
        self.assertEqual(analyze_gcam(text, lexicon=lexicon).counts["c9.1"], 1)

    def test_exclusion_skips_theme_and_weighted_work(self):
        with patch(
            "gdelt_regkg.fields.themes.analyze_themes", side_effect=AssertionError("called")
        ):
            result = analyze_gcam(
                "good hospital", lexicon=self.fixture(), disabled_dictionaries=(18, 26)
            )
        self.assertNotIn("v26.1", result.values)
        self.assertNotIn("c26.1", result.counts)

    def test_all_disabled_absent_known_custom_and_invalid_selectors(self):
        lexicon = self.fixture()
        self.assertEqual(
            analyze_gcam(
                "hello world", lexicon=lexicon, disabled_dictionaries=(2, 3, 9, 18, 26)
            ).to_gkg(),
            "wc:2",
        )
        self.assertIs(lexicon, lexicon.without_dictionaries(("liwc",)))
        custom = GCAMLexicon("custom", {"c99.1": frozenset({"word"})})
        self.assertEqual(
            analyze_gcam("word", lexicon=custom, disabled_dictionaries=(99,)).to_gkg(), "wc:1"
        )
        for selectors, error in [
            (("typo",), ValueError),
            ((99,), ValueError),
            ((True,), TypeError),
            ((9.0,), TypeError),
            ("roget", TypeError),
            (("c9.1",), ValueError),
        ]:
            with self.subTest(selectors=selectors), self.assertRaises(error):
                lexicon.without_dictionaries(selectors)
        many = GCAMLexicon("many", {f"c{code}.1": frozenset({"word"}) for code in range(1, 15)})
        for code in range(1, 15):
            many.without_dictionaries((code,))
        self.assertEqual(len(many._selections), 8)

    def test_value_only_zero_no_match_roundtrip_schema_and_independent_count(self):
        payload = {
            "name": "emfd-shaped",
            "dimensions": [
                {"key": "c42.1", "words": ["care", "flat"]},
                {"key": "v42.2", "scores": {"care": 0.8, "flat": 0}, "emit_count": False},
            ],
        }
        Draft202012Validator(read_resource_json("schemas", "gcam-lexicon.schema.json")).validate(
            payload
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lexicon.json.gz"
            path.write_bytes(gzip.compress(json.dumps(payload).encode()))
            lexicon = GCAMLexicon.from_json(path)
        self.assertEqual(lexicon.implemented_dimensions, ("c42.1", "v42.2"))
        self.assertEqual(analyze_gcam("flat", lexicon=lexicon).to_gkg(), "wc:1,c42.1:1,v42.2:0")
        self.assertEqual(analyze_gcam("unknown", lexicon=lexicon).to_gkg(), "wc:1")
        result = analyze_gcam("care care flat", lexicon=lexicon)
        self.assertAlmostEqual(result.values["v42.2"], 1.6 / 3)
        self.assertNotIn("c42.2", result.counts)
        self.assertEqual(
            analyze_gcam("care", lexicon=lexicon, disabled_dictionaries=(42,)).to_gkg(), "wc:1"
        )
        for dimension in (
            {"key": "c8.1", "words": [], "emit_count": False},
            {"key": "v42.2", "scores": {}, "emit_count": 0},
        ):
            with self.assertRaises(ValueError):
                _load({"name": "bad", "dimensions": [dimension]})

    def test_source_exclusions_preserve_phrase_boundaries_and_other_dictionaries(self):
        lexicon = GCAMLexicon(
            "source-exclusions",
            {"c2.1": frozenset({"taxi"})},
            patterns={"c8.1": ("tax*", "red car"), "c13.1": ("tax*",)},
            exclusions={"8": ("taxi*",)},
        )
        result = analyze_gcam("tax taxi red taxi car taxation", lexicon=lexicon)
        self.assertEqual(result.word_count, 6)
        self.assertEqual(result.counts, {"c2.1": 2, "c8.1": 2, "c13.1": 4})
        self.assertEqual(
            analyze_gcam("tax taxi", lexicon=lexicon, disabled_dictionaries=(8,)).counts["c13.1"], 2
        )

    def test_pipeline_forwards_selection_and_honors_gcam_override(self):
        overrides = {key: "" for key in OVERRIDABLE_COLUMNS if key != "V2GCAM"}
        record = generate_gkg(
            "good child",
            RecordMetadata("https://example.org/", 20200101000000, 1),
            Resources(gcam_lexicon=self.fixture()),
            overrides=overrides,
            gcam_disabled_dictionaries=("vader",),
        )
        self.assertEqual(record.gcam, "wc:2,c2.1:1")
        with patch("gdelt_regkg.pipeline.analyze_gcam", side_effect=AssertionError("called")):
            record = generate_gkg(
                "text",
                RecordMetadata("https://example.org/", 20200101000000, 1),
                overrides={**overrides, "V2GCAM": "wc:1"},
                gcam_disabled_dictionaries=("vader",),
            )
        self.assertEqual(record.gcam, "wc:1")

    def test_benchmark_value_only_inventory_and_disabled_scores(self):
        row = GKGRow({"gcam": "wc:2,c42.1:2,v42.2:0.8,c26.1:1,v26.1:2"})
        prediction = GKGRow({"gcam": "wc:2,c42.1:2,v42.2:0.6,c26.1:100,v26.1:-2"})
        report = evaluate(
            [(row, prediction)],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"c42.1", "v42.2", "c26.1", "v26.1"}),
                gcam_disabled_dictionaries=("vader",),
            ),
        )
        coverage = next(r for r in report.rows if r.calculation == "coverage")
        self.assertEqual(coverage.metrics["supported_dimensions"], 2)
        self.assertEqual(coverage.metrics["dimension_coverage"], 1)
        self.assertFalse(any("VADER" in r.field for r in report.rows))
        score = next(r for r in report.rows if r.calculation == "v42.2 / weighted score")
        self.assertAlmostEqual(score.metrics["mae"], 0.2)

    def test_benchmark_cli_selects_filtered_prediction_lexicon(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "lexicon.json"
            path.write_text(
                json.dumps(
                    {
                        "name": "fixture",
                        "dimensions": [
                            {"key": "c2.1", "words": ["word"]},
                            {"key": "v26.1", "scores": {"good": 2}},
                        ],
                    }
                )
            )
            parser = argparse.ArgumentParser()
            benchmark_cli.add_arguments(parser)
            args = parser.parse_args(
                [
                    "--reference",
                    "reference.tsv",
                    "--prediction",
                    "prediction.tsv",
                    "--gcam-lexicon",
                    str(path),
                    "--gcam-disable",
                    "vader",
                ]
            )
            lexicon, options = benchmark_cli._inventories(args, ("gcam",), BenchmarkOptions(), None)
            self.assertEqual(lexicon.implemented_dimensions, ("c2.1",))
            self.assertEqual(options.gcam_disabled_dictionaries, (26,))
            self.assertIn("v26.1", options.gcam_keys)
            args.gcam_disable = ["typo"]
            with self.assertRaisesRegex(ValueError, "Unknown"):
                benchmark_cli._inventories(args, ("gcam",), BenchmarkOptions(), None)
