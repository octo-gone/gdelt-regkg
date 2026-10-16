"""Checksum-verified acquisition for the CLI."""

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


def download_source(path, entry, *, progress: Progress = ignore_progress, allow_opt_in=False):
    """Fetch an explicitly requested source and verify it before writing."""
    path = Path(path)
    if path.is_file():
        if not entry.get("manual"):
            verify_source(path, entry)
        return
    if entry.get("manual"):
        raise ValueError(
            f"Manual source required: {path.name}. {entry['instructions']} Supply --source NAME=PATH."
        )
    if entry.get("opt_in_flag") and not allow_opt_in:
        raise ValueError(
            f"Source download requires {entry['opt_in_flag']}: {entry['instructions']}"
        )
    if entry.get("terms_url"):
        progress(f"[download] Source terms: {entry['terms_url']}")
    progress(f"[download] Fetching {path.name} from {entry['url']}")
    with urlopen(
        Request(entry["url"], headers={"User-Agent": "gdelt-regkg resource setup"}), timeout=60
    ) as response:
        raw = response.read()
    if entry.get("converter") == "anew-pdf":
        if hashlib.sha256(raw).hexdigest() != entry["pdf_sha256"]:
            raise ValueError(
                f"Downloaded PDF checksum mismatch: {entry['url']}; no file was installed"
            )
        from ..builders.anew import convert_anew_pdf

        progress("[download] Converting ANEW participant rating tables to CSV")
        raw = convert_anew_pdf(raw, backend=entry.get("pdf_backend", "auto"))
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
