import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "refine_tone_lexicon", ROOT / "src/gdelt_regkg/scripts/refine_tone_lexicon.py"
)
refine = importlib.util.module_from_spec(SPEC)
with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
    SPEC.loader.exec_module(refine)


class ToneRefinementTests(unittest.TestCase):
    def test_rare_word_cannot_be_added_from_one_training_document(self):
        from collections import Counter

        rows = []
        for i in range(10):
            tokens = ["neutral", "neutral", "wrong", "rare" if i == 0 else "neutral"]
            rows.append(
                {
                    "tokens": tokens,
                    "counts": Counter(tokens),
                    "original": {"positive": 25 if i == 0 else 0},
                }
            )
        words, history = refine.fit_edits(
            rows, {"wrong"}, {"wrong", "rare"}, "positive", penalty=0.001
        )
        self.assertEqual(words, set())
        self.assertEqual([r["word"] for r in history], ["wrong"])

    def test_source_holdout_and_duplicates_cannot_enter_training_and_validation(self):
        ordinary = next(f"host{i}" for i in range(100) if not refine.source_reserved(f"host{i}"))
        reserved = next(f"host{i}" for i in range(100) if refine.source_reserved(f"host{i}"))

        def row(day, sequence, source, body):
            return {
                "status": "ok",
                "batch": day + "120000",
                "record_id": day + f"120000-{sequence}",
                "source": source,
                "url": f"https://{source}/{day}/{sequence}",
                "text": body,
            }

        rows = [
            row("20260922", 1, ordinary, "shared article body with words"),
            row("20261002", 1, ordinary, "shared article body with words"),
            row("20260922", 2, reserved, "reserved training story"),
            row("20261002", 2, reserved, "reserved validation story"),
            row("20261003", 3, reserved, "independent reserved test content"),
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.jsonl"
            path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            splits, counts, audit = refine.prepare_rows(
                [path], {"20260922"}, "20261002", "20261003", False
            )
        self.assertEqual(counts["source_reserved_for_test"], 2)
        self.assertEqual(counts["exact_duplicate"], 1)
        self.assertEqual(len(splits["train"]), 1)
        self.assertEqual(len(splits["validation"]), 0)
        self.assertEqual(len(splits["test"]), 1)
        self.assertTrue(splits["test"][0]["source_reserved"])

    def test_inflections_are_candidates_and_include_irregular_forms(self):
        forms = refine.inflections({"say", "hope", "try", "stop"})
        self.assertTrue({"said", "hoping", "tried", "stopped"} <= forms)


if __name__ == "__main__":
    unittest.main()
