"""CLI checks using self-contained fixtures and disposable output directories."""

import contextlib
import gzip
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gdelt_regkg.builders.themes import authored_theme_input
from gdelt_regkg.cli import main
from gdelt_regkg.cli.build import publish
from gdelt_regkg.cli.inputs import parse_sources, required_sources, resolve_inputs
from gdelt_regkg.cli.profiles import Artifact, BuildContext, compile_profiles
from gdelt_regkg.utils import read_resource_json


def recipe_for(**sources):
    return {
        "sources": {
            name: {
                "filename": name + ".txt",
                "url": "https://example.org/" + name,
                "sha256": hashlib.sha256(body).hexdigest(),
            }
            for name, body in sources.items()
        },
        "gazetteer_sources": [],
    }


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)


class InputTests(WorkspaceTests):
    def test_explicit_source_wins_over_discovery_and_downloads(self):
        explicit = self.root / "custom.tsv"
        explicit.write_bytes(b"caller supplied edition")
        with patch("gdelt_regkg.cli.inputs.download_source") as download:
            inputs = resolve_inputs(
                self.root / "output",
                targets=("tone",),
                sources={"general-inquirer": explicit},
                sources_dir=self.root / "missing",
                download_sources=True,
                recipe=recipe_for(**{"general-inquirer": b"recorded"}),
            )
        download.assert_not_called()
        self.assertEqual(inputs.sources["general-inquirer"], explicit)
        self.assertFalse(inputs.output.exists())

    def test_discovered_sources_are_checked_without_network(self):
        recipe = recipe_for(**{"general-inquirer": b"recorded"})
        path = self.root / "general-inquirer.txt"
        path.write_bytes(b"recorded")
        with patch("gdelt_regkg.cli.sources.urlopen") as network:
            inputs = resolve_inputs(
                self.root / "output", targets=("tone",), sources_dir=self.root, recipe=recipe
            )
        network.assert_not_called()
        self.assertEqual(inputs.sources["general-inquirer"], path)
        path.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            resolve_inputs(
                self.root / "output", targets=("tone",), sources_dir=self.root, recipe=recipe
            )

    def test_only_needed_sources_are_downloaded_and_verified_before_writing(self):
        recipe = recipe_for(**{"general-inquirer": b"recorded", "crisislex": b"unused"})
        with patch(
            "gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(b"recorded")
        ) as network:
            inputs = resolve_inputs(
                self.root / "output",
                targets=("tone", "counts"),
                sources_dir=self.root,
                download_sources=True,
                recipe=recipe,
            )
        self.assertEqual(network.call_count, 1)
        self.assertEqual(set(inputs.sources), {"general-inquirer"})
        self.assertFalse(inputs.output.exists())
        other = self.root / "other"
        with (
            patch("gdelt_regkg.cli.sources.urlopen", return_value=io.BytesIO(b"changed")),
            self.assertRaisesRegex(ValueError, "checksum mismatch"),
        ):
            resolve_inputs(
                self.root / "output",
                targets=("tone",),
                sources_dir=other,
                download_sources=True,
                recipe=recipe,
            )
        self.assertFalse(other.exists())

    def test_missing_sources_are_reported_together(self):
        with self.assertRaises(ValueError) as error:
            resolve_inputs(self.root / "output", targets=("tone", "themes"))
        self.assertIn("general-inquirer", str(error.exception))
        self.assertIn("crisislex", str(error.exception))
        self.assertFalse((self.root / "output").exists())

    def test_gcam_dependencies_and_authored_theme_mode(self):
        required = required_sources(("gcam",))
        authored = required_sources(("gcam",), authored_themes_only=True)
        self.assertEqual(set(required) - set(authored), {"crisislex"})
        self.assertIn("wordnet-16", authored)
        self.assertEqual(required_sources(("counts", "ner")), ())

    def test_explicit_wordnet_directories_are_supported(self):
        path = self.root / "source.txt"
        path.write_bytes(b"source")
        sources = {name: path for name in required_sources(("gcam",), authored_themes_only=True)}
        for name in ("wordnet-31", "wordnet-20", "wordnet-16", "wordnet-annotations"):
            sources[name] = self.root
        inputs = resolve_inputs(
            self.root / "output", targets=("gcam",), sources=sources, authored_themes_only=True
        )
        self.assertEqual(inputs.sources["wordnet-31"], self.root)

    def test_gazetteer_recipe_format_is_preserved(self):
        body = b"archive"
        archive = self.root / "reference.zip"
        archive.write_bytes(body)
        recipe = {
            "sources": {},
            "gazetteer_sources": [
                {
                    "url": "https://example.org/reference.zip",
                    "sha256": hashlib.sha256(body).hexdigest(),
                }
            ],
        }
        inputs = resolve_inputs(
            self.root / "output", targets=("locations",), sources_dir=self.root, recipe=recipe
        )
        self.assertEqual(inputs.gazetteer_archives, (archive,))
        archive.write_bytes(b"changed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            resolve_inputs(
                self.root / "output", targets=("locations",), sources_dir=self.root, recipe=recipe
            )

    def test_invalid_requests_do_not_write_or_download(self):
        for options in (
            {"targets": ()},
            {"targets": ("unknown",)},
            {"targets": ("counts",), "download_sources": True},
            {"targets": ("counts",), "sources": {"crisislex": self.root}},
            {"targets": ("counts",), "gazetteer_archives": ()},
        ):
            with (
                self.subTest(options=options),
                patch("gdelt_regkg.cli.inputs.download_source") as download,
                self.assertRaises(ValueError),
            ):
                resolve_inputs(self.root / "output", **options)
            download.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_source_syntax_retains_equals_and_spaces_in_paths(self):
        self.assertEqual(
            parse_sources(["general-inquirer=C:/my files/a=b.tsv"]),
            {"general-inquirer": Path("C:/my files/a=b.tsv")},
        )
        for values in (
            ["unknown=file"],
            ["crisislex="],
            ["crisislex"],
            ["crisislex=a", "crisislex=b"],
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                parse_sources(values)


class CommandTests(WorkspaceTests):
    def test_build_exports_selected_authored_profiles_only(self):
        new = self.root / "new"
        with (
            contextlib.redirect_stdout(io.StringIO()),
            patch(
                "gdelt_regkg.cli.sources.urlopen", side_effect=AssertionError("Unexpected download")
            ),
        ):
            main(
                ["build", "themes", "counts", "ner", "--authored-themes-only", "--output", str(new)]
            )
        defaults = json.loads((new / "defaults.json").read_text(encoding="utf-8"))
        expected = {
            "themes.authored.json": authored_theme_input(),
            "counts.v3.json": read_resource_json("counts", "rules.v3.json"),
            "names.v1.json": read_resource_json("ner", "names.v1.json"),
        }
        self.assertEqual(set(defaults.values()), set(expected))
        for filename, payload in expected.items():
            self.assertEqual(
                json.loads((new / "lexicons" / filename).read_text(encoding="utf-8")),
                payload,
            )
        self.assertFalse((new / "lexicons/counts.v1.json").exists())

    def test_partial_build_preserves_unrelated_custom_defaults(self):
        (self.root / "defaults.json").write_text(
            json.dumps({"themes": "custom.json", "gcam": "custom-gcam.json"}), encoding="utf-8"
        )
        with contextlib.redirect_stdout(io.StringIO()):
            main(["build", "counts", "--output", str(self.root)])
        self.assertEqual(
            json.loads((self.root / "defaults.json").read_text()),
            {"themes": "custom.json", "gcam": "custom-gcam.json", "counts": "counts.v3.json"},
        )

    def test_theme_dependency_is_compiled_once_per_build_context(self):
        inputs = resolve_inputs(self.root, targets=("themes",), authored_themes_only=True)
        with patch(
            "gdelt_regkg.cli.profiles.authored_theme_input", return_value={"name": "test"}
        ) as build:
            context = BuildContext(inputs)
            self.assertIs(context.themes, context.themes)
        self.assertEqual(build.call_count, 1)

    def test_failed_compilation_does_not_change_existing_outputs(self):
        defaults = self.root / "defaults.json"
        defaults.write_text('{"themes": "custom.json"}', encoding="utf-8")
        with (
            patch(
                "gdelt_regkg.cli.profiles.BUILDERS",
                {"counts": lambda _: (_ for _ in ()).throw(ValueError("bad source"))},
            ),
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit) as error,
        ):
            main(["build", "counts", "--output", str(self.root)])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual(defaults.read_text(), '{"themes": "custom.json"}')
        self.assertEqual(list(self.root.iterdir()), [defaults])

    def test_bad_defaults_are_rejected_before_profile_writes(self):
        path = self.root / "defaults.json"
        path.write_text("[]", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "field-to-filename"):
            publish(self.root, (Artifact("lexicons/test.json", {}),), {"counts": "test.json"})
        self.assertEqual(list(self.root.iterdir()), [path])

    def test_gzip_is_deterministic_and_defaults_are_written(self):
        artifact = Artifact("lexicons/test.json.gz", {"name": "test"})
        publish(self.root, (artifact,), {"locations": "test.json.gz"})
        first = (self.root / artifact.path).read_bytes()
        publish(self.root, (artifact,), {"locations": "test.json.gz"})
        self.assertEqual(first, (self.root / artifact.path).read_bytes())
        self.assertEqual(json.loads(gzip.decompress(first)), artifact.payload)
        self.assertFalse(list(self.root.glob(".build-*")))

    def test_errors_before_compilation_and_required_subcommand(self):
        for args in (
            [],
            ["build", "unknown"],
            ["build", "tone", "--output", str(self.root / "output")],
        ):
            with (
                self.subTest(args=args),
                patch("gdelt_regkg.cli.build.compile_profiles") as compile_,
                contextlib.redirect_stderr(io.StringIO()),
                self.assertRaises(SystemExit) as error,
            ):
                main(args)
            self.assertEqual(error.exception.code, 2)
            compile_.assert_not_called()
        self.assertFalse((self.root / "output").exists())

    def test_module_entrypoints(self):
        for module in ("gdelt_regkg", "gdelt_regkg.cli"):
            result = subprocess.run(
                [sys.executable, "-m", module, "build", "--help"],
                cwd=self.root,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("NAME=PATH", result.stdout)


if __name__ == "__main__":
    unittest.main()
