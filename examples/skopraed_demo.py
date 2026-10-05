from upstreamradar import SkopraedScheduler, RepositorySignal


records = [
    RepositorySignal(
        name="linux",
        ecosystem="kernel",
        cost=5,
        freshness_hours=1,
        commit_velocity=18,
        release_velocity=4,
        security_signal=8,
        breakage_risk=8,
        dependency_importance=10,
        maintainer_activity=10,
        novelty=8,
        recent_change_hits=9,
        recent_change_misses=1,
    ),
    RepositorySignal(
        name="android-kernel",
        ecosystem="android",
        cost=4,
        freshness_hours=2,
        commit_velocity=14,
        release_velocity=3,
        security_signal=9,
        breakage_risk=8,
        dependency_importance=10,
        maintainer_activity=9,
        novelty=7,
        recent_change_hits=8,
        recent_change_misses=2,
    ),
    RepositorySignal(
        name="framework",
        ecosystem="android",
        cost=3,
        freshness_hours=6,
        commit_velocity=10,
        release_velocity=2,
        issue_velocity=6,
        breakage_risk=7,
        dependency_importance=8,
        maintainer_activity=8,
        novelty=6,
        recent_change_hits=6,
        recent_change_misses=3,
    ),
    RepositorySignal(
        name="agent-runtime",
        ecosystem="ai",
        cost=3,
        freshness_hours=10,
        commit_velocity=9,
        release_velocity=5,
        issue_velocity=8,
        breakage_risk=5,
        dependency_importance=5,
        maintainer_activity=7,
        novelty=10,
        recent_change_hits=5,
        recent_change_misses=5,
    ),
]

dependencies = {
    "framework": ["android-kernel"],
    "android-kernel": ["linux"],
}

result = SkopraedScheduler().schedule(
    records,
    budget=12,
    dependencies=dependencies,
    min_per_ecosystem={"kernel": 1, "android": 1, "ai": 1},
)

print(f"total cost: {result.total_cost}")
print(f"utility:    {result.total_utility:.4f}")
print(f"states:     {result.explored_states}")

for candidate in result.selected:
    print(
        f"- {candidate.name:16} "
        f"utility={candidate.base_utility:.4f} "
        f"graph={candidate.graph_influence:.4f} "
        f"p(change)={candidate.change_probability:.4f}"
    )
