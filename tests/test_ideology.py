"""NOMINATE scores are source estimates, never imputed spectral coordinates."""

import json
import unittest

import pandas as pd

from eigenpolitics.ideology import nominate_fields, nominate_provenance


class IdeologyTests(unittest.TestCase):
    def test_source_scores_are_preserved_including_boundaries(self):
        source = {"nominate_dim1": -1, "nominate_dim2": 1, "conditional": 1}
        result = nominate_fields(source)
        self.assertEqual(result, {
            "nominate_dim1": -1.0, "nominate_dim2": 1.0, "nominate_conditional": True,
        })
        self.assertEqual(source, {"nominate_dim1": -1, "nominate_dim2": 1, "conditional": 1})
        self.assertEqual(nominate_fields({"nominate_dim1": .124, "nominate_dim2": -.508})["nominate_dim1"], .124)

    def test_missing_metadata_serializes_as_null_instead_of_center(self):
        for missing in (None, float("nan"), pd.NA, ""):
            with self.subTest(missing=missing):
                result = nominate_fields({"nominate_dim1": missing, "nominate_dim2": missing})
                self.assertIsNone(result["nominate_dim1"])
                self.assertIsNone(result["nominate_dim2"])
                self.assertIsNone(result["nominate_conditional"])
                self.assertNotIn("NaN", json.dumps(result, allow_nan=False))
        self.assertEqual(nominate_fields({}), {
            "nominate_dim1": None, "nominate_dim2": None, "nominate_conditional": None,
        })

    def test_incomplete_pair_keeps_the_available_score_without_imputation(self):
        result = nominate_fields({"nominate_dim1": .7, "nominate_dim2": None, "x": .1, "y": .2})
        self.assertEqual(result["nominate_dim1"], .7)
        self.assertIsNone(result["nominate_dim2"])
        self.assertEqual(nominate_provenance([result])["complete_member_scores"], 0)

    def test_invalid_scores_fail_instead_of_being_clipped_or_hidden(self):
        for invalid in (-1.01, 1.01, float("inf"), float("-inf"), "invalid"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(ValueError, "Voteview nominate_dim1"):
                    nominate_fields({"nominate_dim1": invalid, "nominate_dim2": .1})
        with self.assertRaisesRegex(ValueError, "Voteview conditional"):
            nominate_fields({"conditional": 2})

    def test_provenance_distinguishes_missing_and_provisional_scores(self):
        nodes = [
            nominate_fields({"nominate_dim1": .2, "nominate_dim2": -.4, "conditional": 1}),
            nominate_fields({"nominate_dim1": 0, "nominate_dim2": 0, "conditional": 0}),
            nominate_fields({"nominate_dim1": .7}),
        ]
        result = nominate_provenance(nodes)
        self.assertEqual(result["complete_member_scores"], 2)
        self.assertEqual(result["missing_member_scores"], 1)
        self.assertEqual(result["conditional_member_scores"], 1)
        self.assertEqual(result["unknown_conditional_status"], 1)
        self.assertEqual(result["axis_bounds"], {"x": [-1, 1], "y": [-1, 1]})


if __name__ == "__main__":
    unittest.main()
