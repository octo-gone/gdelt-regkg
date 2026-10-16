"""Native corpus selection joins exact records and preserves original bodies."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg.benchmark.acquire import _Acquisition, _fetch, native_language
from gdelt_regkg.benchmark.model import FIELD_NAMES
from gdelt_regkg.fields.language import LanguageDetection


def cells(code="fra", identifier="20251101000000-T1"):
    row = [""] * 27
    for key, value in {
        "source_collection": "1",
        "translation": "srclc:" + code,
        "recordid": identifier,
        "document": "https://example.org/story",
    }.items():
        row[FIELD_NAMES.index(key)] = value
    return row


class NativeAcquisitionTests(unittest.TestCase):
    def test_language_labels_and_exact_seed_join(self):
        self.assertEqual(native_language(cells("fre")), "fra")
        self.assertIsNone(native_language(cells("axe")))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.jsonl"
            path.write_text(
                json.dumps(
                    {
                        "url": "https://example.org/story",
                        "record_id": "20251101000000-T1",
                        "text": "Translation",
                        "original_text": "Texte original",
                        "original_language": "fra",
                    }
                ),
                encoding="utf8",
            )
            run = _Acquisition(["fra"], 1, 10, 17)
            run.seed_bodies([path])
            run.observe(cells())
            run.observe(cells())
            self.assertEqual(len(run.retained["fra"]), 1)
            self.assertEqual(run.retained["fra"][0][0]["original_text"], "Texte original")
            wrong = _Acquisition(["fra"], 1, 10, 17)
            wrong.seed_bodies([path])
            wrong.observe(cells(identifier="20251101000000-T2"))
            self.assertFalse(wrong.retained["fra"])
            self.assertEqual(len(wrong.candidates["fra"]), 1)

    def test_fetch_uses_one_original_stream_and_rejects_language_changes(self):
        with (
            patch(
                "gdelt_regkg.benchmark.acquire.fetch_body",
                return_value=("Bonjour", "https://example.org/story"),
            ),
            patch(
                "gdelt_regkg.benchmark.acquire.detect_language",
                return_value=LanguageDetection("fra", 0.99, 0.98, "fixture"),
            ),
        ):
            _, body, _, error = _fetch(("fra", cells()))
            self.assertIsNone(error)
            self.assertEqual(body["text"], "")
            self.assertEqual(body["original_text"], "Bonjour")
            self.assertTrue(body["gcam_native_only"])
        with (
            patch(
                "gdelt_regkg.benchmark.acquire.fetch_body",
                return_value=("English", "https://example.org/story"),
            ),
            patch(
                "gdelt_regkg.benchmark.acquire.detect_language",
                return_value=LanguageDetection("eng", 0.99, 0.98, "fixture"),
            ),
        ):
            _, body, _, error = _fetch(("fra", cells()))
            self.assertIsNone(body)
            self.assertIn("language differs", error)


if __name__ == "__main__":
    unittest.main()
