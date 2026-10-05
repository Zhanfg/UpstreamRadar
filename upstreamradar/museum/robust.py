from __future__ import annotations

from math import isfinite
from statistics import median
from typing import Sequence

_EPS = 1e-12


def _finite(values: Sequence[float]) -> list[float]:
    return [float(value) for value in values if isfinite(float(value))]


def mad(values: Sequence[float], center: float | None = None) -> float:
    xs = _finite(values)
    if not xs:
        return 1.0
    center = median(xs) if center is None else float(center)
    return max(1.4826 * median(abs(value - center) for value in xs), 1e-9)


def huber_location(
    values: Sequence[float],
    *,
    delta: float = 1.345,
    iterations: int = 16,
) -> float:
    """Iteratively reweighted Huber M-location.

    Median/MAD initialize the estimator so a few extreme repositories cannot
    drag the activity baseline.
    """
    xs = _finite(values)
    if not xs:
        return 0.0
    location = float(median(xs))
    scale = mad(xs, location)
    if scale <= _EPS:
        return location

    for _ in range(max(1, iterations)):
        numerator = 0.0
        denominator = 0.0
        threshold = delta * scale
        for value in xs:
            residual = value - location
            absolute = abs(residual)
            weight = 1.0 if absolute <= threshold else threshold / max(absolute, _EPS)
            numerator += weight * value
            denominator += weight
        updated = numerator / max(denominator, _EPS)
        if abs(updated - location) <= 1e-9 * max(1.0, abs(location)):
            return updated
        location = updated
    return location


def winsorized_variance(values: Sequence[float], *, clip_z: float = 3.5) -> float:
    xs = _finite(values)
    if len(xs) < 2:
        return 0.0
    center = huber_location(xs)
    scale = mad(xs, center)
    low = center - clip_z * scale
    high = center + clip_z * scale
    clipped = [min(high, max(low, value)) for value in xs]
    mean = sum(clipped) / len(clipped)
    return sum((value - mean) ** 2 for value in clipped) / (len(clipped) - 1)
