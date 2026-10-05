from __future__ import annotations

from math import log, log1p, sqrt

_EPS = 1e-12


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def bernoulli_kl(p0: float, q0: float) -> float:
    p = min(1.0 - _EPS, max(_EPS, float(p0)))
    q = min(1.0 - _EPS, max(_EPS, float(q0)))
    return p * log(p / q) + (1.0 - p) * log((1.0 - p) / (1.0 - q))


def ucb_v(
    mean: float,
    variance: float,
    pulls: int,
    total_pulls: int,
) -> float:
    """Audibert-style empirical Bernstein/UCB-V index."""
    if pulls <= 0:
        return 1.0
    log_term = log(max(total_pulls, 2))
    bonus = sqrt(2.0 * max(variance, 0.0) * log_term / pulls)
    bonus += 3.0 * log_term / pulls
    return _clamp01(mean + bonus)


def kl_ucb(
    mean: float,
    pulls: int,
    total_pulls: int,
    *,
    precision: float = 1e-7,
) -> float:
    """Bernoulli KL-UCB by monotone binary search."""
    mean = _clamp01(mean)
    if pulls <= 0:
        return 1.0
    t = max(total_pulls, 2)
    budget = (log(t) + 3.0 * log(max(log(t), 1.0))) / pulls
    low, high = mean, 1.0 - _EPS
    while high - low > precision:
        mid = (low + high) / 2.0
        if bernoulli_kl(mean, mid) <= budget:
            low = mid
        else:
            high = mid
    return _clamp01(low)


def exploration_consensus(
    *,
    hits: int,
    misses: int,
    observation_count: int,
    variance: float,
    total_observations: int,
) -> tuple[float, tuple[tuple[str, float], ...]]:
    pulls = max(observation_count, hits + misses, 0)
    mean = (max(hits, 0) + 0.5) / (max(hits, 0) + max(misses, 0) + 1.0)
    ucbv = ucb_v(mean, variance, pulls, total_observations)
    kl = kl_ucb(mean, pulls, total_observations)

    # Information deficit keeps mature arms from permanently monopolizing scans.
    deficit = 1.0 / sqrt(1.0 + pulls)
    votes = (("ucb-v", ucbv), ("kl-ucb", kl), ("information-deficit", deficit))
    mean_vote = sum(value for _, value in votes) / len(votes)
    disagreement = max(value for _, value in votes) - min(value for _, value in votes)
    score = _clamp01(mean_vote * (1.0 - 0.12 * disagreement))
    return score, votes


def discounted_count(observation_count: int, freshness_hours: float) -> float:
    """Effective sample size under recency decay."""
    decay = 1.0 / (1.0 + log1p(max(0.0, freshness_hours)))
    return max(0.0, observation_count * decay)
