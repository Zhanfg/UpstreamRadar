from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import exp, isfinite, log, log1p, sqrt
from statistics import median
from typing import Dict, List, Mapping, MutableMapping, Sequence, Tuple

from .museum import MuseumEvidence, build_museum_evidence
from .museum.graph import centrality_consensus

_EPS = 1e-12


@dataclass(frozen=True)
class RepositorySignal:
    """Raw observation for one upstream repository.

    HARMONY v2 keeps the original scalar telemetry but can additionally consume
    short observation histories. New fields are optional so v1 callers remain
    source-compatible.
    """

    name: str
    ecosystem: str
    cost: int
    freshness_hours: float
    commit_velocity: float = 0.0
    release_velocity: float = 0.0
    issue_velocity: float = 0.0
    security_signal: float = 0.0
    breakage_risk: float = 0.0
    dependency_importance: float = 0.0
    maintainer_activity: float = 0.0
    novelty: float = 0.0
    prior_alpha: float = 1.0
    prior_beta: float = 1.0
    recent_change_hits: int = 0
    recent_change_misses: int = 0
    change_history: Tuple[int, ...] = ()
    impact_history: Tuple[float, ...] = ()
    observation_count: int = 0
    content_signal: float = 0.0
    source_reliability: float = 1.0
    failure_streak: int = 0


@dataclass(frozen=True)
class CandidateScore:
    name: str
    ecosystem: str
    cost: int
    local_signal: float
    change_probability: float
    graph_influence: float
    anomaly: float
    uncertainty: float
    momentum: float
    change_point: float
    entropy: float
    content_yield: float
    reliability: float
    exploration: float
    security_focus: float
    bayesian_surprise: float
    structural_novelty: float
    tail_risk: float
    risk_adjusted_utility: float
    museum: MuseumEvidence
    base_utility: float
    reasons: Tuple[str, ...] = ()


@dataclass(frozen=True)
class ScheduleResult:
    selected: Tuple[CandidateScore, ...]
    total_cost: int
    total_utility: float
    ecosystem_counts: Mapping[str, int]
    explored_states: int
    coverage_score: float = 0.0
    content_score: float = 0.0


@dataclass(frozen=True)
class HarmonyConfig:
    half_life_hours: float = 18.0
    pagerank_damping: float = 0.84
    pagerank_steps: int = 36
    ecosystem_affinity: float = 0.12

    local_weight: float = 0.18
    probability_weight: float = 0.12
    graph_weight: float = 0.15
    anomaly_weight: float = 0.08
    uncertainty_weight: float = 0.07
    security_weight: float = 0.08
    momentum_weight: float = 0.09
    change_point_weight: float = 0.10
    content_weight: float = 0.09
    reliability_weight: float = 0.04
    surprise_weight: float = 0.08
    structural_novelty_weight: float = 0.06
    museum_weight: float = 0.12
    tail_risk_penalty: float = 0.11
    museum_disagreement_penalty: float = 0.08

    diversity_bonus: float = 0.10
    redundancy_penalty: float = 0.07
    dependency_overlap_penalty: float = 0.05
    coverage_bonus_weight: float = 0.18
    exploration_bonus_weight: float = 0.10

    beam_width: int = 128
    robust_clip: float = 4.0
    min_reliability: float = 0.15

    ewma_fast_alpha: float = 0.58
    ewma_medium_alpha: float = 0.26
    ewma_slow_alpha: float = 0.09
    change_point_delta: float = 0.04
    change_point_scale: float = 1.25
    change_ensemble_jump_scale: float = 1.35
    change_ensemble_slope_scale: float = 4.0
    cvar_quantile: float = 0.75
    empirical_bayes_strength: float = 4.0
    empirical_bayes_shrinkage: float = 0.35

    def validate(self) -> None:
        if self.half_life_hours <= 0:
            raise ValueError("half_life_hours must be positive")
        if not 0.0 < self.pagerank_damping < 1.0:
            raise ValueError("pagerank_damping must be in (0, 1)")
        if self.pagerank_steps <= 0:
            raise ValueError("pagerank_steps must be positive")
        if self.beam_width <= 0:
            raise ValueError("beam_width must be positive")
        for name in ("ewma_fast_alpha", "ewma_medium_alpha", "ewma_slow_alpha"):
            alpha = getattr(self, name)
            if not 0.0 < alpha <= 1.0:
                raise ValueError(f"{name} must be in (0, 1]")
        if not 0.0 < self.min_reliability <= 1.0:
            raise ValueError("min_reliability must be in (0, 1]")
        if not 0.5 <= self.cvar_quantile < 1.0:
            raise ValueError("cvar_quantile must be in [0.5, 1)")
        if self.tail_risk_penalty < 0.0:
            raise ValueError("tail_risk_penalty must be non-negative")
        if self.museum_weight < 0.0:
            raise ValueError("museum_weight must be non-negative")
        if self.museum_disagreement_penalty < 0.0:
            raise ValueError("museum_disagreement_penalty must be non-negative")
        if self.empirical_bayes_strength <= 0.0:
            raise ValueError("empirical_bayes_strength must be positive")
        if not 0.0 <= self.empirical_bayes_shrinkage <= 1.0:
            raise ValueError("empirical_bayes_shrinkage must be in [0, 1]")


