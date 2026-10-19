"""GCAM detection, count agreement, cohorts and cache metadata regressions."""

import csv
import json
import sqlite3
import tempfile
import unittest
from argparse import ArgumentParser
from collections import Counter
from contextlib import closing
from dataclasses import replace
from pathlib import Path

from gdelt_regkg.benchmark import BenchmarkOptions, BenchmarkReport, GKGRow, evaluate, write_report
from gdelt_regkg.benchmark.corpus import PredictionOptions, generate_predictions, load_corpus
from gdelt_regkg.benchmark.gcam_metrics import publisher_intervals
from gdelt_regkg.benchmark.storage import BenchmarkStore
from gdelt_regkg.cli.benchmark import add_arguments
from gdelt_regkg.fields.gcam import _load


def item(cell, publisher="example.org", languages=None):
    values = {"gcam": cell, "source": publisher, "document": "https://" + publisher + "/story"}
    if languages:
        values["_gcam_languages"] = json.dumps(languages)
    return GKGRow(values)


def metric(report, field, calculation):
    return next(
        row.metrics for row in report.rows if row.field == field and row.calculation == calculation
    )


class GCAMEvaluationTests(unittest.TestCase):
    def test_joined_and_split_layouts_render_each_dimension_once_in_numeric_order(self):
        keys = ["v23.1", "v23.2", "v23.10", "v23.11", "v23.17"]
        languages = {key: "cat" if key != "v23.17" else "spa" for key in keys}
        options = BenchmarkOptions(
            gcam_keys=frozenset(keys),
            gcam_languages=languages,
            gcam_dimension_names={key: "Level1Positive (Scored Value)" for key in keys},
            gcam_approximate_dimensions=frozenset(),
        )
        pairs = [
            (
                item("wc:10,nwc:8,v23.1:0.1,v23.2:0.2,v23.10:0.3,v23.11:0.4"),
                item("wc:0,nwc:8,v23.1:0.2,v23.2:0.3,v23.10:0.4,v23.11:0.5", languages=["cat"]),
            ),
            (item("wc:10,nwc:8,v23.17:0.5"), item("wc:0,nwc:8,v23.17:0.6", languages=["spa"])),
        ]
        joined = evaluate(pairs, fields=("gcam",), options=options)
        split = evaluate(
            pairs, fields=("gcam",), options=replace(options, gcam_split_languages=True)
        )
        label = "GCAM / ML-SENTICON Multilingual"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name, report in (("joined", joined), ("split", split)):
                score_rows = [
                    row for row in report.rows if row.calculation.endswith(" / weighted score")
                ]
                self.assertEqual([row.dimension_key for row in score_rows], keys)
                identities = Counter(
                    (row.subset, row.calculation) for row in report.rows if row.dimension_key
                )
                self.assertTrue(all(count == 1 for count in identities.values()))
                source_scores = [
                    row
                    for row in report.tables["gcam-sources"]
                    if row.calculation.endswith(" / weighted score")
                ]
                self.assertEqual(len(source_scores), len(keys))
                details = report.details["gcam-dimensions"]
                self.assertEqual(Counter(row["key"] for row in details), Counter(keys))
                write_report(report, root / name)
                markdown = (root / name / "metrics.md").read_text(encoding="utf8")
                self.assertNotIn("all-native", markdown)
                self.assertNotIn("language/", markdown)
                self.assertEqual(
                    markdown.count("| v23.1 / Catalan (cat) / Level 1 Positive / weighted score |"),
                    1 if name == "joined" else 0,
                )
                if name == "joined":
                    self.assertEqual(markdown.count("**" + label + "**"), 1)
                    self.assertFalse(any(row.language for row in report.rows if row.dimension_key))
                    self.assertEqual(len(report.details["gcam-articles"]), 2)
                else:
                    self.assertNotIn("**" + label + "**", markdown)
                    self.assertEqual(markdown.count("**" + label + " / Catalan (cat)**"), 1)
                    self.assertEqual(markdown.count("**" + label + " / Spanish (spa)**"), 1)
                    self.assertEqual(
                        markdown.count("| v23.1 / Level 1 Positive / weighted score |"), 1
                    )
                    self.assertTrue(
                        all(row.language == languages[row.dimension_key] for row in score_rows)
                    )
            self.assertEqual(
                {
                    row.dimension_key: row.metrics
                    for row in joined.rows
                    if row.calculation.endswith(" / weighted score")
                },
                {
                    row.dimension_key: row.metrics
                    for row in split.rows
                    if row.calculation.endswith(" / weighted score")
                },
            )

    def test_language_layout_cli_flags_have_explicit_joined_default(self):
        parser = ArgumentParser()
        add_arguments(parser)
        inputs = ["--reference", "reference.jsonl", "--prediction", "prediction.jsonl"]
        self.assertFalse(parser.parse_args(inputs).gcam_split_languages)
        self.assertTrue(parser.parse_args(inputs + ["--gcam-split-languages"]).gcam_split_languages)
        self.assertFalse(
            parser.parse_args(
                inputs + ["--gcam-split-languages", "--no-gcam-split-languages"]
            ).gcam_split_languages
        )

    def test_split_layout_applies_when_one_language_is_explicitly_selected(self):
        report = evaluate(
            [
                (
                    item("wc:10,nwc:8,v24.3:5"),
                    item("wc:10,nwc:8,v24.3:5.2", languages=["eng", "fra"]),
                )
            ],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"v24.3"}),
                gcam_languages={"v24.3": "fra"},
                gcam_dimension_names={"v24.3": "Happiness"},
                gcam_evaluation_language="fra",
                gcam_split_languages=True,
            ),
        )
        scores = [row for row in report.rows if row.calculation == "v24.3 / weighted score"]
        self.assertEqual(len(scores), 1)
        self.assertEqual(scores[0].language, "fra")
        self.assertEqual(scores[0].dimension_name, "Happiness")
        with self.assertRaisesRegex(ValueError, "language metadata"):
            evaluate([], fields=("gcam",), options=BenchmarkOptions(gcam_split_languages=True))

    def test_weighted_rows_stay_with_their_dictionary_and_render_codebook_names(self):
        report = evaluate(
            [
                (
                    item("wc:10,nwc:8,v10.1:0.2,v24.2:5"),
                    item("wc:10,nwc:8,v10.1:0.2,v24.2:5.5", languages=["eng", "deu"]),
                ),
                (
                    item("wc:10,nwc:8,v10.1:0.3,v24.3:6"),
                    item("wc:10,nwc:8,v10.1:0.3,v24.3:6.2", languages=["eng", "fra"]),
                ),
            ],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"v10.1", "v24.2", "v24.3"}),
                gcam_languages={"v10.1": "eng", "v24.2": "deu", "v24.3": "fra"},
                gcam_dimension_names={
                    "v10.1": "Positive (Scored Value)",
                    "v24.2": "Happiness (Scored Value)",
                    "v24.3": "Happiness (Scored Value)",
                },
            ),
        )
        weighted = [row for row in report.rows if row.dimension_key]
        self.assertTrue(weighted)
        self.assertTrue(all(row.field != "GCAM" for row in weighted))
        french = next(
            row
            for row in weighted
            if row.subset == "all" and row.calculation == "v24.3 / weighted-score coverage"
        )
        self.assertEqual(french.field, "GCAM / Hedonometer Multilingual")
        self.assertEqual(french.dimension_name, "French (fra) / Happiness")
        with tempfile.TemporaryDirectory() as directory:
            write_report(report, directory)
            path = Path(directory)
            markdown = (path / "metrics.md").read_text(encoding="utf8")
            self.assertIn("v24.3 / French (fra) / Happiness / weighted-score coverage", markdown)
            self.assertIn("v24.2 / German (deu) / Happiness / weighted score", markdown)
            self.assertIn("v10.1 / Positive / weighted score", markdown)
            self.assertNotIn("Scored Value", markdown)
            with (path / "metrics.csv").open(encoding="utf8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            encoded = next(
                row
                for row in rows
                if row["subset"] == "all" and row["calculation"] == "v24.3 / weighted score"
            )
            self.assertEqual(encoded["dimension_key"], "v24.3")
            self.assertEqual(encoded["dimension_name"], "French (fra) / Happiness")

    def test_all_native_includes_unimplemented_categories_while_supported_is_conditional(self):
        report = evaluate(
            [(item("wc:10,c2.1:1,c99.1:1"), item("wc:10,c2.1:1"))],
            fields=("gcam",),
            options=BenchmarkOptions(gcam_keys=frozenset({"c2.1"})),
        )
        self.assertAlmostEqual(metric(report, "GCAM", "presence")["recall"], 0.5)
        self.assertEqual(metric(report, "GCAM", "supported presence")["recall"], 1)
        self.assertEqual(
            metric(report, "GCAM / General Inquirer", "presence"),
            metric(report, "GCAM / General Inquirer", "supported presence"),
        )

    def test_bootstrap_does_not_exclude_articles_or_change_point_metrics(self):
        pairs = [
            (item("wc:10,c2.1:1", publisher="a.org"), item("wc:10,c2.1:2")),
            (item("wc:10,c2.1:1", publisher="b.org"), item("wc:10")),
        ]
        plain = evaluate(
            pairs, fields=("gcam",), options=BenchmarkOptions(gcam_keys=frozenset({"c2.1"}))
        )
        bootstrapped = evaluate(
            pairs,
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"c2.1"}), gcam_bootstrap_samples=100, gcam_seed=17
            ),
        )
        self.assertEqual(plain.rows, bootstrapped.rows)
        self.assertEqual(plain.details["gcam-articles"], bootstrapped.details["gcam-articles"])
        self.assertEqual(
            plain.tables["gcam-sampling"],
            [
                row
                for row in bootstrapped.tables["gcam-sampling"]
                if "publisher bootstrap" not in row.calculation
            ],
        )

    def test_regular_report_includes_named_language_groups_and_applicable_streams(self):
        options = BenchmarkOptions(
            gcam_keys=frozenset({"c2.1", "c28.1", "c23.17", "c23.33", "v24.3"}),
            gcam_languages={
                "c2.1": "eng",
                "c28.1": "fra",
                "c23.17": "spa",
                "c23.33": "glg",
                "v24.3": "fra",
            },
            gcam_bootstrap_samples=20,
            gcam_split_languages=True,
        )
        report = evaluate(
            [
                (item("wc:10,c2.1:1,c28.1:9,v24.3:9"), item("wc:10,c2.1:1", languages=["eng"])),
                (
                    item("wc:10,nwc:5,c2.1:2,c28.1:3,v24.3:5"),
                    item("wc:12,nwc:6,c2.1:2,c28.1:2,v24.3:5.5", languages=["eng", "fra"]),
                ),
                (
                    item("wc:10,nwc:8,c2.1:7,c23.17:1,v24.3:3"),
                    item("wc:0,nwc:8,c23.17:1", languages=["spa"]),
                ),
            ],
            fields=("gcam",),
            options=options,
        )
        summaries = {row.calculation: row for row in report.rows if row.field == "GCAM / languages"}
        self.assertEqual(summaries["English (eng)"].documents, 2)
        self.assertEqual(summaries["French (fra)"].documents, 1)
        self.assertEqual(summaries["Spanish (spa)"].documents, 1)
        self.assertEqual(summaries["Galician (glg)"].documents, 0)
        self.assertIsNone(summaries["Galician (glg)"].metrics["f1"])
        self.assertEqual(metric(report, "GCAM", "presence")["f1"], 1)
        french = next(
            row
            for row in report.rows
            if row.language == "fra" and row.calculation == "v24.3 / weighted score"
        )
        self.assertEqual(french.field, "GCAM / Hedonometer Multilingual")
        self.assertEqual(french.documents, 1)
        self.assertEqual(french.metrics["mae"], 0.5)
        self.assertTrue(any(row.language == "fra" for row in report.tables["gcam-sampling"]))
        self.assertFalse(
            any(row.language == "spa" and row.calculation == "wc" for row in report.rows)
        )
        with tempfile.TemporaryDirectory() as directory:
            write_report(report, directory)
            markdown = (Path(directory) / "metrics.md").read_text(encoding="utf8")
            self.assertIn("GCAM / languages", markdown)
            self.assertIn("GCAM / French (fra)", markdown)
            self.assertNotIn("language/French", markdown)
            self.assertIn("Hedonometer Multilingual / French (fra)", markdown)

    def test_automatic_groups_keep_unsupported_languages_and_dictionary_exclusions_visible(self):
        options = BenchmarkOptions(
            gcam_keys=frozenset({"c2.1", "c28.1"}),
            gcam_languages={"c2.1": "eng", "c28.1": "fra"},
            gcam_disabled_dictionaries=(28,),
        )
        report = evaluate(
            [
                (item("wc:5,nwc:4,c2.1:5,c28.1:2"), item("wc:0,nwc:4", languages=["fra"])),
                (item("wc:5,nwc:4,c2.1:5"), item("wc:0,nwc:4", languages=["ron"])),
            ],
            fields=("gcam",),
            options=options,
        )
        summaries = {
            row.calculation: row.metrics for row in report.rows if row.field == "GCAM / languages"
        }
        self.assertEqual(summaries["Romanian (ron)"]["documents"], 1)
        self.assertEqual(summaries["Romanian (ron)"]["compiled_dimensions"], 0)
        self.assertEqual(summaries["French (fra)"]["compiled_dimensions"], 0)
        self.assertIsNone(summaries["French (fra)"]["f1"])
        self.assertFalse(any(row["key"] == "c28.1" for row in report.details["gcam-dimensions"]))

    def test_explicit_english_filter_is_optional_and_does_not_create_native_groups(self):
        report = evaluate(
            [
                (
                    item("wc:5,nwc:4,c2.1:1,c28.1:1"),
                    item("wc:5,nwc:4,c2.1:1,c28.1:1", languages=["eng", "fra"]),
                ),
            ],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"c2.1", "c28.1"}),
                gcam_languages={"c2.1": "eng", "c28.1": "fra"},
                gcam_evaluation_language="eng",
            ),
        )
        self.assertEqual(
            [row.calculation for row in report.rows if row.field == "GCAM / languages"],
            ["English (eng)"],
        )
        self.assertFalse(any(row.subset.startswith("language/") for row in report.rows))

    def test_macro_document_and_active_counts_have_independent_denominators(self):
        pairs = [
            (item("wc:10,c2.1:2"), item("wc:10,c2.1:4")),
            (item("wc:10"), item("wc:10")),
            (item("wc:10,c18.1:1"), item("wc:10")),
        ]
        report = evaluate(
            pairs,
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"c2.1", "c18.1"}),
                gcam_approximate_dimensions=frozenset({"18.1"}),
            ),
        )
        self.assertAlmostEqual(metric(report, "GCAM", "presence")["f1"], 2 / 3)
        self.assertEqual(metric(report, "GCAM", "presence / label macro")["f1"], 0.5)
        agreement = metric(report, "GCAM", "presence / document agreement")
        self.assertEqual(agreement["mean_document_jaccard"], 0.5)
        self.assertEqual(agreement["empty_documents"], 1)
        self.assertAlmostEqual(
            metric(report, "GCAM / General Inquirer", "supported counts")["mae"], 2 / 3
        )
        active = metric(report, "GCAM / General Inquirer", "active supported counts")
        self.assertEqual(active["mae"], 2)
        self.assertEqual(active["paired_values"], 1)
        self.assertEqual(active["within_one_count"], 0)
        source_groups = {
            row.field: row
            for row in report.tables["gcam-sources"]
            if row.calculation == "supported presence"
        }
        self.assertEqual(source_groups["GCAM / source-backed"].metrics["f1"], 1)
        self.assertEqual(source_groups["GCAM / approximate"].metrics["f1"], 0)
        self.assertEqual(len(report.details["gcam-dimensions"]), 2)

    def test_score_availability_includes_defined_zero_and_missing_scores(self):
        report = evaluate(
            [
                (item("v10.1:0"), item("v10.1:0")),
                (item("v10.1:0.2"), item("")),
                (item(""), item("v10.1:0.1")),
            ],
            fields=("gcam",),
            options=BenchmarkOptions(gcam_keys=frozenset({"v10.1"})),
        )
        availability = metric(report, "GCAM / Sentiwordnet", "v10.1 / score availability")
        self.assertEqual(availability, {"precision": 0.5, "recall": 0.5, "f1": 0.5})
        score = metric(report, "GCAM / Sentiwordnet", "v10.1 / weighted score")
        self.assertEqual(score["mae"], 0)
        self.assertIsNone(score["ccc"])

    def test_native_language_scoring_excludes_english_and_unevaluated_streams(self):
        options = BenchmarkOptions(
            gcam_keys=frozenset({"c2.1", "c28.1"}),
            gcam_languages={"c2.1": "eng", "c28.1": "fra"},
            gcam_evaluation_language="fra",
        )
        report = evaluate(
            [
                (
                    item("wc:10,c2.1:9,c28.1:2"),
                    item("wc:11,nwc:4,c28.1:2", languages=["eng", "fra"]),
                ),
                (item("wc:10,c28.1:2"), item("wc:11", languages=["eng"])),
            ],
            fields=("gcam",),
            options=options,
        )
        self.assertEqual(metric(report, "GCAM", "presence")["f1"], 1)
        self.assertEqual(
            metric(report, "GCAM / Rid French", "supported counts")["paired_values"], 1
        )
        self.assertEqual(report.tables["gcam-sampling"][0].metrics["selected_documents"], 1)
        self.assertFalse(
            any(row.field == "GCAM" and row.calculation == "wc" for row in report.rows)
        )

    def test_length_filter_and_sampling_are_reproducible(self):
        pairs = [(item(f"wc:100,c2.1:{i}"), item(f"wc:{100 + i},c2.1:{i}")) for i in range(1, 21)]
        options = BenchmarkOptions(
            gcam_keys=frozenset({"c2.1"}),
            gcam_max_word_count_difference=0.1,
            gcam_sample_size=3,
            gcam_seed=19,
        )
        first = evaluate(pairs, fields=("gcam",), options=options)
        second = evaluate(pairs, fields=("gcam",), options=options)
        self.assertEqual(first.rows, second.rows)
        selection = first.tables["gcam-sampling"][0].metrics
        self.assertEqual(selection["candidate_documents"], 20)
        self.assertEqual(selection["size_eligible"], 10)
        self.assertEqual(selection["selected_documents"], 3)

    def test_publisher_intervals_retain_clusters_and_are_seeded(self):
        groups = {"a": [1, 2, 2, 0.5, 1, 1, 2], "b": [1, 1, 1, 1, 1, 0, 2]}
        self.assertEqual(publisher_intervals(groups, 200, 17), publisher_intervals(groups, 200, 17))
        self.assertEqual(publisher_intervals({"a": groups["a"]}, 200, 17)["micro_f1"], (None, None))
        low, high = publisher_intervals(groups, 200, 17)["micro_f1"]
        self.assertEqual((low, high), (0.5, 1))

    def test_report_writes_separate_source_sampling_and_dimension_files(self):
        report = evaluate(
            [(item("wc:10,c2.1:1"), item("wc:10,c2.1:1"))],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"c2.1"}), gcam_approximate_dimensions=frozenset()
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            write_report(report, directory)
            for name in (
                "gcam-sources.md",
                "gcam-sources.csv",
                "gcam-sampling.md",
                "gcam-sampling.csv",
                "gcam-dimensions.csv",
                "gcam-articles.csv",
            ):
                self.assertTrue((Path(directory) / name).is_file())
            source_report = (Path(directory) / "gcam-sources.md").read_text(encoding="utf-8")
            self.assertIn("# GCAM SOURCES", source_report)
            self.assertIn("Source classifications follow profile annotations", source_report)
            summary = (Path(directory) / "metrics.md").read_text(encoding="utf-8")
            self.assertIn("[gcam-sources](gcam-sources.md)", summary)
            with (Path(directory) / "gcam-dimensions.csv").open(
                encoding="utf-8", newline=""
            ) as stream:
                dimensions = list(csv.DictReader(stream))
            self.assertEqual(dimensions[0]["source_type"], "source-backed")

    def test_value_only_approximation_has_source_classification_without_count_presence(self):
        report = evaluate(
            [(item("v38.1:30"), item("v38.1:32"))],
            fields=("gcam",),
            options=BenchmarkOptions(
                gcam_keys=frozenset({"v38.1"}), gcam_approximate_dimensions=frozenset({"38.1"})
            ),
        )
        rows = report.tables["gcam-sources"]
        self.assertEqual(rows[0].metrics["compiled_dimensions"], 1)
        self.assertEqual(rows[0].metrics["count_dimensions"], 0)
        self.assertEqual(rows[1].metrics["mae"], 2)
        self.assertEqual(report.details["gcam-dimensions"][0]["source_type"], "approximate")

    def test_cache_preserves_language_metadata_and_migrates_old_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cache.sqlite3"
            with BenchmarkStore(path) as store:
                store.put(item("c28.1:2", languages=["eng", "fra"]), signature="row")
                store.commit()
            with BenchmarkStore(path) as store:
                self.assertEqual(
                    json.loads(store.cached("row").get("_gcam_languages")), ["eng", "fra"]
                )
            with closing(sqlite3.connect(path)) as db:
                db.execute('ALTER TABLE rows DROP COLUMN "_gcam_languages"')
                db.execute("PRAGMA user_version=1")
                db.commit()
            with BenchmarkStore(path) as store:
                self.assertEqual(store.cached("row").get("gcam"), "c28.1:2")
                self.assertIsNone(store.cached("row").get("_gcam_languages"))

    def test_new_options_reject_invalid_values(self):
        for updates in (
            {"gcam_sample_size": 0},
            {"gcam_bootstrap_samples": -1},
            {"gcam_max_word_count_difference": float("nan")},
            {"gcam_seed": True},
            {"gcam_split_languages": "yes"},
        ):
            with self.subTest(updates=updates), self.assertRaises(ValueError):
                BenchmarkOptions(**updates)

    def test_native_only_body_stays_native_after_sqlite_checkpoint(self):
        lexicon = _load(
            {
                "name": "fixture",
                "dimensions": [
                    {"key": "c2.1", "language": "eng", "words": ["cat"]},
                    {"key": "c28.1", "language": "fra", "words": ["chat"]},
                ],
            }
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "body.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "url": "https://example.org/story",
                        "text": "",
                        "original_text": "chat chat",
                        "original_language": "fra",
                        "translated": True,
                        "gcam_native_only": True,
                    }
                ),
                encoding="utf8",
            )
            with BenchmarkStore(root / "cache.sqlite3") as store:
                report = BenchmarkReport()
                bodies = load_corpus(
                    [path], report=report, include_translated=True, destination=store.corpus()
                )
                predictions = generate_predictions(
                    bodies,
                    [
                        GKGRow(
                            item("c28.1:2").values
                            | {"date": "20251101000000", "source_collection": "1"}
                        )
                    ],
                    options=PredictionOptions(fields=("gcam",), gcam_lexicon=lexicon),
                    report=report,
                    store=store,
                    signature="native-fixture",
                    progress=lambda _: None,
                )
                self.assertEqual(json.loads(predictions[0].get("_gcam_languages")), ["fra"])
                self.assertEqual(predictions[0].get("gcam"), "wc:0,nwc:2,c28.1:2")
                scored = evaluate(
                    [(item("c28.1:2"), predictions[0])],
                    fields=("gcam",),
                    options=BenchmarkOptions(
                        gcam_keys=frozenset({"c2.1", "c28.1"}),
                        gcam_languages={"c2.1": "eng", "c28.1": "fra"},
                        gcam_evaluation_language="fra",
                    ),
                )
                self.assertEqual(metric(scored, "GCAM", "presence")["f1"], 1)
                english = evaluate(
                    [(item("c28.1:2"), predictions[0])],
                    fields=("gcam",),
                    options=BenchmarkOptions(gcam_evaluation_language="eng"),
                )
                self.assertEqual(
                    english.tables["gcam-sampling"][0].metrics["selected_documents"], 0
                )


if __name__ == "__main__":
    unittest.main()
