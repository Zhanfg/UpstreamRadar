from __future__ import annotations

from dataclasses import dataclass, field
from math import exp, isfinite, log1p, sqrt
from statistics import median
from typing import Dict, List, Mapping, MutableMapping, Sequence, Tuple


_EPS = 1e-12


@dataclass(frozen=True)
class RepositorySignal:
    """Raw observation for one upstream repository.

    Most numeric fields are intentionally unit-agnostic. HARMONY performs
    robust, ecosystem-local normalization before combining them.
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
    base_utility: float


@dataclass(frozen=True)
class ScheduleResult:
    selected: Tuple[CandidateScore, ...]
    total_cost: int
    total_utility: float
    ecosystem_counts: Mapping[str, int]
    explored_states: int


@dataclass(frozen=True)
class HarmonyConfig:
    half_life_hours: float = 18.0
    pagerank_damping: float = 0.85
    pagerank_steps: int = 40

    local_weight: float = 0.28
    probability_weight: float = 0.18
    graph_weight: float = 0.20
    anomaly_weight: float = 0.14
    uncertainty_weight: float = 0.10
    security_weight: float = 0.10

    diversity_bonus: float = 0.14
    redundancy_penalty: float = 0.08
    dependency_overlap_penalty: float = 0.06
    beam_width: int = 96

    robust_clip: float = 4.0

    def validate(self) -> None:
        if self.half_life_hours <= 0:
            raise ValueError("half_life_hours must be positive")
        if not 0.0 < self.pagerank_damping < 1.0:
            raise ValueError("pagerank_damping must be in (0, 1)")
        if self.pagerank_steps <= 0:
            raise ValueError("pagerank_steps must be positive")
        if self.beam_width <= 0:
            raise ValueError("beam_width must be positive")


@dataclass
class _BeamState:
    chosen: Tuple[int, ...] = ()
    cost: int = 0
    utility: float = 0.0
    ecosystem_counts: Dict[str, int] = field(default_factory=dict)
    selected_names: frozenset[str] = frozenset()

    def signature(self) -> Tuple[int, Tuple[Tuple[str, int], ...], frozenset[str]]:
        return (
            self.cost,
            tuple(sorted(self.ecosystem_counts.items())),
            self.selected_names,
        )


class HarmonyScheduler:
    """Hierarchical Adaptive Radar Multi-objective Optimizer.

    Pipeline:
      1. robust normalization inside each ecosystem,
      2. Bayesian change-probability estimation,
      3. dependency-graph influence diffusion,
      4. robust anomaly scoring,
      5. multi-objective utility fusion,
      6. diversity-aware budgeted beam search.
    """

    _LOCAL_FEATURES = (
        "commit_velocity",
        "release_velocity",
        "issue_velocity",
        "security_signal",
        "breakage_risk",
        "dependency_importance",
        "maintainer_activity",
        "novelty",
    )

    def __init__(self, config: HarmonyConfig | None = None) -> None:
        self.config = config or HarmonyConfig()
        self.config.validate()

    @staticmethod
    def _safe(value: float) -> float:
        if not isfinite(value):
            return 0.0
        return float(value)

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

        normalized: Dict[str, Dict[str, float]] = {r.name: {} for r in records}

        for ecosystem_records in by_ecosystem.values():
            for feature in self._LOCAL_FEATURES:
                values = [self._safe(getattr(r, feature)) for r in ecosystem_records]
                center = median(values)
                scale = self._mad(values, center)
                for record, value in zip(ecosystem_records, values):
                    z = (value - center) / scale
                    z = max(-self.config.robust_clip, min(self.config.robust_clip, z))
                    normalized[record.name][feature] = z

        return normalized

    def _change_probability(self, record: RepositorySignal) -> Tuple[float, float]:
        alpha = max(record.prior_alpha, _EPS) + max(record.recent_change_hits, 0)
        beta = max(record.prior_beta, _EPS) + max(record.recent_change_misses, 0)
        total = alpha + beta

        posterior_mean = alpha / total
        posterior_variance = (alpha * beta) / (total * total * (total + 1.0))

        freshness = max(self._safe(record.freshness_hours), 0.0)
        decay = exp(-log1p(1.0) * freshness / self.config.half_life_hours)

        probability = posterior_mean * (0.20 + 0.80 * decay)
        uncertainty = sqrt(max(posterior_variance, 0.0))
        return probability, uncertainty

    def _pagerank(
        self,
        records: Sequence[RepositorySignal],
        dependencies: Mapping[str, Sequence[str]],
    ) -> Dict[str, float]:
        names = tuple(r.name for r in records)
        if not names:
            return {}
        known = set(names)
        n = len(names)
        base = 1.0 / n
        rank = {name: base for name in names}

        reverse: Dict[str, List[str]] = {name: [] for name in names}
        out_degree: Dict[str, int] = {name: 0 for name in names}

        for src in names:
            deps = [dst for dst in dependencies.get(src, ()) if dst in known and dst != src]
            out_degree[src] = len(deps)
            for dst in deps:
                reverse[dst].append(src)

        d = self.config.pagerank_damping
        for _ in range(self.config.pagerank_steps):
            dangling = sum(rank[name] for name in names if out_degree[name] == 0)
            next_rank: Dict[str, float] = {}
            for node in names:
                incoming = sum(
                    rank[src] / out_degree[src]
                    for src in reverse[node]
                    if out_degree[src] > 0
                )
                next_rank[node] = (1.0 - d) * base + d * (incoming + dangling * base)
            rank = next_rank

        total = sum(rank.values()) or 1.0
        return {name: value / total for name, value in rank.items()}

    def _local_and_anomaly(
        self,
        record: RepositorySignal,
        z: Mapping[str, float],
    ) -> Tuple[float, float]:
        activity = (
            0.34 * z["commit_velocity"]
            + 0.22 * z["release_velocity"]
            + 0.16 * z["issue_velocity"]
            + 0.18 * z["maintainer_activity"]
            + 0.10 * z["novelty"]
        )
        risk = (
            0.42 * z["security_signal"]
            + 0.36 * z["breakage_risk"]
            + 0.22 * z["dependency_importance"]
        )

        interaction = self._sigmoid(activity) * self._sigmoid(risk)
        local_signal = self._sigmoid(
            0.54 * activity
            + 0.46 * risk
            + 0.55 * interaction
        )

        groups = (
            (z["commit_velocity"], z["release_velocity"], z["issue_velocity"]),
            (z["security_signal"], z["breakage_risk"]),
            (z["dependency_importance"], z["maintainer_activity"], z["novelty"]),
        )
        group_energy = [
            sqrt(sum(v * v for v in group) / max(len(group), 1))
            for group in groups
        ]
        anomaly = self._sigmoid(
            0.50 * group_energy[0]
            + 0.30 * group_energy[1]
            + 0.20 * group_energy[2]
            - 0.75
        )
        return local_signal, anomaly

    def score(
        self,
        records: Sequence[RepositorySignal],
        dependencies: Mapping[str, Sequence[str]] | None = None,
    ) -> Tuple[CandidateScore, ...]:
        dependencies = dependencies or {}
        if not records:
            return ()

        names = [r.name for r in records]
        if len(names) != len(set(names)):
            raise ValueError("repository names must be unique")
        if any(r.cost <= 0 for r in records):
            raise ValueError("cost must be a positive integer")

        z = self._robust_normalize(records)
        graph = self._pagerank(records, dependencies)
        max_graph = max(graph.values(), default=1.0) or 1.0

        scored: List[CandidateScore] = []
        for record in records:
            local, anomaly = self._local_and_anomaly(record, z[record.name])
            probability, uncertainty = self._change_probability(record)
            influence = graph.get(record.name, 0.0) / max_graph
            security = self._sigmoid(z[record.name]["security_signal"])

            c = self.config
            utility = (
                c.local_weight * local
                + c.probability_weight * probability
                + c.graph_weight * influence
                + c.anomaly_weight * anomaly
                + c.uncertainty_weight * uncertainty
                + c.security_weight * security
            )

            density_adjustment = 1.0 + 0.08 * log1p(1.0 / record.cost)
            utility *= density_adjustment

            scored.append(
                CandidateScore(
                    name=record.name,
                    ecosystem=record.ecosystem,
                    cost=record.cost,
                    local_signal=local,
                    change_probability=probability,
                    graph_influence=influence,
                    anomaly=anomaly,
                    uncertainty=uncertainty,
                    base_utility=utility,
                )
            )

        return tuple(sorted(scored, key=lambda x: (-x.base_utility, x.name)))

    def _marginal_utility(
        self,
        candidate: CandidateScore,
        state: _BeamState,
        dependency_sets: Mapping[str, frozenset[str]],
    ) -> float:
        same_ecosystem = state.ecosystem_counts.get(candidate.ecosystem, 0)

        diversity = self.config.diversity_bonus / (1.0 + same_ecosystem)
        redundancy = self.config.redundancy_penalty * same_ecosystem

        overlap_penalty = 0.0
        deps = dependency_sets.get(candidate.name, frozenset())
        if deps and state.selected_names:
            max_overlap = 0.0
            for selected in state.selected_names:
                other = dependency_sets.get(selected, frozenset())
                if not other:
                    continue
                union = deps | other
                if union:
                    max_overlap = max(max_overlap, len(deps & other) / len(union))
            overlap_penalty = self.config.dependency_overlap_penalty * max_overlap

        exploration = self.config.uncertainty_weight * candidate.uncertainty
        return candidate.base_utility + diversity + exploration - redundancy - overlap_penalty

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
        min_per_ecosystem = dict(min_per_ecosystem or {})
        max_per_ecosystem = dict(max_per_ecosystem or {})

        scores = self.score(records, dependencies)
        if not scores or budget == 0:
            return ScheduleResult((), 0, 0.0, {}, 1)

        for eco, minimum in min_per_ecosystem.items():
            if minimum < 0:
                raise ValueError(f"negative minimum for ecosystem {eco}")
        for eco, maximum in max_per_ecosystem.items():
            if maximum < 0:
                raise ValueError(f"negative maximum for ecosystem {eco}")
            if maximum < min_per_ecosystem.get(eco, 0):
                raise ValueError(f"maximum below minimum for ecosystem {eco}")

        dependency_sets = {
            name: frozenset(dependencies.get(name, ()))
            for name in (s.name for s in scores)
        }

        ordered = tuple(
            sorted(
                scores,
                key=lambda s: (
                    -(0.72 * s.base_utility + 0.28 * (s.base_utility / s.cost)),
                    s.name,
                ),
            )
        )

        beam: List[_BeamState] = [_BeamState()]
        explored = 1

        for idx, candidate in enumerate(ordered):
            next_states: List[_BeamState] = []

            for state in beam:
                next_states.append(state)

                new_cost = state.cost + candidate.cost
                if new_cost > budget:
                    continue

                current_count = state.ecosystem_counts.get(candidate.ecosystem, 0)
                max_allowed = max_per_ecosystem.get(candidate.ecosystem)
                if max_allowed is not None and current_count >= max_allowed:
                    continue

                gain = self._marginal_utility(candidate, state, dependency_sets)
                counts = dict(state.ecosystem_counts)
                counts[candidate.ecosystem] = current_count + 1

                next_states.append(
                    _BeamState(
                        chosen=state.chosen + (idx,),
                        cost=new_cost,
                        utility=state.utility + gain,
                        ecosystem_counts=counts,
                        selected_names=state.selected_names | {candidate.name},
                    )
                )
                explored += 1

            dedup: MutableMapping[
                Tuple[int, Tuple[Tuple[str, int], ...], frozenset[str]],
                _BeamState,
            ] = {}
            for state in next_states:
                sig = state.signature()
                old = dedup.get(sig)
                if old is None or state.utility > old.utility:
                    dedup[sig] = state

            remaining = ordered[idx + 1 :]
            optimistic_tail = sum(
                s.base_utility
                for s in remaining[: max(0, self.config.beam_width // 8)]
            )

            beam = sorted(
                dedup.values(),
                key=lambda s: (
                    -(s.utility + optimistic_tail),
                    -s.utility,
                    s.cost,
                    tuple(sorted(s.selected_names)),
                ),
            )[: self.config.beam_width]

        def satisfies_minimums(state: _BeamState) -> bool:
            return all(
                state.ecosystem_counts.get(eco, 0) >= minimum
                for eco, minimum in min_per_ecosystem.items()
            )

        feasible = [state for state in beam if satisfies_minimums(state)]
        if not feasible:
            raise ValueError(
                "no schedule satisfies budget and ecosystem minimum constraints"
            )

        best = max(
            feasible,
            key=lambda s: (
                s.utility,
                -s.cost,
                tuple(sorted(s.selected_names)),
            ),
        )

        selected = tuple(ordered[i] for i in best.chosen)
        return ScheduleResult(
            selected=selected,
            total_cost=best.cost,
            total_utility=best.utility,
            ecosystem_counts=dict(sorted(best.ecosystem_counts.items())),
            explored_states=explored,
        )
