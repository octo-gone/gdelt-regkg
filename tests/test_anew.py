"""ANEW table conversion, optional PDF backends and build acquisition."""

import csv
import hashlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from gdelt_regkg.builders.anew import anew_csv, convert_anew_pdf, main, pdf_text
from gdelt_regkg.cli.gcam import GCAMOptions
from gdelt_regkg.cli.inputs import BuildOptions, resolve_inputs
from gdelt_regkg.cli.profiles import compile_profiles
from gdelt_regkg.cli.sources import download_source
from gdelt_regkg.dependencies import OptionalDependencyError
from gdelt_regkg.fields.gcam import _load, analyze_gcam


class ANEWTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        ids = patch("gdelt_regkg.builders.anew.WORD_IDS", frozenset({1, 2}))
        ids.start()
        self.addCleanup(ids.stop)
        self.text = "\n".join(
            (
                "Affective Norms for English Words. All Subjects Table 1",
                "alpha 1 2.10 (0.10) 3.20 (0.20) 4.30 (0.30) . "
                "beta 2 3.10 (0.10) 4.20 (0.20) 5.30 (0.30) 20",
                "Affective Norms for English Words. Male Subjects Table 2",
                "beta 2 6.10 (0.10) 7.20 (0.20) 8.30 (0.30) 20",
                "alpha 1 5.10 (0.10) 6.20 (0.20) 7.30 (0.30) .",
                "Affective Norms for English Words. Female Subjects Table 3",
                "alpha 1 6.10 (0.10) 7.20 (0.20) 8.30 (0.30) .",
                "beta 2 7.10 (0.10) 8.20 (0.20) 9.00 (0.30) 20",
            )
        )
        self.csv = anew_csv(self.text)
        self.pdf = b"%PDF-authored-fixture"
        self.entry = {
            "filename": "anew.csv",
            "url": "https://example.org/anew.pdf",
            "converter": "anew-pdf",
            "pdf_sha256": hashlib.sha256(self.pdf).hexdigest(),
            "sha256": hashlib.sha256(self.csv).hexdigest(),
        }

    def test_tables_join_by_word_number_and_preserve_single_column_rows(self):
        rows = list(csv.DictReader(io.StringIO(self.csv.decode())))
        self.assertEqual([row["word"] for row in rows], ["alpha", "beta"])
        self.assertEqual(rows[0]["Valence (Pleasure) (All)"], "2.10")
        self.assertEqual(rows[0]["Arousal (Men)"], "6.20")
        self.assertEqual(rows[0]["Dominance (Women)"], "8.30")
        self.assertEqual(len(rows[0]), 10)
        self.assertEqual(anew_csv(self.text.replace(" ", "  ")), self.csv)

    def test_incomplete_duplicate_mismatched_and_malformed_tables_fail(self):
        cases = (
            (self.text.rsplit("\n", 1)[0], "Incomplete"),
            (self.text + "\nalpha 1 6.10 (0.10) 7.20 (0.20) 8.30 (0.30) .", "Duplicate"),
            (self.text.replace("alpha 1 6.10", "other 1 6.10"), "identity"),
            (self.text.replace("2.10 (0.10)", "9.10 (0.10)"), "Invalid"),
            (self.text.replace("2.10 (0.10)", "2.10 (broken)"), "Unrecognized"),
            (self.text.replace("beta 2", "beta 3"), "Incomplete"),
        )
        for text, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                anew_csv(text)

    def test_pypdf_normalizes_page_rotation_and_skips_non_table_pages(self):
        page = MagicMock()
        page.extract_text.side_effect = [self.text, self.text]
        introduction = MagicMock()
        introduction.extract_text.return_value = "Introduction"
        module = MagicMock()
        module.PdfReader.return_value.pages = [introduction, page]
        with (
            patch("gdelt_regkg.builders.anew.require_dependency", return_value=module) as require,
            patch("gdelt_regkg.builders.anew.shutil.which") as which,
        ):
            self.assertEqual(convert_anew_pdf(self.pdf, backend="pypdf"), self.csv)
        require.assert_called_once_with("pypdf", "build")
        which.assert_not_called()
        page.transfer_rotation_to_content.assert_called_once()
        page.extract_text.assert_called_with(extraction_mode="layout")
        introduction.transfer_rotation_to_content.assert_not_called()

    def test_pdftotext_and_missing_dependency(self):
        completed = subprocess.CompletedProcess([], 0, self.text.encode(), b"")
        with (
            patch(
                "gdelt_regkg.builders.anew.shutil.which", return_value="/path with spaces/pdftotext"
            ),
            patch("gdelt_regkg.builders.anew.subprocess.run", return_value=completed) as run,
            patch("gdelt_regkg.builders.anew.require_dependency") as require,
        ):
            self.assertEqual(convert_anew_pdf(self.pdf), self.csv)
        require.assert_not_called()
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ["/path with spaces/pdftotext", "-layout", "-enc", "UTF-8"])
        self.assertEqual(command[-1], "-")
        self.assertNotIn("shell", run.call_args.kwargs)
        with patch("gdelt_regkg.builders.anew.shutil.which", return_value=None):
            with self.assertRaisesRegex(FileNotFoundError, "pdftotext"):
                pdf_text(self.pdf, backend="pdftotext")
            with (
                patch("gdelt_regkg.dependencies.import_module", side_effect=ImportError("missing")),
                self.assertRaisesRegex(OptionalDependencyError, r"gdelt-regkg\[build\]"),
            ):
                pdf_text(self.pdf)
        with self.assertRaisesRegex(ValueError, "backend"):
            pdf_text(self.pdf, backend="unknown")

    def test_acquisition_verifies_pdf_and_csv_before_installing(self):
        output = self.root / "sources/anew.csv"
        with (
            patch("gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(self.pdf)),
            patch("gdelt_regkg.builders.anew.convert_anew_pdf", return_value=self.csv) as convert,
        ):
            download_source(output, self.entry)
        self.assertEqual(output.read_bytes(), self.csv)
        convert.assert_called_once_with(self.pdf, backend="auto")
        for body, csv_body, error in (
            (b"wrong PDF", self.csv, "PDF checksum"),
            (self.pdf, b"wrong CSV", "source checksum"),
        ):
            target = self.root / error / "anew.csv"
            with (
                patch("gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(body)),
                patch("gdelt_regkg.builders.anew.convert_anew_pdf", return_value=csv_body),
                self.assertRaisesRegex(ValueError, error),
            ):
                download_source(target, self.entry)
            self.assertFalse(target.exists())
        with patch("gdelt_regkg.cli.sources.urlopen") as fetch:
            download_source(output, self.entry)
        fetch.assert_not_called()

    def test_build_downloads_anew_and_maps_nine_native_scores(self):
        baseline = self.root / "base.json"
        baseline.write_text(json.dumps({"name": "authored", "dimensions": []}))
        labels = list(csv.DictReader(io.StringIO(self.csv.decode())))[0]
        book = self.root / "codebook.txt"
        book.write_text(
            "Variable\tDictionaryID\tDimensionID\tType\tLanguageCode\tDictionaryHumanName\tDimensionHumanName\tReference\n"
            + "\n".join(
                f"{prefix}19.{index}\t19\t{index}\t{kind}\teng\tANEW\t{label}{suffix}\tReference"
                for index, label in enumerate(list(labels)[1:], 1)
                for prefix, kind, suffix in (
                    ("c", "WORDCOUNT", ""),
                    ("v", "SCOREDVALUE", " (Scored Value)"),
                )
            )
        )
        with (
            patch("gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(self.pdf)),
            patch("gdelt_regkg.builders.anew.convert_anew_pdf", return_value=self.csv),
        ):
            inputs = resolve_inputs(
                self.root / "built",
                BuildOptions(
                    targets=("gcam",),
                    sources={"codebook": book},
                    sources_dir=self.root / "sources",
                    download_sources=True,
                    gcam=GCAMOptions(baseline=baseline, additions=("anew",)),
                    recipe={"sources": {"anew": self.entry}},
                ),
            )
            artifacts, defaults = compile_profiles(inputs)
        self.assertEqual(defaults["gcam"], "gcam.custom.json.gz")
        result = analyze_gcam("alpha alpha beta", lexicon=_load(artifacts[0].payload))
        self.assertEqual(result.counts["c19.1"], 3)
        self.assertAlmostEqual(result.values["v19.1"], (2.1 * 2 + 3.1) / 3)
        self.assertEqual(len(result.values), 9)
        coverage = next(a.payload for a in artifacts if "coverage." in a.path)
        self.assertEqual(coverage["supported_dimensions"], 9)

    def test_standalone_local_pdf_rejects_changes_and_converts_verified_input(self):
        pdf = self.root / "source.pdf"
        pdf.write_bytes(self.pdf)
        output = self.root / "anew.csv"
        with (
            patch(
                "gdelt_regkg.utils.read_resource_json",
                return_value={"sources": {"anew": self.entry}},
            ),
            patch("gdelt_regkg.builders.anew.convert_anew_pdf", return_value=self.csv),
            patch("sys.stdout", new_callable=io.StringIO),
        ):
            main(["--pdf", str(pdf), "--output", str(output)])
            self.assertEqual(output.read_bytes(), self.csv)
            pdf.write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "PDF checksum"):
                main(["--pdf", str(pdf), "--output", str(output)])


if __name__ == "__main__":
    unittest.main()
