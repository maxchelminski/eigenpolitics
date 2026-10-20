"""Small exact examples test the graph conventions, not just implementation."""

from datetime import date
import itertools
import unittest

import networkx as nx
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.sparse.csgraph import laplacian

from eigenpolitics.analysis import (
    analyze_congress, centrality_graph, current_congress, gini, orient_vector,
    prepare_votes, similarity_matrix, sweep_conductance,
)


def fixture_frames():
    members = pd.DataFrame([
        [119, "Senate", 1, 43, "FL", 200, "EXAMPLE, Republican"],
        [119, "Senate", 2, 1, "CT", 100, "EXAMPLE, A"],
        [119, "Senate", 3, 2, "ME", 328, "EXAMPLE, B"],
        [119, "Senate", 4, 3, "MA", 100, "EXAMPLE, Inactive"],
        [119, "Senate", 42304, 99, "USA", 200, "VANCE, J. D."],
        [119, "President", 99912, 99, "USA", 200, "TRUMP, Donald"],
    ], columns=["congress", "chamber", "icpsr", "state_icpsr", "state_abbrev", "party_code", "bioname"])
    patterns = {1: [1, 6, 1, 6] * 5, 2: [6, 1, 6, 1] * 5, 3: [1, 1, 6, 6] * 5,
                4: [1] + [9] * 19, 42304: [1, 1, 6, 6] * 5}
    votes = pd.DataFrame(
        [[119, "Senate", identifier, roll + 1, code]
         for identifier, codes in patterns.items() for roll, code in enumerate(codes)],
        columns=["congress", "chamber", "icpsr", "rollnumber", "cast_code"],
    )
    rollcalls = pd.DataFrame(
        [[119, "Senate", number, f"2025-01-{number + 2:02d}"] for number in range(1, 21)],
        columns=["congress", "chamber", "rollnumber", "date"],
    )
    return votes, members, rollcalls


