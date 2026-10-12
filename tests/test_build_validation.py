"""Output checksum checks, including recipe selection and CLI warning behavior."""

import contextlib
import gzip
import hashlib
import io
import json
import unittest
import zipfile
from unittest.mock import patch

from test_cli import WorkspaceTests

from gdelt_regkg.builders.gazetteer import build_gazetteer
from gdelt_regkg.builders.gcam_lexicon import CATEGORIES, build_gcam_lexicon
from gdelt_regkg.cli import main
from gdelt_regkg.cli.validation import semantic_sha256, validate_output
from gdelt_regkg.utils import read_resource_json

LOGGER = "gdelt_regkg.cli.validation"


class OutputValidationTests(WorkspaceTests):
    def manifest_reader(self, outputs):
        def read(*parts):
            if parts == ("recipes.json",):
                return read_resource_json(*parts) | {"outputs": outputs}
            return read_resource_json(*parts)

        return read

    def test_hash_ignores_json_formatting_but_preserves_content(self):
        payload = {"words": ["café", "peace"], "name": "fixture"}
        formatted = json.dumps(payload, ensure_ascii=False, indent=4)
        expected = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertEqual(semantic_sha256(json.loads(formatted)), expected)
        self.assertEqual(semantic_sha256(dict(reversed(list(payload.items())))), expected)
        self.assertNotEqual(semantic_sha256(payload | {"words": ["peace", "café"]}), expected)

    def test_matching_hash_reports_verification(self):
        payload = {"name": "fixture"}
        messages = []
        with self.assertNoLogs(LOGGER, level="WARNING"):
            validate_output(
                "fixture.json",
                payload,
                {"fixture.json": {"semantic_sha256": semantic_sha256(payload)}},
                progress=messages.append,
            )
        self.assertEqual(messages, ["[validate] Verified fixture.json against the recorded recipe"])

    def test_unrecorded_custom_output_is_not_compared(self):
        messages = []
        with self.assertNoLogs(LOGGER, level="WARNING"):
            validate_output("custom.json", {}, {}, progress=messages.append)
        self.assertEqual(messages, [])

    def test_mismatch_warns_and_cli_still_publishes(self):
        expected = "0" * 64
        payload = read_resource_json("counts", "rules.v3.json")
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.manifest_reader({"counts.v3.json": {"semantic_sha256": expected}}),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertLogs(LOGGER, level="WARNING") as logs,
        ):
            main(["build", "counts", "--output", str(self.root)])
        self.assertIn("Output checksum mismatch for counts.v3.json", logs.output[0])
        self.assertIn(expected, logs.output[0])
        self.assertIn(semantic_sha256(payload), logs.output[0])
        self.assertIn("Build will continue", logs.output[0])
        self.assertEqual(
            json.loads((self.root / "lexicons/counts.v3.json").read_text(encoding="utf-8")), payload
        )
        self.assertIn("Built counts: counts.v3.json", stdout.getvalue())
        self.assertNotIn("[validate] Verified", stderr.getvalue())

    def test_suffix_does_not_change_the_recipe_used_for_validation(self):
        payload = read_resource_json("counts", "rules.v3.json")
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.manifest_reader(
                    {
                        "counts.v3.json": {"semantic_sha256": semantic_sha256(payload)},
                        "counts.v1.json": {"semantic_sha256": "0" * 64},
                    }
                ),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertNoLogs(LOGGER, level="WARNING"),
        ):
            main(["build", "counts", "--suffix", "v1", "--output", str(self.root)])
        self.assertIn("[validate] Verified counts.v3.json", stderr.getvalue())
        self.assertIn("Built counts: counts.v1.json", stdout.getvalue())

    def test_gcam_filename_and_compression_do_not_change_validation(self):
        source = self.root / "gi.tsv"
        source.write_text(
            "Entry\t"
            + "\t".join(CATEGORIES.values())
            + "\n"
            + "HAND\t"
            + "\t".join(CATEGORIES.values())
            + "\n",
            encoding="utf-8",
        )
        payload = build_gcam_lexicon(source)
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.manifest_reader(
                    {"gcam.v1.json": {"semantic_sha256": semantic_sha256(payload)}}
                ),
            ),
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
            self.assertNoLogs(LOGGER, level="WARNING"),
        ):
            main(
                [
                    "build",
                    "gcam",
                    "--use",
                    "v1",
                    "--source",
                    f"general-inquirer={source}",
                    "--gcam-filename",
                    "renamed.json.gz",
                    "--output",
                    str(self.root),
                ]
            )
        self.assertIn("[validate] Verified gcam.v1.json", stderr.getvalue())
        self.assertEqual(
            json.loads(gzip.decompress((self.root / "lexicons/renamed.json.gz").read_bytes())),
            payload,
        )

    def test_gazetteer_filename_override_keeps_the_recorded_recipe_reference(self):
        archive = self.root / "reference.zip"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("reference.csv", "")
        payload = build_gazetteer([archive], name="gkg-reference-gazetteer-v1")
        stderr = io.StringIO()
        with (
            patch(
                "gdelt_regkg.cli.profiles.read_resource_json",
                side_effect=self.manifest_reader(
                    {"locations.v1.json.gz": {"semantic_sha256": semantic_sha256(payload)}}
                ),
            ),
            contextlib.redirect_stdout(io.StringIO()),
            contextlib.redirect_stderr(stderr),
            self.assertNoLogs(LOGGER, level="WARNING"),
        ):
            main(
                [
                    "build",
                    "locations",
                    "--gazetteer-archives",
                    str(archive),
                    "--gazetteer-filename",
                    "places.json",
                    "--output",
                    str(self.root),
                ]
            )
        self.assertIn("[validate] Verified locations.v1.json.gz", stderr.getvalue())
        self.assertEqual(
            json.loads((self.root / "lexicons/places.json").read_text(encoding="utf-8")), payload
        )


if __name__ == "__main__":
    unittest.main()
