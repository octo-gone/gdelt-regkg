"""Reproducible external corpus preparation without translation or retrieval."""

import json
import tempfile
import unittest
from pathlib import Path

from gdelt_regkg.benchmark.model import FIELD_NAMES
from gdelt_regkg.benchmark.prepare import prepare, prepared_article


class GCAMPrepareTests(unittest.TestCase):
    def test_original_source_text_is_preserved_and_hashed(self):
        row = prepared_article(
            {
                "url": "https://example.org/a",
                "text": "English translation",
                "source_text": "Amour et bonheur",
                "translated": True,
                "source_language": "fre",
            }
        )
        self.assertEqual(row["original_language"], "fra")
        self.assertEqual(row["original_text"], "Amour et bonheur")
        self.assertEqual(row["text"], "English translation")
        self.assertEqual(len(row["original_text_sha256"]), 64)
        self.assertIsNone(prepared_article({"url": "x", "text": "translated", "translated": True}))

    def test_sampling_uses_native_gcam_word_counts_and_exports_exact_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = []
            for i in range(20):
                native = [""] * 27
                native[FIELD_NAMES.index("gcam")] = "wc:10"
                native[FIELD_NAMES.index("document")] = f"https://example.org/{i}"
                rows.append(
                    {
                        "url": native[FIELD_NAMES.index("document")],
                        "record_id": str(i),
                        "text": "word " * (10 if i < 10 else 20),
                        "native_cells": native,
                    }
                )
            path = root / "input.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            a = prepare(
                [path],
                root / "a.jsonl",
                sample_size=4,
                seed=17,
                max_word_count_difference=0.1,
                reference_output=root / "reference.jsonl",
            )
            b = prepare(
                [path], root / "b.jsonl", sample_size=4, seed=17, max_word_count_difference=0.1
            )
            self.assertEqual(a["eligible"], 10)
            self.assertEqual(a["selection_sha256"], b["selection_sha256"])
            self.assertEqual(len((root / "reference.jsonl").read_text().splitlines()), 4)
            self.assertEqual(path.read_text().count('"native_cells"'), 20)

    def test_split_languages_keeps_native_bodies_separate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "input.jsonl"
            rows = [
                {
                    "url": "https://example.org/" + code,
                    "text": "English",
                    "translated": True,
                    "source_text": body,
                    "source_language": code,
                }
                for code, body in (("fra", "amour"), ("spa", "amor"))
            ]
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            manifest = prepare([path], root / "native", split_languages=True)
            self.assertEqual(manifest["languages"], {"fra": 1, "spa": 1})
            self.assertEqual(
                json.loads((root / "native/fra.jsonl").read_text())["original_text"], "amour"
            )


if __name__ == "__main__":
    unittest.main()
