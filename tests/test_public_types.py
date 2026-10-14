"""Check public result inference from a consumer outside the package."""

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path


class PublicTypingTests(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("mypy"), "Requires the development mypy dependency"
    )
    def test_consumer_factory_return_types(self):
        path = Path(__file__).parent / "typing/public_api.py"
        result = subprocess.run(
            [sys.executable, "-m", "mypy", "--follow-imports=silent", str(path)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
