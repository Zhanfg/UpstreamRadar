from __future__ import annotations

from math import log2
from typing import Sequence

_EPS = 1e-12


def _normalize(values: Sequence[float]) -> tuple[float, ...]:
    positive = [max(0.0, float(value)) for value in values]
    total = sum(positive)
    if total <= _EPS:
        if not positive:
            return ()
        return tuple(1.0 / len(positive) for _ in positive)
    return tuple(value / total for value in positive)


def entropy(probabilities: Sequence[float]) -> float:
    ps = _normalize(probabilities)
    return -sum(p * log2(p) for p in ps if p > _EPS)


def jensen_shannon(left: Sequence[float], right: Sequence[float]) -> float:
    """Normalized Jensen–Shannon divergence in [0,1]."""
    n = max(len(left), len(right))
    if n == 0:
        return 0.0
    l = _normalize(tuple(left) + (0.0,) * (n - len(left)))
    r = _normalize(tuple(right) + (0.0,) * (n - len(right)))
    midpoint = tuple((a + b) / 2.0 for a, b in zip(l, r))

    def kl(p: Sequence[float], q: Sequence[float]) -> float:
        return sum(
            a * log2(a / b)
            for a, b in zip(p, q)
            if a > _EPS and b > _EPS
        )

    return max(0.0, min(1.0, 0.5 * kl(l, midpoint) + 0.5 * kl(r, midpoint)))


def history_information_gain(values: Sequence[float]) -> float:
    """Compare older vs recent empirical distributions over four bins."""
    xs = [max(0.0, min(1.0, float(value))) for value in values]
    if len(xs) < 4:
        return 0.0
    split = max(2, len(xs) // 2)

    def histogram(segment: Sequence[float]) -> tuple[int, int, int, int]:
        bins = [0, 0, 0, 0]
        for value in segment:
            bins[min(3, int(value * 4.0))] += 1
        return tuple(bins)

    return jensen_shannon(histogram(xs[:split]), histogram(xs[split:]))


def _quantile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    position = max(0.0, min(1.0, q)) * (len(sorted_values) - 1)
    lower = int(position)
    upper = min(len(sorted_values) - 1, lower + 1)
    fraction = position - lower
    return (
        float(sorted_values[lower]) * (1.0 - fraction)
        + float(sorted_values[upper]) * fraction
    )


def wasserstein_1d(left: Sequence[float], right: Sequence[float]) -> float:
    """Equal-mass empirical 1-Wasserstein distance for values in [0,1]."""
    if not left and not right:
        return 0.0
    if not left or not right:
        return 1.0
    a = sorted(max(0.0, min(1.0, float(v))) for v in left)
    b = sorted(max(0.0, min(1.0, float(v))) for v in right)
    samples = max(len(a), len(b), 2)
    distances = [
        abs(
            _quantile(a, index / (samples - 1))
            - _quantile(b, index / (samples - 1))
        )
        for index in range(samples)
    ]
    return max(0.0, min(1.0, sum(distances) / len(distances)))


def history_distribution_shift(
    values: Sequence[float],
) -> tuple[float, tuple[tuple[str, float], ...]]:
    xs = [max(0.0, min(1.0, float(value))) for value in values]
    if len(xs) < 4:
        return 0.0, (("jsd", 0.0), ("wasserstein-1", 0.0))
    split = max(2, len(xs) // 2)
    older, recent = xs[:split], xs[split:]

    def histogram(segment: Sequence[float]) -> tuple[int, int, int, int]:
        bins = [0, 0, 0, 0]
        for value in segment:
            bins[min(3, int(value * 4.0))] += 1
        return tuple(bins)

    js = jensen_shannon(histogram(older), histogram(recent))
    w1 = wasserstein_1d(older, recent)
    disagreement = abs(js - w1)
    consensus = max(0.0, min(1.0, (0.60 * js + 0.40 * w1) * (1.0 - 0.12 * disagreement)))
    return consensus, (("jsd", js), ("wasserstein-1", w1))
