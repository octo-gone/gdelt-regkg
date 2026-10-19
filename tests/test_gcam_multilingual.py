"""Language routing, native source formats and dual-text benchmark contracts."""

import csv
import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg import RecordMetadata, Resources, generate_gkg
from gdelt_regkg.benchmark.checkpoint import article_signature
from gdelt_regkg.benchmark.corpus import PredictionOptions, generate_predictions, load_corpus
from gdelt_regkg.benchmark.engine import evaluate
from gdelt_regkg.benchmark.inputs import json_row
from gdelt_regkg.benchmark.model import BenchmarkOptions, BenchmarkReport, GKGRow
from gdelt_regkg.builders.gcam_imports import add_ml_senticon
from gdelt_regkg.builders.gcam_multilingual import (
    LABMT_LANGUAGES,
    add_labmt_languages,
    add_rid,
    add_senticon_languages,
    add_spanish_anew,
)
from gdelt_regkg.fields.gcam import GCAMLexicon, _load, analyze_gcam
from gdelt_regkg.fields.gcam_tokens import tokenize_gcam
from gdelt_regkg.pipeline import OVERRIDABLE_COLUMNS


def book(rows):
    return {
        "source_sha256": "authored",
        "dimensions": {
            key: {"category": category, "language": language, "dictionary": "authored"}
            for key, category, language in rows
        },
    }


class MultilingualGCAMTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.baseline = {"name": "authored", "dimensions": []}

    def fixture(self):
        return _load(
            {
                "name": "multilingual",
                "dimensions": [
                    {"key": "c2.1", "words": ["chat"]},
                    {"key": "c28.1", "words": ["chat"], "language": "fra"},
                    {"key": "v23.1", "scores": {"chat": 0.5}, "language": "cat"},
                    {"key": "v23.17", "scores": {"chat": 0.8}, "language": "spa"},
                ],
            }
        )

    def test_language_routing_dual_text_and_shared_dictionary_ids(self):
        lexicon = self.fixture()
        self.assertEqual(analyze_gcam("chat", lexicon=lexicon).to_gkg(), "wc:1,c2.1:1")
        self.assertEqual(
            analyze_gcam(
                "", lexicon=lexicon, original_text="chat", original_language="fr"
            ).to_gkg(),
            "wc:0,nwc:1,c28.1:1",
        )
        result = analyze_gcam(
            "chat chat", lexicon=lexicon, original_text="chat", original_language="French"
        )
        self.assertEqual(result.to_gkg(), "wc:2,nwc:1,c2.1:2,c28.1:1")
        self.assertNotIn("v23.1", result.implemented_dimensions)
        spanish = analyze_gcam("", lexicon=lexicon, original_text="chat", original_language="es")
        self.assertEqual(spanish.values, {"v23.17": 0.8})
        self.assertNotIn("v23.1", spanish.implemented_dimensions)
        self.assertEqual(
            analyze_gcam(
                "",
                lexicon=lexicon,
                original_text="chat",
                original_language="es",
                disabled_dictionaries=(23,),
            ).to_gkg(),
            "wc:0,nwc:1",
        )
        self.assertIs(lexicon.for_language("fr"), lexicon.for_language("fra"))

    def test_missing_original_labels_chinese_and_incompatible_language_metadata(self):
        lexicon = self.fixture()
        for kwargs in (
            {"original_text": "chat"},
            {"original_language": "fra"},
            {"original_text": "chat", "original_language": "eng"},
            {"original_text": "chat", "original_language": "unknown"},
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                analyze_gcam("chat", lexicon=lexicon, **kwargs)
        with self.assertRaises(TypeError):
            analyze_gcam("chat", lexicon=lexicon, language="fr")
        with self.assertRaisesRegex(ValueError, "same language"):
            GCAMLexicon(
                "bad",
                {},
                weighted_dimensions={"v23.1": {"chat": 1}},
                languages={"v23.1": "cat", "c23.1": "spa"},
            )

    def test_chinese_segmentation_and_dual_stream_exclusions(self):
        lexicon = GCAMLexicon(
            "Chinese labMT fixture",
            {},
            weighted_dimensions={"v24.11": {"幸福": 6, "快乐": 8}},
            languages={"v24.11": "zho"},
        )
        direct = analyze_gcam(
            "I am happy.",
            original_text="我很幸福，也很快乐。",
            original_language="zh",
            lexicon=lexicon,
        )
        self.assertEqual(direct.counts["c24.11"], 2)
        self.assertEqual(direct.values["v24.11"], 7)
        self.assertEqual(direct.native_word_count, 6)
        both = analyze_gcam(
            "I am happy.",
            original_text="我很幸福，也很快乐。",
            original_language="zho",
            lexicon=lexicon,
        )
        self.assertEqual(both.native_word_count, 6)
        self.assertEqual(both.values["v24.11"], 7)
        disabled = analyze_gcam(
            "I am happy.",
            original_text="我很幸福，也很快乐。",
            original_language="zho",
            lexicon=lexicon,
            disabled_dictionaries=[24],
        )
        self.assertEqual(disabled.values, {})
        self.assertEqual(disabled.native_word_count, 6)

    def test_unicode_combining_marks_and_phrase_exclusions_keep_denominators(self):
        self.assertEqual(tokenize_gcam("अच्छा अच्छा बुरा", "hin"), ["अच्छा", "अच्छा", "बुरा"])
        lexicon = _load(
            {
                "name": "native",
                "dimensions": [
                    {"key": "v24.4", "scores": {"अच्छा": 7.0}, "language": "hin"},
                    {"key": "c30.1", "patterns": ["ad*", "tűz*"], "language": "hun"},
                ],
                "exclusions": {"30": ["ad* be", "tűz* ki"]},
            }
        )
        result = analyze_gcam(
            "", original_text="अच्छा अच्छा बुरा", original_language="hi", lexicon=lexicon
        )
        self.assertEqual(result.to_gkg(), "wc:0,nwc:3,c24.4:2,v24.4:7")
        result = analyze_gcam(
            "", original_text="ad be ad tűz ki tűz", original_language="hu", lexicon=lexicon
        )
        self.assertEqual(result.to_gkg(), "wc:0,nwc:6,c30.1:2")

    def test_pipeline_forwards_original_body_without_changing_primary_text(self):
        metadata = RecordMetadata(
            identifier="https://example.org/article",
            batch_time="20200101000000",
            sequence=1,
            source_language="fra",
            translation_engine="authored-engine",
        )
        result = generate_gkg(
            "chat chat",
            metadata,
            Resources(gcam_lexicon=self.fixture()),
            overrides={key: "" for key in OVERRIDABLE_COLUMNS if key != "V2GCAM"},
            gcam_original_text="chat",
        )
        self.assertEqual(result.gcam, "wc:2,nwc:1,c2.1:2,c28.1:1")

    def senticon_book(self):
        return book(
            [
                (
                    f"v{dictionary}.{offset + 2 * (level - 1) + index}",
                    f"Level{level}{polarity} (Scored Value)",
                    language,
                )
                for dictionary, language, offset in (
                    (20, "eng", 0),
                    (23, "cat", 0),
                    (23, "spa", 16),
                    (23, "glg", 32),
                )
                for level in (1, 2)
                for index, polarity in ((1, "Positive"), (2, "Negative"))
            ]
        )

    def senticon(self, code):
        path = self.root / f"senticon.{code}.xml"
        path.write_text(
            f'<senticon lang="{code}"><layer level="2"><positive><lemma pos="a" pol="0.8">great</lemma></positive><negative/></layer><layer level="1"><positive><lemma pos="a" pol="0.4">good</lemma></positive><negative><lemma pos="a" pol="-0.5">bad</lemma></negative></layer></senticon>'
        )
        return path

    def test_senticon_inherits_lower_layers_and_routes_codebook_language_offsets(self):
        native = self.senticon_book()
        profile = add_ml_senticon(self.baseline, self.senticon("en"), native)
        result = analyze_gcam("good great bad", lexicon=_load(profile))
        self.assertAlmostEqual(result.values["v20.3"], 0.6)
        self.assertEqual(result.counts["c20.3"], 2)
        self.assertEqual(result.values["v20.4"], -0.5)
        profile = add_senticon_languages(
            self.baseline,
            {"ml-senticon-" + code: self.senticon(code) for code in ("ca", "es", "gl")},
            native,
        )
        result = analyze_gcam(
            "", original_text="good great", original_language="es", lexicon=_load(profile)
        )
        self.assertAlmostEqual(result.values["v23.19"], 0.6)
        self.assertNotIn("v23.3", result.values)

    def test_hungarian_encoding_category_root_and_exclusion_phrases(self):
        path = self.root / "hungarian.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr(
                "RID.cat", "ELSŐDLEGES\n\tIKAROSZ\n\t\tTŰZ\n\t\t\ttűz* (1)\n".encode("cp1250")
            )
            archive.writestr("RID.exc", "tűz* ki\n".encode("cp1250"))
        native = book([("c30.8", "EMOTIONS/IKAROSZ/TUZ", "hun")])
        profile = add_rid(self.baseline, path, native, "rid-hungarian")
        result = analyze_gcam(
            "", original_text="tűz ki tűz", original_language="hu", lexicon=_load(profile)
        )
        self.assertEqual(result.counts["c30.8"], 1)
        self.assertEqual(profile["sources"]["rid-hungarian"]["encoding"], "cp1250")

    def test_spanish_anew_maps_women_before_men_and_omits_unavailable_values(self):
        headers = (
            ["Number", "S-Word"]
            + [
                f"{rating}-Mn-{group}"
                for group in ("All", "Fem", "Mal")
                for rating in ("Val", "Aro", "Dom")
            ]
            + ["Fam", "Con", "Imag "]
        )
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter="\t")
        writer.writerow(headers)
        writer.writerow(["1", "corazón", 2, 3, 4, 5, 6, 7, 8, 9, 1, "UnAv", 3, 4])
        path = self.root / "spanish.zip"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("data/Redondo(2007).txt", buffer.getvalue().encode("cp1252"))
        native = book([(f"v22.{index}", f"Rating{index}", "spa") for index in range(1, 13)])
        with patch("gdelt_regkg.builders.gcam_multilingual.SPANISH_WORDS", 1):
            profile = add_spanish_anew(self.baseline, path, native)
        result = analyze_gcam(
            "", original_text="corazón", original_language="es", lexicon=_load(profile)
        )
        self.assertEqual(result.values["v22.4"], 5)
        self.assertEqual(result.values["v22.7"], 8)
        self.assertNotIn("v22.10", result.values)

    def test_labmt_rejects_pagination_and_compiles_chinese(self):
        sources = {}
        native = book(
            [
                (f"v24.{index}", "Happiness (Scored Value)", language)
                for index, language in enumerate(LABMT_LANGUAGES.values(), 1)
            ]
        )
        for code in LABMT_LANGUAGES:
            path = self.root / f"labMT-{code}.json"
            path.write_text(
                json.dumps(
                    {
                        "meta": {"total_count": 1, "next": None},
                        "objects": [
                            {"word": "word", "happs": 6, "wordlist": {"title": f"labMT-{code}-v1"}}
                        ],
                    }
                )
            )
            sources["hedonometer-" + code] = path
        profile = add_labmt_languages(self.baseline, sources, native)
        self.assertEqual(len(profile["dimensions"]), 11)
        self.assertEqual(profile["sources"]["hedonometer-multilingual"]["deferred_languages"], [])
        payload = json.loads(sources["hedonometer-fr"].read_text())
        payload["meta"]["next"] = "next-page"
        sources["hedonometer-fr"].write_text(json.dumps(payload))
        with self.assertRaisesRegex(ValueError, "complete"):
            add_labmt_languages(self.baseline, sources, native)

    def test_corpus_hashes_and_cache_signatures_include_original_text(self):
        path = self.root / "corpus.jsonl"
        row = {
            "url": "https://example.org/article",
            "text": "chat chat",
            "original_text": "chat",
            "original_language": "fr",
        }
        path.write_text(json.dumps(row) + "\n")
        corpus = load_corpus([path], report=BenchmarkReport())
        article = next(iter(corpus.values()))
        self.assertEqual(article["original_language"], "fra")
        self.assertEqual(article["original_text_sha256"], hashlib.sha256(b"chat").hexdigest())
        reference = GKGRow({"document": row["url"]})
        self.assertNotEqual(
            article_signature("test", reference, article),
            article_signature("test", reference, {**article, "original_text": "different"}),
        )
        path.write_text(json.dumps({**row, "original_text_sha256": "wrong"}) + "\n")
        with self.assertRaisesRegex(ValueError, "original body checksum"):
            load_corpus([path], report=BenchmarkReport())

    def test_benchmark_count_denominators_exclude_unevaluated_native_dimensions(self):
        reference = GKGRow({"gcam": "wc:1,c2.1:1"})
        prediction = json_row(
            {
                "document": "https://example.org/story",
                "gcam": "wc:1,c2.1:1",
                "_gcam_languages": '["eng"]',
            }
        )
        options = BenchmarkOptions(
            gcam_keys=frozenset({"c2.1", "c28.1"}), gcam_languages={"c2.1": "eng", "c28.1": "fra"}
        )
        report = evaluate([(reference, prediction)], fields=("gcam",), options=options)
        native = next(
            row
            for row in report.rows
            if row.field == "GCAM / Rid French" and row.calculation == "count coverage"
        )
        self.assertEqual(native.metrics["paired_values"], 0)
        self.assertEqual(native.metrics["dimensions"], 0)
        invalid = json_row(
            {"document": "https://example.org/story", "gcam": "wc:1", "_gcam_languages": "broken"}
        )
        report = evaluate([(reference, invalid)], fields=("gcam",), options=options)
        native = next(
            row
            for row in report.rows
            if row.field == "GCAM / Rid French" and row.calculation == "count coverage"
        )
        self.assertEqual(native.metrics["paired_values"], 1)
        self.assertTrue(any(key[2] == "malformed_language_metadata" for key in report.audit))

    def test_benchmark_predictions_score_original_without_fabricating_translation_metadata(self):
        article = {
            "document": "https://example.org/story",
            "text": "chat chat",
            "text_sha256": hashlib.sha256(b"chat chat").hexdigest(),
            "original_text": "chat",
            "original_language": "fra",
        }
        reference = GKGRow(
            {"document": article["document"], "date": "20200101000000", "source_collection": "1"}
        )
        predictions = generate_predictions(
            {(None, article["document"]): article},
            [reference],
            options=PredictionOptions(fields=("gcam",), gcam_lexicon=self.fixture()),
            report=BenchmarkReport(),
            progress=lambda _: None,
        )
        self.assertEqual(predictions[0].get("gcam"), "wc:2,nwc:1,c2.1:2,c28.1:1")
        self.assertEqual(json.loads(predictions[0].get("_gcam_languages")), ["eng", "fra"])
        self.assertIsNone(predictions[0].get("translation"))


if __name__ == "__main__":
    unittest.main()
