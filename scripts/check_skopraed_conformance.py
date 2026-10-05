from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance" / "fixtures" / "skopraed-v1-basic.json"
CONTRACT = ROOT / "conformance" / "contract" / "skopraed-v1.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def python_payload(fixture: dict[str, Any], command: str) -> dict[str, Any]:
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from upstreamradar import RepositorySignal, SkopraedScheduler

    supported = {
        "name",
        "ecosystem",
        "cost",
        "freshness_hours",
        "commit_velocity",
        "release_velocity",
        "issue_velocity",
        "security_signal",
        "breakage_risk",
        "dependency_importance",
        "maintainer_activity",
        "novelty",
        "recent_change_hits",
        "recent_change_misses",
        "observation_count",
        "source_reliability",
        "failure_streak",
    }

    records = []
    dependencies: dict[str, tuple[str, ...]] = {}
    for raw in fixture["repositories"]:
        kwargs = {key: raw[key] for key in supported if key in raw}
        kwargs["change_history"] = tuple(raw.get("change_history", ()))
        kwargs["impact_history"] = tuple(raw.get("impact_history", ()))
        records.append(RepositorySignal(**kwargs))
        dependencies[raw["name"]] = tuple(raw.get("dependencies", ()))

    scheduler = SkopraedScheduler()
    if command == "score":
        candidates = scheduler.score(records, dependencies=dependencies)
        return {
            "version": "skopraed-python/1",
            "command": "score",
            "count": len(candidates),
            "candidates": [
                {
                    "name": candidate.name,
                    "utility": candidate.base_utility,
                    "museum": {
                        "consensus": candidate.museum.consensus,
                        "disagreement": candidate.museum.disagreement,
                    },
                }
                for candidate in candidates
            ],
        }

    result = scheduler.schedule(
        records,
        budget=int(fixture["budget"]),
        dependencies=dependencies,
    )
    return {
        "version": "skopraed-python/1",
        "command": "schedule",
        "schedule": {
            "selected": [{"name": item.name} for item in result.selected],
            "spent": result.total_cost,
            "budget": int(fixture["budget"]),
            "objective": result.total_utility,
        },
    }


def external_payload(
    fixture: dict[str, Any],
    command: str,
    runtime: str,
) -> dict[str, Any]:
    request = {
        "command": command,
        "budget": int(fixture["budget"]),
        "repositories": fixture["repositories"],
    }
    encoded = json.dumps(request).encode()

    if runtime == "rust":
        if shutil.which("cargo") is None:
            raise RuntimeError("cargo is required for Rust conformance")
        args = [
            "cargo",
            "run",
            "--quiet",
            "--manifest-path",
            str(ROOT / "core" / "skopraed-rs" / "Cargo.toml"),
            "--bin",
            "skopraed-museum",
        ]
        cwd = ROOT
    elif runtime == "go":
        if shutil.which("go") is None:
            raise RuntimeError("go is required for Go conformance")
        args = ["go", "run", "./cmd/radar-go"]
        cwd = ROOT / "services" / "radar-go"
    else:
        raise ValueError(runtime)

    completed = subprocess.run(
        args,
        input=encoded,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"{runtime} conformance command failed:\n"
            + completed.stderr.decode(errors="replace")
        )
    return json.loads(completed.stdout)


def run_once(
    runtime: str,
    fixture: dict[str, Any],
    command: str,
) -> dict[str, Any]:
    if runtime == "python":
        return python_payload(fixture, command)
    return external_payload(fixture, command, runtime)


def validate_score(
    runtime: str,
    payload: dict[str, Any],
    input_names: set[str],
) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise AssertionError(f"{runtime}: score output is empty")

    seen: set[str] = set()
    for candidate in candidates:
        name = str(candidate["name"])
        if name not in input_names:
            raise AssertionError(f"{runtime}: unknown candidate {name}")
        if name in seen:
            raise AssertionError(f"{runtime}: duplicate candidate {name}")
        seen.add(name)

        utility = float(candidate["utility"])
        if not math.isfinite(utility) or utility < 0:
            raise AssertionError(f"{runtime}: invalid utility for {name}")

        museum = candidate.get("museum") or {}
        for key in ("consensus", "disagreement"):
            value = float(museum[key])
            if not 0.0 <= value <= 1.0:
                raise AssertionError(
                    f"{runtime}: museum {key} out of range for {name}: {value}"
                )

    return str(candidates[0]["name"])


def validate_schedule(
    runtime: str,
    payload: dict[str, Any],
    input_names: set[str],
    budget: int,
) -> tuple[str, ...]:
    schedule = payload["schedule"]
    spent = int(schedule["spent"])
    if spent > budget:
        raise AssertionError(f"{runtime}: spent {spent} exceeds budget {budget}")

    names = tuple(str(item["name"]) for item in schedule.get("selected", ()))
    if len(names) != len(set(names)):
        raise AssertionError(f"{runtime}: duplicate schedule selection")
    unknown = set(names) - input_names
    if unknown:
        raise AssertionError(f"{runtime}: unknown selected names {sorted(unknown)}")
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--runtime",
        action="append",
        choices=("python", "rust", "go"),
        dest="runtimes",
    )
    args = parser.parse_args()
    runtimes = args.runtimes or ["python"]

    fixture = load_json(FIXTURE)
    contract = load_json(CONTRACT)
    if fixture["contract"] != "skopraed-v1":
        raise AssertionError("fixture contract mismatch")
    if contract["name"] != "skopraed-v1-conformance":
        raise AssertionError("conformance contract mismatch")

    input_names = {str(item["name"]) for item in fixture["repositories"]}
    budget = int(fixture["budget"])

    top_candidates: dict[str, str] = {}
    schedules: dict[str, tuple[str, ...]] = {}

    for runtime in runtimes:
        first_score = run_once(runtime, fixture, "score")
        second_score = run_once(runtime, fixture, "score")
        if first_score != second_score:
            raise AssertionError(f"{runtime}: non-deterministic score replay")

        first_schedule = run_once(runtime, fixture, "schedule")
        second_schedule = run_once(runtime, fixture, "schedule")
        if first_schedule != second_schedule:
            raise AssertionError(f"{runtime}: non-deterministic schedule replay")

        top_candidates[runtime] = validate_score(
            runtime, first_score, input_names
        )
        schedules[runtime] = validate_schedule(
            runtime, first_schedule, input_names, budget
        )

    unique_tops = set(top_candidates.values())
    if len(unique_tops) != 1:
        raise AssertionError(
            "production runtimes disagree on top candidate: "
            + json.dumps(top_candidates, sort_keys=True)
        )

    print(
        json.dumps(
            {
                "contract": fixture["contract"],
                "runtimes": runtimes,
                "top_candidate": next(iter(unique_tops)),
                "schedules": schedules,
                "status": "ok",
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
