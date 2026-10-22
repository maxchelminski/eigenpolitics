"""Ensure scheduled publishing preserves history and avoids timestamp-only commits."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eigenpolitics import METHODOLOGY_VERSION
from scripts.refresh_pages import main, snapshot_fingerprint


def write_snapshot(output, numbers=(1, 2), *, timestamp="2026-10-20", checksum="a" * 64,
                   methodology=METHODOLOGY_VERSION):
    (output / "congresses").mkdir(parents=True, exist_ok=True)
    version = {"schema_version": 1, "methodology_version": methodology}
    rows = []
    for number in numbers:
        row = {"congress": number, "data_file": f"congresses/{number}.json"}
        rows.append(row)
        data = {**version, **row, "provenance": {"generated_at": timestamp, "sources": {
            kind: {"sha256": checksum, "fetched_at": timestamp}
            for kind in ("votes", "members", "rollcalls")}}}
        (output / row["data_file"]).write_text(json.dumps(data), encoding="utf-8")
    (output / "index.json").write_text(json.dumps({**version, "generated_at": timestamp,
                                                   "congresses": rows}), encoding="utf-8")


class PagesRefreshTests(unittest.TestCase):
    def test_timestamps_do_not_change_source_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_snapshot(output)
            before = snapshot_fingerprint(output)
            write_snapshot(output, timestamp="2026-10-22")
            self.assertEqual(before, snapshot_fingerprint(output))

    def test_source_content_methodology_and_rollover_change_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            write_snapshot(output)
            before = snapshot_fingerprint(output)
            for change in ({"checksum": "b" * 64}, {"methodology": "next"}, {"numbers": (1, 2, 3)}):
                with self.subTest(change=change):
                    write_snapshot(output, **change)
                    self.assertNotEqual(before, snapshot_fingerprint(output))

    def test_history_gaps_duplicate_congresses_and_invalid_hashes_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            for change in ({"numbers": (1, 3)}, {"numbers": (1, 1)}, {"checksum": "missing"}):
                with self.subTest(change=change):
                    write_snapshot(output, **change)
                    with self.assertRaises(ValueError):
                        snapshot_fingerprint(output)

    def test_check_is_offline_and_rejects_outdated_methodology(self):
        with tempfile.TemporaryDirectory() as directory, patch("scripts.refresh_pages.refresh_data") as refresh:
            output = Path(directory)
            write_snapshot(output)
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--check", "--output", str(output)]), 0)
            write_snapshot(output, methodology="old")
            with redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--check", "--output", str(output)]), 1)
            refresh.assert_not_called()

    def test_refresh_failure_does_not_signal_a_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "data"
            github_output = Path(directory) / "actions-output"
            write_snapshot(output)
            before = snapshot_fingerprint(output)
            with patch.dict(os.environ, {"GITHUB_OUTPUT": str(github_output)}), \
                    patch("scripts.refresh_pages.refresh_data", return_value=1), \
                    redirect_stderr(io.StringIO()):
                self.assertEqual(main(["--output", str(output)]), 1)
            self.assertFalse(github_output.exists())
            self.assertEqual(before, snapshot_fingerprint(output))

    def test_refresh_only_current_previous_and_reports_content_change(self):
        for changed in (False, True):
            with self.subTest(changed=changed), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / "data"
                github_output = Path(directory) / "actions-output"
                write_snapshot(output)

                def refresh(argv):
                    self.assertEqual(argv[:4], ["--congress", "3", "2", "--refresh"])
                    write_snapshot(output, numbers=(1, 2, 3) if changed else (1, 2),
                                   timestamp="2026-10-22")
                    return 0

                with patch.dict(os.environ, {"GITHUB_OUTPUT": str(github_output)}), \
                        patch("scripts.refresh_pages.current_congress", return_value=3), \
                        patch("scripts.refresh_pages.refresh_data", side_effect=refresh), \
                        redirect_stdout(io.StringIO()):
                    self.assertEqual(main(["--output", str(output)]), 0)
                self.assertEqual(github_output.read_text(encoding="utf-8"), f"changed={str(changed).lower()}\n")


if __name__ == "__main__":
    unittest.main()
