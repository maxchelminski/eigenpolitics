"""Failure-path tests ensure broken downloads cannot replace the public data."""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from eigenpolitics.cli import main, publish
from eigenpolitics.data import fetch_csv, json_bytes, validate_csv


CSV = b"congress,chamber,icpsr,rollnumber,cast_code\n119,Senate,1,1,1\n"


class Response(io.BytesIO):
    headers = {"Last-Modified": "Tue, 20 Oct 2026 00:00:00 GMT"}


def summary(number=119):
    return {"congress": number, "start_year": 1789 + (number-1)*2, "end_year": 1791 + (number-1)*2,
            "members": 3, "rollcalls": 4, "last_vote_date": "2026-09-30", "fiedler_value": .4,
            "sweep_conductance": .3, "mean_betweenness": .1, "max_betweenness": .2,
            "gini_betweenness": .5, "data_file": f"congresses/{number}.json",
            "nodes": [{"x": -.1, "y": .2, "betweenness": .2}]}


class DataIntegrityTests(unittest.TestCase):
    def test_download_provenance_and_offline_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch("eigenpolitics.data.urlopen", return_value=Response(CSV)) as request:
                frame, provenance = fetch_csv(119, "votes", cache)
            self.assertEqual(len(frame), 1)
            self.assertEqual(len(provenance["sha256"]), 64)
            self.assertFalse(provenance["cache_used"])
            self.assertIn("S119_votes.csv", provenance["url"])
            request.assert_called_once()
            with patch("eigenpolitics.data.urlopen", side_effect=AssertionError("Network must not be used")):
                _, cached_provenance = fetch_csv(119, "votes", cache, offline=True)
            self.assertTrue(cached_provenance["cache_used"])
            self.assertEqual(provenance["fetched_at"], cached_provenance["fetched_at"])

    def test_checksum_failure_is_not_silently_accepted(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch("eigenpolitics.data.urlopen", return_value=Response(CSV)):
                fetch_csv(119, "votes", cache)
            (cache / "S119_votes.csv").write_bytes(CSV + b"\n")
            with self.assertRaisesRegex(ValueError, "checksum"):
                fetch_csv(119, "votes", cache, offline=True)

    def test_invalid_refresh_does_not_replace_valid_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            cache = Path(directory)
            with patch("eigenpolitics.data.urlopen", return_value=Response(CSV)):
                fetch_csv(119, "votes", cache)
            prior = (cache / "S119_votes.csv").read_bytes()
            with patch("eigenpolitics.data.urlopen", return_value=Response(b"<html>maintenance</html>")):
                with self.assertRaises(RuntimeError):
                    fetch_csv(119, "votes", cache, refresh=True, retries=1)
            self.assertEqual((cache / "S119_votes.csv").read_bytes(), prior)

    def test_wrong_congress_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected"):
            validate_csv(CSV, "votes", 118)

    def test_publish_merges_previous_history(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            publish([summary(118)], output)
            publish([summary(119)], output)
            index = json.loads((output / "index.json").read_text())
            self.assertEqual([row["congress"] for row in index["congresses"]], [118, 119])
            self.assertTrue((output / "congresses/118.json").exists())

    def test_subset_refresh_keeps_fixed_axes_covering_historical_nodes(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            historical = {**summary(1), "nodes": [{"x": -.68, "y": .83, "betweenness": .7}]}
            initial = publish([historical, summary()], output)
            refreshed = publish([summary()], output)
            bounds = refreshed["axis_bounds"]
            self.assertEqual(bounds, initial["axis_bounds"])
            self.assertEqual(bounds, {"x": [-.75, .75], "y": [-.9, .9], "betweenness": [0, .75]})
            for node in historical["nodes"]:
                for axis, value in node.items():
                    self.assertLess(bounds[axis][0], value)
                    self.assertGreater(bounds[axis][1], value)

    def test_refreshed_nodes_expand_fixed_axes_before_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            publish([summary()], output)
            updated = {**summary(), "nodes": [{"x": .51, "y": -.64, "betweenness": .81}]}
            index = publish([updated], output)
            self.assertEqual(index["axis_bounds"],
                             {"x": [-.55, .55], "y": [-.7, .7], "betweenness": [0, .9]})

    def test_missing_historical_details_prevent_partial_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            publish([summary(118)], output)
            before = (output / "index.json").read_bytes()
            (output / "congresses/118.json").unlink()
            with self.assertRaises(FileNotFoundError):
                publish([summary(119)], output)
            self.assertEqual((output / "index.json").read_bytes(), before)
            self.assertFalse((output / "congresses/119.json").exists())

    def test_nonfinite_result_preserves_previous_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            publish([summary()], output)
            before = (output / "index.json").read_bytes()
            broken = {**summary(), "fiedler_value": float("nan")}
            with self.assertRaises(ValueError):
                publish([broken], output)
            self.assertEqual((output / "index.json").read_bytes(), before)
            self.assertEqual((output / "congresses/119.json").read_bytes(), json_bytes(summary()))

    def test_failed_congress_prevents_partial_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            publish([summary()], output)
            before = (output / "index.json").read_bytes()
            with patch("eigenpolitics.cli.build_congress", side_effect=RuntimeError("upstream failed")):
                with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                    result = main(["--congress", "119", "--output", str(output)])
            self.assertEqual(result, 1)
            self.assertEqual((output / "index.json").read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