class ScientificTests(unittest.TestCase):
    def test_similarity_has_no_self_loops_and_correct_endpoints(self):
        votes = np.array([[1, -1, 1], [1, -1, 1], [-1, 1, -1]])
        adjacency = similarity_matrix(votes)
        np.testing.assert_allclose(np.diag(adjacency), 0)
        self.assertAlmostEqual(adjacency[0, 1], 1)
        self.assertAlmostEqual(adjacency[0, 2], 0)
        np.testing.assert_allclose(adjacency, adjacency.T)

    def test_constant_rows_are_rejected_instead_of_fabricating_correlation(self):
        with self.assertRaises(ValueError):
            similarity_matrix(np.array([[1, 1, 1], [1, -1, 0]]))

    def test_weighted_shortest_paths_really_use_distances(self):
        # Two strong edges have total distance .2, less than the direct .4.
        # Unweighted centrality would instead give every node zero.
        adjacency = np.array([[0, .9, .6], [.9, 0, .9], [.6, .9, 0]])
        graph = centrality_graph(adjacency)
        centrality = nx.betweenness_centrality(graph, weight="distance")
        self.assertEqual(centrality[1], 1)
        self.assertEqual(centrality[0], 0)
        self.assertEqual(len(list(nx.selfloop_edges(graph))), 0)

    def test_identical_voters_have_positive_distance_and_threshold_is_inclusive(self):
        graph = centrality_graph(np.array([[0, 1, .5], [1, 0, .49], [.5, .49, 0]]))
        self.assertGreater(graph[0][1]["distance"], 0)
        self.assertTrue(graph.has_edge(0, 2))
        self.assertFalse(graph.has_edge(1, 2))

    def test_complete_graph_spectrum_and_sweep(self):
        adjacency = np.ones((4, 4)) - np.eye(4)
        eigenvalues, eigenvectors = eigh(laplacian(adjacency, normed=True))
        np.testing.assert_allclose(eigenvalues, [0, 4/3, 4/3, 4/3], atol=1e-12)
        conductance, partition = sweep_conductance(adjacency, eigenvectors[:, 1])
        self.assertAlmostEqual(conductance, 2/3)
        self.assertEqual(len(partition), 2)

    def test_sweep_uses_degree_normalized_coordinates(self):
        adjacency = np.array([[0, .9, .1, .1], [.9, 0, .9, .8], [.1, .9, 0, .2], [.1, .8, .2, 0]])
        vector = np.array([.1, .2, .17, .3])
        degrees = adjacency.sum(axis=1)
        normalized_order = np.argsort(vector / np.sqrt(degrees))
        self.assertFalse(np.array_equal(normalized_order, np.argsort(vector)))
        candidates = []
        for size in range(1, 4):
            left, right = normalized_order[:size], normalized_order[size:]
            candidates.append(adjacency[np.ix_(left, right)].sum() / min(degrees[left].sum(), degrees[right].sum()))
        score, chosen = sweep_conductance(adjacency, vector)
        self.assertAlmostEqual(score, min(candidates))
        self.assertEqual(chosen, normalized_order[:np.argmin(candidates) + 1].tolist())

    def test_sweep_is_upper_bound_on_exhaustive_minimum(self):
        adjacency = np.array([[0, .9, .1, .1], [.9, 0, .2, .1], [.1, .2, 0, .9], [.1, .1, .9, 0]])
        eigenvalues, eigenvectors = eigh(laplacian(adjacency, normed=True))
        degrees = adjacency.sum(axis=1)
        all_scores = []
        for size in range(1, 4):
            for selected in itertools.combinations(range(4), size):
                other = [i for i in range(4) if i not in selected]
                score = adjacency[np.ix_(selected, other)].sum() / min(degrees[list(selected)].sum(), degrees[other].sum())
                all_scores.append(score)
        sweep, _ = sweep_conductance(adjacency, eigenvectors[:, 1])
        self.assertGreaterEqual(sweep + 1e-12, min(all_scores))
        self.assertLessEqual(eigenvalues[1] / 2, min(all_scores) + 1e-12)

    def test_metadata_and_minimum_vote_checks_retain_eligible_senators(self):
        votes, members, _ = fixture_frames()
        prepared = prepare_votes(votes, members, 119)
        self.assertIn(1, prepared.matrix.index)
        self.assertNotIn(42304, prepared.matrix.index)
        self.assertNotIn(4, prepared.matrix.index)
        excluded_ids = {entry["id"] for entry in prepared.excluded}
        self.assertEqual(excluded_ids, {4, 42304})

    def test_eligibility_depends_on_record_not_name_or_congress(self):
        votes, members, _ = fixture_frames()
        votes.loc[votes["icpsr"] == 1, "icpsr"] = 41102
        members.loc[members["icpsr"] == 1, ["icpsr", "bioname"]] = [41102, "RUBIO, Marco"]
        for congress in (1, 118, 119, 120):
            historical_votes, historical_members = votes.copy(), members.copy()
            historical_votes["congress"] = historical_members["congress"] = congress
            historical = prepare_votes(historical_votes, historical_members, congress)
            self.assertIn(41102, historical.matrix.index)
            self.assertNotIn(41102, {entry["id"] for entry in historical.excluded})

    def test_excluded_short_record_cannot_change_analysis(self):
        votes, members, rollcalls = fixture_frames()
        expected = analyze_congress(votes, members, rollcalls, 119, {})
        short_member = members[members["icpsr"] == 1].copy()
        short_member[["icpsr", "bioname"]] = [5, "EXAMPLE, Short record"]
        short_votes = votes[votes["icpsr"] == 1].copy()
        short_votes["icpsr"] = 5
        short_votes["cast_code"] = [1, 6] + [9] * 18
        actual = analyze_congress(
            pd.concat([votes, short_votes]), pd.concat([members, short_member]),
            rollcalls, 119, {},
        )
        self.assertIn(5, {entry["id"] for entry in actual["provenance"]["excluded_members"]})
        # Equality of all published analytical fields verifies that this is a
        # reanalysis without the member, rather than hiding a plotted node.
        actual.pop("provenance")
        expected.pop("provenance")
        self.assertEqual(actual, expected)

    def test_absolute_and_percentage_threshold_boundaries_are_inclusive(self):
        for rollcall_count, required in ((200, 20), (201, 21), (400, 40)):
            votes, members, _ = fixture_frames()
            members = members[members.icpsr.isin([1, 2, 3, 4])].copy()
            extra = members[members.icpsr == 4].copy()
            extra["icpsr"] = 5
            members = pd.concat([members, extra])
            patterns = {
                1: [1 if i % 2 else 6 for i in range(rollcall_count)],
                2: [6 if i % 2 else 1 for i in range(rollcall_count)],
                3: [1 if i % 4 < 2 else 6 for i in range(rollcall_count)],
                4: [1 if i % 2 else 6 for i in range(required - 1)] + [9] * (rollcall_count - required + 1),
                5: [1 if i % 2 else 6 for i in range(required)] + [9] * (rollcall_count - required),
            }
            votes = pd.DataFrame(
                [[119, "Senate", identifier, roll + 1, code]
                 for identifier, pattern in patterns.items() for roll, code in enumerate(pattern)],
                columns=votes.columns,
            )
            prepared = prepare_votes(votes, members, 119)
            self.assertNotIn(4, prepared.matrix.index)
            self.assertIn(5, prepared.matrix.index)
            self.assertEqual(prepared.effective_minimum_votes, required)
            self.assertEqual(prepared.source_rollcall_denominator, rollcall_count)
            excluded = next(entry for entry in prepared.excluded if entry["id"] == 4)
            self.assertEqual(excluded["votes_cast"], required - 1)
            self.assertEqual(excluded["effective_minimum_votes"], required)
            self.assertEqual(excluded["source_rollcall_denominator"], rollcall_count)

    def test_threshold_denominator_is_fixed_before_short_records_are_removed(self):
        votes, members, _ = fixture_frames()
        # Expand the twenty baseline calls to two hundred. Only the short-record
        # member votes on call201; its removal must not lower ceil(10% *201)=21.
        copies = []
        for block in range(10):
            copy = votes.copy()
            copy["rollnumber"] += block * 20
            copies.append(copy)
        votes = pd.concat(copies)
        last_call = pd.DataFrame([[119, "Senate", 4, 201, 1]], columns=votes.columns)
        prepared = prepare_votes(pd.concat([votes, last_call]), members, 119)
        self.assertEqual(prepared.matrix.shape[1], 200)
        self.assertEqual(prepared.source_rollcall_denominator, 201)
        self.assertEqual(prepared.effective_minimum_votes, 21)
        self.assertNotIn(4, prepared.matrix.index)

    def test_fewer_than_twenty_rollcalls_fails_without_relaxing_policy(self):
        votes, members, _ = fixture_frames()
        with self.assertRaisesRegex(ValueError, "at least 20.*19 available"):
            prepare_votes(votes[votes.rollnumber <= 19], members, 119)

    def test_denominator_excludes_non_senator_and_all_zero_rollcalls(self):
        votes, members, _ = fixture_frames()
        added = pd.DataFrame([
            [119, "Senate", 99912, 21, 1],
            [119, "Senate", 42304, 22, 1],
            [119, "Senate", 1, 23, 9],
        ], columns=votes.columns)
        prepared = prepare_votes(pd.concat([votes, added]), members, 119)
        self.assertEqual(prepared.source_rollcalls, 21)
        self.assertEqual(prepared.source_rollcall_denominator, 20)
        self.assertEqual(prepared.matrix.shape[1], 20)

    def test_insufficient_eligible_members_fails_explicitly(self):
        votes, members, _ = fixture_frames()
        votes.loc[(votes.icpsr == 3) & (votes.rollnumber > 19), "cast_code"] = 9
        with self.assertRaisesRegex(ValueError, "insufficient usable data"):
            prepare_votes(votes, members, 119)

    def test_presidential_positions_and_sparse_senator_exclusions_are_explained(self):
        votes, members, rollcalls = fixture_frames()
        # A departing senator's state metadata is valid, but one usable vote
        # cannot support a correlation. Presidential positions are not senators.
        members.loc[members["icpsr"] == 42304, ["state_icpsr", "state_abbrev"]] = [35, "OH"]
        votes.loc[votes["icpsr"] == 42304, "cast_code"] = [1] + [9] * 19
        presidential_votes = votes[votes["icpsr"] == 1].copy()
        presidential_votes["icpsr"] = 99912
        votes = pd.concat([votes, presidential_votes])
        result = analyze_congress(votes, members, rollcalls, 119, {})
        exclusions = {entry["id"]: entry for entry in result["provenance"]["excluded_members"]}
        self.assertEqual(exclusions[99912],
                         {"id": 99912, "name": "TRUMP, Donald", "reason": "non-Senate office (President)"})
        self.assertIn("1 usable vote; requires 20", exclusions[42304]["reason"])
        self.assertEqual({node["id"] for node in result["nodes"]}, {1, 2, 3})

    def test_non_senate_metadata_does_not_override_eligible_senate_record(self):
        votes, members, _ = fixture_frames()
        second_office = members[members["icpsr"] == 1].copy()
        second_office[["chamber", "state_icpsr", "state_abbrev"]] = ["President", 99, "USA"]
        members = pd.concat([members, second_office])
        prepared = prepare_votes(votes, members, 119)
        self.assertIn(1, prepared.matrix.index)
        self.assertNotIn(1, {entry["id"] for entry in prepared.excluded})

    def test_duplicate_votes_fail_validation(self):
        votes, members, _ = fixture_frames()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            prepare_votes(pd.concat([votes, votes.iloc[:1]]), members, 119)

    def test_eligibility_is_rechecked_after_dropping_empty_rollcalls(self):
        votes, members, _ = fixture_frames()
        votes.loc[votes["icpsr"] == 4, "cast_code"] = 9
        added_votes = [[119, "Senate", identifier, 21, 1 if identifier == 4 else 0]
                       for identifier in votes["icpsr"].unique()]
        added_votes += [[119, "Senate", 5, roll, 1 if roll < 21 else 0] for roll in range(1, 22)]
        votes = pd.concat([votes, pd.DataFrame(added_votes, columns=votes.columns)])
        extra_member = members.iloc[[0]].copy()
        extra_member["icpsr"] = 5
        members = pd.concat([members, extra_member])
        prepared = prepare_votes(votes, members, 119)
        self.assertNotIn(5, prepared.matrix.index)
        self.assertNotIn(21, prepared.matrix.columns)
        self.assertEqual(prepared.matrix.shape, (3, 20))

    def test_payload_satisfies_data_contract(self):
        votes, members, rollcalls = fixture_frames()
        result = analyze_congress(votes, members, rollcalls, 119, {"sources": {}})
        self.assertEqual(result["last_vote_date"], "2025-01-22")
        self.assertEqual(result["members"], 3)
        self.assertEqual(result["rollcalls"], 20)
        self.assertEqual(result["data_file"], "congresses/119.json")
        self.assertEqual(result["provenance"]["parameters"]["minimum_usable_votes"], 20)
        self.assertEqual(result["provenance"]["parameters"]["minimum_participation_rate"], .10)
        self.assertEqual(result["provenance"]["effective_minimum_votes"], 20)
        self.assertTrue(all(edge["source"] != edge["target"] for edge in result["edges"]))

    def test_missing_rollcall_metadata_is_rejected(self):
        votes, members, rollcalls = fixture_frames()
        with self.assertRaisesRegex(ValueError, "matching roll-call"):
            analyze_congress(votes, members, rollcalls.iloc[:-1], 119, {})

    def test_sign_rule_is_deterministic(self):
        vector = np.array([.4, -.2, .3])
        parties = np.array([100, 200, 328])
        np.testing.assert_allclose(orient_vector(vector, parties), orient_vector(-vector, parties))
        self.assertLess(orient_vector(vector, parties)[0], orient_vector(vector, parties)[1])

    def test_zero_and_concentrated_gini(self):
        self.assertEqual(gini([0, 0, 0]), 0)
        self.assertEqual(gini([1, 1, 1]), 0)
        self.assertAlmostEqual(gini([0, 0, 1]), 2/3)
        with self.assertRaises(ValueError):
            gini([-1, 1])

    def test_current_congress_handles_transition(self):
        self.assertEqual(current_congress(date(2026, 10, 20)), 119)
        self.assertEqual(current_congress(date(2027, 1, 2)), 119)
        self.assertEqual(current_congress(date(2027, 1, 3)), 120)


if __name__ == "__main__":
    unittest.main()
