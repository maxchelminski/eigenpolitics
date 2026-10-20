"""Shared-member registration preserves geometry and exposes uncertain links."""

from copy import deepcopy
import unittest

import numpy as np

from eigenpolitics.alignment import align_congresses


POINTS = np.array([[-.3, -.1], [.2, -.2], [.1, .4], [.05, .06]])


def congress(number, points=POINTS, identifiers=None):
    identifiers = identifiers or list(range(1, len(points) + 1))
    return {
        "congress": number, "fiedler_value": .5, "sweep_partition": [1, 2],
        "eigenvalues": [0, .5, .8], "edges": [{"source": 1, "target": 2, "weight": .9}],
        "nodes": [{"id": identifier, "x": float(point[0]), "y": float(point[1]), "betweenness": .1}
                  for identifier, point in zip(identifiers, points)],
    }


def aligned_points(result):
    return np.array([[node["aligned_x"], node["aligned_y"]] for node in result["nodes"]])


class AlignmentTests(unittest.TestCase):
    def test_rotation_reflection_translation_recovered_without_scaling(self):
        angle = .7
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        for transform in (rotation, rotation @ np.diag([-1, 1])):
            with self.subTest(transform=transform):
                source = POINTS @ transform + [.8, -.6]
                results = align_congresses([congress(1), congress(2, source)])
                np.testing.assert_allclose(aligned_points(results[1]), POINTS, atol=1e-12)
                self.assertLess(results[1]["alignment"]["residual_after"], 1e-12)
                self.assertEqual(results[1]["alignment"]["scale"], 1)
                self.assertEqual(results[1]["alignment"]["anchor_ids"], [1, 2, 3, 4])
                fit = np.array(results[1]["alignment"]["rotation"])
                np.testing.assert_allclose(fit.T @ fit, np.eye(2), atol=1e-12)

    def test_member_change_survives_registration_relative_to_shared_anchors(self):
        angle = -.4
        rotation = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
        # New member 5 has no anchor constraint, so its real offset survives.
        current = np.vstack([POINTS[:3], POINTS[3] + [.07, -.12]])
        results = align_congresses([
            congress(1), congress(2, current @ rotation + [.3, .2], [1, 2, 3, 5]),
        ])
        np.testing.assert_allclose(aligned_points(results[1]), current, atol=1e-12)
        self.assertEqual(results[1]["alignment"]["anchor_ids"], [1, 2, 3])
        # A shared senator's changed geometry also produces nonzero residual.
        changed = POINTS.copy()
        changed[3] += [.07, -.12]
        result = align_congresses([congress(1), congress(2, changed)])[1]
        self.assertGreater(result["alignment"]["residual_after"], .01)
        self.assertGreater(np.linalg.norm(aligned_points(result)[3] - POINTS[3]), .01)

    def test_raw_eigenvectors_graph_and_inputs_are_untouched(self):
        source = [congress(2, POINTS + [.1, .2]), congress(1)]
        before = deepcopy(source)
        results = align_congresses(source)
        self.assertEqual(source, before)
        self.assertEqual([result["congress"] for result in results], [1, 2])
        for result, original in zip(results, reversed(before)):
            self.assertEqual(result["eigenvalues"], original["eigenvalues"])
            self.assertEqual(result["edges"], original["edges"])
            self.assertEqual(result["sweep_partition"], original["sweep_partition"])
            self.assertEqual(result["fiedler_value"], original["fiedler_value"])
            for node, raw in zip(result["nodes"], original["nodes"]):
                self.assertEqual({key: node[key] for key in raw}, raw)
            distances = np.linalg.norm(POINTS[:, None] - POINTS[None, :], axis=2)
            transformed = aligned_points(result)
            np.testing.assert_allclose(
                np.linalg.norm(transformed[:, None] - transformed[None, :], axis=2), distances,
                atol=1e-12,
            )

    def test_insufficient_overlap_resets_and_next_link_uses_new_segment(self):
        results = align_congresses([
            congress(1), congress(2, identifiers=[1, 2, 5, 6]),
            congress(3, POINTS + [.1, -.2], identifiers=[1, 2, 5, 6]),
        ])
        self.assertEqual(results[1]["alignment"]["status"], "reset")
        self.assertEqual(results[1]["alignment"]["anchor_count"], 2)
        self.assertEqual(results[1]["alignment"]["root_congress"], 2)
        np.testing.assert_array_equal(aligned_points(results[1]), POINTS)
        self.assertEqual(results[2]["alignment"]["status"], "aligned")
        self.assertEqual(results[2]["alignment"]["segment_id"], 2)
        np.testing.assert_allclose(aligned_points(results[2]), POINTS, atol=1e-12)

    def test_missing_congress_and_rank_deficiency_reset(self):
        gap = align_congresses([congress(1), congress(3)])[1]
        self.assertEqual(gap["alignment"]["status"], "reset")
        self.assertIsNone(gap["alignment"]["reference_congress"])
        self.assertEqual(gap["alignment"]["segment_id"], 3)
        line = np.array([[-.2, 0], [0, 0], [.2, 0], [.4, 0]])
        for first, second in [(line, POINTS), (POINTS, line), (line, line)]:
            result = align_congresses([congress(1, first), congress(2, second)])[1]
            self.assertEqual(result["alignment"]["status"], "reset")
            self.assertIn("rank deficient", result["alignment"]["reason"])
            self.assertIsNone(result["alignment"]["residual_after"])

    def test_scale_difference_is_preserved_and_weak_links_are_flagged(self):
        result = align_congresses([congress(1), congress(2, POINTS * 2)])[1]
        self.assertEqual(result["alignment"]["status"], "aligned")
        self.assertEqual(result["alignment"]["quality"], "weak")
        self.assertAlmostEqual(result["alignment"]["relative_residual"], 1)
        self.assertEqual(result["alignment"]["weak_relative_residual_threshold"], .5)
        self.assertAlmostEqual(np.linalg.norm(aligned_points(result)[0] - aligned_points(result)[1]),
                               2 * np.linalg.norm(POINTS[0] - POINTS[1]))

    def test_full_rank_point_sets_with_rank_deficient_cross_covariance_reset(self):
        first = np.array([[1, 0], [-1, 0], [0, 1], [0, -1]])
        second = np.array([[1, 1], [-1, 1], [0, -1], [0, -1]])
        result = align_congresses([congress(1, first), congress(2, second)])[1]
        self.assertEqual(result["alignment"]["source_rank"], 2)
        self.assertEqual(result["alignment"]["target_rank"], 2)
        self.assertEqual(result["alignment"]["cross_rank"], 1)
        self.assertEqual(result["alignment"]["status"], "reset")

    def test_nonfinite_and_duplicate_coordinates_fail(self):
        invalid = congress(2)
        invalid["nodes"][0]["x"] = float("nan")
        with self.assertRaisesRegex(ValueError, "Nonfinite"):
            align_congresses([congress(1), invalid])
        duplicate = congress(2, identifiers=[1, 1, 2, 3])
        with self.assertRaisesRegex(ValueError, "Duplicate member"):
            align_congresses([duplicate])
        with self.assertRaisesRegex(ValueError, "duplicate Congress"):
            align_congresses([congress(1), congress(1)])


if __name__ == "__main__":
    unittest.main()
