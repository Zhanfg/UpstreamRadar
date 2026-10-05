from __future__ import annotations

from math import exp, sqrt
from typing import Mapping, Sequence

from .bandit import exploration_consensus
from .change import change_consensus
from .information import history_information_gain
from .model import MuseumEvidence
from .robust import huber_location, winsorized_variance
from .sketches import dependency_novelty as minhash_novelty


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def build_museum_evidence(
    *,
    local_features: Sequence[float],
    impact_history: Sequence[float],
    change_history: Sequence[int],
    hits: int,
    misses: int,
    observation_count: int,
    total_observations: int,
    dependencies: Sequence[str],
    peer_dependencies: Sequence[Sequence[str]],
    graph_consensus: float,
    graph_trace: Sequence[tuple[str, float]] = (),
) -> MuseumEvidence:
    robust_location = huber_location(local_features)
    robust_activity = _clamp01(_sigmoid(robust_location))

    normalized_history = [
        _clamp01(float(value) / 10.0)
        for value in impact_history
    ]
    change_score, change_trace = change_consensus(
        impact_history,
        change_history,
    )
    information_gain = history_information_gain(normalized_history)

    variance = winsorized_variance(
        normalized_history or [float(bool(value)) for value in change_history]
    )
    bandit_index, bandit_trace = exploration_consensus(
        hits=hits,
        misses=misses,
        observation_count=observation_count,
        variance=variance,
        total_observations=total_observations,
    )
    dependency_novelty = minhash_novelty(
        dependencies,
        peer_dependencies,
    )

    gallery_votes = (
        robust_activity,
        change_score,
        information_gain,
        _clamp01(graph_consensus),
        bandit_index,
        dependency_novelty,
    )
    mean = sum(gallery_votes) / len(gallery_votes)
    variance_of_votes = sum((value - mean) ** 2 for value in gallery_votes) / len(gallery_votes)
    disagreement = _clamp01(sqrt(variance_of_votes) * 2.0)

    # The museum consensus is deliberately conservative: diversity of evidence
    # helps, but cross-gallery disagreement prevents a single exotic detector
    # from dominating production scheduling.
    consensus = _clamp01(mean * (1.0 - 0.24 * disagreement))

    trace = tuple(
        list(change_trace)
        + list(graph_trace)
        + list(bandit_trace)
        + [
            ("huber", robust_activity),
            ("jsd", information_gain),
            ("minhash", dependency_novelty),
        ]
    )
    return MuseumEvidence(
        robust_activity=robust_activity,
        change_consensus=change_score,
        information_gain=information_gain,
        graph_consensus=_clamp01(graph_consensus),
        bandit_index=bandit_index,
        dependency_novelty=dependency_novelty,
        disagreement=disagreement,
        consensus=consensus,
        trace=trace,
    )
