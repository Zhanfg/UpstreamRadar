from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any, Mapping


UTC = timezone.utc


@dataclass(frozen=True)
class ActivityCandidate:
    kind: str
    key: str
    title: str
    priority: float
    target: str | None
    body: str
    labels: tuple[str, ...] = ()
    evidence_hash: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["labels"] = list(self.labels)
        return data


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def stable_hash(value: Any) -> str:
    import json

    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:16]


def current_cycle(now: datetime) -> str:
    iso = now.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def cycle_title(now: datetime, config: Mapping[str, Any]) -> str:
    prefix = str(config.get("milestones", {}).get("title_prefix", "Radar Cycle"))
    return f"{prefix} {current_cycle(now)}"


def release_tag(now: datetime, config: Mapping[str, Any]) -> str:
    prefix = str(config.get("releases", {}).get("tag_prefix", "radar"))
    return f"{prefix}-{current_cycle(now)}"


def _recent(model: Mapping[str, Any], now: datetime, hours: float) -> bool:
    checked = parse_time(model.get("last_checked_at"))
    if checked is None:
        return False
    return now - checked <= timedelta(hours=max(0.0, hours))


def plan_signal_issues(
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime,
) -> tuple[ActivityCandidate, ...]:
    policy = config.get("signals", {})
    major = float(policy.get("major_impact", 6.5))
    critical = float(policy.get("critical_impact", 8.0))
    recent_hours = float(policy.get("recent_hours", 18))
    limit = int(policy.get("max_new_issues_per_run", 2))
    important = {
        str(value)
        for value in policy.get(
            "important_fields",
            [
                "latest_release",
                "latest_commit",
                "default_branch",
                "archived",
                "disabled",
                "license",
            ],
        )
    }

    repositories = state.get("repositories")
    if repositories is None:
        repositories = state.get("projects", {})

    candidates: list[ActivityCandidate] = []
    for name, model in repositories.items():
        if not _recent(model, now, recent_hours):
            continue

        impact = float(model.get("last_semantic_impact", 0.0))
        delta = tuple(str(x) for x in model.get("last_semantic_delta", []))
        relevant_field = bool(important.intersection(delta))
        if impact < major:
            continue
        if impact < critical and not relevant_field:
            continue

        breakage = float(model.get("breakage_risk", 0.0))
        ewma_impact = float(model.get("ewma_impact", 0.0))
        issue_velocity = float(model.get("ewma_issue_delta", 0.0))
        fields = ", ".join(delta) if delta else "semantic snapshot"
        evidence = {
            "target": name,
            "impact": round(impact, 4),
            "fields": delta,
            "breakage_risk": round(breakage, 4),
            "ewma_impact": round(ewma_impact, 4),
            "issue_velocity": round(issue_velocity, 4),
            "platform": platform,
            "last_checked_at": model.get("last_checked_at"),
        }
        body = (
            "UpstreamRadar detected a material upstream change that crossed the "
            "configured engineering-triage threshold.\n\n"
            f"- target: {name}\n"
            f"- platform: {platform}\n"
            f"- semantic impact: {impact:.2f}\n"
            f"- changed fields: {fields}\n"
            f"- EWMA impact: {ewma_impact:.2f}\n"
            f"- issue velocity: {issue_velocity:.2f}\n"
            f"- breakage risk: {breakage:.2f}\n"
            f"- last checked: {model.get('last_checked_at')}\n\n"
            "This is an evidence-backed investigation task, not a synthetic "
            "activity event. Close it when the change has been assessed or the "
            "signal falls below the configured recovery threshold."
        )
        labels = ["activity:signal", "triage"]
        if impact >= critical:
            labels.append("priority:high")
        elif issue_velocity >= 3.0 or breakage >= 5.0:
            labels.append("priority:medium")

        candidates.append(
            ActivityCandidate(
                kind="signal_issue",
                key=f"signal:{platform}:{name}",
                title=f"[signal] Investigate material upstream change: {name}",
                priority=impact + min(3.0, issue_velocity / 3.0) + breakage / 10.0,
                target=name,
                body=body,
                labels=tuple(labels),
                evidence_hash=stable_hash(evidence),
            )
        )

    candidates.sort(key=lambda item: (-item.priority, item.key))
    return tuple(candidates[: max(0, limit)])


