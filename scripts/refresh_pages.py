#!/usr/bin/env python3
"""Refresh Pages data and report content changes without timestamp-only commits."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eigenpolitics import METHODOLOGY_VERSION
from eigenpolitics.analysis import current_congress
from eigenpolitics.cli import main as refresh_data


def snapshot_fingerprint(output: Path) -> tuple:
    """Identify source content and method, ignoring retrieval/build timestamps."""
    index = json.loads((output / "index.json").read_text(encoding="utf-8"))
    version = (index["schema_version"], index["methodology_version"])
    rows = sorted(index["congresses"], key=lambda row: row["congress"])
    numbers = [row["congress"] for row in rows]
    if not numbers or numbers != list(range(1, max(numbers) + 1)):
        raise ValueError("Published history must contain each Congress exactly once, starting at 1.")
    fingerprints = []
    for row in rows:
        number = row["congress"]
        if row["data_file"] != f"congresses/{number}.json":
            raise ValueError(f"Unexpected snapshot path for Congress {number}.")
        data = json.loads((output / row["data_file"]).read_text(encoding="utf-8"))
        if data["congress"] != number or (data["schema_version"], data["methodology_version"]) != version:
            raise ValueError(f"Congress {number} does not match its index version/identity.")
        sources = data["provenance"]["sources"]
        hashes = tuple(sources[kind]["sha256"] for kind in ("votes", "members", "rollcalls"))
        if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in hashes):
            raise ValueError(f"Congress {number} has missing or invalid source checksums.")
        fingerprints.append((number, hashes))
    return version + (tuple(fingerprints),)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate the existing snapshot without network access.")
    parser.add_argument("--output", type=Path, default=Path("site/data"))
    parser.add_argument("--cache-dir", type=Path, default=Path(".cache/voteview"))
    args = parser.parse_args(argv)
    try:
        before = snapshot_fingerprint(args.output)
        if before[:2] != (1, METHODOLOGY_VERSION):
            raise ValueError("Snapshot methodology/schema is outdated; rebuild the full history before publishing.")
        if args.check:
            print(f"Validated {len(before[2])} Congress snapshots (method {METHODOLOGY_VERSION}).")
            return 0
        latest = current_congress()
        result = refresh_data([
            "--congress", str(latest), str(max(1, latest - 1)), "--refresh",
            "--output", str(args.output), "--cache-dir", str(args.cache_dir),
        ])
        if result:
            print("Refresh failed; the previously deployed Pages site remains live.", file=sys.stderr)
            return result
        changed = before != snapshot_fingerprint(args.output)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"Pages snapshot validation failed: {exc}", file=sys.stderr)
        return 1
    message = ("Source content changed; the validated snapshot will be committed before deployment."
               if changed else "Source content unchanged; updated retrieval times will deploy without a Git commit.")
    print(message)
    if github_output := os.environ.get("GITHUB_OUTPUT"):
        with Path(github_output).open("a", encoding="utf-8") as stream:
            stream.write(f"changed={str(changed).lower()}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