@dataclass
class _BeamState:
    chosen: Tuple[int, ...] = ()
    cost: int = 0
    utility: float = 0.0
    ecosystem_counts: Dict[str, int] = field(default_factory=dict)
    selected_names: frozenset[str] = frozenset()

    def signature(self) -> Tuple[int, Tuple[Tuple[str, int], ...], frozenset[str]]:
        return self.cost, tuple(sorted(self.ecosystem_counts.items())), self.selected_names


class HarmonyScheduler:
    """HARMONY v4: curated algorithm-museum information scheduling."""

    _LOCAL_FEATURES = (
        "commit_velocity",
        "release_velocity",
        "issue_velocity",
        "security_signal",
        "breakage_risk",
        "dependency_importance",
        "maintainer_activity",
        "novelty",
        "content_signal",
    )

    def __init__(self, config: HarmonyConfig | None = None) -> None:
        self.config = config or HarmonyConfig()
        self.config.validate()

    @staticmethod
    def _safe(value: float) -> float:
        return 0.0 if not isfinite(value) else float(value)

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _sigmoid(x: float) -> float:
        if x >= 0:
            z = exp(-x)
            return 1.0 / (1.0 + z)
        z = exp(x)
        return z / (1.0 + z)

    @staticmethod
    def _mad(values: Sequence[float], center: float) -> float:
        if not values:
            return 1.0
        mad = median(abs(x - center) for x in values)
        return max(1.4826 * mad, 1e-6)

    def _robust_normalize(
        self,
        records: Sequence[RepositorySignal],
    ) -> Dict[str, Dict[str, float]]:
        by_ecosystem: Dict[str, List[RepositorySignal]] = {}
        for record in records:
            by_ecosystem.setdefault(record.ecosystem, []).append(record)

        global_stats: Dict[str, Tuple[float, float]] = {}
        for feature in self._LOCAL_FEATURES:
            values = [self._safe(getattr(record, feature)) for record in records]
            center = median(values)
            global_stats[feature] = (center, self._mad(values, center))

        normalized: Dict[str, Dict[str, float]] = {record.name: {} for record in records}
        for ecosystem_records in by_ecosystem.values():
            shrink = min(1.0, len(ecosystem_records) / 4.0)
            for feature in self._LOCAL_FEATURES:
                values = [self._safe(getattr(record, feature)) for record in ecosystem_records]
                local_center = median(values)
                local_scale = self._mad(values, local_center)
                global_center, global_scale = global_stats[feature]
                center = shrink * local_center + (1.0 - shrink) * global_center
                scale = shrink * local_scale + (1.0 - shrink) * global_scale
                scale = max(scale, 1e-6)

                for record, value in zip(ecosystem_records, values):
                    z = (value - center) / scale
                    limit = self.config.robust_clip
                    normalized[record.name][feature] = max(-limit, min(limit, z))
        return normalized

    def _empirical_bayes_priors(
        self,
        records: Sequence[RepositorySignal],
    ) -> Dict[str, Tuple[float, float]]:
        global_hits = sum(max(record.recent_change_hits, 0) for record in records)
        global_misses = sum(max(record.recent_change_misses, 0) for record in records)
        global_rate = (global_hits + 1.0) / (global_hits + global_misses + 2.0)

        by_ecosystem: Dict[str, Tuple[int, int]] = {}
        for record in records:
            hits, misses = by_ecosystem.get(record.ecosystem, (0, 0))
            by_ecosystem[record.ecosystem] = (
                hits + max(record.recent_change_hits, 0),
                misses + max(record.recent_change_misses, 0),
            )

        priors: Dict[str, Tuple[float, float]] = {}
        strength = self.config.empirical_bayes_strength
        shrinkage = self.config.empirical_bayes_shrinkage
        for ecosystem, (hits, misses) in by_ecosystem.items():
            local_rate = (hits + 1.0) / (hits + misses + 2.0)
            sample_weight = (hits + misses) / (hits + misses + strength)
            blended_local = sample_weight * local_rate + (1.0 - sample_weight) * global_rate
            rate = (1.0 - shrinkage) * blended_local + shrinkage * global_rate
            priors[ecosystem] = (
                max(_EPS, 1.0 + strength * rate),
                max(_EPS, 1.0 + strength * (1.0 - rate)),
            )
        return priors

    def _change_probability(
        self,
        record: RepositorySignal,
        ecosystem_prior: Tuple[float, float] | None = None,
    ) -> Tuple[float, float]:
        prior_alpha, prior_beta = ecosystem_prior or (
            max(record.prior_alpha, _EPS),
            max(record.prior_beta, _EPS),
        )
        alpha = prior_alpha + max(record.recent_change_hits, 0)
        beta = prior_beta + max(record.recent_change_misses, 0)
        total = alpha + beta
        posterior_mean = alpha / total
        posterior_variance = (alpha * beta) / (total * total * (total + 1.0))

        freshness = max(self._safe(record.freshness_hours), 0.0)
        decay = exp(-log(2.0) * freshness / self.config.half_life_hours)
        probability = posterior_mean * (0.18 + 0.82 * decay)
        uncertainty = sqrt(max(posterior_variance, 0.0))
        return probability, uncertainty

    @staticmethod
    def _ewma(values: Sequence[float], alpha: float) -> float:
        if not values:
            return 0.0
        value = float(values[0])
        for item in values[1:]:
            value = (1.0 - alpha) * value + alpha * float(item)
        return value

    def _dynamics(self, record: RepositorySignal) -> Tuple[float, float, float, float]:
        if record.impact_history:
            history = tuple(
                self._clamp(self._safe(value) / 10.0)
                for value in record.impact_history
            )
        elif record.change_history:
            history = tuple(float(bool(value)) for value in record.change_history)
        else:
            posterior = record.recent_change_hits / max(
                record.recent_change_hits + record.recent_change_misses,
                1,
            )
            history = (posterior,)

        fast = self._ewma(history, self.config.ewma_fast_alpha)
        medium = self._ewma(history, self.config.ewma_medium_alpha)
        slow = self._ewma(history, self.config.ewma_slow_alpha)
        acceleration = (fast - medium) + 0.6 * (medium - slow)
        momentum = self._sigmoid(4.0 * acceleration)

        mean = 0.0
        cumulative = 0.0
        minimum = 0.0
        peak = 0.0
        for index, value in enumerate(history, start=1):
            mean += (value - mean) / index
            cumulative += value - mean - self.config.change_point_delta
            minimum = min(minimum, cumulative)
            peak = max(peak, cumulative - minimum)
        change_point = 1.0 - exp(
            -max(peak, 0.0) / self.config.change_point_scale
        )

        center = sum(history) / len(history)
        volatility = sqrt(
            sum((value - center) ** 2 for value in history) / len(history)
        )

        if record.change_history:
            hits = sum(int(bool(value)) for value in record.change_history)
            probability = hits / len(record.change_history)
        else:
            probability = center

        if probability <= _EPS or probability >= 1.0 - _EPS:
            entropy = 0.0
        else:
            entropy = -(
                probability * log(probability)
                + (1.0 - probability) * log(1.0 - probability)
            ) / log(2.0)

        return (
            momentum,
            change_point,
            self._clamp(volatility * 2.0),
            self._clamp(entropy),
        )

    def _local_and_anomaly(
        self,
        z: Mapping[str, float],
    ) -> Tuple[float, float]:
        activity = (
            0.30 * z["commit_velocity"]
            + 0.20 * z["release_velocity"]
            + 0.14 * z["issue_velocity"]
            + 0.16 * z["maintainer_activity"]
            + 0.08 * z["novelty"]
            + 0.12 * z["content_signal"]
        )
        risk = (
            0.42 * z["security_signal"]
            + 0.34 * z["breakage_risk"]
            + 0.24 * z["dependency_importance"]
        )
        interaction = self._sigmoid(activity) * self._sigmoid(risk)
        local_signal = self._sigmoid(
            0.50 * activity + 0.42 * risk + 0.62 * interaction
        )

        groups = (
            (z["commit_velocity"], z["release_velocity"], z["issue_velocity"]),
            (z["security_signal"], z["breakage_risk"]),
            (z["dependency_importance"], z["maintainer_activity"], z["novelty"]),
            (z["content_signal"],),
        )
        energy = [
            sqrt(sum(value * value for value in group) / max(len(group), 1))
            for group in groups
        ]
        anomaly = self._sigmoid(
            0.38 * energy[0]
            + 0.24 * energy[1]
            + 0.20 * energy[2]
            + 0.18 * energy[3]
            - 0.72
        )
        return local_signal, anomaly

    def _seeded_graph_diffusion(
        self,
        records: Sequence[RepositorySignal],
        dependencies: Mapping[str, Sequence[str]],
        seeds: Mapping[str, float],
    ) -> Dict[str, float]:
        names = tuple(record.name for record in records)
        if not names:
            return {}

        known = set(names)
        by_ecosystem: Dict[str, List[str]] = {}
        for record in records:
            by_ecosystem.setdefault(record.ecosystem, []).append(record.name)

        outgoing: Dict[str, Dict[str, float]] = {name: {} for name in names}
        for record in records:
            source = record.name
            for target in dependencies.get(source, ()):
                if target in known and target != source:
                    outgoing[source][target] = outgoing[source].get(target, 0.0) + 1.0

            peers = [
                peer
                for peer in by_ecosystem[record.ecosystem]
                if peer != source
            ]
            if peers:
                affinity = self.config.ecosystem_affinity / len(peers)
                for peer in peers:
                    outgoing[source][peer] = outgoing[source].get(peer, 0.0) + affinity

        seed_total = sum(max(seeds.get(name, 0.0), _EPS) for name in names)
        teleport = {
            name: max(seeds.get(name, 0.0), _EPS) / seed_total
            for name in names
        }
        rank = dict(teleport)
        damping = self.config.pagerank_damping

        for _ in range(self.config.pagerank_steps):
            next_rank = {
                name: (1.0 - damping) * teleport[name]
                for name in names
            }
            dangling = 0.0
            for source in names:
                edges = outgoing[source]
                weight_sum = sum(edges.values())
                if weight_sum <= _EPS:
                    dangling += rank[source]
                    continue
                for target, weight in edges.items():
                    next_rank[target] += damping * rank[source] * weight / weight_sum

            if dangling:
                for name in names:
                    next_rank[name] += damping * dangling * teleport[name]
            rank = next_rank

        total = sum(rank.values()) or 1.0
        return {
            name: value / total
            for name, value in rank.items()
        }

    @staticmethod
    def _bernoulli_kl(q: float, p: float) -> float:
        q = max(_EPS, min(1.0 - _EPS, q))
        p = max(_EPS, min(1.0 - _EPS, p))
        return q * log(q / p) + (1.0 - q) * log((1.0 - q) / (1.0 - p))

    def _bayesian_surprise(
        self,
        record: RepositorySignal,
        predicted_probability: float,
    ) -> float:
        if record.change_history:
            history = tuple(int(bool(value)) for value in record.change_history)
            window = history[-min(len(history), 12):]
            empirical = (sum(window) + 0.5) / (len(window) + 1.0)
        else:
            total = max(record.recent_change_hits + record.recent_change_misses, 0)
            empirical = (max(record.recent_change_hits, 0) + 0.5) / (total + 1.0)
        divergence = self._bernoulli_kl(empirical, predicted_probability)
        return self._clamp(1.0 - exp(-3.4 * divergence))

    def _change_ensemble(
        self,
        record: RepositorySignal,
        page_hinkley: float,
    ) -> float:
        if record.impact_history:
            history = [
                self._clamp(self._safe(value) / 10.0)
                for value in record.impact_history
            ]
        elif record.change_history:
            history = [float(bool(value)) for value in record.change_history]
        else:
            return page_hinkley

        if len(history) < 2:
            return page_hinkley

        prior = history[:-1]
        latest = history[-1]
        center = median(prior)
        scale = self._mad(prior, center)
        robust_jump = self._clamp(
            abs(latest - center)
            / max(scale * self.config.change_ensemble_jump_scale, _EPS)
        )

        n = len(history)
        mean_x = (n - 1.0) / 2.0
        mean_y = sum(history) / n
        denominator = sum((index - mean_x) ** 2 for index in range(n))
        slope = 0.0
        if denominator > _EPS:
            slope = sum(
                (index - mean_x) * (value - mean_y)
                for index, value in enumerate(history)
            ) / denominator
        slope_signal = self._clamp(
            abs(slope) * self.config.change_ensemble_slope_scale
        )
        return self._clamp(
            0.50 * page_hinkley
            + 0.30 * robust_jump
            + 0.20 * slope_signal
        )

    def _tail_risk(self, record: RepositorySignal) -> float:
        history = sorted(
            self._clamp(self._safe(value) / 10.0)
            for value in record.impact_history
        )
        if history:
            start = min(
                len(history) - 1,
                int(len(history) * self.config.cvar_quantile),
            )
            tail = history[start:]
            cvar = sum(tail) / len(tail)
        else:
            cvar = 0.0

        security = self._clamp(self._safe(record.security_signal) / 10.0)
        breakage = self._clamp(self._safe(record.breakage_risk) / 10.0)
        failure = 1.0 - exp(-0.28 * max(record.failure_streak, 0))
        return self._clamp(
            0.46 * cvar
            + 0.24 * security
            + 0.18 * breakage
            + 0.12 * failure
        )

    def _structural_novelty(
        self,
        record: RepositorySignal,
        dependencies: Mapping[str, Sequence[str]],
        dependency_frequency: Mapping[str, int],
    ) -> float:
        deps = tuple(dict.fromkeys(dependencies.get(record.name, ())))
        if not deps:
            return 0.22 * self._clamp(self._safe(record.novelty) / 10.0)
        rarity = sum(
            1.0 / max(dependency_frequency.get(dep, 1), 1)
            for dep in deps
        ) / len(deps)
        breadth = 1.0 - exp(-len(deps) / 3.0)
        intrinsic = self._clamp(self._safe(record.novelty) / 10.0)
        return self._clamp(0.48 * rarity + 0.32 * breadth + 0.20 * intrinsic)

    def _reliability(self, record: RepositorySignal) -> float:
        base = self._clamp(self._safe(record.source_reliability))
        decay = exp(-0.22 * max(record.failure_streak, 0))
        return max(self.config.min_reliability, base * decay)

    def _reasons(self, score: CandidateScore) -> Tuple[str, ...]:
        reasons: List[str] = []
        if score.change_point >= 0.45:
            reasons.append("regime-shift")
        if score.momentum >= 0.62:
            reasons.append("accelerating")
        if score.content_yield >= 0.62:
            reasons.append("high-content-yield")
        if score.graph_influence >= 0.65:
            reasons.append("dependency-hub")
        if score.security_focus >= 0.62:
            reasons.append("security-focus")
        if score.exploration >= 0.10:
            reasons.append("uncertainty-exploration")
        if score.change_probability >= 0.62:
            reasons.append("likely-change")
        if score.anomaly >= 0.65:
            reasons.append("anomalous")
        if score.bayesian_surprise >= 0.45:
            reasons.append("high-surprise")
        if score.structural_novelty >= 0.58:
            reasons.append("structural-novelty")
        if score.tail_risk >= 0.72:
            reasons.append("tail-risk")
        if score.museum.consensus >= 0.64:
            reasons.append("museum-consensus")
        if score.museum.disagreement >= 0.46:
            reasons.append("algorithm-disagreement")
        return tuple(reasons[:8])

    def score(
        self,
        records: Sequence[RepositorySignal],
        dependencies: Mapping[str, Sequence[str]] | None = None,
    ) -> Tuple[CandidateScore, ...]:
        dependencies = dependencies or {}
        if not records:
            return ()

        names = [record.name for record in records]
        if len(names) != len(set(names)):
            raise ValueError("repository names must be unique")
        if any(record.cost <= 0 for record in records):
            raise ValueError("cost must be a positive integer")

        normalized = self._robust_normalize(records)
        empirical_priors = self._empirical_bayes_priors(records)
        prepared: Dict[str, Dict[str, float]] = {}
        dependency_frequency: Dict[str, int] = {}
        for source in records:
            for target in set(dependencies.get(source.name, ())):
                dependency_frequency[target] = dependency_frequency.get(target, 0) + 1
        total_observations = 1 + sum(
            max(record.observation_count, 0)
            for record in records
        )

        for record in records:
            local, anomaly = self._local_and_anomaly(
                normalized[record.name]
            )
            probability, uncertainty = self._change_probability(
                record,
                empirical_priors.get(record.ecosystem),
            )
            momentum, change_point, volatility, entropy = self._dynamics(record)
            change_point = self._change_ensemble(record, change_point)
            reliability = self._reliability(record)
            surprise = self._bayesian_surprise(record, probability)
            structural_novelty = self._structural_novelty(
                record,
                dependencies,
                dependency_frequency,
            )
            tail_risk = self._tail_risk(record)
            content_yield = self._sigmoid(
                0.68 * normalized[record.name]["content_signal"]
                + 1.10 * change_point
                + 0.78 * entropy
                + 0.62 * volatility
                + 0.42 * momentum
            )
            exploration = uncertainty * sqrt(
                log1p(total_observations)
                / (1.0 + max(record.observation_count, 0))
            )
            security = self._sigmoid(
                normalized[record.name]["security_signal"]
            )
            seed = (
                0.28 * local
                + 0.24 * change_point
                + 0.22 * content_yield
                + 0.14 * security
                + 0.12 * probability
            )
            prepared[record.name] = {
                "local": local,
                "anomaly": anomaly,
                "probability": probability,
                "uncertainty": uncertainty,
                "momentum": momentum,
                "change_point": change_point,
                "entropy": entropy,
                "content_yield": content_yield,
                "reliability": reliability,
                "exploration": exploration,
                "security": security,
                "surprise": surprise,
                "structural_novelty": structural_novelty,
                "tail_risk": tail_risk,
                "seed": seed
                + 0.10 * surprise
                + 0.08 * structural_novelty
                - 0.05 * tail_risk,
            }

        graph_seeds = {
            name: values["seed"]
            for name, values in prepared.items()
        }
        museum_graph, museum_graph_trace = centrality_consensus(
            dependencies,
            seeds=graph_seeds,
        )
        config = self.config
        weight_sum = (
            config.local_weight
            + config.probability_weight
            + config.graph_weight
            + config.anomaly_weight
            + config.uncertainty_weight
            + config.security_weight
            + config.momentum_weight
            + config.change_point_weight
            + config.content_weight
            + config.reliability_weight
            + config.surprise_weight
            + config.structural_novelty_weight
            + config.museum_weight
        )

        scored: List[CandidateScore] = []
        dependency_sets = {
            record.name: tuple(dict.fromkeys(dependencies.get(record.name, ())))
            for record in records
        }
        for record in records:
            values = prepared[record.name]
            influence = self._clamp(museum_graph.get(record.name, 0.0))
            peers = [
                dependency_sets[other.name]
                for other in records
                if other.name != record.name
            ]
            museum = build_museum_evidence(
                local_features=tuple(normalized[record.name].values()),
                impact_history=record.impact_history,
                change_history=record.change_history,
                hits=record.recent_change_hits,
                misses=record.recent_change_misses,
                observation_count=record.observation_count,
                total_observations=total_observations,
                dependencies=dependency_sets[record.name],
                peer_dependencies=peers,
                graph_consensus=influence,
                graph_trace=museum_graph_trace.get(record.name, ()),
            )

            change_point = self._clamp(
                0.58 * values["change_point"]
                + 0.42 * museum.change_consensus
            )
            exploration = self._clamp(
                0.44 * min(values["exploration"] * 4.0, 1.0)
                + 0.56 * museum.bandit_index
            )
            structural_novelty = self._clamp(
                0.60 * values["structural_novelty"]
                + 0.40 * museum.dependency_novelty
            )

            utility = (
                config.local_weight * values["local"]
                + config.probability_weight * values["probability"]
                + config.graph_weight * influence
                + config.anomaly_weight * values["anomaly"]
                + config.uncertainty_weight * values["uncertainty"]
                + config.security_weight * values["security"]
                + config.momentum_weight * values["momentum"]
                + config.change_point_weight * change_point
                + config.content_weight * values["content_yield"]
                + config.reliability_weight * values["reliability"]
                + config.surprise_weight * values["surprise"]
                + config.structural_novelty_weight * structural_novelty
                + config.museum_weight * museum.consensus
            ) / weight_sum

            utility *= 1.0 - config.museum_disagreement_penalty * museum.disagreement
            risk_adjusted = utility * (
                1.0 - config.tail_risk_penalty * values["tail_risk"]
            )
            risk_adjusted += 0.025 * values["surprise"] * values["reliability"]
            utility = risk_adjusted
            utility *= 0.82 + 0.18 * values["reliability"]
            utility *= 1.0 + 0.07 * log1p(1.0 / record.cost)

            provisional = CandidateScore(
                name=record.name,
                ecosystem=record.ecosystem,
                cost=record.cost,
                local_signal=values["local"],
                change_probability=values["probability"],
                graph_influence=influence,
                anomaly=values["anomaly"],
                uncertainty=values["uncertainty"],
                momentum=values["momentum"],
                change_point=change_point,
                entropy=values["entropy"],
                content_yield=values["content_yield"],
                reliability=values["reliability"],
                exploration=exploration,
                security_focus=values["security"],
                bayesian_surprise=values["surprise"],
                structural_novelty=structural_novelty,
                tail_risk=values["tail_risk"],
                risk_adjusted_utility=risk_adjusted,
                museum=museum,
                base_utility=utility,
            )
            scored.append(
                replace(
                    provisional,
                    reasons=self._reasons(provisional),
                )
            )

        return tuple(
            sorted(
                scored,
                key=lambda item: (-item.base_utility, item.name),
            )
        )

    @staticmethod
    def _jaccard(
        left: frozenset[str],
        right: frozenset[str],
    ) -> float:
        union = left | right
        return 0.0 if not union else len(left & right) / len(union)

    def _similarity(
        self,
        left: CandidateScore,
        right: CandidateScore,
        dependency_sets: Mapping[str, frozenset[str]],
    ) -> float:
        if left.name == right.name:
            return 1.0

        ecosystem = 1.0 if left.ecosystem == right.ecosystem else 0.0
        dependency = self._jaccard(
            dependency_sets.get(left.name, frozenset()),
            dependency_sets.get(right.name, frozenset()),
        )
        profile_distance = (
            abs(left.content_yield - right.content_yield)
            + abs(left.change_point - right.change_point)
            + abs(left.security_focus - right.security_focus)
            + abs(left.bayesian_surprise - right.bayesian_surprise)
            + abs(left.tail_risk - right.tail_risk)
            + abs(left.museum.consensus - right.museum.consensus)
            + abs(left.museum.information_gain - right.museum.information_gain)
        ) / 7.0
        profile = exp(-2.4 * profile_distance)
        return self._clamp(
            0.42 * ecosystem
            + 0.34 * dependency
            + 0.24 * profile
        )

    def _coverage_gain(
        self,
        candidate: CandidateScore,
        selected_names: frozenset[str],
        scores_by_name: Mapping[str, CandidateScore],
        similarity: Mapping[Tuple[str, str], float],
    ) -> float:
        if not scores_by_name:
            return 0.0

        gain = 0.0
        for target_name in scores_by_name:
            current = max(
                (
                    similarity[(target_name, selected)]
                    for selected in selected_names
                ),
                default=0.0,
            )
            proposed = max(
                current,
                similarity[(target_name, candidate.name)],
            )
            gain += proposed - current
        return gain / len(scores_by_name)

    def _marginal_utility(
        self,
        candidate: CandidateScore,
        state: _BeamState,
        dependency_sets: Mapping[str, frozenset[str]],
        scores_by_name: Mapping[str, CandidateScore],
        similarity: Mapping[Tuple[str, str], float],
    ) -> float:
        same_ecosystem = state.ecosystem_counts.get(
            candidate.ecosystem,
            0,
        )
        diversity = self.config.diversity_bonus / (
            1.0 + same_ecosystem
        )
        redundancy = (
            self.config.redundancy_penalty * same_ecosystem
        )

        max_overlap = 0.0
        candidate_dependencies = dependency_sets.get(
            candidate.name,
            frozenset(),
        )
        for selected in state.selected_names:
            max_overlap = max(
                max_overlap,
                self._jaccard(
                    candidate_dependencies,
                    dependency_sets.get(selected, frozenset()),
                ),
            )

        coverage = self._coverage_gain(
            candidate,
            state.selected_names,
            scores_by_name,
            similarity,
        )
        exploration = (
            self.config.exploration_bonus_weight
            * candidate.exploration
        )
        content_bonus = (
            0.04
            * candidate.content_yield
            * (1.0 + candidate.change_point)
        )
        novelty_bonus = (
            0.035 * candidate.structural_novelty
            + 0.025 * candidate.bayesian_surprise
            + 0.030 * candidate.museum.information_gain
        )
        museum_bonus = 0.045 * candidate.museum.consensus
        disagreement_penalty = 0.025 * candidate.museum.disagreement
        tail_penalty = 0.025 * candidate.tail_risk

        return (
            candidate.base_utility
            + diversity
            + self.config.coverage_bonus_weight * coverage
            + exploration
            + content_bonus
            + novelty_bonus
            + museum_bonus
            - disagreement_penalty
            - tail_penalty
            - redundancy
            - self.config.dependency_overlap_penalty * max_overlap
        )

    def _fractional_upper_bound(
        self,
        state: _BeamState,
        remaining: Sequence[CandidateScore],
        budget: int,
    ) -> float:
        capacity = budget - state.cost
        if capacity <= 0:
            return state.utility

        optimistic = []
        for candidate in remaining:
            gain = (
                candidate.base_utility
                + self.config.diversity_bonus
                + self.config.coverage_bonus_weight
                + self.config.exploration_bonus_weight
                * candidate.exploration
                + 0.08 * candidate.content_yield
            )
            optimistic.append(
                (gain / candidate.cost, gain, candidate.cost)
            )
        optimistic.sort(reverse=True)

        bound = state.utility
        remaining_capacity = float(capacity)
        for _, gain, cost in optimistic:
            if remaining_capacity <= 0:
                break
            if cost <= remaining_capacity:
                bound += gain
                remaining_capacity -= cost
            else:
                bound += gain * (remaining_capacity / cost)
                break
        return bound

    def _portfolio_coverage(
        self,
        selected_names: frozenset[str],
        scores_by_name: Mapping[str, CandidateScore],
        similarity: Mapping[Tuple[str, str], float],
    ) -> float:
        if not scores_by_name or not selected_names:
            return 0.0

        total = 0.0
        for target_name in scores_by_name:
            total += max(
                similarity[(target_name, selected)]
                for selected in selected_names
            )
        return total / len(scores_by_name)

    @staticmethod
    def _ordering_priority(score: CandidateScore) -> float:
        return (
            0.60 * score.base_utility
            + 0.22 * (score.base_utility / score.cost)
            + 0.10 * score.content_yield
            + 0.08 * score.change_point
            + 0.05 * score.bayesian_surprise
            + 0.04 * score.structural_novelty
            + 0.05 * score.museum.consensus
            + 0.03 * score.museum.information_gain
            - 0.03 * score.tail_risk
            - 0.02 * score.museum.disagreement
        )

    def _extend_state(
        self,
        *,
        index: int,
        candidate: CandidateScore,
        state: _BeamState,
        budget: int,
        maximums: Mapping[str, int],
        dependency_sets: Mapping[str, frozenset[str]],
        scores_by_name: Mapping[str, CandidateScore],
        similarity: Mapping[Tuple[str, str], float],
    ) -> _BeamState | None:
        new_cost = state.cost + candidate.cost
        if new_cost > budget:
            return None

        current_count = state.ecosystem_counts.get(candidate.ecosystem, 0)
        maximum = maximums.get(candidate.ecosystem)
        if maximum is not None and current_count >= maximum:
            return None

        counts = dict(state.ecosystem_counts)
        counts[candidate.ecosystem] = current_count + 1
        gain = self._marginal_utility(
            candidate,
            state,
            dependency_sets,
            scores_by_name,
            similarity,
        )
        return _BeamState(
            chosen=state.chosen + (index,),
            cost=new_cost,
            utility=state.utility + gain,
            ecosystem_counts=counts,
            selected_names=state.selected_names | {candidate.name},
        )

    def _beam_rank(
        self,
        state: _BeamState,
        remaining: Sequence[CandidateScore],
        budget: int,
    ) -> tuple[float, float, int, tuple[str, ...]]:
        upper_bound = self._fractional_upper_bound(state, remaining, budget)
        return (
            -upper_bound,
            -state.utility,
            state.cost,
            tuple(sorted(state.selected_names)),
        )

    def schedule(
        self,
        records: Sequence[RepositorySignal],
        budget: int,
        dependencies: Mapping[str, Sequence[str]] | None = None,
        min_per_ecosystem: Mapping[str, int] | None = None,
        max_per_ecosystem: Mapping[str, int] | None = None,
    ) -> ScheduleResult:
        if budget < 0:
            raise ValueError("budget must be non-negative")

        dependencies = dependencies or {}
        minimums = dict(min_per_ecosystem or {})
        maximums = dict(max_per_ecosystem or {})
        scores = self.score(records, dependencies)

        if not scores or budget == 0:
            return ScheduleResult(
                (),
                0,
                0.0,
                {},
                1,
                0.0,
                0.0,
            )

        for ecosystem, minimum in minimums.items():
            if minimum < 0:
                raise ValueError(
                    f"negative minimum for ecosystem {ecosystem}"
                )
        for ecosystem, maximum in maximums.items():
            if maximum < 0:
                raise ValueError(
                    f"negative maximum for ecosystem {ecosystem}"
                )
            if maximum < minimums.get(ecosystem, 0):
                raise ValueError(
                    f"maximum below minimum for ecosystem {ecosystem}"
                )

        dependency_sets = {
            score.name: frozenset(
                dependencies.get(score.name, ())
            )
            for score in scores
        }
        scores_by_name = {
            score.name: score
            for score in scores
        }
        similarity = {
            (left.name, right.name): self._similarity(
                left,
                right,
                dependency_sets,
            )
            for left in scores
            for right in scores
        }

        ordered = tuple(
            sorted(
                scores,
                key=lambda score: (
                    -self._ordering_priority(score),
                    score.name,
                ),
            )
        )

        beam: List[_BeamState] = [_BeamState()]
        explored = 1

        for index, candidate in enumerate(ordered):
            next_states: List[_BeamState] = []

            for state in beam:
                next_states.append(state)
                extended = self._extend_state(
                    index=index,
                    candidate=candidate,
                    state=state,
                    budget=budget,
                    maximums=maximums,
                    dependency_sets=dependency_sets,
                    scores_by_name=scores_by_name,
                    similarity=similarity,
                )
                if extended is None:
                    continue
                next_states.append(extended)
                explored += 1

            dedup: MutableMapping[tuple, _BeamState] = {}
            for state in next_states:
                signature = state.signature()
                previous = dedup.get(signature)
                if (
                    previous is None
                    or state.utility > previous.utility
                ):
                    dedup[signature] = state

            remaining = ordered[index + 1 :]
            beam = sorted(
                dedup.values(),
                key=lambda state: self._beam_rank(state, remaining, budget),
            )[: self.config.beam_width]

        feasible = [
            state
            for state in beam
            if all(
                state.ecosystem_counts.get(ecosystem, 0)
                >= minimum
                for ecosystem, minimum in minimums.items()
            )
        ]
        if not feasible:
            raise ValueError(
                "no schedule satisfies budget and "
                "ecosystem minimum constraints"
            )

        best = max(
            feasible,
            key=lambda state: (
                state.utility,
                -state.cost,
                tuple(sorted(state.selected_names)),
            ),
        )
        selected = tuple(
            ordered[index]
            for index in best.chosen
        )
        coverage = self._portfolio_coverage(
            best.selected_names,
            scores_by_name,
            similarity,
        )
        content_score = (
            sum(
                score.content_yield
                for score in selected
            )
            / len(selected)
            if selected
            else 0.0
        )

        return ScheduleResult(
            selected=selected,
            total_cost=best.cost,
            total_utility=best.utility,
            ecosystem_counts=dict(
                sorted(best.ecosystem_counts.items())
            ),
            explored_states=explored,
            coverage_score=coverage,
            content_score=content_score,
        )
