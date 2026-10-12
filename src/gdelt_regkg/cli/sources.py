"""Checksum-verified acquisition for the new CLI."""

from __future__ import annotations

import hashlib
import io
import zipfile
from pathlib import Path
from urllib.request import Request, urlopen

from .progress import Progress, ignore_progress


def verify_source(path, entry):
    if hashlib.sha256(Path(path).read_bytes()).hexdigest() != entry["sha256"]:
        raise ValueError(
            f"Source checksum mismatch: {path}. Use the recorded edition; extraction metrics apply to those inputs."
        )


def download_source(path, entry, *, progress: Progress = ignore_progress):
    """Fetch an explicitly requested source and verify it before writing."""
    path = Path(path)
    if path.is_file():
        verify_source(path, entry)
        return
    progress(f"[download] Fetching {path.name} from {entry['url']}")
    with urlopen(
        Request(entry["url"], headers={"User-Agent": "gdelt-regkg resource setup"}), timeout=60
    ) as response:
        raw = response.read()
    if "archive_member" in entry:
        if hashlib.sha256(raw).hexdigest() != entry["archive_sha256"]:
            raise ValueError(f"Downloaded archive checksum mismatch: {entry['url']}")
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            raw = archive.read(entry["archive_member"])
    if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError(
            f"Downloaded source checksum mismatch: {entry['url']}; no file was installed"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    progress(f"[download] Verified and saved {path} ({len(raw):,} bytes)")
