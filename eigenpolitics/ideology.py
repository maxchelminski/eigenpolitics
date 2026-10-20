"""Publish Voteview's common-scale scores without altering spectral geometry.

The current member export's NOMINATE positions are career-constant estimates.
They are a separate source measurement, not aligned or rescaled eigenvectors.
Missing scores remain missing: the browser can plot only complete pairs.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
import math

import pandas as pd

MEMBER_IDEOLOGY_REFERENCE = "https://voteview.com/articles/data_help_members"
POLARIZATION_REFERENCE = "https://voteview.com/articles/party_polarization"
HISTORICAL_COMPARISON_REFERENCE = "https://legacy.voteview.com/page2a.htm"


def _nullable_number(value: object, field: str) -> float | None:
    """Convert scalar CSV metadata without turning missing values into zero."""
    if value is None or pd.isna(value) or (isinstance(value, str) and not value.strip()):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid Voteview {field}: {value!r}.") from error
    if not math.isfinite(number):
        raise ValueError(f"Non-finite Voteview {field}: {value!r}.")
    return number


def nominate_fields(member: Mapping) -> dict:
    """Copy the published source scores and preserve their nullable status.

    Each coordinate is kept independently, but the two-dimensional plot
    requires both. Reject invalid coordinates instead of clipping, normalizing,
    replacing them with spectral positions, or rendering them as centrists.
    """
    coordinates = {}
    for field in ("nominate_dim1", "nominate_dim2"):
        number = _nullable_number(member.get(field), field)
        if number is not None and not -1 <= number <= 1:
            raise ValueError(f"Voteview {field} must be within [-1, 1], got {number}.")
        coordinates[field] = number
    conditional = _nullable_number(member.get("conditional"), "conditional")
    if conditional is not None and conditional not in (0, 1):
        raise ValueError(f"Voteview conditional must be 0, 1, or missing, got {conditional}.")
    coordinates["nominate_conditional"] = None if conditional is None else bool(conditional)
    return coordinates


def nominate_provenance(nodes: Iterable[Mapping]) -> dict:
    """Describe the imported model and count scores for the retained population."""
    nodes = list(nodes)
    complete = sum(
        node.get("nominate_dim1") is not None and node.get("nominate_dim2") is not None
        for node in nodes
    )
    return {
        "model": "Voteview NOMINATE common scale",
        "source_fields": ["nominate_dim1", "nominate_dim2"],
        "conditional_source_field": "conditional",
        "axis_bounds": {"x": [-1, 1], "y": [-1, 1]},
        "complete_member_scores": complete,
        "missing_member_scores": len(nodes) - complete,
        "conditional_member_scores": sum(node.get("nominate_conditional") is True for node in nodes),
        "unknown_conditional_status": sum(node.get("nominate_conditional") is None for node in nodes),
        "position_model": "Current source estimates hold each member's position constant across their career.",
        "transformation": "Source coordinates copied unchanged; independent of the spectral graph.",
        "missing_scores": "Incomplete pairs are omitted only from the ideology plot; no imputation or spectral fallback.",
        "interpretation": "Compare within a stable party system; historical issue meanings, especially dimension 2, change.",
        "references": [
            MEMBER_IDEOLOGY_REFERENCE,
            POLARIZATION_REFERENCE,
            HISTORICAL_COMPARISON_REFERENCE,
        ],
    }
