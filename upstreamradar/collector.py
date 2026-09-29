from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from math import ceil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .content import build_content_plan
from .engine import HarmonyScheduler, RepositorySignal


UTC = timezone.utc
LOCAL_TZ = ZoneInfo("Asia/Shanghai")
USER_AGENT = "UpstreamRadar/0.1 (+https://github.com/Zhanfg/UpstreamRadar)"


@dataclass(frozen=True)
class Target:
    full_name: str
    ecosystem: str
    cost: int = 2
    importance: float = 5.0
    security: float = 0.0
    dependencies: tuple[str, ...] = ()


class GitHubClient:
    def __init__(self, token: str | None, timeout: int = 20) -> None:
        self.token = token
        self.timeout = timeout

    def _get(self, url: str, *, allow_404: bool = False) -> Any:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        last_error: Exception | None = None
        for attempt in range(3):
            try:
                request = Request(url, headers=headers)
                with urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except HTTPError as exc:
                if allow_404 and exc.code == 404:
                    return None
                if exc.code not in {429, 500, 502, 503, 504}:
                    raise
                last_error = exc
            except URLError as exc:
                last_error = exc

            time.sleep(1.5 * (attempt + 1))

        if last_error is not None:
            raise last_error
        raise RuntimeError(f"failed to fetch {url}")

    def repository(self, full_name: str) -> Mapping[str, Any]:
        return self._get(f"https://api.github.com/repos/{full_name}")

    def latest_release(self, full_name: str) -> Mapping[str, Any] | None:
        return self._get(
            f"https://api.github.com/repos/{full_name}/releases/latest",
            allow_404=True,
        )


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def atomic_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def load_targets(path: Path) -> tuple[list[Target], dict[str, Any]]:
    raw = load_json(path, {})
    targets: list[Target] = []

    for item in raw.get("repositories", []):
        targets.append(
            Target(
                full_name=item["full_name"],
                ecosystem=item["ecosystem"],
                cost=int(item.get("cost", 2)),
                importance=float(item.get("importance", 5.0)),
                security=float(item.get("security", 0.0)),
                dependencies=tuple(item.get("dependencies", [])),
            )
        )

    if not targets:
        raise ValueError("repository configuration is empty")
    if len({target.full_name for target in targets}) != len(targets):
        raise ValueError("repository configuration contains duplicates")

    return targets, raw


def run_probability(local_hour: int) -> float:
    if 0 <= local_hour < 6:
        return 0.40
    if 6 <= local_hour < 9:
        return 0.70
    if 9 <= local_hour < 18:
        return 0.95
    if 18 <= local_hour < 23:
        return 0.85
    return 0.60


def should_run(now: datetime, *, force: bool = False) -> tuple[bool, float, float]:
    if force:
        return True, 1.0, 0.0

    local = now.astimezone(LOCAL_TZ)
    slot_minute = (local.minute // 15) * 15
    slot = local.replace(minute=slot_minute, second=0, microsecond=0)
    probability = run_probability(local.hour)

    digest = hashlib.sha256(
        f"UpstreamRadar|gate-v1|{slot.isoformat()}".encode("utf-8")
    ).digest()
    sample = int.from_bytes(digest[:8], "big") / float(2**64 - 1)
    return sample < probability, probability, sample


def catch_up_multiplier(
    last_run_at: str | None,
    now: datetime,
    *,
    grace_hours: float = 0.5,
    ramp_hours: float = 2.5,
    maximum: float = 2.5,
) -> tuple[float, float]:
    """Increase scan breadth after GitHub schedule delays.

    The multiplier changes *current* scan breadth only. It never fabricates
    historical observations or backdates commits.
    """
    previous = parse_time(last_run_at)
    if previous is None:
        return 1.0, 0.0

    elapsed = max(0.0, (now - previous).total_seconds() / 3600.0)
    overdue = max(0.0, elapsed - grace_hours)
    multiplier = 1.0 + min(maximum - 1.0, overdue / max(ramp_hours, 1e-9))
    return round(multiplier, 4), round(elapsed, 4)


def slug(full_name: str) -> str:
    return full_name.replace("/", "__")


def snapshot_path(root: Path, full_name: str) -> Path:
    return root / f"{slug(full_name)}.json"


def stable_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in snapshot.items() if key != "observed_at"}


