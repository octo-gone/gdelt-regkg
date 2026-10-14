"""Field-scoring, report-format and independent CLI integration checks."""

import contextlib
import csv
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg.benchmark import (
    BenchmarkOptions,
    BenchmarkReport,
    GKGRow,
    ResultRow,
    evaluate,
    write_report,
)
from gdelt_regkg.benchmark.inputs import align_rows, load_rows, resolve_inputs
from gdelt_regkg.benchmark.model import FIELD_NAMES
from gdelt_regkg.benchmark.report import markdown
from gdelt_regkg.cli import main
from gdelt_regkg.fields.ner import NameRules


def row(**updates):
    values = dict.fromkeys(FIELD_NAMES, "")
    values.update(
        recordid="20260101000000-1",
        date="20260101000000",
        source_collection="1",
        source="example.org",
        document="https://example.org/a",
    )
    return GKGRow(values | updates)


def find(report, field, calculation):
    return next(
        value for value in report.rows if value.field == field and value.calculation == calculation
    )


class BenchmarkTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)

    def write_rows(self, name, rows):
        path = self.root / name
        path.write_text(
            "".join(json.dumps(value.values) + "\n" for value in rows), encoding="utf-8"
        )
        return path

    def invoke(self, *arguments):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            main(["benchmark", *map(str, arguments)])

    def test_theme_micro_macro_and_supported_scopes_are_separate(self):
        report = evaluate(
            [(row(themes="A;B;"), row(themes="A;C;"))],
            fields=("themes",),
            options=BenchmarkOptions(theme_labels=frozenset({"A", "B"})),
        )
        result = find(report, "Themes", "all labels").metrics
        self.assertEqual(result["f1"], 0.5)
        self.assertAlmostEqual(
            find(report, "Themes", "all labels / label macro").metrics["f1"], 1 / 3
        )
        self.assertAlmostEqual(find(report, "Themes", "supported labels").metrics["f1"], 2 / 3)

    def test_repeated_counts_are_scored_as_a_multiset(self):
        count = "#".join(["KILL", "1", "people", "0", "", "", "", "", "", ""]) + ";"
        report = evaluate([(row(counts=count * 2), row(counts=count))], fields=("counts",))
        values = find(report, "Counts", "label + quantity").metrics
        self.assertEqual(values["precision"], 1)
        self.assertEqual(values["recall"], 0.5)
        self.assertAlmostEqual(values["f1"], 2 / 3)

    def test_offset_errors_are_computed_before_offset_gating(self):
        report = evaluate(
            [(row(enhanced_persons="Jane,0"), row(enhanced_persons="Jane,500"))],
            fields=("enhanced_persons",),
        )
        self.assertEqual(find(report, "Enhanced Persons", "mentions / content").metrics["f1"], 1)
        self.assertEqual(
            find(report, "Enhanced Persons", "mentions / exact offset").metrics["f1"], 0
        )
        self.assertEqual(
            find(report, "Enhanced Persons", "mentions / offset ≤100 chars").metrics["f1"], 0
        )
        self.assertEqual(
            find(report, "Enhanced Persons", "mentions / offset error").metrics["offset_mae_chars"],
            500,
        )

    def test_invalid_native_field_does_not_exclude_other_fields(self):
        report = evaluate(
            [(row(amounts="bad", themes="A;"), row(amounts="1,people,0", themes="A;"))],
            fields=("amounts", "themes"),
        )
        self.assertEqual(find(report, "Themes", "all labels").metrics["f1"], 1)
        self.assertEqual(find(report, "Amounts", "values").documents, 0)
        self.assertTrue(
            any(key[:3] == ("reference", "amounts", "malformed") for key in report.audit)
        )

    def test_invalid_prediction_is_not_removed_to_improve_f1(self):
        report = evaluate([(row(themes="A;"), row(themes="not-a-label"))], fields=("themes",))
        self.assertEqual(find(report, "Themes", "all labels").metrics["f1"], 0)
        self.assertEqual(find(report, "Themes", "all labels").documents, 1)

    def test_missing_field_is_distinct_from_empty_field(self):
        report = evaluate([(row(persons="Jane"), row(persons=None))], fields=("persons",))
        self.assertEqual(find(report, "Persons", "normalized identities").documents, 0)
        self.assertIsNone(find(report, "Persons", "normalized identities").metrics["f1"])
        report = evaluate([(row(persons="Jane"), row(persons=""))], fields=("persons",))
        self.assertEqual(find(report, "Persons", "normalized identities").metrics["f1"], 0)

    def test_gc_am_unreported_companion_is_not_zero(self):
        options = BenchmarkOptions(gcam_keys=frozenset({"c26.1"}))
        report = evaluate(
            [(row(gcam="wc:10,v26.1:0"), row(gcam="wc:10,c26.1:2,v26.1:0"))],
            fields=("gcam",),
            options=options,
        )
        self.assertIsNone(find(report, "GCAM / VADER", "supported counts").metrics["mae"])
        self.assertIsNone(find(report, "GCAM / VADER", "supported presence").metrics["f1"])
        self.assertEqual(find(report, "GCAM / VADER", "v26.1 / weighted score").metrics["mae"], 0)
        self.assertEqual(
            find(report, "GCAM", "v26.1 / weighted-score coverage").metrics["paired_values"], 1
        )

    def test_gc_am_known_sparse_zeros_and_unknown_dimensions_have_distinct_scopes(self):
        options = BenchmarkOptions(gcam_keys=frozenset({"c2.1"}))
        report = evaluate(
            [(row(gcam="wc:10,c2.1:2,c9.1:3"), row(gcam="wc:10"))],
            fields=("gcam",),
            options=options,
        )
        self.assertEqual(
            find(report, "GCAM / General Inquirer", "supported counts").metrics["mae"], 2
        )
        self.assertEqual(
            find(report, "GCAM / General Inquirer", "supported counts").metrics["count_wape"], 1
        )
        self.assertEqual(find(report, "GCAM", "coverage").metrics["dimension_coverage"], 0.5)
        self.assertEqual(find(report, "GCAM", "coverage").metrics["occurrence_coverage"], 0.4)

    def test_weighted_scores_require_both_defined_values(self):
        report = evaluate([(row(gcam="wc:1,v26.1:2"), row(gcam="wc:1"))], fields=("gcam",))
        self.assertIsNone(find(report, "GCAM / VADER", "v26.1 / weighted score").metrics["mae"])
        self.assertEqual(
            find(report, "GCAM", "v26.1 / weighted-score coverage").metrics["paired_values"], 0
        )

    def test_dates_retain_component_identity_and_count_occurrences(self):
        report = evaluate(
            [
                (
                    row(enhanced_dates="3#1#1#2026#0;3#1#1#2026#10"),
                    row(enhanced_dates="3,1,1,2026,0"),
                )
            ],
            fields=("dates",),
        )
        self.assertEqual(find(report, "Dates", "components").metrics["f1"], 1)
        self.assertAlmostEqual(find(report, "Dates", "occurrences / content").metrics["f1"], 2 / 3)

    def test_relaxed_results_are_opt_in_and_always_have_precision_recall(self):
        pair = (row(amounts="100,injured people,0"), row(amounts="105,injured person,0"))
        report = evaluate([pair], fields=("amounts",))
        self.assertFalse(any("relaxed" in value.calculation for value in report.rows))
        report = evaluate([pair], fields=("amounts",), options=BenchmarkOptions(relaxed=True))
        relaxed = next(
            value
            for value in report.rows
            if "relaxed" in value.calculation and "f1" in value.metrics
        )
        self.assertEqual(relaxed.metrics["f1"], 1)
        for value in report.rows:
            if "f1" in value.metrics:
                self.assertIn("precision", value.metrics)
                self.assertIn("recall", value.metrics)

    def test_metadata_has_one_validity_row_per_field(self):
        report = evaluate(
            [(row(), row(recordid="bad", date="20260230000000", source_collection="9"))],
            fields=("metadata",),
        )
        self.assertEqual(len(report.rows), 5)
        self.assertEqual(find(report, "Record ID", "validity").metrics["validity_rate"], 0)
        self.assertEqual(find(report, "Date", "validity").metrics["validity_rate"], 0)
        self.assertEqual(find(report, "Source collection", "validity").metrics["validity_rate"], 0)

    def test_identical_complete_rows_score_all_field_types_and_optional_diagnostics(self):
        count = "#".join(["KILL", "1", "people", "0", "", "", "", "", "", ""])
        value = row(
            counts=count + ";",
            enhanced_counts=count + "#0;",
            themes="A;",
            enhanced_themes="A,0;",
            persons="Jane Doe",
            enhanced_persons="Jane Doe,0",
            organizations="Acme",
            enhanced_organizations="Acme,0",
            locations="4#Paris#FR#A8#48.85#2.35#-1456928",
            enhanced_locations="4#Paris#FR#A8##48.85#2.35#-1456928#0",
            tone="0,1,1,2,3,4,2",
            enhanced_dates="3#1#1#2026#0",
            gcam="wc:2,c2.1:1,v26.1:0",
            sharing_image="https://example.org/a.jpg",
            related_images="https://example.org/a.jpg",
            social_image_embeds="https://example.org/image",
            social_video_embeds="https://example.org/video",
            quotations="0|11|said|hello world",
            all_names="Jane Doe,0",
            amounts="1,people,0",
            translation="srclc:fra;eng:fixture",
            extras_xml='<A value="1">text</A>',
        )
        report = evaluate(
            [(value, value)],
            options=BenchmarkOptions(
                relaxed=True,
                diagnostics=True,
                gcam_keys=frozenset({"c2.1", "c26.1"}),
                theme_labels=frozenset({"A"}),
            ),
        )
        for result in report.rows:
            if result.metrics.get("f1") is not None:
                with self.subTest(row=result.name):
                    self.assertEqual(result.metrics["precision"], 1)
                    self.assertEqual(result.metrics["recall"], 1)
                    self.assertEqual(result.metrics["f1"], 1)
        self.assertEqual(
            find(report, "Enhanced locations", "coordinate error on identity matches").metrics[
                "distance_median_km"
            ],
            0,
        )
        self.assertEqual(find(report, "Tone", "tone").metrics["mae"], 0)

    def test_subset_audits_remain_separate_from_whole_dataset_counts(self):
        pairs = [(row(themes="bad-label"), row(themes="A;"))]
        report = evaluate(pairs, fields=("themes",))
        evaluate(pairs, fields=("themes",), report=report, subset="month/202601")
        self.assertEqual(sum(count for key, count in report.audit.items() if key[4] == "all"), 1)
        self.assertEqual(
            sum(count for key, count in report.audit.items() if key[4] == "month/202601"), 1
        )

    def test_xml_agreement_ignores_attribute_order_but_checks_content(self):
        report = evaluate(
            [(row(extras_xml='<A a="1" b="2">x</A>'), row(extras_xml='<A b="2" a="1">x</A>'))],
            fields=("extras_xml",),
        )
        self.assertEqual(
            find(report, "Extra XML", "canonical structure").metrics["exact_agreement"], 1
        )

    def test_conflicting_duplicate_keys_are_excluded_not_paired_by_row_order(self):
        report = BenchmarkReport()
        reference = [row(themes="A;"), row(themes="B;"), row(document="https://example.org/b")]
        prediction = [row(themes="A;"), row(document="https://example.org/b")]
        pairs = align_rows(reference, prediction, report=report)
        self.assertEqual(len(pairs), 1)
        self.assertTrue(any(key[2] == "conflicting_key" for key in report.audit))

    def test_identical_duplicates_are_deduplicated_and_unmatched_rows_are_audited(self):
        report = BenchmarkReport()
        pairs = align_rows(
            [row(), row(), row(document="https://example.org/b")], [row()], report=report
        )
        self.assertEqual(len(pairs), 1)
        self.assertEqual(find(report, "Alignment", "documents").metrics["recall"], 0.5)

    def test_plain_gzip_zip_and_uppercase_json_inputs_agree(self):
        values = row().values
        text = "\t".join(values[name] for name in FIELD_NAMES) + "\n"
        plain = self.root / "rows.tsv"
        plain.write_text(text, encoding="utf-8")
        zipped = self.root / "rows.zip"
        with zipfile.ZipFile(zipped, "w") as archive:
            archive.writestr("rows.csv", text)
            archive.writestr("README.txt", "not a GKG row")
        compressed = self.root / "rows.tsv.gz"
        with gzip.open(compressed, "wt", encoding="utf-8") as stream:
            stream.write(text)
        for path in (plain, zipped, compressed):
            result = load_rows([path], report=BenchmarkReport(), side="reference", strict=True)
            self.assertEqual(result[0].values, values)
        from gdelt_regkg.utils import GKG_COLUMNS

        uppercase = self.root / "rows.jsonl"
        uppercase.write_text(
            json.dumps(dict(zip(GKG_COLUMNS, (values[name] for name in FIELD_NAMES)))) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(
            load_rows([uppercase], report=BenchmarkReport(), side="reference")[0].values, values
        )

    def test_directory_discovery_is_recursive_sorted_and_deduplicates_overlapping_paths(self):
        nested = self.root / "nested"
        nested.mkdir()
        first = self.write_rows("a.JSONL", [row()])
        second = self.write_rows("nested/b.jsonl", [row(document="https://example.org/b")])
        (self.root / "README.md").write_text("Ignored", encoding="utf-8")
        self.assertEqual(
            resolve_inputs([self.root, nested, first]), [first.resolve(), second.resolve()]
        )
        rows = load_rows(
            [self.root, first], report=BenchmarkReport(), side="reference", strict=True
        )
        self.assertEqual(len(rows), 2)

    def test_directory_inputs_reject_empty_missing_and_explicit_unsupported_files(self):
        unsupported = self.root / "rows.json"
        unsupported.write_text("[]", encoding="utf-8")
        for path, message in (
            (self.root, "No supported input files"),
            (unsupported, "Unsupported input extension"),
            (self.root / "missing", "does not exist"),
        ):
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, message):
                resolve_inputs([path])
        with self.assertRaisesRegex(ValueError, "at least one"):
            resolve_inputs([])

    def test_compression_does_not_accept_arbitrary_csv_or_json_schemas(self):
        invalid_csv = self.root / "bad.CSV.GZ"
        with gzip.open(invalid_csv, "wt", encoding="utf-8") as stream:
            stream.write("url,tone\nhttps://example.org/a,0\n")
        with self.assertRaisesRegex(ValueError, "27 tab-separated"):
            load_rows([invalid_csv], report=BenchmarkReport(), side="reference", strict=True)
        invalid_json = self.root / "bad.JSONL"
        invalid_json.write_text('[{"document":"https://example.org/a"}]\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "requires an object"):
            load_rows([invalid_json], report=BenchmarkReport(), side="reference", strict=True)
        archive = self.root / "empty.ZIP"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("readme.txt", "No rows")
        with self.assertRaisesRegex(ValueError, "no CSV, TSV or JSONL"):
            load_rows([archive], report=BenchmarkReport(), side="reference", strict=True)

    def test_cli_matches_directory_rows_across_file_boundaries_and_hashes_discovered_files(self):
        reference_dir, prediction_dir = self.root / "reference", self.root / "prediction"
        (reference_dir / "nested").mkdir(parents=True)
        prediction_dir.mkdir()
        first = row(themes="A;")
        second = row(document="https://example.org/b", themes="B;")
        reference = self.write_rows("reference/nested/batch.JSONL", [first, second])
        predicted = prediction_dir / "one.ZIP"
        with zipfile.ZipFile(predicted, "w") as archive:
            archive.writestr("nested/rows.JSONL", json.dumps(second.values) + "\n")
        compressed = prediction_dir / "two.TSV.GZ"
        with gzip.open(compressed, "wt", encoding="utf-8") as stream:
            stream.write("\t".join(first.values[name] for name in FIELD_NAMES) + "\n")
        self.invoke(
            "--reference",
            reference_dir,
            reference,
            "--prediction",
            prediction_dir,
            "--fields",
            "themes",
            "--output",
            self.root / "output",
            "--resources-dir",
            self.root / "missing",
        )
        with (self.root / "output/metrics.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        score = next(
            value
            for value in rows
            if value["field"] == "Themes" and value["calculation"] == "all labels"
        )
        self.assertEqual((score["documents"], score["f1"]), ("2", "1.0"))
        run = (self.root / "output/run.md").read_text(encoding="utf-8")
        for path in (reference, predicted, compressed):
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), run)
        self.assertIn("scipy_version", run)

    def test_cli_explains_missing_benchmark_dependencies(self):
        stderr = io.StringIO()
        with (
            patch(
                "gdelt_regkg.dependencies.import_module", side_effect=ModuleNotFoundError("scipy")
            ),
            contextlib.redirect_stderr(stderr),
            self.assertRaises(SystemExit) as error,
        ):
            main(["benchmark", "--reference", "native.tsv", "--prediction", "predicted.tsv"])
        self.assertEqual(error.exception.code, 2)
        self.assertIn("install gdelt-regkg[benchmark]", stderr.getvalue())

    def test_reports_have_five_markdown_slots_and_full_precision_csv(self):
        report = BenchmarkReport(
            rows=[
                ResultRow(
                    "Example", "calculation", {"precision": 1 / 3, "recall": 1 / 2, "f1": 0.4}, 2
                )
            ]
        )
        write_report(report, self.root)
        self.assertEqual(
            {p.name for p in self.root.iterdir()},
            {"metrics.md", "metrics.csv", "audit.csv", "run.md"},
        )
        markdown = (self.root / "metrics.md").read_text(encoding="utf-8")
        self.assertIn("**Precision**<br>0.3333", markdown)
        self.assertIn("| **Example** |  |  |  |  |  |", markdown)
        self.assertIn("**F1**<br>0.4000 |  |  |", markdown)
        with (self.root / "metrics.csv").open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(len(reader.fieldnames), len(set(reader.fieldnames)))
            result = next(reader)
        self.assertEqual(float(result["precision"]), 1 / 3)

        report.rows.append(ResultRow("Example", "coverage", {"documents": 2}, 2))
        write_report(report, self.root)
        with (self.root / "metrics.csv").open(encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            self.assertEqual(reader.fieldnames.count("documents"), 1)
            self.assertEqual(list(reader)[-1]["documents"], "2")

    def test_markdown_groups_metric_layouts_and_distinguishes_missing_from_unused_cells(self):
        rows = [
            ResultRow("Counts", "labels", {"precision": None, "recall": 0.0, "f1": 0.0}),
            ResultRow("Counts", "labels / coverage", {"documents": 2, "reference_support": 3}),
            ResultRow("Counts", "object", {"precision": 0.5, "recall": None, "f1": None}),
            ResultRow("Counts", "object / coverage", {"documents": 2, "reference_support": 4}),
            ResultRow("Tone", "validity", {"validity_rate": 0.5}),
        ]
        report = BenchmarkReport(rows=list(rows))
        rendered = markdown(report)
        self.assertEqual(report.rows, rows)
        self.assertLess(rendered.index("| object |"), rendered.index("| labels / coverage |"))
        self.assertEqual(rendered.count("**Precision**"), 1)
        self.assertIn(
            "| labels | **Precision**<br>- | **Recall**<br>0.0000 | **F1**<br>0.0000 |  |  |",
            rendered,
        )
        self.assertIn("| object | 0.5000 | - | - |  |  |", rendered)
        self.assertIn("| object / coverage | 2 | 4 |  |  |  |", rendered)
        self.assertIn("| validity | **Validity**<br>50.000% |  |  |  |  |", rendered)
        write_report(report, self.root)
        with (self.root / "metrics.csv").open(encoding="utf-8", newline="") as stream:
            self.assertEqual(
                [r["calculation"] for r in csv.DictReader(stream)], [r.calculation for r in rows]
            )

    def test_markdown_repeats_labels_for_new_fields_subsets_units_and_continuation_layouts(self):
        report = BenchmarkReport(
            rows=[
                ResultRow("Tone", "tone", {"mae": 1.0}, unit="points"),
                ResultRow("Tone", "word count", {"mae": 2.0}, unit="words"),
                ResultRow("Tone", "tone", {"mae": None}, unit="points", subset="month/202601"),
                ResultRow("GCAM", "score", {"mae": 3.0}, unit="points"),
                ResultRow("Wide", "first", dict.fromkeys(("a", "b", "c", "d", "e", "f"), 1)),
                ResultRow("Wide", "second", dict.fromkeys(("a", "b", "c", "d", "e", "f"), 2)),
            ]
        )
        rendered = markdown(report)
        self.assertEqual(rendered.count("**MAE**"), 4)
        self.assertIn("| **month/202601 / Tone** |", rendered)
        self.assertIn("| tone | **MAE**<br>- |  |  |  |  |", rendered)
        self.assertIn("**MAE**<br>2.0000 words", rendered)
        self.assertIn("| first / continued 2 | **F**<br>1 |  |  |  |  |", rendered)
        self.assertIn("| second / continued 2 | 2 |  |  |  |  |", rendered)
        self.assertTrue(
            all(line.count("|") == 7 for line in rendered.splitlines() if line.startswith("|"))
        )

    def test_cli_writes_tables_and_strata(self):
        reference = self.write_rows("reference.jsonl", [row(themes="A;")])
        prediction = self.write_rows("prediction.jsonl", [row(themes="A;B;")])
        self.invoke(
            "--reference",
            reference,
            "--prediction",
            prediction,
            "--fields",
            "themes",
            "--stratify",
            "month",
            "--min-stratum",
            "1",
            "--output",
            self.root / "output",
            "--resources-dir",
            self.root / "missing",
        )
        with (self.root / "output/metrics.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertTrue(any(value["subset"] == "month/202601" for value in rows))

    def test_cli_rejects_bad_options_before_reading_inputs(self):
        for options in (
            ("--offset-tolerance", "-1"),
            ("--number-tolerance", "nan"),
            ("--fields", "unknown"),
        ):
            with (
                self.subTest(options=options),
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main(["benchmark", "--reference", "absent", "--prediction", "absent", *options])
            self.assertEqual(error.exception.code, 2)

    def test_excluding_an_enhanced_partner_does_not_reintroduce_it_during_scoring(self):
        reference = self.write_rows("reference.jsonl", [row(themes="A;", enhanced_themes="A,0;")])
        self.invoke(
            "--reference",
            reference,
            "--prediction",
            reference,
            "--fields",
            "themes",
            "--exclude",
            "enhanced_themes",
            "--output",
            self.root / "output",
            "--resources-dir",
            self.root / "missing",
        )
        with (self.root / "output/metrics.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertFalse(any(value["field"] == "Enhanced Themes" for value in rows))

    def test_saved_body_without_record_id_preserves_supplied_translation_provenance(self):
        provenance = "srclc:fra;eng:fixture"
        reference = self.write_rows("reference.jsonl", [row(translation=provenance)])
        corpus_dir = self.root / "bodies"
        corpus_dir.mkdir()
        corpus = corpus_dir / "corpus.jsonl"
        corpus.write_text(
            json.dumps({"url": row().get("document"), "text": "Hello.", "translation": provenance})
            + "\n",
            encoding="utf-8",
        )
        self.invoke(
            "--reference",
            reference,
            "--corpus",
            corpus_dir,
            "--fields",
            "translation",
            "--output",
            self.root / "output",
            "--resources-dir",
            self.root / "missing",
        )
        with (self.root / "output/metrics.csv").open(encoding="utf-8", newline="") as stream:
            result = next(
                value
                for value in csv.DictReader(stream)
                if value["calculation"] == "source language"
            )
        self.assertEqual(result["exact_agreement"], "1.0")

    def test_saved_body_mode_marks_missing_broad_names(self):
        reference = self.write_rows("reference.jsonl", [row(persons="Jane Doe")])
        text = "Jane Doe spoke."
        checksum = hashlib.sha256(text.encode()).hexdigest()
        corpus = self.root / "corpus.jsonl"
        corpus.write_text(
            json.dumps(
                {
                    "record_id": row().get("recordid"),
                    "url": row().get("document"),
                    "text": text,
                    "text_sha256": checksum,
                }
            )
            + "\n",
            encoding="utf-8",
        )
        cache = self.root / "ner.jsonl"
        cache.write_text(
            json.dumps(
                {
                    "record_id": row().get("recordid"),
                    "url": row().get("document"),
                    "text_sha256": checksum,
                    "entity_mentions": [
                        {"text": "Jane Doe", "start": 0, "end": 8, "label": "PERSON"}
                    ],
                }
            )
            + "\n",
            encoding="utf-8",
        )
        with patch("gdelt_regkg.benchmark.corpus.default_name_rules", return_value=NameRules()):
            self.invoke(
                "--reference",
                reference,
                "--corpus",
                corpus,
                "--ner-cache",
                cache,
                "--fields",
                "ner",
                "all_names",
                "--output",
                self.root / "output",
            )
        with (self.root / "output/metrics.csv").open(encoding="utf-8", newline="") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(
            next(
                value
                for value in rows
                if value["field"] == "Persons" and value["calculation"] == "normalized identities"
            )["f1"],
            "1.0",
        )
        self.assertTrue(
            any(value["field"] == "All names" and value["documents"] == "0" for value in rows)
        )


if __name__ == "__main__":
    unittest.main()
