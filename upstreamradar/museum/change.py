from __future__ import annotations

from dataclasses import dataclass
from math import exp, log, sqrt
from typing import Sequence

from .robust import theil_sen_slope

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
    """Finite Beta-Bernoulli Bayesian online changepoint recursion.

    Changepoint mass uses the *prior predictive* for the new regime, while
    growth mass uses each run-length state's posterior predictive. This is the
    distinction that lets evidence move reset probability away from the hazard.
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
        next_size = min(length + 1, max_run_length + 1)
        next_prob = [0.0] * next_size
        next_alpha = [float(prior_alpha)] * next_size
        next_beta = [float(prior_beta)] * next_size

        prior_predictive = (
            prior_alpha / (prior_alpha + prior_beta)
            if observation
            else prior_beta / (prior_alpha + prior_beta)
        )
        next_prob[0] = hazard * prior_predictive * sum(probabilities[:length])
        next_alpha[0] = prior_alpha + observation
        next_beta[0] = prior_beta + (1 - observation)

        for run_length in range(length):
            target = run_length + 1
            if target >= next_size:
                continue
            alpha = alphas[run_length]
            beta = betas[run_length]
            predictive = (
                alpha / (alpha + beta)
                if observation
                else beta / (alpha + beta)
            )
            next_prob[target] = (
                probabilities[run_length]
                * predictive
                * (1.0 - hazard)
            )
            next_alpha[target] = alpha + observation
            next_beta[target] = beta + (1 - observation)

        total = sum(next_prob)
        if total <= _EPS:
            next_prob = [1.0] + [0.0] * (next_size - 1)
        else:
            next_prob = [value / total for value in next_prob]
        probabilities, alphas, betas = next_prob, next_alpha, next_beta

    expected = sum(
        index * probability
        for index, probability in enumerate(probabilities)
    )
    return BOCPDResult(
        reset_probability=_clamp01(probabilities[0]),
        expected_run_length=expected,
        run_length_posterior=tuple(probabilities),
    )


def adwin_score(
    values: Sequence[float],
    *,
    delta: float = 0.01,
    min_window: int = 3,
) -> float:
    """Deterministic ADWIN-style adaptive-window cut scan."""
    xs = [_clamp01(v) for v in values]
    if len(xs) < 2 * min_window:
        return 0.0
    strongest = 0.0
    confidence = max(1e-12, min(0.5, delta))
    log_term = log(4.0 / confidence)

    prefix = [0.0]
    for value in xs:
        prefix.append(prefix[-1] + value)

    for cut in range(min_window, len(xs) - min_window + 1):
        n0 = cut
        n1 = len(xs) - cut
        mean0 = prefix[cut] / n0
        mean1 = (prefix[-1] - prefix[cut]) / n1
        epsilon = sqrt(0.5 * log_term * (1.0 / n0 + 1.0 / n1))
        excess = abs(mean1 - mean0) - epsilon
        if excess > 0.0:
            strongest = max(strongest, excess / (1.0 + epsilon))
    return _clamp01(strongest * 2.5)


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
    ad = adwin_score(normalized)
    slope = _clamp01(abs(theil_sen_slope(normalized)) * 4.0)

    votes = (
        ("page-hinkley", ph),
        ("cusum", cu),
        ("bocpd-beta", bo),
        ("adwin", ad),
        ("theil-sen", slope),
    )
    # No single detector may dominate the ensemble.
    mean = sum(value for _, value in votes) / len(votes)
    spread = max(value for _, value in votes) - min(value for _, value in votes)
    consensus = _clamp01(mean * (1.0 - 0.22 * spread))
    return consensus, votes