def repo_snapshot(
    repository: Mapping[str, Any],
    release: Mapping[str, Any] | None,
    observed_at: datetime,
) -> dict[str, Any]:
    license_data = repository.get("license") or {}
    release_data = None
    if release:
        release_data = {
            "tag_name": release.get("tag_name"),
            "name": release.get("name"),
            "published_at": release.get("published_at"),
            "prerelease": bool(release.get("prerelease")),
            "draft": bool(release.get("draft")),
        }

    return {
        "full_name": repository.get("full_name"),
        "html_url": repository.get("html_url"),
        "description": repository.get("description"),
        "default_branch": repository.get("default_branch"),
        "language": repository.get("language"),
        "topics": sorted(repository.get("topics") or []),
        "license": license_data.get("spdx_id"),
        "archived": bool(repository.get("archived")),
        "disabled": bool(repository.get("disabled")),
        "fork": bool(repository.get("fork")),
        "visibility": repository.get("visibility"),
        "size_kb": int(repository.get("size") or 0),
        "stars": int(repository.get("stargazers_count") or 0),
        "forks": int(repository.get("forks_count") or 0),
        "watchers": int(repository.get("subscribers_count") or 0),
        "open_issues": int(repository.get("open_issues_count") or 0),
        "created_at": repository.get("created_at"),
        "updated_at": repository.get("updated_at"),
        "pushed_at": repository.get("pushed_at"),
        "latest_release": release_data,
        "observed_at": iso(observed_at),
    }


def initial_state() -> dict[str, Any]:
    return {
        "version": 3,
        "repositories": {},
        "daily": {},
        "scheduler": {},
    }


def repo_model(state: Mapping[str, Any], full_name: str) -> dict[str, Any]:
    repositories = state.get("repositories", {})
    current = repositories.get(full_name, {})
    return dict(current)


def bounded_window(values: Iterable[int], item: int, limit: int = 48) -> list[int]:
    result = [int(bool(x)) for x in values]
    result.append(int(bool(item)))
    return result[-limit:]


def bounded_float_window(
    values: Iterable[float],
    item: float,
    limit: int = 48,
) -> list[float]:
    result = [float(value) for value in values]
    result.append(float(item))
    return result[-limit:]


def semantic_impact(
    old_snapshot: Mapping[str, Any] | None,
    new_snapshot: Mapping[str, Any] | None,
) -> float:
    """Estimate how much reportable meaning changed between two snapshots."""
    if old_snapshot is None or new_snapshot is None:
        return 0.0

    old = stable_snapshot(old_snapshot)
    new = stable_snapshot(new_snapshot)
    weights = {
        "latest_release": 4.0,
        "pushed_at": 2.4,
        "default_branch": 4.0,
        "archived": 5.0,
        "disabled": 5.0,
        "topics": 1.6,
        "description": 1.2,
        "language": 1.4,
        "license": 1.4,
        "open_issues": 1.0,
        "forks": 0.6,
        "stars": 0.35,
        "watchers": 0.35,
        "size_kb": 0.2,
    }
    impact = sum(
        weight
        for key, weight in weights.items()
        if old.get(key) != new.get(key)
    )
    return min(10.0, round(impact, 4))


def ewma(previous: float, observation: float, alpha: float = 0.25) -> float:
    return (1.0 - alpha) * float(previous) + alpha * float(observation)


