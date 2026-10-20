"""Explicit graph conventions for a corrected implementation of the thesis.

The spectral graph uses every positive transformed Pearson correlation.
Betweenness uses a separate graph with similarity >= 0.5. These are not the
same graph. Zero-coded nonparticipation follows the archival scripts and is
an assumption of the model, not an observed neutral political position.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone

import networkx as nx
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.sparse.csgraph import connected_components, laplacian

from . import METHODOLOGY_VERSION

EDGE_THRESHOLD = 0.5
DISTANCE_EPSILON = 1e-6
MIN_USABLE_VOTES = 2
CAST_VALUES = {0: 0, 1: 1, 2: 1, 3: 1, 4: -1, 5: -1, 6: -1, 7: 0, 8: 0, 9: 0}
# Official mapping: https://voteview.com/articles/data_help_parties
PARTIES = {
    1: "Federalist", 13: "Democratic-Republican", 22: "Adams",
    26: "Anti-Masonic", 29: "Whig", 37: "Constitutional Unionist",
    44: "Nullifier", 46: "States Rights", 100: "Democratic",
    108: "Anti-Lecompton Democrat", 112: "Conservative", 114: "Readjuster",
    117: "Readjuster Democrat", 200: "Republican", 203: "Unconditional Unionist",
    206: "Unionist", 208: "Liberal Republican", 213: "Progressive Republican",
    300: "Free Soil", 310: "American", 326: "National Greenbacker",
    328: "Independent", 329: "Independent Democrat", 331: "Independent Republican",
    340: "Populist", 347: "Prohibitionist", 354: "Silver Republican",
    355: "Union Labor", 356: "Union Labor", 370: "Progressive", 380: "Socialist",
    402: "Liberal", 403: "Law and Order", 522: "American Labor",
    523: "American Labor (La Guardia)", 537: "Farmer-Labor", 555: "Jackson",
    603: "Independent Whig", 1060: "Silver", 1111: "Liberty",
    1116: "Conservative Republican", 1275: "Anti-Jacksonian",
    1346: "Jackson Republican", 3333: "Opposition", 3334: "Opposition (36th)",
    4000: "Anti-Administration", 4444: "Constitutional Unionist",
    5000: "Pro-Administration", 6000: "Crawford Federalist",
    7000: "Jackson Federalist", 7777: "Crawford Republican",
    8000: "Adams-Clay Federalist", 8888: "Adams-Clay Republican",
}


def current_congress(today: date | None = None) -> int:
    """Congress changes on January 3 in odd years (modern calendar)."""
    today = today or datetime.now(timezone.utc).date()
    year = today.year - int(today.year % 2 == 1 and (today.month, today.day) < (1, 3))
    return (year - 1789) // 2 + 1


def gini(values: np.ndarray | list[float]) -> float:
    """Gini of nonnegative values; an all-zero vector has inequality zero."""
    x = np.sort(np.asarray(values, dtype=float))
    if x.size == 0 or np.any(x < 0) or not np.isfinite(x).all():
        raise ValueError("Gini requires a nonempty finite nonnegative vector.")
    if x.sum() == 0:
        return 0.0
    return float(np.dot(2 * np.arange(1, x.size + 1) - x.size - 1, x) / (x.size * x.sum()))


def similarity_matrix(votes: np.ndarray) -> np.ndarray:
    """Map row-wise Pearson correlations to [0,1], excluding self-loops."""
    votes = np.asarray(votes, dtype=float)
    if votes.ndim != 2 or min(votes.shape) < 2:
        raise ValueError("At least two members and two roll calls are required.")
    if not np.isfinite(votes).all() or np.any(np.std(votes, axis=1) == 0):
        raise ValueError("Vote rows must be finite and have nonzero variance.")
    adjacency = np.clip((np.corrcoef(votes) + 1) / 2, 0, 1)
    adjacency = (adjacency + adjacency.T) / 2
    np.fill_diagonal(adjacency, 0.0)
    return adjacency


def centrality_graph(adjacency: np.ndarray, threshold: float = EDGE_THRESHOLD) -> nx.Graph:
    """Build the retained graph and set strictly positive distance on it."""
    graph = nx.Graph()
    graph.add_nodes_from(range(len(adjacency)))
    for i, j in zip(*np.triu_indices(len(adjacency), k=1)):
        weight = float(adjacency[i, j])
        if weight >= threshold:
            graph.add_edge(int(i), int(j), weight=weight, distance=max(1.0 - weight, DISTANCE_EPSILON))
    return graph


def sweep_conductance(adjacency: np.ndarray, eigenvector: np.ndarray) -> tuple[float, list[int]]:
    """Best cut in the D^-1/2 u ordering; an upper bound on the true minimum.

    ``eigenvector`` is an eigenvector of the symmetric normalized Laplacian.
    A sweep searches only n-1 cuts, rather than all possible graph cuts.
    """
    degrees = adjacency.sum(axis=1)
    if np.any(degrees <= 0):
        raise ValueError("Conductance requires positive weighted degrees.")
    order = np.argsort(np.asarray(eigenvector) / np.sqrt(degrees), kind="stable")
    total_volume = degrees.sum()
    selected: list[int] = []
    best_cut: list[int] = []
    best = float("inf")
    volume = cut = 0.0
    for node in order[:-1]:
        cut += degrees[node] - 2 * adjacency[node, selected].sum()
        volume += degrees[node]
        selected.append(int(node))
        score = max(0.0, float(cut)) / min(volume, total_volume - volume)
        if score < best:
            best, best_cut = score, selected.copy()
    return float(best), best_cut


def orient_vector(vector: np.ndarray, party_codes: np.ndarray | None = None) -> np.ndarray:
    """Fix arbitrary sign for display; not a cross-Congress alignment."""
    vector = vector.copy()
    if party_codes is not None and np.any(party_codes == 100) and np.any(party_codes == 200):
        delta = vector[party_codes == 200].mean() - vector[party_codes == 100].mean()
        if abs(delta) > 1e-12:
            return vector if delta > 0 else -vector
    # Member IDs are sorted upstream. The largest-magnitude coordinate anchors sign.
    return vector if vector[np.argmax(np.abs(vector))] >= 0 else -vector


@dataclass
class PreparedVotes:
    matrix: pd.DataFrame
    members: pd.DataFrame
    excluded: list[dict]
    source_rollcalls: int


def prepare_votes(votes: pd.DataFrame, members: pd.DataFrame, congress: int) -> PreparedVotes:
    """Select state-representing senators using metadata, not hardcoded IDs."""
    chamber_members = members[(members["congress"] == congress) & (members["chamber"] == "Senate")].copy()
    # Voteview's nationally representing President/VP records have state code 99.
    nonstate = (chamber_members["state_icpsr"] == 99) | (chamber_members["state_abbrev"] == "USA")
    excluded = [
        {"id": int(row.icpsr), "name": row.bioname, "reason": "non-state Senate office (vice president)"}
        for row in chamber_members[nonstate].itertuples()
    ]
    chamber_members = chamber_members[~nonstate].drop_duplicates("icpsr", keep="last").set_index("icpsr")
    chamber_votes = votes[(votes["congress"] == congress) & (votes["chamber"] == "Senate")].copy()
    if not chamber_votes["cast_code"].isin(CAST_VALUES).all():
        raise ValueError(f"Congress {congress}: unknown cast codes.")
    unknown_members = set(chamber_votes["icpsr"]) - set(members["icpsr"])
    if unknown_members:
        raise ValueError(f"Congress {congress}: votes lack metadata for {sorted(unknown_members)}.")
    chamber_votes = chamber_votes[chamber_votes["icpsr"].isin(chamber_members.index)]
    if chamber_votes.duplicated(["icpsr", "rollnumber"]).any():
        raise ValueError(f"Congress {congress}: duplicate member/roll-call records.")
    chamber_votes["value"] = chamber_votes["cast_code"].map(CAST_VALUES)
    source_rollcalls = int(chamber_votes["rollnumber"].nunique())
    matrix = chamber_votes.pivot(index="icpsr", columns="rollnumber", values="value").fillna(0).sort_index()
    for identifier in chamber_members.index.difference(matrix.index):
        excluded.append({"id": int(identifier), "name": str(chamber_members.loc[identifier, "bioname"]),
                         "reason": "no recorded Senate votes"})
    # Removing an ineligible row can leave an all-zero column. Dropping that
    # column may make another row constant, so reach a stable usable matrix.
    while len(matrix):
        matrix = matrix.loc[:, (matrix != 0).any(axis=0)]
        usable = (matrix != 0).sum(axis=1)
        variable = matrix.std(axis=1, ddof=0) > 0
        keep = (usable >= MIN_USABLE_VOTES) & variable
        for identifier in matrix.index[~keep]:
            excluded.append({
                "id": int(identifier), "name": str(chamber_members.loc[identifier, "bioname"]),
                "reason": "fewer than 2 usable votes" if usable.loc[identifier] < MIN_USABLE_VOTES else "constant encoded vote row",
            })
        matrix = matrix.loc[keep]
        if keep.all():
            break
    if matrix.shape[0] < 3 or matrix.shape[1] < 2:
        raise ValueError(f"Congress {congress}: insufficient usable data for spectral analysis.")
    return PreparedVotes(matrix, chamber_members.loc[matrix.index], excluded, source_rollcalls)


def analyze_congress(votes: pd.DataFrame, members: pd.DataFrame, rollcalls: pd.DataFrame,
                     congress: int, provenance: dict) -> dict:
    prepared = prepare_votes(votes, members, congress)
    matrix = prepared.matrix
    metadata = prepared.members
    adjacency = similarity_matrix(matrix.to_numpy())
    if np.any(adjacency.sum(axis=1) <= 0):
        raise ValueError(f"Congress {congress}: an isolated node prevents normalized sweep analysis.")
    eigenvalues, eigenvectors = eigh(laplacian(adjacency, normed=True))
    eigenvalues = np.maximum(eigenvalues, 0)
    parties = metadata["party_code"].fillna(0).astype(int).to_numpy()
    x = orient_vector(eigenvectors[:, 1], parties)
    y = orient_vector(eigenvectors[:, 2])
    conductance, partition = sweep_conductance(adjacency, x)
    graph = centrality_graph(adjacency)
    between = nx.betweenness_centrality(graph, normalized=True, weight="distance")
    centrality = np.array([between[i] for i in range(len(matrix))])
    ids = [int(value) for value in matrix.index]
    selected_rollcalls = rollcalls.loc[
        (rollcalls["congress"] == congress) & (rollcalls["chamber"] == "Senate")
        & rollcalls["rollnumber"].isin(matrix.columns)]
    if set(matrix.columns) - set(selected_rollcalls["rollnumber"]):
        raise ValueError(f"Congress {congress}: some vote records lack matching roll-call metadata.")
    dates = pd.to_datetime(selected_rollcalls["date"], errors="coerce")
    if dates.empty or dates.isna().any():
        raise ValueError(f"Congress {congress}: roll-call dates unavailable.")
    start_year = 1789 + 2 * (congress - 1)
    result = {
        "schema_version": 1,
        "methodology_version": METHODOLOGY_VERSION,
        "congress": congress, "start_year": start_year, "end_year": start_year + 2,
        "members": len(matrix), "rollcalls": matrix.shape[1],
        "last_vote_date": dates.max().date().isoformat(),
        "fiedler_value": float(eigenvalues[1]), "sweep_conductance": conductance,
        "mean_betweenness": float(centrality.mean()), "max_betweenness": float(centrality.max()),
        "gini_betweenness": gini(centrality), "data_file": f"congresses/{congress}.json",
        "eigenvalues": [float(v) for v in eigenvalues],
        "cheeger_lower_bound": float(eigenvalues[1] / 2),
        "cheeger_upper_bound": min(1.0, float(np.sqrt(2 * eigenvalues[1]))),
        "spectral_components": int(connected_components(adjacency, directed=False)[0]),
        "threshold_components": nx.number_connected_components(graph),
        "sweep_partition": [ids[i] for i in partition],
        "nodes": [{
            "id": identifier, "name": str(metadata.loc[identifier, "bioname"]),
            "party": PARTIES.get(int(parties[i]), f"Other ({parties[i]})"),
            "party_code": int(parties[i]), "state": str(metadata.loc[identifier, "state_abbrev"]),
            "x": float(x[i]), "y": float(y[i]), "betweenness": float(centrality[i]),
            "votes_cast": int((matrix.iloc[i] != 0).sum()),
            "participation_rate": float((matrix.iloc[i] != 0).mean()),
        } for i, identifier in enumerate(ids)],
        "edges": [{"source": ids[u], "target": ids[v], "weight": float(attrs["weight"])}
                  for u, v, attrs in graph.edges(data=True)],
        "provenance": {
            **provenance, "methodology_version": METHODOLOGY_VERSION,
            "source_rollcalls": prepared.source_rollcalls,
            "excluded_members": prepared.excluded,
            "parameters": {
                "similarity": "(Pearson correlation + 1) / 2; zero diagonal",
                "missing_vote_encoding": 0, "minimum_usable_votes": MIN_USABLE_VOTES,
                "centrality_edge_threshold": EDGE_THRESHOLD,
                "centrality_distance": "max(1 - similarity, 0.000001)",
                "distance_epsilon": DISTANCE_EPSILON,
                "sweep_order": "symmetric normalized Fiedler vector / sqrt(weighted degree)",
            },
        },
    }
    return result
