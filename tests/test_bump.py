import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(".github/scripts/bump.py")
METADATA = (Path("pyproject.toml"), Path("CITATION.cff"), Path("docs/README.md"))


class BumpTests(unittest.TestCase):
    def prepare(self, root, newline="\n"):
        for relative in (SCRIPT, *METADATA):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            text = (ROOT / relative).read_text(encoding="utf-8")
            path.write_bytes(text.replace("\n", newline).encode("utf-8"))

    def run_bump(self, root, part):
        return subprocess.run(
            [sys.executable, str(root / SCRIPT), f"--{part}"],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_bumps_all_versions_and_preserves_other_content(self):
        current = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"][
            "version"
        ]
        major, minor, patch = map(int, current.split("."))
        versions = {
            "patch": f"{major}.{minor}.{patch + 1}",
            "minor": f"{major}.{minor + 1}.0",
            "major": f"{major + 1}.0.0",
        }
        for part, version in versions.items():
            for newline in ("\n", "\r\n"):
                with self.subTest(part=part, newline=repr(newline)):
                    with tempfile.TemporaryDirectory() as directory:
                        root = Path(directory)
                        self.prepare(root, newline)
                        docs_path = root / "docs/README.md"
                        # Other citations can contain the same version number.
                        unrelated = (
                            f"{newline}## Another citation{newline}"
                            f"  version = {{{current}}},{newline}"
                            f"  note = {{Version {current}}},{newline}"
                        ).encode("utf-8")
                        docs_path.write_bytes(docs_path.read_bytes() + unrelated)
                        before = {path: (root / path).read_bytes() for path in METADATA}
                        result = self.run_bump(root, part)
                        self.assertEqual(result.returncode, 0, result.stderr)
                        for path in METADATA[:2]:
                            self.assertEqual(
                                (root / path).read_bytes(),
                                before[path].replace(current.encode(), version.encode()),
                            )
                        expected_docs = before[METADATA[2]][: -len(unrelated)].replace(
                            f"version {current} is:".encode(), f"version {version} is:".encode()
                        )
                        for prefix in ("  version = {", "  note = {Version "):
                            expected_docs = expected_docs.replace(
                                f"{prefix}{current}}},".encode(), f"{prefix}{version}}},".encode()
                            )
                        self.assertEqual(docs_path.read_bytes(), expected_docs + unrelated)

    def test_invalid_docs_leave_all_metadata_unchanged(self):
        for invalid in ("missing section", "missing note", "duplicate version", "missing file"):
            with self.subTest(invalid=invalid):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    self.prepare(root)
                    docs_path = root / "docs/README.md"
                    docs = docs_path.read_text(encoding="utf-8")
                    if invalid == "missing section":
                        docs = docs.replace("## Citing the software", "## Software")
                    elif invalid == "missing note":
                        docs = docs.replace("  note = {Version ", "  release = {Version ")
                    elif invalid == "duplicate version":
                        docs = docs.replace("  version = {", "  version = {0.0.0},\n  version = {")
                    if invalid == "missing file":
                        docs_path.unlink()
                    else:
                        docs_path.write_text(docs, encoding="utf-8")
                    before = {
                        path: (root / path).read_bytes()
                        for path in METADATA
                        if (root / path).exists()
                    }
                    result = self.run_bump(root, "patch")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("docs", result.stderr)
                    for path, content in before.items():
                        self.assertEqual((root / path).read_bytes(), content)


if __name__ == "__main__":
    unittest.main()