def signal_for(
    target: Target,
    model: Mapping[str, Any],
    now: datetime,
) -> RepositorySignal:
    last_checked = parse_time(model.get("last_checked_at"))
    freshness = 72.0 if last_checked is None else max(
        0.0,
        (now - last_checked).total_seconds() / 3600.0,
    )

    change_window = list(model.get("change_window", []))
    impact_window = list(model.get("impact_window", []))
    hits = sum(int(bool(x)) for x in change_window)
    misses = len(change_window) - hits
    checks = int(model.get("checks", 0))
    successful_checks = int(model.get("successful_checks", 0))

    novelty = 10.0 / ((checks + 1) ** 0.5)
    breakage = float(model.get("breakage_risk", 0.0))
    reliability = (successful_checks + 3.0) / (checks + 3.0)

    return RepositorySignal(
        name=target.full_name,
        ecosystem=target.ecosystem,
        cost=max(1, target.cost),
        freshness_hours=freshness,
        commit_velocity=10.0 * float(model.get("ewma_change", 0.5)),
        release_velocity=10.0 * float(model.get("ewma_release", 0.2)),
        issue_velocity=min(10.0, float(model.get("ewma_issue_delta", 0.0))),
        security_signal=target.security,
        breakage_risk=breakage,
        dependency_importance=target.importance,
        maintainer_activity=10.0 * float(model.get("ewma_change", 0.5)),
        novelty=novelty,
        prior_alpha=1.0,
        prior_beta=1.0,
        recent_change_hits=hits,
        recent_change_misses=misses,
        change_history=tuple(int(bool(value)) for value in change_window),
        impact_history=tuple(float(value) for value in impact_window),
        observation_count=checks,
        content_signal=float(model.get("ewma_impact", 0.0)),
        source_reliability=reliability,
        failure_streak=int(model.get("error_streak", 0)),
    )


def select_targets(
    targets: Sequence[Target],
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    now: datetime,
    *,
    pressure: float = 1.0,
) -> tuple[list[Target], list[dict[str, Any]], dict[str, Any]]:
    scheduler = HarmonyScheduler()
    signals = [signal_for(target, repo_model(state, target.full_name), now) for target in targets]
    dependencies = {target.full_name: target.dependencies for target in targets}

    scheduling = config.get("scheduling", {})
    base_budget = int(scheduling.get("budget", 28))
    base_max_repositories = int(scheduling.get("max_repositories_per_run", 16))
    pressure = max(1.0, min(float(pressure), 2.5))
    budget = max(base_budget, int(ceil(base_budget * pressure)))
    max_repositories = min(
        len(targets),
        max(base_max_repositories, int(ceil(base_max_repositories * pressure))),
    )
    per_ecosystem_cap = int(scheduling.get("max_per_ecosystem", 6))
    ecosystems = sorted({target.ecosystem for target in targets})

    result = scheduler.schedule(
        signals,
        budget=budget,
        dependencies=dependencies,
        max_per_ecosystem={eco: per_ecosystem_cap for eco in ecosystems},
    )

    target_by_name = {target.full_name: target for target in targets}
    ordered = sorted(result.selected, key=lambda candidate: (-candidate.base_utility, candidate.name))
    ordered = ordered[:max_repositories]

    selected = [target_by_name[candidate.name] for candidate in ordered]
    scores = [
        {
            "full_name": candidate.name,
            "ecosystem": candidate.ecosystem,
            "cost": candidate.cost,
            "utility": round(candidate.base_utility, 8),
            "change_probability": round(candidate.change_probability, 8),
            "graph_influence": round(candidate.graph_influence, 8),
            "anomaly": round(candidate.anomaly, 8),
            "uncertainty": round(candidate.uncertainty, 8),
            "momentum": round(candidate.momentum, 8),
            "change_point": round(candidate.change_point, 8),
            "entropy": round(candidate.entropy, 8),
            "content_yield": round(candidate.content_yield, 8),
            "reliability": round(candidate.reliability, 8),
            "exploration": round(candidate.exploration, 8),
            "security_focus": round(candidate.security_focus, 8),
            "reasons": list(candidate.reasons),
        }
        for candidate in ordered
    ]
    content_plan = [
        asdict(item)
        for item in build_content_plan(ordered, limit=min(8, len(ordered)))
    ]
    selection_meta = {
        "coverage_score": round(result.coverage_score, 8),
        "content_score": round(result.content_score, 8),
        "content_plan": content_plan,
    }
    return selected, scores, selection_meta


