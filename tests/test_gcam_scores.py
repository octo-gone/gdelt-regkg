import json
import math
import tempfile
import unittest
import zipfile
from pathlib import Path

from gdelt_regkg import GCAMLexicon, analyze_gcam, default_gcam_lexicon, fields
from gdelt_regkg.gcam import _load
from gdelt_regkg.scripts.benchmark_fields import benchmark_fields
from gdelt_regkg.scripts.build_gcam_lexicon import extend_gcam_lexicon, read_lexicoder_source
from gdelt_regkg.utils import read_resource_json


class WeightedGCAMTests(unittest.TestCase):
    def fixture(self):
        return GCAMLexicon("test", {}, {"v26.1": {"good": 2, "bad": -2, "neutral": 0}})

    def test_repeated_occurrence_mean_zero_and_no_match(self):
        result = analyze_gcam("good good bad unknown", lexicon=self.fixture())
        self.assertEqual(result.counts["c26.1"], 3)
        self.assertAlmostEqual(result.values["v26.1"], 2 / 3)
        self.assertIn("c26.1:3,v26.1:", result.to_gkg())
        self.assertEqual(
            analyze_gcam("good bad", lexicon=self.fixture()).to_gkg(), "wc:2,c26.1:2,v26.1:0"
        )
        self.assertEqual(
            analyze_gcam("neutral", lexicon=self.fixture()).to_gkg(), "wc:1,c26.1:1,v26.1:0"
        )
        self.assertEqual(analyze_gcam("unknown", lexicon=self.fixture()).to_gkg(), "wc:1")
        self.assertNotIn("v26.1", analyze_gcam("unknown", lexicon=self.fixture()).values)
        self.assertEqual(
            fields.extract_gcam("good", lexicon=self.fixture()), "wc:1,c26.1:1,v26.1:2"
        )

    def test_immutable_and_finite_validation(self):
        source = {"good": 2}
        lexicon = GCAMLexicon("test", {}, {"v26.1": source})
        source["good"] = -8
        self.assertEqual(lexicon.weighted_dimensions["v26.1"]["good"], 2)
        with self.assertRaises(TypeError):
            lexicon.weighted_dimensions["v26.1"]["good"] = 3
        for score in (math.nan, math.inf, True, "2"):
            with self.subTest(score=score), self.assertRaises(ValueError):
                GCAMLexicon("bad", {}, {"v26.1": {"good": score}})
        with self.assertRaises(ValueError):
            GCAMLexicon("bad", {"c26.1": frozenset({"good"})}, {"v26.1": {"good": 2}})
        with self.assertRaises(ValueError):
            GCAMLexicon("bad", {}, {"v26.1": {"GOOD": 2}})

    def test_whitespace_emoticons_punctuation_and_no_sentence_rules(self):
        lexicon = GCAMLexicon("test", {}, {"v26.1": {"good": 2, ":)": 1}}, {"v26.1": "whitespace"})
        result = analyze_gcam("GOOD!!! :) not good very good", lexicon=lexicon)
        self.assertEqual(result.counts["c26.1"], 4)
        self.assertEqual(result.values["v26.1"], 1.75)
        self.assertEqual(
            result.values, analyze_gcam("good very good not :) GOOD!!!", lexicon=lexicon).values
        )

    def test_json_old_profile_and_new_forms(self):
        self.assertEqual(len(_load(read_resource_json("lexicons", "gcam.v1.json")).dimensions), 8)
        lexicon = default_gcam_lexicon()
        self.assertEqual(len(lexicon.weighted_dimensions["v26.1"]), 7490)
        self.assertEqual(lexicon.weighted_dimensions["v26.1"]["good"], 1.9)
        with self.assertRaises(ValueError):
            _load({"name": "bad", "dimensions": [{"key": "v26.1", "scores": {}, "words": []}]})
        with self.assertRaises(ValueError):
            _load({"name": "bad", "dimensions": [{"key": "c3.1", "words": []}] * 2})

    def test_builders_record_sources_and_optional_synthetic_lexicoder(self):
        baseline = {"name": "original", "dimensions": [{"key": "c2.21", "words": ["hand"]}]}
        with tempfile.TemporaryDirectory() as directory:
            vader = Path(directory) / "vader.txt"
            vader.write_text("good\t2.0\t0.2\n: )\t1.0\n", encoding="utf-8")
            lexicoder = Path(directory) / "lexicoder.json"
            # Authored fixture, not copied Lexicoder vocabulary.
            lexicoder.write_text(
                json.dumps(
                    {
                        "negative": ["bad*", "badly"],
                        "positive": ["good*"],
                        "neg_negative": ["not bad*"],
                        "neg_positive": ["not good*"],
                    }
                ),
                encoding="utf-8",
            )
            payload = extend_gcam_lexicon(baseline, vader_source=vader, lexicoder_source=lexicoder)
            self.assertEqual(payload["vader_source"]["skipped_multiword_entries"], [": )"])
            self.assertIn("source_sha256", payload["vader_source"])
            self.assertFalse(payload["lexicoder_source"]["bundled_with_package"])
            result = analyze_gcam("not badly not good hand", lexicon=_load(payload))
            self.assertEqual([result.counts[f"c3.{i}"] for i in range(1, 5)], [1, 1, 1, 1])
            self.assertEqual(baseline["name"], "original")
            self.assertEqual(len(baseline["dimensions"]), 1)

    def test_value_benchmark_excludes_undefined_means_and_audits_one_sided_matches(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus, archive = root / "corpus.jsonl", root / "original.zip"
            rows, originals = [], []
            cases = [
                ("good bad", "wc:2,c26.1:2,v26.1:1"),
                ("unknown", "wc:1,c26.1:1,v26.1:-1"),
                ("good", "wc:1"),
                ("unknown", "wc:1"),
                ("good", "wc:1,c26.1:1"),
                ("good bad", "wc:2,v26.1:0"),
            ]
            for i, (text, original) in enumerate(cases):
                cells = [""] * 27
                cells[0], cells[4], cells[17] = str(i), f"https://example.org/{i}", original
                cells[10] = "deliberately malformed unrelated location"
                originals.append("\t".join(cells))
                rows.append({"record_id": str(i), "url": cells[4], "status": "ok", "text": text})
            corpus.write_text("\n".join(map(json.dumps, rows)) + "\n", encoding="utf-8")
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("original.csv", "\n".join(originals))
            report = benchmark_fields(
                corpus, [archive], gcam_only=True, gcam_lexicon=self.fixture()
            )
            values = report["gcam"]["values"]["v26.1"]
            self.assertEqual(values["paired_articles"], 2)
            self.assertEqual(values["value_mae"], 0.5)
            self.assertEqual(values["value_bias"], -0.5)
            self.assertEqual(
                values["audit"],
                {
                    "reference_matches_only": 1,
                    "local_matches_only": 1,
                    "both_no_matches": 1,
                    "missing_reference_value": 1,
                    "reference_match_count_unreported": 1,
                },
            )
            self.assertEqual(report["metrics"], {})
            self.assertEqual(report["audit"]["articles"], 6)
            self.assertEqual(report["gcam"]["dimensions"]["c26.1"]["articles"], 3)
            self.assertEqual(
                report["gcam"]["dimensions"]["c26.1"]["excluded_unreported_native_count"], 3
            )

    def test_original_zip_and_lc3_directory_with_authored_vocabulary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base = b"+negative#AA0000\r\nbad*\r\n+positive#008800\r\ngood*\r\n"
            negated = b"+neg_positive\n not good*\n+neg_negative\n not bad*\n"
            (root / "LSD2015.lc3").write_bytes(base)
            (root / "LSD2015_NEG.lc3").write_bytes(negated)
            archive = root / "source.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("LSDaug2015/LSD2015.lc3", base)
                stream.writestr("LSDaug2015/LSD2015_NEG.lc3", negated)
                stream.writestr("__MACOSX/LSD2015.lc3", b"ignored resource fork")
                stream.writestr("../../must-not-execute.scpt", b"ignored script")
            zipped, zip_metadata = read_lexicoder_source(archive)
            direct, direct_metadata = read_lexicoder_source(root)
            self.assertEqual(zipped, direct)
            self.assertEqual(zip_metadata["format"], "original-lc3-zip")
            self.assertEqual(direct_metadata["format"], "lc3-directory")
            self.assertEqual(len(zip_metadata["members"]), 2)
            self.assertTrue(all(len(m["sha256"]) == 64 for m in zip_metadata["members"]))
            self.assertFalse((root / "must-not-execute.scpt").exists())
            profile = extend_gcam_lexicon(
                {"name": "test", "dimensions": []}, lexicoder_source=archive
            )
            counts = analyze_gcam("not good not badly", lexicon=_load(profile)).counts
            self.assertEqual([counts[f"c3.{i}"] for i in range(1, 5)], [1, 1, 1, 1])
            self.assertEqual(
                profile["lexicoder_source"]["source_entries"],
                {
                    "negative": 1,
                    "positive": 1,
                    "neg_positive": 1,
                    "neg_negative": 1,
                },
            )

    def test_zip_rejects_missing_or_ambiguous_dictionary_members(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "source.zip"
            with zipfile.ZipFile(archive, "w") as stream:
                stream.writestr("LSD2015.lc3", "+negative\nbad*\n+positive\ngood*\n")
            with self.assertRaisesRegex(ValueError, "LSD2015_NEG"):
                read_lexicoder_source(archive)
            with zipfile.ZipFile(archive, "a") as stream:
                stream.writestr("another/LSD2015.lc3", "+negative\nbad*\n")
            with self.assertRaisesRegex(ValueError, "exactly one LSD2015.lc3"):
                read_lexicoder_source(archive)


if __name__ == "__main__":
    unittest.main()
