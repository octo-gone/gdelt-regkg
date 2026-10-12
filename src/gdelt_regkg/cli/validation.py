"""Compare compiled JSON with the recorded recipe, independently of filenames."""

import hashlib
import json
import logging

from .progress import Progress, ignore_progress

LOGGER = logging.getLogger(__name__)


def semantic_sha256(payload: dict) -> str:
    """Hash parsed JSON using the serialization used by existing recipe hashes."""
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


def validate_output(
    filename: str,
    payload: dict,
    outputs: dict,
    *,
    progress: Progress = ignore_progress,
) -> None:
    """Warn about changed recorded output; custom recipes may have no reference."""
    expected = outputs.get(filename, {}).get("semantic_sha256")
    if expected is None:
        return
    actual = semantic_sha256(payload)
    if actual != expected:
        LOGGER.warning(
            "[warning] Output checksum mismatch for %s: expected %s, got %s. "
            "Build will continue; custom inputs or options may produce different contents.",
            filename,
            expected,
            actual,
        )
    else:
        progress(f"[validate] Verified {filename} against the recorded recipe")