def update_model(
    previous: Mapping[str, Any],
    *,
    old_snapshot: Mapping[str, Any] | None,
    new_snapshot: Mapping[str, Any] | None,
    changed: bool,
    error: str | None,
    now: datetime,
) -> dict[str, Any]:
    model = dict(previous)
    model["checks"] = int(model.get("checks", 0)) + 1
    model["last_checked_at"] = iso(now)

    if error is not None:
        model["error_streak"] = int(model.get("error_streak", 0)) + 1
        model["failed_checks"] = int(model.get("failed_checks", 0)) + 1
        model["last_error"] = error[:500]
        return model

    model["error_streak"] = 0
    model["successful_checks"] = int(model.get("successful_checks", 0)) + 1
    model.pop("last_error", None)
    model["change_window"] = bounded_window(model.get("change_window", []), int(changed))
    model["ewma_change"] = round(
        ewma(float(model.get("ewma_change", 0.5)), float(changed)),
        8,
    )
    impact = semantic_impact(old_snapshot, new_snapshot)
    model["impact_window"] = bounded_float_window(
        model.get("impact_window", []),
        impact,
    )
    model["ewma_impact"] = round(
        ewma(float(model.get("ewma_impact", 0.0)), impact),
        8,
    )
    model["last_semantic_impact"] = impact

    old_release = (old_snapshot or {}).get("latest_release") or {}
    new_release = (new_snapshot or {}).get("latest_release") or {}
    release_changed = old_release.get("tag_name") != new_release.get("tag_name")
    if old_snapshot is None:
        release_changed = False
    model["release_window"] = bounded_window(
        model.get("release_window", []),
        int(release_changed),
    )
    model["ewma_release"] = round(
        ewma(float(model.get("ewma_release", 0.2)), float(release_changed)),
        8,
    )

    old_issues = int((old_snapshot or {}).get("open_issues", 0))
    new_issues = int((new_snapshot or {}).get("open_issues", 0))
    issue_delta = abs(new_issues - old_issues) if old_snapshot is not None else 0
    model["ewma_issue_delta"] = round(
        ewma(float(model.get("ewma_issue_delta", 0.0)), float(issue_delta)),
        8,
    )

    archived = bool((new_snapshot or {}).get("archived"))
    disabled = bool((new_snapshot or {}).get("disabled"))
    model["breakage_risk"] = 10.0 if disabled else (7.0 if archived else 0.0)

    if changed:
        model["last_change_at"] = iso(now)
    if release_changed:
        model["last_release_change_at"] = iso(now)

    return model


