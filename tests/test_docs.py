"""Offline documentation checks with disposable Markdown fixtures."""

import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github/scripts/check_docs.py"
CHECK_DOCS = runpy.run_path(str(SCRIPT))["check_repository"]


class DocumentationTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.write(
            "pyproject.toml",
            "[project.urls]\n"
            'Repository = "https://github.com/example/library"\n'
            'Documentation = "https://github.com/example/library/blob/master/docs/README.md"\n'
            'Changelog = "https://github.com/example/library/blob/master/CHANGELOG.md"\n',
        )
        self.write("README.md", "# Library\n")
        self.write("CHANGELOG.md", "# Changelog\n")
        self.write("docs/README.md", "# Documentation\n")

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def check(self):
        return CHECK_DOCS(self.root)

    def test_links_images_and_heading_or_html_anchors(self):
        self.write(
            "docs/target.md",
            "# Café: `item_name`\n\n# Entry\n\n# Entry\n\n# Entry-1\n\n"
            'Setext heading\n==============\n\n<a id="dictionary-1"></a>\n',
        )
        self.write("docs/My (file).md", "# File\n")
        self.write("docs/image.svg", "<svg/>\n")
        self.write(
            "docs/README.md",
            "# Documentation\n\n"
            "[Unicode](target.md#caf%C3%A9-item_name)\n"
            "[Duplicate](target.md#entry-1-1)\n"
            "[Setext](target.md#setext-heading)\n"
            "[HTML](target.md#dictionary-1)\n"
            "[GitHub fragment](target.md#user-content-entry)\n"
            '[Spaces](<My (file).md> "Title")\n'
            "[Parentheses](My%20(file).md)\n"
            "![Image](image.svg)\n"
            '<a href="target.md#entry">HTML link</a>\n'
            '<img src="image.svg">\n',
        )
        self.assertEqual(self.check(), [])

    def test_missing_files_and_sections_report_the_source_line(self):
        self.write(
            "docs/README.md", "# Documentation\n\n[File](missing.md)\n[Section](README.md#absent)\n"
        )
        errors = self.check()
        self.assertTrue(
            any("docs/README.md:3: missing link target: missing.md" in error for error in errors)
        )
        self.assertTrue(
            any("docs/README.md:4: missing section anchor" in error for error in errors)
        )

    def test_reference_links_and_undefined_explicit_references(self):
        self.write(
            "docs/README.md",
            "# Documentation\n\n[Full][manual]\n[Manual][]\n[Manual]\n"
            '[Missing][undefined]\n\n[MANUAL]: README.md#documentation "Title"\n',
        )
        self.assertEqual(len(self.check()), 1)
        self.assertIn("undefined link reference [undefined]", self.check()[0])
        self.write("docs/README.md", "# Documentation\n\n[Link][manual]\n\n[manual]: missing.md\n")
        self.assertTrue(any("missing link target" in error for error in self.check()))

    def test_inline_and_fenced_code_do_not_create_links_or_anchors(self):
        self.write(
            "docs/README.md",
            "# Documentation\n\n`[Ignored](missing.md)`\n"
            "``[Ignored](missing.md) with `backticks` ``\n"
            "~~~text\n[Ignored](missing.md)\n# Not a heading\n~~~~\n"
            "    [Ignored](missing.md)\n"
            '```python\nraise RuntimeError("examples must not execute")\n```\n',
        )
        self.assertEqual(self.check(), [])
        self.write("docs/link.md", "[Missing heading](README.md#not-a-heading)\n")
        self.assertTrue(any("missing section anchor" in error for error in self.check()))

    def test_example_syntax_and_unclosed_fences(self):
        self.write(
            "docs/README.md",
            "# Documentation\n\n```python\nif True\n```\n"
            '```json\n{"key": }\n```\n'
            '```jsonl\n{"first": 1}\n{"second": }\n```\n'
            "~~~text\nunclosed\n",
        )
        errors = "\n".join(self.check())
        for expected in (
            "invalid python example",
            "invalid json example",
            "invalid jsonl example",
            "unclosed code fence",
        ):
            self.assertIn(expected, errors)
        self.assertIn("docs/README.md:11: invalid jsonl example", errors)

    def test_heading_emphasis_and_html_comments(self):
        self.write(
            "docs/README.md",
            "# _Emphasized_ and `_literal_`\n\n"
            "[Heading](#emphasized-and-_literal_)\n"
            "<!-- [Ignored](missing.md)\n# Invisible heading\n-->\n",
        )
        self.assertEqual(self.check(), [])
        self.write("docs/link.md", "[Invisible](README.md#invisible-heading)\n")
        self.assertTrue(any("missing section anchor" in error for error in self.check()))

    def test_fragments_in_markdown_targets_outside_default_scan_directories(self):
        self.write("examples/README.md", "# Example\n")
        self.write("docs/README.md", "[Example](../examples/README.md#example)\n")
        self.assertEqual(self.check(), [])
        self.write("examples/README.md", "# Renamed\n")
        self.assertTrue(any("missing section anchor" in error for error in self.check()))

    def test_current_github_file_links_resolve_locally_but_remote_urls_are_not_fetched(self):
        self.write(
            "README.md",
            "# Library\n\n[Docs](https://github.com/example/library/blob/master/docs/README.md#documentation)\n"
            "[Directory](https://github.com/example/library/tree/main/docs)\n"
            "[External](https://does-not-exist.invalid/page)\n"
            "[Historical](https://github.com/example/library/blob/v1.0/removed.md)\n",
        )
        self.assertEqual(self.check(), [])
        self.write(
            "docs/README.md",
            "# Documentation\n[Broken](https://github.com/example/library/blob/main/deleted.md)\n",
        )
        self.assertTrue(any("missing link target" in error for error in self.check()))

    def test_readme_portability_metadata_links_and_repository_boundary(self):
        self.write("README.md", "# Library\n[Local anchor](#library)\n[Relative](docs/README.md)\n")
        self.assertTrue(any("absolute URL for PyPI" in error for error in self.check()))
        self.write("docs/README.md", "# Documentation\n[Outside](../../outside.md)\n")
        self.assertTrue(any("link leaves the repository" in error for error in self.check()))
        (self.root / "CHANGELOG.md").unlink()
        self.assertTrue(
            any("pyproject.toml:1: missing link target" in error for error in self.check())
        )

    def test_command_works_without_site_packages_and_exits_nonzero_on_failure(self):
        command = [sys.executable, "-S", str(SCRIPT), "--root", str(self.root)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.write("docs/README.md", "[Broken](missing.md)\n")
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("missing link target", result.stdout)


if __name__ == "__main__":
    unittest.main()
