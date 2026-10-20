"""Refresh validated static-site data; preserve published files on fetch failure."""

from __future__ import annotations

import argparse
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import math
from pathlib import Path
import sys

from . import METHODOLOGY_VERSION
from .alignment import align_congresses
from .analysis import analyze_congress, current_congress
from .data import atomic_write, fetch_csv, json_bytes, utc_now

SUMMARY_KEYS = (
    "congress", "start_year", "end_year", "members", "rollcalls", "last_vote_date",
    "fiedler_value", "sweep_conductance", "mean_betweenness", "max_betweenness",
    "gini_betweenness", "data_file",
)


def build_congress(congress: int, cache: Path, refresh: bool, offline: bool) -> dict:
    frames = {}
    sources = {}
    for kind in ("votes", "members", "rollcalls"):
        frames[kind], sources[kind] = fetch_csv(congress, kind, cache, refresh=refresh, offline=offline)
    return analyze_congress(frames["votes"], frames["members"], frames["rollcalls"], congress,
                            {"sources": sources, "generated_at": utc_now()})


def axis_bounds(congresses: Iterable[dict], *, aligned: bool = False) -> dict[str, list[float]]:
    """Use the same padded display limits for every published Congress."""
    maxima = {"x": 0.0, "y": 0.0} if aligned else {"x": 0.0, "y": 0.0, "betweenness": 0.0}
    for congress in congresses:
        for node in congress["nodes"]:
            for axis in maxima:
                value = float(node[f"aligned_{axis}" if aligned else axis])
                if not math.isfinite(value):
                    raise ValueError(f"Nonfinite {axis} coordinate in Congress {congress['congress']}.")
                maxima[axis] = max(maxima[axis], abs(value))
    limits = {axis: round(math.ceil(max(value * 1.05, 0.05) / 0.05) * 0.05, 6)
              for axis, value in maxima.items()}
    return {axis: [0.0 if axis == "betweenness" else -limit, limit]
            for axis, limit in limits.items()}


def publish(results: list[dict], output: Path) -> dict:
    """Merge successful analyses after the entire requested build has passed.

    A refreshed Congress can change every later alignment, so merge the raw
    analyses and recompute the complete chain before publishing. All JSON
    serializes before any published file is changed. Individual files replace
    atomically and the index is published last.
    """
    index_path = output / "index.json"
    existing = {}
    if index_path.exists():
        previous = json.loads(index_path.read_text(encoding="utf-8"))
        if previous.get("schema_version") != 1 or previous.get("methodology_version") != METHODOLOGY_VERSION:
            requested = {result["congress"] for result in results}
            historical = {row["congress"] for row in previous.get("congresses", [])}
            if historical - requested:
                raise ValueError("Methodology/schema changed: rebuild all previously published Congresses.")
        existing = {row["congress"]: row for row in previous.get("congresses", [])}
    if len({result["congress"] for result in results}) != len(results):
        raise ValueError("Cannot publish duplicate Congress numbers.")
    for result in results:
        existing[result["congress"]] = {key: result[key] for key in SUMMARY_KEYS}
    updated = {result["congress"]: result for result in results}

    def published_congresses() -> Iterable[dict]:
        for number, summary in existing.items():
            if number in updated:
                yield updated[number]
            else:
                yield json.loads((output / summary["data_file"]).read_text(encoding="utf-8"))

    aligned = align_congresses(published_congresses())
    serialized = [(output / result["data_file"], json_bytes(result)) for result in aligned]
    index = {
        "schema_version": 1, "generated_at": utc_now(),
        "source": {"name": "Voteview Congressional Roll-Call Votes Database", "url": "https://voteview.com/data"},
        "methodology_version": METHODOLOGY_VERSION,
        "axis_bounds": axis_bounds(aligned),
        "aligned_axis_bounds": axis_bounds(aligned, aligned=True),
        "congresses": [existing[number] for number in sorted(existing)],
    }
    encoded_index = json_bytes(index)
    for path, content in serialized:
        atomic_write(path, content)
    atomic_write(index_path, encoded_index)
    return index


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--congress", nargs="+", default=["all"], help="Congress numbers, 'current', or 'all' (default).")
    command.add_argument("--refresh", action="store_true", help="Re-download selected source data instead of using cache.")
    command.add_argument("--offline", action="store_true", help="Use only checksummed local source caches.")
    command.add_argument("--cache-dir", type=Path, default=Path(".cache/voteview"))
    command.add_argument("--output", type=Path, default=Path("site/data"))
    command.add_argument("--workers", type=int, default=4, help="Concurrent Congress builds (1-8, default 4).")
    return command


def main(argv: list[str] | None = None) -> int:
    command = parser()
    args = command.parse_args(argv)
    if args.refresh and args.offline:
        command.error("--refresh and --offline cannot be combined.")
    if not 1 <= args.workers <= 8:
        command.error("--workers must be between 1 and 8.")
    latest = current_congress()
    try:
        congresses = set()
        for value in args.congress:
            if value == "all":
                congresses.update(range(1, latest + 1))
            else:
                congresses.add(latest if value == "current" else int(value))
        if not congresses or min(congresses) < 1 or max(congresses) > latest:
            raise ValueError
    except ValueError:
        command.error(f"--congress accepts integers 1-{latest}, 'current', or 'all'.")
    results = []
    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        jobs = {executor.submit(build_congress, congress, args.cache_dir, args.refresh, args.offline): congress
                for congress in sorted(congresses)}
        for future in as_completed(jobs):
            congress = jobs[future]
            try:
                result = future.result()
                results.append(result)
                print(f"Congress {congress}: {result['members']} senators, {result['rollcalls']} votes, "
                      f"latest {result['last_vote_date']}", flush=True)
            except Exception as exc:
                failures.append(congress)
                print(f"Congress {congress} failed: {exc}", file=sys.stderr, flush=True)
    if failures:
        print(f"Build failed for {sorted(failures)}. Published site data was not changed.", file=sys.stderr)
        return 1
    try:
        index = publish(results, args.output)
    except (OSError, ValueError, KeyError) as exc:
        print(f"Could not publish data: {exc}", file=sys.stderr)
        return 1
    print(f"Published {len(results)} Congresses; index contains {len(index['congresses'])}.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
