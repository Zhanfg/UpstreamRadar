from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from upstreamradar.engine import HarmonyConfig, HarmonyScheduler, RepositorySignal


UTC = timezone.utc


def records(count: int) -> tuple[RepositorySignal, ...]:
    ecosystems = ("kernel", "android", "network", "ai", "security", "tooling")
    result = []
    for index in range(count):
        history = tuple(
            int(((index * 5 + step * 7) % 13) >= 8)
            for step in range(16)
        )
        impact = tuple(
            float(((index * 11 + step * 3) % 10) if history[step] else 0)
            for step in range(16)
        )
        hits = sum(history)
        result.append(
            RepositorySignal(
                name=f"bench-{index:04d}",
                ecosystem=ecosystems[index % len(ecosystems)],
                cost=1 + index % 4,
                freshness_hours=float(index % 24),
                commit_velocity=float((index * 7) % 20),
                release_velocity=float((index * 5) % 10),
                issue_velocity=float((index * 11) % 15),
                security_signal=float((index * 3) % 10),
                breakage_risk=float((index * 2) % 8),
                dependency_importance=float((index * 5) % 10),
                maintainer_activity=float((index * 13) % 18),
                novelty=float((index * 17) % 10),
                recent_change_hits=hits,
                recent_change_misses=len(history) - hits,
                change_history=history,
                impact_history=impact,
                observation_count=8 + index,
                content_signal=sum(impact) / len(impact),
                source_reliability=0.85 + 0.15 * ((index % 5) / 4),
                failure_streak=index % 2,
            )
        )
    return tuple(result)


def dependencies(items: tuple[RepositorySignal, ...]) -> dict[str, tuple[str, ...]]:
    names = [item.name for item in items]
    graph = {}
    for index, name in enumerate(names):
        graph[name] = (
            names[(index + 1) % len(names)],
            names[(index + 9) % len(names)],
            names[(index + 23) % len(names)],
        )
    return graph


def selected_hash(result) -> str:
    raw = "\n".join(item.name for item in result.selected).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def run_benchmark(
    *,
    count: int,
    budget: int,
    iterations: int,
) -> dict:
    items = records(count)
    graph = dependencies(items)
    scheduler = HarmonyScheduler(
        HarmonyConfig(
            beam_width=64,
            pagerank_steps=24,
        )
    )

    durations = []
    hashes = []
    selected_count = 0
    total_cost = 0
    utility = 0.0
    coverage = 0.0
    content = 0.0

    for _ in range(iterations):
        started = time.perf_counter()
        result = scheduler.schedule(
            items,
            budget=budget,
            dependencies=graph,
        )
        durations.append((time.perf_counter() - started) * 1000.0)
        hashes.append(selected_hash(result))
        selected_count = len(result.selected)
        total_cost = result.total_cost
        utility = result.total_utility
        coverage = result.coverage_score
        content = result.content_score

    deterministic = len(set(hashes)) == 1
    return {
        "candidate_count": count,
        "budget": budget,
        "iterations": iterations,
        "median_ms": round(statistics.median(durations), 4),
        "min_ms": round(min(durations), 4),
        "max_ms": round(max(durations), 4),
        "selected_count": selected_count,
        "total_cost": total_cost,
        "total_utility": round(utility, 8),
        "coverage_score": round(coverage, 8),
        "content_score": round(content, 8),
        "selection_hash": hashes[0],
        "deterministic": deterministic,
    }


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/activity_fabric.json")
    parser.add_argument("--baseline", default="state/benchmark.json")
    parser.add_argument("--output")
    args = parser.parse_args()

    config = load(Path(args.config), {})
    policy = config.get("benchmark", {})
    count = int(policy.get("candidates", 120))
    budget = int(policy.get("budget", 80))
    iterations = int(policy.get("iterations", 5))
    ratio = float(policy.get("regression_ratio", 1.75))
    history_limit = int(policy.get("history", 14))

    result = run_benchmark(
        count=count,
        budget=budget,
        iterations=iterations,
    )
    now = datetime.now(UTC).replace(microsecond=0)
    baseline_path = Path(args.baseline)
    baseline = load(
        baseline_path,
        {
            "version": 1,
            "history": [],
        },
    )

    previous = baseline.get("median_ms")
    regressed = bool(
        previous
        and result["median_ms"] > float(previous) * ratio
    )
    determinism_regressed = not result["deterministic"]

    report = {
        "observed_at": now.isoformat(),
        "previous_median_ms": previous,
        "regression_ratio": ratio,
        "regressed": regressed,
        "determinism_regressed": determinism_regressed,
        **result,
    }

    history = list(baseline.get("history", []))
    history.append(
        {
            "observed_at": report["observed_at"],
            "median_ms": result["median_ms"],
            "selection_hash": result["selection_hash"],
        }
    )
    baseline["history"] = history[-history_limit:]
    if not regressed and result["deterministic"]:
        if previous is None:
            baseline["median_ms"] = result["median_ms"]
        else:
            baseline["median_ms"] = round(
                0.8 * float(previous) + 0.2 * result["median_ms"],
                4,
            )
        baseline["selection_hash"] = result["selection_hash"]
    baseline["last_observed_at"] = report["observed_at"]
    write(baseline_path, baseline)

    output = Path(
        args.output
        or f"reports/benchmarks/{now.date().isoformat()}.json"
    )
    write(output, report)
    print(
        "BENCHMARK=PASS "
        f"median_ms={result['median_ms']} "
        f"deterministic={result['deterministic']} "
        f"regressed={regressed}"
    )
    return 2 if determinism_regressed else 0


if __name__ == "__main__":
    raise SystemExit(main())