def render_daily_report(
    date_key: str,
    summary: Mapping[str, Any],
    state: Mapping[str, Any],
) -> str:
    daily = state.get("daily", {}).get(date_key, {})
    recent = daily.get("recent_changed", [])[-20:]

    lines = [
        f"# UpstreamRadar daily report — {date_key}",
        "",
        "This report is generated from real GitHub upstream observations.",
        "",
        "## Totals",
        "",
        f"- collection runs: **{int(daily.get('runs', 0))}**",
        f"- repositories scanned: **{int(daily.get('scanned', 0))}**",
        f"- changed snapshots: **{int(daily.get('changed', 0))}**",
        f"- collection errors: **{int(daily.get('errors', 0))}**",
        "",
        "## Latest run",
        "",
        f"- observed at: `{summary['observed_at']}`",
        f"- selected repositories: **{len(summary.get('selected', []))}**",
        f"- changed repositories: **{len(summary.get('changed', []))}**",
        f"- errors: **{len(summary.get('errors', []))}**",
        f"- catch-up multiplier: **{float(summary.get('catch_up_multiplier', 1.0)):.2f}×**",
        f"- hours since previous successful collection: **{float(summary.get('elapsed_since_previous_run_hours', 0.0)):.2f}**",
        f"- portfolio coverage: **{float(summary.get('coverage_score', 0.0)):.3f}**",
        f"- mean content yield: **{float(summary.get('content_score', 0.0)):.3f}**",
        "",
        "## Content opportunities",
        "",
    ]

    opportunities = summary.get("content_plan", [])
    if opportunities:
        for item in opportunities[:6]:
            evidence = ", ".join(item.get("evidence", []))
            lines.append(
                f"- **{item['name']}** — {item['angle']} "
                f"(priority={float(item['priority']):.3f}; {evidence})"
            )
    else:
        lines.append("- No content opportunities in the latest run.")

    lines.extend(
        [
            "",
            "## Recent changes",
            "",
        ]
    )

    if recent:
        lines.extend(f"- `{name}`" for name in recent)
    else:
        lines.append("- No upstream snapshot changes observed yet.")

    lines.extend(
        [
            "",
            "## Scheduling",
            "",
            "Repository selection is produced by HARMONY v2 using multi-timescale change "
            "dynamics, online regime-shift evidence, content yield, seeded dependency "
            "diffusion, uncertainty-aware exploration, portfolio coverage, and scan cost.",
            "",
        ]
    )
    return "\n".join(lines)


def prune_daily(state: dict[str, Any], keep: int = 14) -> None:
    daily = state.setdefault("daily", {})
    keys = sorted(daily)
    for key in keys[:-keep]:
        daily.pop(key, None)


