"""Prediction resume, invalidation and disk-backed input contracts."""

import hashlib
import json
import sqlite3
import tempfile
import unittest
from argparse import Namespace
from contextlib import closing
from pathlib import Path
from unittest.mock import Mock, patch

from gdelt_regkg.benchmark.checkpoint import article_signature, prediction_signature, select_device
from gdelt_regkg.benchmark.corpus import generate_predictions
from gdelt_regkg.benchmark.inputs import align_rows
from gdelt_regkg.benchmark.model import BenchmarkReport, GKGRow
from gdelt_regkg.benchmark.storage import BenchmarkStore, StoredRow
from gdelt_regkg.fields.ner import NERResult
from gdelt_regkg.utils import GKG_COLUMNS


class CheckpointTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.path = self.root / "benchmark.sqlite3"

    def article(self, index=1):
        text = f"Example article {index}."
        return {
            "record_id": str(index),
            "url": str(index),
            "document": str(index),
            "text": text,
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }

    def reference(self, index=1):
        return GKGRow(
            {
                "recordid": str(index),
                "document": str(index),
                "date": "20260101000000",
                "source_collection": "1",
                "source": "example.org",
            }
        )

    def generate(self, store, *, namespace="test", articles=None, **options):
        articles = articles or [self.article(i) for i in range(1, 4)]
        return generate_predictions(
            {(a["record_id"], a["document"]): a for a in articles},
            [self.reference(int(a["record_id"])) for a in articles],
            fields=("tone",),
            report=BenchmarkReport(),
            resources_dir=self.root,
            store=store,
            signature=namespace,
            batch_size=1,
            progress=lambda _: None,
            **options,
        )

    def test_interruption_preserves_committed_predictions_and_resume_skips_them(self):
        empty = dict.fromkeys(GKG_COLUMNS, "")
        with BenchmarkStore(self.path) as store:
            with patch(
                "gdelt_regkg.benchmark.corpus.generate_gkg",
                side_effect=[empty, RuntimeError("interrupted")],
            ):
                with self.assertRaisesRegex(RuntimeError, "interrupted"):
                    self.generate(store)
        with BenchmarkStore(self.path) as store:
            with patch(
                "gdelt_regkg.benchmark.corpus.generate_gkg", return_value=empty
            ) as extractor:
                rows = self.generate(store)
                self.assertEqual(extractor.call_count, 2)
            self.assertTrue(all(isinstance(r, StoredRow) for r in rows))
            self.assertEqual(len(rows), 3)
        with BenchmarkStore(self.path) as store:
            with patch(
                "gdelt_regkg.benchmark.corpus.generate_gkg",
                side_effect=AssertionError("cache miss"),
            ):
                self.assertEqual(len(self.generate(store)), 3)

    def test_changed_configuration_or_article_does_not_reuse_predictions(self):
        empty = dict.fromkeys(GKG_COLUMNS, "")
        with (
            BenchmarkStore(self.path) as store,
            patch("gdelt_regkg.benchmark.corpus.generate_gkg", return_value=empty) as extract,
        ):
            self.generate(store)
            self.generate(store, namespace="changed-model-or-resources")
            self.assertEqual(extract.call_count, 6)
            changed = self.article() | {"sharing_image": "https://example.org/changed.jpg"}
            self.generate(store, articles=[changed])
            self.assertEqual(extract.call_count, 7)
            original = self.article()
            self.assertNotEqual(
                article_signature("test", self.reference(), original),
                article_signature("test", self.reference(), original | {"text_sha256": "changed"}),
            )

    def test_disk_inputs_preserve_missing_null_and_duplicate_conflicts(self):
        with BenchmarkStore(self.path) as store:
            corpus = store.corpus()
            corpus[("1", "1")] = self.article()
            self.assertEqual(corpus[("1", "1")], self.article())
            left, right = store.rows("reference"), store.rows("prediction")
            left.append(self.reference())
            left.append(self.reference())
            right.append(self.reference())
            report = BenchmarkReport()
            pairs = align_rows(left, right, report=report)
            self.assertEqual(len(pairs), 1)
            self.assertEqual(pairs[0][0].values, self.reference().values)
            right.append(GKGRow(self.reference().values | {"tone": None}))
            with self.assertRaisesRegex(ValueError, "No unambiguous"):
                align_rows(left, right, report=BenchmarkReport())

    def test_duplicate_checkpoint_keys_and_uncommitted_rollback(self):
        with BenchmarkStore(self.path) as store:
            a = store.put(self.reference(), signature="key")
            b = store.put(self.reference(), signature="key")
            self.assertEqual(a.identifier, b.identifier)
            # No commit: an interrupted batch is recomputed, not partially trusted.
        with BenchmarkStore(self.path) as store:
            self.assertIsNone(store.cached("key"))

    def test_resource_content_and_device_settings_invalidate_configuration(self):
        lexicons = self.root / "lexicons"
        lexicons.mkdir()
        tone = lexicons / "tone.v3.json"
        tone.write_text("{}", encoding="utf8")
        args = Namespace(
            resources_dir=self.root,
            gcam_lexicon=None,
            ner_cache=None,
            batch_size=16,
            batch_chars=100000,
            numeric_date_order=None,
        )
        first = prediction_signature(args, ("tone",), "cpu")
        self.assertEqual(first, prediction_signature(args, ("tone",), "cpu"))
        tone.write_text(json.dumps({"name": "changed"}), encoding="utf8")
        self.assertNotEqual(first, prediction_signature(args, ("tone",), "cpu"))
        second = prediction_signature(args, ("tone",), "cpu")
        self.assertNotEqual(second, prediction_signature(args, ("tone",), "cuda:0"))
        args.batch_size = 8
        self.assertNotEqual(second, prediction_signature(args, ("tone",), "cpu"))

    def test_second_writer_cannot_reset_active_inputs(self):
        with BenchmarkStore(self.path) as store:
            corpus = store.corpus()
            corpus[("1", "1")] = self.article()
            with self.assertRaisesRegex(ValueError, "cache is in use"):
                with BenchmarkStore(self.path):
                    pass
            self.assertEqual(len(corpus), 1)

    def test_ner_uses_bounded_batches_and_is_not_loaded_for_cache_hits(self):
        articles = [self.article(i) for i in range(1, 4)]
        corpus = {(a["record_id"], a["document"]): a for a in articles}
        references = [self.reference(i) for i in range(1, 4)]
        model = Mock()
        model.analyze_many.side_effect = lambda texts, batch_size: iter(
            NERResult(text, (), backend_name="fixture") for text in texts
        )
        options = dict(
            fields=("persons",),
            report=BenchmarkReport(),
            resources_dir=self.root,
            signature="fixture-ner",
            batch_size=2,
            batch_chars=1000,
            progress=lambda _: None,
        )
        with (
            BenchmarkStore(self.path) as store,
            patch("gdelt_regkg.benchmark.corpus.SpacyNER.from_model", return_value=model),
            patch(
                "gdelt_regkg.benchmark.corpus.generate_gkg",
                return_value=dict.fromkeys(GKG_COLUMNS, ""),
            ),
        ):
            self.assertEqual(
                len(generate_predictions(corpus, references, store=store, **options)), 3
            )
            self.assertEqual(
                [len(call.args[0]) for call in model.analyze_many.call_args_list], [2, 1]
            )
        with (
            BenchmarkStore(self.path) as store,
            patch(
                "gdelt_regkg.benchmark.corpus.SpacyNER.from_model",
                side_effect=AssertionError("should reuse cache"),
            ),
        ):
            self.assertEqual(
                len(generate_predictions(corpus, references, store=store, **options)), 3
            )

    def test_refuses_unrelated_sqlite_database(self):
        with closing(sqlite3.connect(self.path)) as db:
            with db:
                db.execute("CREATE TABLE bodies (precious TEXT)")
                db.execute("INSERT INTO bodies VALUES ('keep')")
        with self.assertRaisesRegex(ValueError, "Not a benchmark cache"):
            with BenchmarkStore(self.path):
                pass
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT * FROM bodies").fetchall(), [("keep",)])

    def test_explicit_cuda_fails_and_auto_falls_back(self):
        with (
            patch("spacy.require_gpu", side_effect=ValueError("no CUDA")),
            patch("spacy.require_cpu") as cpu,
        ):
            with self.assertRaisesRegex(ValueError, "CUDA initialization failed"):
                select_device("cuda", 0, lambda _: None)
            cpu.assert_not_called()
            self.assertEqual(select_device("auto", 0, lambda _: None), "cpu")
            cpu.assert_called_once()

    def test_refuses_overlapping_cupy_wheels_before_loading_models(self):
        with patch("gdelt_regkg.benchmark.checkpoint.metadata.version", return_value="14.2.0"):
            with self.assertRaisesRegex(ValueError, "Both CUDA 12 and CUDA 13"):
                select_device("cuda", 0, lambda _: None)


if __name__ == "__main__":
    unittest.main()
