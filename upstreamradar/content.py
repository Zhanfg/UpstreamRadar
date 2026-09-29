from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .engine import CandidateScore


@dataclass(frozen=True)
class ContentOpportunity:
    name: str
    priority: float
    angle: str
    reasons: tuple[str, ...]
    evidence: tuple[str, ...]


def _angle(score: CandidateScore) -> str:
    reasons = set(score.reasons)
    if "regime-shift" in reasons and "dependency-hub" in reasons:
        return "Upstream regime shift with downstream blast-radius implications"
    if "security-focus" in reasons and "likely-change" in reasons:
        return "Security-relevant upstream movement with elevated change probability"
    if "high-content-yield" in reasons and "accelerating" in reasons:
        return "Accelerating upstream activity with high reportable information yield"
    if "uncertainty-exploration" in reasons:
        return "Exploration candidate where a new observation can reduce scheduler uncertainty"
    if "anomalous" in reasons:
        return "Anomalous upstream behavior worth contextual investigation"
    if "dependency-hub" in reasons:
        return "Dependency hub whose changes can propagate across the tracked graph"
    return "General upstream update selected by multi-objective scheduling"


def _evidence(score: CandidateScore) -> tuple[str, ...]:
    metrics = (
        ("change-point", score.change_point),
        ("content-yield", score.content_yield),
        ("graph-influence", score.graph_influence),
        ("change-probability", score.change_probability),
        ("momentum", score.momentum),
        ("anomaly", score.anomaly),
        ("exploration", score.exploration),
        ("reliability", score.reliability),
    )
    ranked = sorted(metrics, key=lambda item: (-item[1], item[0]))
    return tuple(
        f"{name}={value:.3f}"
        for name, value in ranked[:4]
    )


def build_content_plan(
    scores: Sequence[CandidateScore] | Iterable[CandidateScore],
    *,
    limit: int = 8,
) -> tuple[ContentOpportunity, ...]:
    """Create report-ready investigation opportunities from scheduler evidence.

    This layer deliberately does not generate articles. It exposes why a
    selected upstream is information-rich so later report generation can stay
    evidence-first rather than inventing narrative.
    """
    if limit < 0:
        raise ValueError("limit must be non-negative")

    opportunities = []
    for score in scores:
        priority = (
            0.34 * score.content_yield
            + 0.22 * score.change_point
            + 0.16 * score.graph_influence
            + 0.12 * score.change_probability
            + 0.08 * score.security_focus
            + 0.08 * min(score.exploration * 4.0, 1.0)
        ) * score.reliability

        opportunities.append(
            ContentOpportunity(
                name=score.name,
                priority=priority,
                angle=_angle(score),
                reasons=score.reasons,
                evidence=_evidence(score),
            )
        )

    opportunities.sort(
        key=lambda item: (-item.priority, item.name)
    )
    return tuple(opportunities[:limit])