def collect(
    *,
    config_path: Path,
    state_path: Path,
    snapshot_root: Path,
    run_root: Path,
    report_root: Path,
    manifest_path: Path,
    force: bool,
    token: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    now = now or utc_now()
    permitted, probability, sample = should_run(now, force=force)

    manifest: dict[str, Any] = {
        "ran": False,
        "gate_probability": probability,
        "gate_sample": sample,
        "changed_files": [],
        "checkpoint_files": [],
        "anomalies": [],
    }

    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    if not permitted:
        atomic_json(manifest_path, manifest)
        return manifest

    targets, config = load_targets(config_path)
    state = load_json(state_path, initial_state())
    scheduler_state = state.setdefault("scheduler", {})
    pressure, elapsed_hours = catch_up_multiplier(
        scheduler_state.get("last_run_at"),
        now,
    )
    selected, scores, selection_meta = select_targets(
        targets,
        state,
        config,
        now,
        pressure=pressure,
    )
    client = GitHubClient(token)

    changed_names: list[str] = []
    unchanged_names: list[str] = []
    errors: list[dict[str, str]] = []
    changed_files: list[str] = []
    anomalies: list[dict[str, Any]] = []

    repositories_state = state.setdefault("repositories", {})

    for target in selected:
        path = snapshot_path(snapshot_root, target.full_name)
        old_snapshot = load_json(path, None)
        previous_model = dict(repositories_state.get(target.full_name, {}))

        try:
            repository = client.repository(target.full_name)
            release = client.latest_release(target.full_name)
            new_snapshot = repo_snapshot(repository, release, now)

            changed = (
                old_snapshot is None
                or stable_snapshot(old_snapshot) != stable_snapshot(new_snapshot)
            )

            if changed:
                atomic_json(path, new_snapshot)
                changed_files.append(path.as_posix())
                changed_names.append(target.full_name)
            else:
                unchanged_names.append(target.full_name)

            repositories_state[target.full_name] = update_model(
                previous_model,
                old_snapshot=old_snapshot,
                new_snapshot=new_snapshot,
                changed=changed,
                error=None,
                now=now,
            )
        except Exception as exc:
            message = f"{type(exc).__name__}: {exc}"
            errors.append({"full_name": target.full_name, "error": message})
            model = update_model(
                previous_model,
                old_snapshot=old_snapshot,
                new_snapshot=None,
                changed=False,
                error=message,
                now=now,
            )
            repositories_state[target.full_name] = model

            if int(model.get("error_streak", 0)) >= 3:
                anomalies.append(
                    {
                        "kind": "collection_failure",
                        "full_name": target.full_name,
                        "error_streak": int(model.get("error_streak", 0)),
                        "message": message,
                    }
                )

    local = now.astimezone(LOCAL_TZ)
    date_key = local.date().isoformat()
    slot_key = local.strftime("%H%M")

    daily = state.setdefault("daily", {}).setdefault(
        date_key,
        {
            "runs": 0,
            "scanned": 0,
            "changed": 0,
            "errors": 0,
            "recent_changed": [],
        },
    )
    daily["runs"] = int(daily.get("runs", 0)) + 1
    daily["scanned"] = int(daily.get("scanned", 0)) + len(selected)
    daily["changed"] = int(daily.get("changed", 0)) + len(changed_names)
    daily["errors"] = int(daily.get("errors", 0)) + len(errors)
    daily["recent_changed"] = (
        list(daily.get("recent_changed", [])) + changed_names
    )[-100:]
    prune_daily(state)

    scheduler_state["last_run_at"] = iso(now)
    scheduler_state["last_elapsed_hours"] = elapsed_hours
    scheduler_state["last_catch_up_multiplier"] = pressure

    summary = {
        "observed_at": iso(now),
        "local_time": local.replace(microsecond=0).isoformat(),
        "gate_probability": probability,
        "gate_sample": sample,
        "elapsed_since_previous_run_hours": elapsed_hours,
        "catch_up_multiplier": pressure,
        "selected": [target.full_name for target in selected],
        "scores": scores,
        "coverage_score": selection_meta["coverage_score"],
        "content_score": selection_meta["content_score"],
        "content_plan": selection_meta["content_plan"],
        "changed": changed_names,
        "unchanged": unchanged_names,
        "errors": errors,
    }

    run_path = run_root / date_key / f"{slot_key}.json"
    atomic_json(run_path, summary)
    atomic_json(state_path, state)

    report_path = report_root / f"{date_key}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        render_daily_report(date_key, summary, state),
        encoding="utf-8",
    )

    manifest.update(
        {
            "ran": True,
            "observed_at": iso(now),
            "changed_files": changed_files,
            "checkpoint_files": [
                state_path.as_posix(),
                run_path.as_posix(),
                report_path.as_posix(),
            ],
            "anomalies": anomalies,
            "summary": summary,
        }
    )
    atomic_json(manifest_path, manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one UpstreamRadar collection cycle")
    parser.add_argument("--config", default="config/repositories.json")
    parser.add_argument("--state", default="state/model.json")
    parser.add_argument("--snapshots", default="data/snapshots")
    parser.add_argument("--runs", default="data/runs")
    parser.add_argument("--reports", default="reports/daily")
    parser.add_argument("--manifest", default=".radar/manifest.json")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest = collect(
        config_path=Path(args.config),
        state_path=Path(args.state),
        snapshot_root=Path(args.snapshots),
        run_root=Path(args.runs),
        report_root=Path(args.reports),
        manifest_path=Path(args.manifest),
        force=args.force,
        token=os.environ.get("UPSTREAMRADAR_TOKEN"),
    )

    if not manifest.get("ran"):
        print(
            "collection skipped by deterministic gate: "
            f"p={manifest['gate_probability']:.2f}, "
            f"sample={manifest['gate_sample']:.4f}"
        )
        return 0

    summary = manifest["summary"]
    print(
        "collection complete: "
        f"selected={len(summary['selected'])}, "
        f"changed={len(summary['changed'])}, "
        f"errors={len(summary['errors'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
