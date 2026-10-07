"""Guard language cohorts, fixed sampling, and translated-body replay."""

import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gdelt_regkg.scripts.benchmark_extraction import load_originals, prepare_translation, retrieve
from gdelt_regkg.scripts.benchmark_samples import sample_windows
from gdelt_regkg.translation import TranslationResult


class SampleTests(unittest.TestCase):
    def test_windows_preserve_quotas_and_exclude_known_urls(self):
        plan = {
            "development": {"days": ["20260110"]},
            "utc_windows": ["001500", "121500"],
            "english_per_window": 3,
            "translated_per_window": 2,
            "per_source_per_day": 1,
            "seed": 42,
        }
        rows = [
            {
                "batch": "20260110" + time,
                "source": str(i),
                "url": f"https://{i}/{time}/{translated}",
                "translated": translated,
            }
            for time in plan["utc_windows"]
            for translated in [False, True]
            for i in range(20)
        ]
        selected, windows = sample_windows(rows, plan, "development", {rows[0]["url"]})
        self.assertEqual(len(selected), 10)
        self.assertEqual(len({r["source"] for r in selected}), 10)
        self.assertNotIn(rows[0]["url"], {r["url"] for r in selected})
        self.assertEqual(sum(r["translated"] for r in selected), 4)
        self.assertEqual(
            selected, sample_windows(list(reversed(rows)), plan, "development", {rows[0]["url"]})[0]
        )
        self.assertTrue(all(v["selected"] == v["requested"] for v in windows.values()))

    def test_translated_originals_are_opt_in_and_keep_language(self):
        cells = [""] * 27
        cells[:5] = [
            "20260110001500-T1",
            "20260110001500",
            "1",
            "example.org",
            "http://example.org/article",
        ]
        cells[15] = "1,2,1,3,20,1,100"
        cells[25] = "srclc:spa;eng:test"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "original.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("original.csv", "\t".join(cells) + "\n")
            self.assertEqual(load_originals([path])[0], [])
            row = load_originals([path], include_translated=True)[0][0]
        self.assertTrue(row["translated"])
        self.assertEqual(row["translation_info"], cells[25])

    def test_pending_corpus_does_not_apply_english_word_limit_to_source(self):
        source = "中文" * 150
        row = {
            "url": "http://example.org/article",
            "translated": True,
            "original": {"word_count": 100},
        }
        saved = {
            **row,
            "status": "ok",
            "text": source,
            "source_text": source,
            "translation_pending": True,
        }
        result = retrieve(row, SimpleNamespace(min_words=50), {row["url"]: saved})
        self.assertEqual(result["text"], source)
        self.assertTrue(result["translation_pending"])
        text = "The hospital treated three injured people. " * 12
        with patch(
            "gdelt_regkg.translation.translate_text",
            return_value=TranslationResult(source, text, "zho", "fake CUDA test"),
        ) as translate:
            prepared = prepare_translation(result, object())
        self.assertEqual(translate.call_args.args[0], source)
        self.assertEqual(prepared["source_text"], source)
        self.assertEqual(prepared["text"], text)
        self.assertFalse(prepared["translation_pending"])
        self.assertEqual(prepared["source_language"], "zho")
        self.assertEqual(prepared["translation_engine"], "fake CUDA test")

    def test_unsupported_archive_language_hint_falls_back_to_detection(self):
        source = "Source text to translate. " * 20
        text = "The hospital treated three injured people. " * 12
        row = {
            "status": "ok",
            "translated": True,
            "translation_pending": True,
            "translation_info": "srclc:axe",
            "text": source,
            "original": {"word_count": 100},
        }
        with patch(
            "gdelt_regkg.translation.translate_text",
            return_value=TranslationResult(source, text, "aze", "fake CUDA test"),
        ) as translate:
            prepared = prepare_translation(row, object())
        self.assertIsNone(translate.call_args.kwargs["language"])
        self.assertEqual(prepared["source_language_hint_error"], "axe")
        self.assertEqual(prepared["status"], "ok")


if __name__ == "__main__":
    unittest.main()
