from __future__ import annotations

from dataclasses import dataclass
from math import exp, log
from typing import Sequence

_EPS = 1e-12


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def cusum_score(values: Sequence[float], *, drift: float = 0.02) -> float:
    xs = [_clamp01(v) for v in values]
    if len(xs) < 2:
        return 0.0
    mean = sum(xs) / len(xs)
    positive = negative = maximum = 0.0
    for value in xs:
        residual = value - mean
        positive = max(0.0, positive + residual - drift)
        negative = min(0.0, negative + residual + drift)
        maximum = max(maximum, positive, -negative)
    return _clamp01(1.0 - exp(-2.4 * maximum))


def page_hinkley_score(values: Sequence[float], *, delta: float = 0.04) -> float:
    xs = [_clamp01(v) for v in values]
    if len(xs) < 2:
        return 0.0
    running_mean = cumulative = minimum = peak = 0.0
    for index, value in enumerate(xs, start=1):
        running_mean += (value - running_mean) / index
        cumulative += value - running_mean - delta
        minimum = min(minimum, cumulative)
        peak = max(peak, cumulative - minimum)
    return _clamp01(1.0 - exp(-peak / 1.25))


@dataclass(frozen=True)
class BOCPDResult:
    reset_probability: float
    expected_run_length: float
    run_length_posterior: tuple[float, ...]


def bernoulli_bocpd(
    observations: Sequence[int],
    *,
    hazard: float = 0.08,
    prior_alpha: float = 1.0,
    prior_beta: float = 1.0,
    max_run_length: int = 64,
) -> BOCPDResult:
    """Exact finite Beta-Bernoulli Bayesian online changepoint recursion.

    Each run-length state carries its own conjugate Beta sufficient statistics.
    Complexity is O(n * min(n, max_run_length)).
    """
    xs = [1 if int(value) else 0 for value in observations]
    if not xs:
        return BOCPDResult(0.0, 0.0, (1.0,))

    hazard = min(0.95, max(1e-6, float(hazard)))
    probabilities = [1.0]
    alphas = [float(prior_alpha)]
    betas = [float(prior_beta)]

    for observation in xs:
        length = min(len(probabilities), max_run_length + 1)
        next_prob = [0.0] * min(length + 1, max_run_length + 1)
        next_alpha = [float(prior_alpha)] * len(next_prob)
        next_beta = [float(prior_beta)] * len(next_prob)

        reset_mass = 0.0
        growth_stats: list[tuple[int, float, float, float]] = []
        for run_length in range(length):
            p = probabilities[run_length]
            alpha = alphas[run_length]
            beta = betas[run_length]
            predictive = (
                alpha / (alpha + beta)
                if observation
                else beta / (alpha + beta)
            )
            joint = p * predictive
            reset_mass += joint * hazard
            target = run_length + 1
            if target < len(next_prob):
                growth = joint * (1.0 - hazard)
                next_prob[target] += growth
                growth_stats.append((
                    target,
                    growth,
                    alpha + observation,
                    beta + (1 - observation),
                ))

        next_prob[0] = reset_mass
        for target, mass, alpha, beta in growth_stats:
            if mass <= 0.0:
                continue
            existing = next_prob[target]
            if existing <= _EPS:
                continue
            weight = mass / existing
            next_alpha[target] += weight * (alpha - prior_alpha)
            next_beta[target] += weight * (beta - prior_beta)

        total = sum(next_prob)
        if total <= _EPS:
            next_prob = [1.0] + [0.0] * (len(next_prob) - 1)
        else:
            next_prob = [value / total for value in next_prob]
        probabilities, alphas, betas = next_prob, next_alpha, next_beta

    expected = sum(index * probability for index, probability in enumerate(probabilities))
    return BOCPDResult(
        reset_probability=_clamp01(probabilities[0]),
        expected_run_length=expected,
        run_length_posterior=tuple(probabilities),
    )


def change_consensus(
    impact_history: Sequence[float],
    change_history: Sequence[int],
) -> tuple[float, tuple[tuple[str, float], ...]]:
    normalized = [_clamp01(float(value) / 10.0) for value in impact_history]
    if not normalized:
        normalized = [float(bool(value)) for value in change_history]
    ph = page_hinkley_score(normalized)
    cu = cusum_score(normalized)
    bo = bernoulli_bocpd(change_history).reset_probability if change_history else 0.0

    votes = (("page-hinkley", ph), ("cusum", cu), ("bocpd-beta", bo))
    # No single detector may dominate the ensemble. Geometric-ish agreement
    # bonus rewards detectors that independently point in the same direction.
    mean = sum(value for _, value in votes) / len(votes)
    spread = max(value for _, value in votes) - min(value for _, value in votes)
    consensus = _clamp01(mean * (1.0 - 0.22 * spread))
    return consensus, votes
