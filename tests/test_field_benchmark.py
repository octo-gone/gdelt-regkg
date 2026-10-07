import gzip
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from gdelt_regkg import EntityMention, NERResult
from gdelt_regkg.gcam import GCAMLexicon
from gdelt_regkg.scripts.benchmark_fields import (
    benchmark_fields,
    bootstrap_f1,
    parse_quotation_reference,
    parse_references,
    score_sets,
)
from gdelt_regkg.scripts.build_gazetteer import build_gazetteer
from gdelt_regkg.scripts.build_resources import build_resources
from gdelt_regkg.utils import read_resource_json, resource_path


class FieldBenchmarkTests(unittest.TestCase):
    def test_quotation_content_verb_and_coordinates(self):
        content, verbs = parse_quotation_reference(
            "10|12|said|We're ready.#100|12|SAID|WE’RE  READY."
        )
        self.assertEqual(content, {"we're ready."})
        self.assertEqual(verbs, {("we're ready.", "said")})
        for cell in ("bad", "-1|3|said|yes", "0|0|said|yes", "0|3|said| "):
            with self.assertRaises(ValueError):
                parse_quotation_reference(cell)
        self.assertEqual(parse_quotation_reference(""), (set(), set()))

    def test_bootstrap_empty_perfect_and_reproducible(self):
        self.assertIsNone(bootstrap_f1([], samples=100, seed=1))
        self.assertEqual(bootstrap_f1([({1}, {1}), ({2}, {2})], samples=100, seed=1), [1, 1])
        rows = [({1, 2}, {1}), ({3}, {4}), (set(), {5})]
        interval = bootstrap_f1(rows, samples=100, seed=1729)
        self.assertEqual(interval, bootstrap_f1(rows, samples=100, seed=1729))
        self.assertLessEqual(interval[0], score_sets(rows)["f1"])
        self.assertGreaterEqual(interval[1], score_sets(rows)["f1"])

    def test_fields_only_and_malformed_quote_exclusions(self):
        text = 'Jane said, "We are ready."'
        ner = Mock(name="fixture", analyze=Mock(return_value=NERResult(text, ())))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, archive = root / "corpus.jsonl", root / "original.zip"
            cells = self.cells()
            cells[22] = "12|13|said|We are ready."
            corpus.write_text(
                json.dumps(
                    {
                        "record_id": cells[0],
                        "url": cells[4],
                        "status": "ok",
                        "text": text,
                        "source": "example.org",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with zipfile.ZipFile(archive, "w") as stream:
                unrelated = list(cells)
                unrelated[4] = "https://example.org/unrelated"
                stream.writestr("a.csv", "\t".join(unrelated) + "\n" + "\t".join(cells))
            with patch("gdelt_regkg.scripts.benchmark_fields.analyze_gcam") as gcam:
                report = benchmark_fields(
                    corpus, [archive], recognizer=ner, fields_only=True, bootstrap_samples=100
                )
                gcam.assert_not_called()
            self.assertIsNone(report["gcam"])
            self.assertEqual(report["audit"]["ignored_same_id_other_url_records"], 1)
            self.assertEqual(report["metrics"]["quotations"]["f1"], 1)
            self.assertEqual(report["metrics"]["quotations_with_verbs"]["f1_ci95"], [1, 1])
            self.assertEqual(report["metrics"]["quotations"]["reference_positive_articles"], 1)
            cells[22] = "malformed"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("a.csv", "\t".join(cells))
            report = benchmark_fields(corpus, [archive], recognizer=ner, fields_only=True)
            self.assertEqual(report["audit"]["excluded_malformed_quotations"], 1)
            self.assertEqual(report["metrics"]["locations"]["articles"], 1)
            self.assertEqual(report["metrics"]["quotations"]["articles"], 0)
            cells[10] = "0#bad#location"
            cells[22] = "12|13|said|We are ready."
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("a.csv", "\t".join(cells))
            report = benchmark_fields(corpus, [archive], recognizer=ner, fields_only=True)
            self.assertEqual(report["audit"]["excluded_malformed_locations"], 1)
            self.assertEqual(report["metrics"]["locations"]["articles"], 0)
            self.assertEqual(report["metrics"]["dates"]["articles"], 1)
            self.assertEqual(report["metrics"]["quotations"]["f1"], 1)
            with self.assertRaises(ValueError):
                benchmark_fields(
                    corpus, [archive], recognizer=ner, fields_only=True, gcam_only=True
                )

    def test_coverage_pairing_and_reference_cache_invalidation(self):
        lexicon = GCAMLexicon("fixture", {"c2.21": frozenset({"hand"})}, {"v26.1": {"good": 1}})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, archive = root / "corpus.jsonl", root / "original.zip"
            cells = self.cells()
            corpus.write_text(
                json.dumps(
                    {"record_id": cells[0], "url": cells[4], "status": "ok", "text": "hand good"}
                )
                + "\n",
                encoding="utf-8",
            )
            cells[17] = "wc:2,c2.21:1,c26.1:1,v26.1:0,c9.1:3"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("original.csv", "\t".join(cells))
            report = benchmark_fields(corpus, [archive], gcam_only=True, gcam_lexicon=lexicon)
            coverage = report["gcam"]["coverage"]
            self.assertEqual(coverage["implemented_dimensions"], 2)
            self.assertEqual(coverage["native_document_dimension_assignments"], 3)
            self.assertEqual(coverage["supported_native_document_dimension_assignments"], 2)
            self.assertEqual(coverage["native_count_occurrence_fraction"], 2 / 5)
            self.assertEqual(report["gcam"]["families"]["2"]["count_wape"], 0)
            cells[17] = "wc:2,c2.21:3,c9.1:3"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("original.csv", "\t".join(cells))
            changed = benchmark_fields(corpus, [archive], gcam_only=True, gcam_lexicon=lexicon)
            self.assertEqual(changed["gcam"]["dimensions"]["c2.21"]["count_mae"], 2)
            self.assertNotEqual(report["archives"], changed["archives"])

    def test_explicit_directory_uses_selected_geographic_profile(self):
        text = "France"
        ner = Mock(
            name="fixture",
            analyze=Mock(
                return_value=NERResult(text, (EntityMention("France", "LOCATION", 0, 6),))
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, archive = root / "corpus.jsonl", root / "original.zip"
            cells = self.cells()
            corpus.write_text(
                json.dumps({"record_id": cells[0], "url": cells[4], "status": "ok", "text": text})
                + "\n",
                encoding="utf-8",
            )
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("original.csv", "\t".join(cells))
            (root / "lexicons").mkdir()
            (root / "defaults.json").write_text(
                json.dumps({"locations": "custom-places.json"}), encoding="utf-8"
            )
            (root / "lexicons" / "custom-places.json").write_text(
                json.dumps(build_gazetteer([archive])), encoding="utf-8"
            )
            report = benchmark_fields(
                corpus, [archive], recognizer=ner, fields_only=True, resources_dir=root
            )
            self.assertEqual(report["metrics"]["locations"]["f1"], 1)
            self.assertEqual(set(report["resource_sha256"]), {"custom-places.json"})

    def cells(self):
        cells = [""] * 27
        cells[0] = "20261001091500-1"
        cells[4] = "https://example.org/a"
        cells[10] = "1#France#FR#FR##46#2#FR#0"
        cells[16] = "1#0#0#2025#10"
        cells[17] = "wc:8,c2.21:2"
        cells[23] = "France,0;France,22"
        cells[24] = "12,trucks,15;12,trucks,40"
        return cells

    def test_reference_parsing_deduplication_and_separator_compatibility(self):
        cells = self.cells()
        result = parse_references(cells)
        self.assertEqual(len(result["all_names"]), 1)
        self.assertEqual(len(result["amounts"]), 1)
        self.assertEqual(result["locations"], {("1", "FR", "FR", "FR")})
        self.assertEqual(result["dates"], {(1, 0, 0, 2025)})
        cells[16] = "1,0,0,2025,10"
        self.assertEqual(parse_references(cells), result)
        cells[17] += ",wc:8"
        with self.assertRaises(ValueError):
            parse_references(cells)
        cells[17] = "wc:nan"
        with self.assertRaises(ValueError):
            parse_references(cells)

    def test_scores_and_missing_reference_audit(self):
        self.assertEqual(score_sets([({1, 2}, {2, 3})])["f1"], 0.5)
        self.assertIsNone(score_sets([])["f1"])
        text = "France in 2025 sent 12 trucks."
        ner = Mock(
            name="fixture",
            analyze=Mock(
                return_value=NERResult(text, (EntityMention("France", "LOCATION", 0, 6),))
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "results.jsonl"
            row = {
                "record_id": self.cells()[0],
                "status": "ok",
                "text": text,
                "url": self.cells()[4],
            }
            corpus.write_text(json.dumps(row) + "\n", encoding="utf-8")
            archive = root / "archive.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("a.csv", "\t".join(self.cells()) + "\n")
            report = benchmark_fields(corpus, [archive], recognizer=ner)
            self.assertEqual(report["audit"]["articles"], 1)
            self.assertEqual(report["metrics"]["locations"]["f1"], 1)
            self.assertEqual(report["metrics"]["amounts"]["f1"], 1)
            self.assertEqual(report["metrics"]["dates"]["f1"], 1)
            self.assertEqual(report["gcam"]["dimensions"]["c2.21"]["count_mae"], 2)
            payload = build_gazetteer([archive])
            self.assertEqual(payload["places"][0]["country_code"], "FR")
            self.assertIn("sha256", payload["sources"][0])
            row["record_id"] = "missing"
            corpus.write_text(json.dumps(row) + "\n", encoding="utf-8")
            report = benchmark_fields(corpus, [archive], recognizer=ner)
            self.assertEqual(report["audit"]["missing_original_record"], 1)
            self.assertIsNone(report["metrics"]["dates"]["f1"])

    def test_local_resources_validate_and_builder_requires_sources(self):
        from jsonschema import Draft202012Validator

        for filename, schema in (
            ("locations.v1.json.gz", "gazetteer.schema.json"),
            ("gcam.v1.json", "gcam-lexicon.schema.json"),
            ("gcam.v2.json", "gcam-lexicon.schema.json"),
            ("gcam.v3.json.gz", "gcam-lexicon.schema.json"),
        ):
            data = read_resource_json("lexicons", filename)
            validator = Draft202012Validator(read_resource_json("schemas", schema))
            validator.validate(data)
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "Required source inputs"):
                build_resources(directory, fields=("locations", "gcam"))
            self.assertFalse((Path(directory) / "lexicons").exists())


if __name__ == "__main__":
    unittest.main()