def plan_scheduler_issue(
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime,
) -> ActivityCandidate | None:
    scheduler = state.get("scheduler", {})
    policy = config.get("scheduler", {})
    multiplier = float(scheduler.get("last_catch_up_multiplier", 1.0))
    elapsed = float(scheduler.get("last_elapsed_hours", 0.0))
    min_multiplier = float(policy.get("delay_multiplier", 2.5))
    min_elapsed = float(policy.get("delay_hours", 4.0))

    if multiplier < min_multiplier or elapsed < min_elapsed:
        return None

    evidence = {
        "platform": platform,
        "multiplier": multiplier,
        "elapsed_hours": elapsed,
        "last_run_at": scheduler.get("last_run_at"),
    }
    return ActivityCandidate(
        kind="scheduler_issue",
        key=f"scheduler-delay:{platform}",
        title=f"[scheduler] Delayed {platform} radar execution",
        priority=5.0 + min(5.0, elapsed / 2.0),
        target=None,
        body=(
            "The radar required maximum catch-up pressure after a delayed "
            "scheduled wake-up.\n\n"
            f"- platform: {platform}\n"
            f"- catch-up multiplier: {multiplier:.2f}x\n"
            f"- elapsed since previous successful run: {elapsed:.2f} h\n"
            f"- last run: {scheduler.get('last_run_at')}\n\n"
            "This issue tracks scheduler reliability. It should be updated "
            "while the condition persists and closed automatically after the "
            "schedule recovers."
        ),
        labels=("activity:scheduler", "reliability"),
        evidence_hash=stable_hash(evidence),
    )


def weekly_metrics(
    state: Mapping[str, Any],
    *,
    now: datetime,
) -> dict[str, int]:
    daily = state.get("daily", {})
    start = (now - timedelta(days=6)).date()
    runs = scanned = changed = errors = 0
    included_days = 0
    for day, values in daily.items():
        try:
            parsed = datetime.fromisoformat(day).date()
        except ValueError:
            continue
        if start <= parsed <= now.date():
            included_days += 1
            runs += int(values.get("runs", 0))
            scanned += int(values.get("scanned", 0))
            changed += int(values.get("changed", 0))
            errors += int(values.get("errors", 0))
    return {
        "days": included_days,
        "runs": runs,
        "scanned": scanned,
        "changed": changed,
        "errors": errors,
    }


def weekly_release_due(
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    now: datetime,
) -> tuple[bool, dict[str, int]]:
    policy = config.get("releases", {})
    if not policy.get("enabled", True):
        return False, {}
    metrics = weekly_metrics(state, now=now)
    enough = (
        metrics["changed"] >= int(policy.get("min_changed_observations", 50))
        and metrics["runs"] >= int(policy.get("min_runs", 3))
    )
    return enough, metrics


def release_notes(
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime,
) -> str:
    metrics = weekly_metrics(state, now=now)
    signals = plan_signal_issues(state, config, platform=platform, now=now)
    top = list(signals[:5])

    lines = [
        f"# UpstreamRadar {current_cycle(now)}",
        "",
        "Evidence-backed weekly telemetry release.",
        "",
        "## Coverage",
        "",
        f"- platform: {platform}",
        f"- collection runs: {metrics['runs']}",
        f"- repositories/projects scanned: {metrics['scanned']}",
        f"- changed observations: {metrics['changed']}",
        f"- collection errors: {metrics['errors']}",
        "",
        "## Material signals",
        "",
    ]
    if top:
        for item in top:
            lines.append(
                f"- {item.target} - priority={item.priority:.2f}; "
                f"evidence={item.evidence_hash}"
            )
    else:
        lines.append("- No signal crossed the material-triage threshold.")
    lines += [
        "",
        "This release is created only when a real weekly observation threshold "
        "is reached; it is not emitted for empty or unchanged periods.",
        "",
    ]
    return "\n".join(lines)


def plan_all(
    state: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime | None = None,
) -> tuple[ActivityCandidate, ...]:
    now = now or datetime.now(UTC)
    items = list(plan_signal_issues(state, config, platform=platform, now=now))
    scheduler = plan_scheduler_issue(state, config, platform=platform, now=now)
    if scheduler is not None:
        items.append(scheduler)
    items.sort(key=lambda item: (-item.priority, item.key))
    return tuple(items)
