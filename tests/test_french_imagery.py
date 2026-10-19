"""French imagery OCR conversion, approximation details and build imports."""

import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from gdelt_regkg.builders.french_imagery import (
    _line_bands,
    _ocr_page,
    class_csv,
    convert_pdf,
    ocr_pdf,
    verify_pdf,
)
from gdelt_regkg.builders.gcam_expansion import gcam_coverage
from gdelt_regkg.builders.gcam_imports import add_weighted_table
from gdelt_regkg.fields.gcam import _load, analyze_gcam

MODULE = "gdelt_regkg.builders.french_imagery"
CLASSES = {
    key: (low, high, 2)
    for key, low, high in (
        ("I", 15, 24),
        ("II", 25, 34),
        ("III", 35, 44),
        ("IV", 45, 54),
        ("V", 55, 64),
        ("VI", 65, 70),
    )
}
TEXT = """[I]
cause, raison
[II]
âme, français (la langue)
[III]
français (les ...), quelque chose
[IV]
école, cerf-
volant
[V]
œil, fête
[VI]
eau, soleil
"""


class FrenchImageryTests(unittest.TestCase):
    def convert(self, text=TEXT):
        with patch(MODULE + ".CLASSES", CLASSES):
            return class_csv(text, pdf_sha256="authored", reviewed=True)

    def test_midpoints_unicode_conflicts_and_compounds(self):
        raw, audit = self.convert()
        rows = {r["word"]: r for r in csv.DictReader(io.StringIO(raw.decode()))}
        self.assertEqual(rows["cause"]["ImageryValence"], "19.5")
        self.assertEqual(rows["soleil"]["ImageryValence"], "67.5")
        self.assertIn("œil", rows)
        self.assertIn("cerf-volant", rows)
        self.assertNotIn("français", rows)
        self.assertNotIn("quelque chose", rows)
        self.assertEqual(audit["conflicting_terms"], ["français"])
        self.assertEqual(audit["scored_terms"], 9)
        self.assertEqual(audit["review_status"], "reviewed-text")

    def test_invalid_or_partial_ocr_is_rejected(self):
        for text in (
            TEXT.replace("[VI]", "[V]"),
            TEXT.replace("cause", "cau5e"),
            TEXT.replace("cause, raison", "cause"),
        ):
            with self.subTest(text=text), self.assertRaises(ValueError):
                self.convert(text)

    def test_count_discrepancy_is_reported(self):
        classes = {**CLASSES, "I": (15, 24, 10)}
        text = TEXT.replace("cause, raison", ", ".join(["cause"] * 9))
        with patch(MODULE + ".CLASSES", classes), self.assertWarns(UserWarning):
            _, audit = class_csv(text, pdf_sha256="authored")
        self.assertEqual(audit["classes"]["I"], {"expected": 10, "extracted": 9})
        self.assertEqual(audit["review_status"], "unreviewed-ocr")

    def test_ocr_class_labels_are_recovered_from_intervals(self):
        text = TEXT
        for label, heading in (
            ("I", "Classe 1 (valences de 1.5 à 2,4) N = 41"),
            ("II", "Classe 1 (valences de 2,5 à 3,4) N = 260"),
            ("III", "Classe nr (valences de 3,5 à 4,4) N = 256"),
            ("IV", "Classe 1v (valences de 4,5 à 5,4) N = 293"),
            ("V", "Classe v (valences de 5.5 à 6,4) N = 278"),
            ("VI", "Classe vi (valences de 6,5 et au delà) N = 2"),
        ):
            text = text.replace(f"[{label}]", heading)
        self.assertEqual(self.convert(text)[0], self.convert()[0])
        with self.assertRaisesRegex(ValueError, "conflicts"):
            self.convert(text.replace("Classe nr", "Classe II"))

    def test_failed_pdf_conversion_preserves_ocr_for_review(self):
        with tempfile.TemporaryDirectory() as directory:
            draft = Path(directory) / "paper.ocr.txt"
            with (
                patch(MODULE + ".verify_pdf", return_value="authored"),
                patch(MODULE + ".ocr_pdf", return_value="unreadable draft"),
                self.assertRaisesRegex(ValueError, "OCR draft saved"),
            ):
                convert_pdf(b"authored", draft_path=draft)
            self.assertEqual(draft.read_text(encoding="utf-8"), "unreadable draft")

    def test_pdf_identity_checked_before_ocr(self):
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            verify_pdf(b"different report")

    def test_ocr_renders_only_appendix_pages_in_python(self):
        pdfium, ocr = MagicMock(), Mock()
        document = pdfium.PdfDocument.return_value
        document.__len__.return_value = 10
        pages = [Mock() for _ in range(10)]
        document.__getitem__.side_effect = pages.__getitem__
        progress = Mock()
        with (
            patch(MODULE + ".verify_pdf"),
            patch(MODULE + ".require_dependency", side_effect=[pdfium, ocr, Mock()]),
            patch("gdelt_regkg.cli.sources.download_source") as download,
            patch(MODULE + "._ocr_page", return_value="appendix text"),
        ):
            self.assertEqual(
                ocr_pdf(b"authored", progress=progress), "\n".join(["appendix text"] * 4)
            )
        messages = [call.args[0] for call in progress.call_args_list]
        self.assertTrue(any("Tesseract ready" in message for message in messages))
        self.assertEqual(sum("Finished appendix page" in message for message in messages), 4)
        for index, page in enumerate(pages):
            self.assertEqual(page.render.call_count, int(index >= 6))
            self.assertEqual(page.close.call_count, int(index >= 6))
            if index >= 6:
                page.render.assert_called_once_with(scale=2, grayscale=True)
        document.close.assert_called_once()
        download.assert_called_once()
        self.assertEqual(download.call_args.args[1]["filename"], "fra.traineddata")

    def test_missing_tesseract_fails_before_downloading_language_data(self):
        ocr = Mock()
        ocr.TesseractNotFoundError = FileNotFoundError
        ocr.TesseractError = RuntimeError
        with (
            patch(MODULE + ".verify_pdf"),
            patch(MODULE + ".require_dependency", side_effect=[Mock(), ocr, Mock()]),
            patch("gdelt_regkg.cli.sources.download_source") as download,
        ):
            ocr.get_tesseract_version.side_effect = FileNotFoundError("missing engine")
            with self.assertRaisesRegex(RuntimeError, "Tesseract on PATH"):
                ocr_pdf(b"authored")
        download.assert_not_called()
        ocr.image_to_string.assert_not_called()

    def test_line_bands_ignore_thin_rules_and_keep_text_order(self):
        image, mask = Mock(), Mock()
        image.width, image.height = 120, 60
        image.crop.return_value = mask
        mask.width, mask.height = 100, 60
        pixels = bytearray([255] * 6000)
        for y in [*range(5, 16), 25, *range(35, 45)]:
            pixels[y * 100 : y * 100 + 20] = bytes(20)
        mask.point.return_value.tobytes.return_value = bytes(pixels)
        self.assertEqual(_line_bands(image), [(5, 15), (35, 44)])
        mask.close.assert_called_once()

    def test_line_recognition_uses_french_lstm_and_bounded_timeout(self):
        image, ocr, pillow = Mock(), Mock(), Mock()
        image.width, image.height = 1000, 1500
        crop = image.crop.return_value
        crop.width, crop.height = 850, 20
        ocr.image_to_string.return_value = "cause, raison"
        with patch(MODULE + "._line_bands", return_value=[(100, 110)]):
            self.assertEqual(_ocr_page(image, ocr, pillow, Mock()), "cause, raison")
        options = ocr.image_to_string.call_args.kwargs
        self.assertEqual(options["lang"], "fra")
        self.assertIn("--psm 7 --oem 1", options["config"])
        self.assertLessEqual(options["timeout"], 15)
        crop.resize.assert_called_once_with((1275, 30), pillow.Resampling.LANCZOS)
        crop.resize.return_value.close.assert_called_once()

    def test_page_timeout_stops_queued_lines(self):
        with (
            patch(MODULE + "._line_bands", return_value=[(100, 110)]),
            patch(MODULE + ".perf_counter", side_effect=[0, 121]),
            self.assertRaises(TimeoutError),
        ):
            _ocr_page(Mock(), Mock(), Mock(), Mock())

    def test_ocr_separators_preserve_sense_annotations(self):
        text = TEXT.replace("cause, raison", "cause. raison")
        with patch(MODULE + ".CLASSES", CLASSES):
            raw, audit = class_csv(text, pdf_sha256="authored")
        self.assertEqual(audit["classes"]["I"]["extracted"], 2)
        self.assertEqual(audit["review_status"], "unreviewed-ocr")
        self.assertIn(b"cause,19.5", raw)

    def test_build_csv_and_pdf_source_details_and_coverage(self):
        raw, audit = self.convert()
        book = {
            "source_sha256": "authored",
            "dimensions": {
                key: {
                    "category": "ImageryValence",
                    "language": "fra",
                    "dictionary": "French imagery",
                }
                for key in ("c38.1",)
            },
        }
        baseline = {"name": "authored", "dimensions": []}
        with tempfile.TemporaryDirectory() as directory:
            for suffix in (".csv", ".pdf"):
                source = Path(directory) / ("imagery" + suffix)
                source.write_bytes(raw if suffix == ".csv" else b"authored PDF")
                with patch(MODULE + ".convert_pdf", return_value=(raw, audit)):
                    profile = add_weighted_table(baseline, source, book, "french-imagery")
                self.assertEqual(
                    profile["sources"]["french-imagery"]["approximation"], "class-midpoint"
                )
                result = analyze_gcam(
                    "water sun",
                    lexicon=_load(profile),
                    original_text="eau soleil",
                    original_language="fra",
                )
                self.assertEqual(result.values["v38.1"], 67.5)
                coverage = gcam_coverage(profile, book)
                self.assertEqual(coverage["compiled_dimensions"], 1)
                self.assertEqual(coverage["supported_dimensions"], 0)
                self.assertEqual(coverage["approximate_dimensions"], ["38.1"])


if __name__ == "__main__":
    unittest.main()
