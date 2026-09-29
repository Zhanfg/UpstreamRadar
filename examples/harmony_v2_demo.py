from upstreamradar import (
    HarmonyScheduler,
    RepositorySignal,
    build_content_plan,
)


def main() -> None:
    records = (
        RepositorySignal(
            name="kernel",
            ecosystem="kernel",
            cost=4,
            freshness_hours=1,
            commit_velocity=14,
            security_signal=8,
            dependency_importance=10,
            recent_change_hits=4,
            recent_change_misses=2,
            change_history=(0, 0, 1, 1, 1, 1),
            impact_history=(0, 0, 4, 7, 9, 10),
            observation_count=24,
            content_signal=8.2,
        ),
        RepositorySignal(
            name="framework",
            ecosystem="android",
            cost=3,
            freshness_hours=2,
            commit_velocity=10,
            security_signal=5,
            dependency_importance=8,
            recent_change_hits=3,
            recent_change_misses=3,
            change_history=(0, 1, 0, 1, 1, 0),
            impact_history=(0, 4, 0, 5, 6, 0),
            observation_count=18,
            content_signal=5.5,
        ),
        RepositorySignal(
            name="agent-runtime",
            ecosystem="ai",
            cost=2,
            freshness_hours=6,
            commit_velocity=8,
            novelty=9,
            recent_change_hits=2,
            recent_change_misses=4,
            change_history=(0, 0, 1, 0, 1, 0),
            impact_history=(0, 0, 3, 0, 4, 0),
            observation_count=8,
            content_signal=4.0,
        ),
    )

    scheduler = HarmonyScheduler()
    result = scheduler.schedule(
        records,
        budget=6,
        dependencies={"framework": ("kernel",)},
    )

    print(
        "portfolio",
        f"cost={result.total_cost}",
        f"coverage={result.coverage_score:.3f}",
        f"content={result.content_score:.3f}",
    )

    for candidate in result.selected:
        print(
            candidate.name,
            f"utility={candidate.base_utility:.3f}",
            f"change_point={candidate.change_point:.3f}",
            f"content_yield={candidate.content_yield:.3f}",
            f"reasons={','.join(candidate.reasons) or 'general'}",
        )

    print("\ncontent plan")
    for item in build_content_plan(result.selected):
        print(
            f"- {item.name}: priority={item.priority:.3f}; "
            f"angle={item.angle}; evidence={', '.join(item.evidence)}"
        )


if __name__ == "__main__":
    main()
