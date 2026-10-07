import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "benchmark_tone", ROOT / "src/gdelt_regkg/scripts/benchmark_tone.py"
)
benchmark = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(benchmark)


class ToneBenchmarkTests(unittest.TestCase):
    def test_metrics_handle_ties_zero_variance_and_empty_samples(self):
        self.assertEqual(benchmark.ranks([4, 2, 2, 8]), [2, 0.5, 0.5, 3])
        self.assertIsNone(benchmark.correlation([1, 1], [2, 3]))
        self.assertIsNone(benchmark.summarize([])["metrics"])
        rows = []
        for actual, predicted in ((1, 2), (3, 2)):
            rows.append(
                {
                    "source": "example.org",
                    "word_count_ratio": 1,
                    "original": dict.fromkeys(benchmark.FIELDS, actual),
                    "predicted": dict.fromkeys(benchmark.FIELDS, predicted),
                }
            )
        report = benchmark.summarize(rows)
        self.assertEqual(report["metrics"]["tone"]["mae"], 1)
        self.assertEqual(report["metrics"]["tone"]["bias"], 0)
        self.assertIsNone(report["metrics"]["tone"]["pearson"])

    def test_original_matching_excludes_conflicting_versions_and_translations(self):
        def line(identifier, url, tone, translation=""):
            cells = [""] * 27
            cells[0:5] = [identifier, "20260930120000", "1", "example.org", url]
            cells[15], cells[25] = tone, translation
            return "\t".join(cells) + "\n"

        first = "1,2,1,3,20,1,100"
        second = "2,3,1,4,20,1,100"
        lines = (
            line("20260930120000-1", "https://example.org/duplicate", first)
            + line("20260930120000-2", "https://example.org/duplicate", first)
            + line("20260930120000-3", "https://example.org/conflict", first)
            + line("20260930120000-4", "https://example.org/conflict", second)
            + line("20260930120000-T5", "https://example.org/translated", first)
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "original.gkg.csv.zip"
            with zipfile.ZipFile(path, "w") as archive:
                archive.writestr("original.gkg.csv", lines.encode() + b"\xff\n")
            rows, counts, _ = benchmark.load_originals([path])
        self.assertEqual([r["url"] for r in rows], ["https://example.org/duplicate"])
        self.assertEqual(counts["excluded_conflicting_urls"], 1)
        self.assertEqual(counts["malformed_original_rows"], 1)
        self.assertEqual(counts["identical_duplicate_rows"], 1)

    def test_sample_is_deterministic_and_limits_source_concentration(self):
        rows = [
            {"source": str(source), "url": f"https://{source}/{i}"}
            for source in range(3)
            for i in range(10)
        ]
        selected = benchmark.sample_records(rows, 100, 2, 42)
        self.assertEqual(len(selected), 6)
        self.assertEqual(selected, benchmark.sample_records(list(reversed(rows)), 100, 2, 42))

    def test_tone_parser_rejects_nonfinite_wrong_length_and_fractional_word_counts(self):
        for cell in ("nan,2,1,3,20,1,100", "1,2", "1,2,1,3,20,1,100.5"):
            with self.assertRaises(ValueError):
                benchmark.parse_tone(cell)

    def test_archive_retry_does_not_cache_failed_transfer(self):
        import io

        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("original.csv", "original row")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            responses = iter([TimeoutError("interrupted"), (data.getvalue(), {})])

            def transfer(*args, **kwargs):
                self.assertFalse((root / "20260922120000.gkg.csv.zip").exists())
                result = next(responses)
                if isinstance(result, Exception):
                    raise result
                return result

            with (
                patch.object(benchmark, "download", side_effect=transfer) as download,
                patch.object(benchmark.time, "sleep"),
            ):
                path = benchmark.acquire_archive("20260922120000", root, 5)
                self.assertTrue(zipfile.is_zipfile(path))
                self.assertEqual(download.call_count, 2)
                self.assertTrue(download.call_args.args[0].startswith("http://"))


if __name__ == "__main__":
    unittest.main()
