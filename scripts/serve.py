#!/usr/bin/env python3
"""Serve the Eigenpolitics static site locally using the Python standard library."""

from __future__ import annotations

import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import math
from pathlib import Path
import subprocess
import sys
import threading
import time
import webbrowser


ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"
REFRESH_TIMEOUT_SECONDS = 20 * 60


class LocalHandler(SimpleHTTPRequestHandler):
    """Avoid stale JSON and directory listings during local development."""

    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()

    def list_directory(self, path: str):
        self.send_error(404, "Directory listing is disabled")
        return None


def stop_process(process: subprocess.Popen) -> None:
    """Reap an active refresh process when the server stops or time runs out."""
    if process.poll() is None:
        try:
            process.terminate()
        except ProcessLookupError:
            pass
    try:
        process.communicate(timeout=5)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except ProcessLookupError:
            pass
        process.communicate()


def run_refresh(stop_event: threading.Event, timeout_seconds: float = REFRESH_TIMEOUT_SECONDS) -> bool:
    """Run one bounded refresh without interrupting the HTTP server."""
    if stop_event.is_set():
        return False
    command = [sys.executable, str(ROOT / "scripts" / "refresh_data.py"),
               "--congress", "current", "--refresh"]
    print("[refresh] Fetching and recomputing the current Congress...", flush=True)
    try:
        process = subprocess.Popen(
            command, cwd=str(ROOT), stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
        )
    except OSError as exc:
        print(f"[refresh] Could not start the data pipeline: {exc}", flush=True)
        return False

    deadline = time.monotonic() + timeout_seconds
    while not stop_event.is_set():
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            stop_process(process)
            print("[refresh] Timed out. The next scheduled attempt will retry.", flush=True)
            return False
        try:
            output, _ = process.communicate(timeout=min(1, remaining))
        except subprocess.TimeoutExpired:
            continue
        except OSError as exc:
            stop_process(process)
            print(f"[refresh] Could not read pipeline output: {exc}", flush=True)
            return False
        if output.strip():
            print(output.strip()[-12000:], flush=True)
        if process.returncode == 0:
            print("[refresh] Complete. The updated snapshot is available to the site.", flush=True)
            return True
        print(f"[refresh] Pipeline exited with code {process.returncode}. "
              "Check the output above; the server will keep running.", flush=True)
        return False

    stop_process(process)
    print("[refresh] Stopped with the local server.", flush=True)
    return False


def refresh_loop(stop_event: threading.Event, interval_seconds: float) -> None:
    """Refresh immediately, then wait between runs; never overlap refreshes."""
    while not stop_event.is_set():
        run_refresh(stop_event)
        # Short waits also avoid platform limits on very large timeout values.
        next_run = time.monotonic() + interval_seconds
        while not stop_event.is_set():
            remaining = next_run - time.monotonic()
            if remaining <= 0:
                break
            stop_event.wait(min(60, remaining))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default: loopback only)")
    parser.add_argument("--port", type=int, default=4173, help="Port number (default: 4173)")
    parser.add_argument("--open", action="store_true", help="Open the site in the default browser")
    parser.add_argument("--refresh-hours", type=float, metavar="HOURS",
                        help="Refresh current-Congress data immediately and every HOURS while running")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    if args.refresh_hours is not None and (
        not math.isfinite(args.refresh_hours) or args.refresh_hours <= 0
    ):
        parser.error("--refresh-hours must be a finite positive number")
    if not (SITE / "index.html").is_file():
        parser.error(f"Site entry point not found: {SITE / 'index.html'}")

    handler = functools.partial(LocalHandler, directory=str(SITE))
    try:
        server = ThreadingHTTPServer((args.host, args.port), handler)
    except OSError as exc:
        print(f"Could not start the local server: {exc}", file=sys.stderr)
        print("If the port is already in use, try --port 4174.", file=sys.stderr)
        return 1

    browser_host = "127.0.0.1" if args.host == "0.0.0.0" else args.host
    url = f"http://{browser_host}:{args.port}/"
    print(f"Eigenpolitics: {url}", flush=True)
    print(f"Serving {SITE}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    stop_event = threading.Event()
    refresh_thread = None
    if args.refresh_hours is not None:
        refresh_thread = threading.Thread(
            target=refresh_loop, args=(stop_event, args.refresh_hours * 3600),
            name="eigenpolitics-refresh", daemon=True,
        )
        print(f"Local data refresh enabled: immediately, then {args.refresh_hours:g} hours "
              "after each attempt. Keep this process running.", flush=True)
        refresh_thread.start()
    try:
        if args.open:
            webbrowser.open(url)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Eigenpolitics.")
    finally:
        stop_event.set()
        server.server_close()
        if refresh_thread:
            refresh_thread.join(timeout=7)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
