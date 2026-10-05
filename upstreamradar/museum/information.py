from __future__ import annotations

from math import exp, log2, sqrt
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


def maximum_mean_discrepancy(
    left: Sequence[float],
    right: Sequence[float],
    *,
    bandwidth: float | None = None,
) -> float:
    """Biased RBF-kernel MMD, normalized to [0,1] for [0,1] samples."""
    a = [max(0.0, min(1.0, float(v))) for v in left]
    b = [max(0.0, min(1.0, float(v))) for v in right]
    if not a and not b:
        return 0.0
    if not a or not b:
        return 1.0

    if bandwidth is None:
        distances = sorted(
            abs(x - y)
            for index, x in enumerate(a + b)
            for y in (a + b)[index + 1:]
            if abs(x - y) > _EPS
        )
        sigma = distances[len(distances) // 2] if distances else 0.1
    else:
        sigma = max(float(bandwidth), 1e-6)
    sigma = max(sigma, 1e-6)

    def kernel(x: float, y: float) -> float:
        distance = x - y
        return exp(-(distance * distance) / (2.0 * sigma * sigma))

    aa = sum(kernel(x, y) for x in a for y in a) / (len(a) * len(a))
    bb = sum(kernel(x, y) for x in b for y in b) / (len(b) * len(b))
    ab = sum(kernel(x, y) for x in a for y in b) / (len(a) * len(b))
    mmd2 = max(0.0, aa + bb - 2.0 * ab)
    return max(0.0, min(1.0, sqrt(mmd2 / 2.0)))


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
    mmd = maximum_mean_discrepancy(older, recent)
    votes = (("jsd", js), ("wasserstein-1", w1), ("mmd-rbf", mmd))
    mean = 0.42 * js + 0.30 * w1 + 0.28 * mmd
    disagreement = max(value for _, value in votes) - min(value for _, value in votes)
    consensus = max(0.0, min(1.0, mean * (1.0 - 0.12 * disagreement)))
    return consensus, votes
