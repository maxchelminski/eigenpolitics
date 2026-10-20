"""Register adjacent Senate spectral embeddings through shared members.

Each fit uses an orthogonal transform and a translation, without rescaling.
Raw eigenvectors and graph statistics are never changed. The resulting frame
tracks relative geometry; shared members are an estimated reference rather
than fixed ideological landmarks.
"""

from __future__ import annotations

from copy import deepcopy
from collections.abc import Iterable

import numpy as np
from scipy.linalg import orthogonal_procrustes

ALIGNMENT_METHOD = "shared-senator rigid Procrustes"
MINIMUM_ANCHORS = 3
WEAK_RELATIVE_RESIDUAL = 0.5
RANK_RELATIVE_TOLERANCE = 1e-10


def _rank(values: np.ndarray) -> int:
    singular = np.linalg.svd(values, compute_uv=False)
    if singular.size == 0 or singular[0] == 0:
        return 0
    return int(np.count_nonzero(singular > singular[0] * RANK_RELATIVE_TOLERANCE))


def _rms(values: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.sum(values * values, axis=1))))


def _coordinates(congress: dict, *, aligned: bool = False) -> dict[int, np.ndarray]:
    fields = ("aligned_x", "aligned_y") if aligned else ("x", "y")
    result = {}
    for node in congress["nodes"]:
        identifier = int(node["id"])
        if identifier in result:
            raise ValueError(f"Duplicate member {identifier} in Congress {congress['congress']}.")
        point = np.asarray([node[field] for field in fields], dtype=float)
        if not np.isfinite(point).all():
            raise ValueError(f"Nonfinite spectral coordinate in Congress {congress['congress']}.")
        result[identifier] = point
    if not result:
        raise ValueError(f"No spectral coordinates in Congress {congress['congress']}.")
    return result


def align_congresses(congresses: Iterable[dict]) -> list[dict]:
    """Return copies aligned in chronological, contiguous segments.

    For row coordinates A from the new Congress and B from the already aligned
    previous Congress, minimize ||(A - mean(A)) R - (B - mean(B))||_F with
    R.T @ R = I. Reflection is allowed; scale is always one. Apply
    ``point @ R + mean(B) - mean(A) @ R`` to every current member.

    Three shared members with full two-dimensional rank are necessary. Gaps,
    too few anchors, or degenerate anchor geometry start a fresh segment and
    carry no comparable displacement across that boundary.
    """
    ordered = sorted(deepcopy(list(congresses)), key=lambda row: int(row["congress"]))
    numbers = [int(row["congress"]) for row in ordered]
    if len(set(numbers)) != len(numbers):
        raise ValueError("Cannot align duplicate Congress numbers.")
    previous = None
    for current in ordered:
        number = int(current["congress"])
        raw = _coordinates(current)
        rotation = np.eye(2)
        translation = np.zeros(2)
        reference = None
        root = number
        anchor_ids = []
        source_rank = target_rank = cross_rank = 0
        residual_before = residual_after = relative_residual = None
        status = "reference" if previous is None else "reset"
        quality = status
        reason = "First published Congress establishes this segment's reference frame."
        if previous is not None:
            if number != int(previous["congress"]) + 1:
                reason = "Gap in published Congresses; a new reference segment begins."
            else:
                reference = int(previous["congress"])
                target = _coordinates(previous, aligned=True)
                anchor_ids = sorted(set(raw) & set(target))
                if len(anchor_ids) < MINIMUM_ANCHORS:
                    reason = "Fewer than three shared eligible senators; a new reference segment begins."
                else:
                    source_points = np.array([raw[identifier] for identifier in anchor_ids])
                    target_points = np.array([target[identifier] for identifier in anchor_ids])
                    source_mean = source_points.mean(axis=0)
                    target_mean = target_points.mean(axis=0)
                    source_centered = source_points - source_mean
                    target_centered = target_points - target_mean
                    source_rank = _rank(source_centered)
                    target_rank = _rank(target_centered)
                    cross_rank = _rank(source_centered.T @ target_centered)
                    if min(source_rank, target_rank, cross_rank) < 2:
                        reason = "Shared-member geometry is rank deficient; a new reference segment begins."
                    else:
                        rotation, _ = orthogonal_procrustes(source_centered, target_centered)
                        translation = target_mean - source_mean @ rotation
                        residual_before = _rms(source_points - target_points)
                        residual_after = _rms(source_points @ rotation + translation - target_points)
                        relative_residual = residual_after / _rms(target_centered)
                        root = previous["alignment"]["root_congress"]
                        status = "aligned"
                        quality = "weak" if relative_residual > WEAK_RELATIVE_RESIDUAL else "ok"
                        reason = (
                            "Large shared-member residual; interpret this link cautiously."
                            if quality == "weak" else
                            "Aligned to the previous Congress using shared eligible senators."
                        )
        for node in current["nodes"]:
            point = raw[int(node["id"])] @ rotation + translation
            node["aligned_x"], node["aligned_y"] = map(float, point)
        current["alignment"] = {
            "method": ALIGNMENT_METHOD, "status": status, "quality": quality, "reason": reason,
            "reference_congress": reference, "root_congress": root, "segment_id": root,
            "anchor_ids": anchor_ids, "anchor_count": len(anchor_ids),
            "source_rank": source_rank, "target_rank": target_rank, "cross_rank": cross_rank,
            "rotation": rotation.tolist(), "translation": translation.tolist(), "scale": 1.0,
            "residual_before": residual_before, "residual_after": residual_after,
            "relative_residual": relative_residual,
            "minimum_anchors": MINIMUM_ANCHORS,
            "weak_relative_residual_threshold": WEAK_RELATIVE_RESIDUAL,
            "rank_relative_tolerance": RANK_RELATIVE_TOLERANCE,
        }
        previous = current
    return ordered
