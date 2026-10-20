"""Bounded Voteview downloads with validated, checksummed on-disk caching."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
from datetime import datetime, timezone
from urllib.request import Request, urlopen

import pandas as pd

BASE_URL = "https://voteview.com/static/data/out"
MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
REQUIRED_COLUMNS = {
    "votes": {"congress", "chamber", "icpsr", "rollnumber", "cast_code"},
    "members": {"congress", "chamber", "icpsr", "state_icpsr", "state_abbrev", "party_code", "bioname"},
    "rollcalls": {"congress", "chamber", "rollnumber", "date"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write(path: Path, content: bytes) -> None:
    """Replace a file only after its complete contents have reached disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def json_bytes(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")


def validate_csv(content: bytes, kind: str, congress: int) -> pd.DataFrame:
    frame = pd.read_csv(io.BytesIO(content), low_memory=False)
    missing = REQUIRED_COLUMNS[kind] - set(frame.columns)
    if missing:
        raise ValueError(f"{kind} schema missing columns: {sorted(missing)}")
    if frame.empty or not (frame["congress"] == congress).all():
        raise ValueError(f"Unexpected or empty Congress {congress} {kind} data.")
    if not (frame["chamber"] == "Senate").any():
        raise ValueError(f"No Senate records in Congress {congress} {kind} data.")
    return frame


def fetch_csv(congress: int, kind: str, cache_dir: Path, *, refresh: bool = False,
              offline: bool = False, timeout: float = 30.0, retries: int = 3) -> tuple[pd.DataFrame, dict]:
    if kind not in REQUIRED_COLUMNS:
        raise ValueError(f"Unsupported data kind: {kind}")
    if offline and refresh:
        raise ValueError("--offline and --refresh cannot be combined.")
    filename = f"S{congress:03d}_{kind}.csv"
    url = f"{BASE_URL}/{kind}/{filename}"
    cached = cache_dir / filename
    sidecar = cache_dir / f"{filename}.json"
    if cached.exists() and sidecar.exists() and not refresh:
        content = cached.read_bytes()
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        if hashlib.sha256(content).hexdigest() != metadata.get("sha256"):
            raise ValueError(f"Cache checksum mismatch for {filename}; rerun with --refresh.")
        return validate_csv(content, kind, congress), {**metadata, "cache_used": True}
    if offline:
        raise FileNotFoundError(f"Missing verified cache for {filename}. Run once without --offline.")
    error = None
    for attempt in range(retries):
        try:
            request = Request(url, headers={"User-Agent": "Eigenpolitics/1.0 (academic Senate network analysis)"})
            with urlopen(request, timeout=timeout) as response:
                content = response.read(MAX_DOWNLOAD_BYTES + 1)
                if len(content) > MAX_DOWNLOAD_BYTES:
                    raise ValueError(f"Download exceeds {MAX_DOWNLOAD_BYTES} bytes: {filename}")
                modified = response.headers.get("Last-Modified")
            frame = validate_csv(content, kind, congress)
            metadata = {"url": url, "fetched_at": utc_now(), "sha256": hashlib.sha256(content).hexdigest(),
                        "bytes": len(content), "source_last_modified": modified}
            atomic_write(cached, content)
            atomic_write(sidecar, json_bytes(metadata))
            return frame, {**metadata, "cache_used": False}
        except (OSError, ValueError, pd.errors.ParserError) as exc:
            error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Failed to fetch {url} after {retries} attempts: {error}") from error
