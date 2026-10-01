from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
import re
from typing import Any, Mapping, Sequence


UTC = timezone.utc
USES_RE = re.compile(r"(?m)^\s*-?\s*uses:\s*([^\s#]+)\s*$")


@dataclass(frozen=True)
class MaintenanceSignal:
    key: str
    active: bool
    severity: str
    title: str
    evidence: dict[str, Any]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(UTC)
    except ValueError:
        return None


def ci_reliability(
    runs: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> MaintenanceSignal:
    completed = [
        item
        for item in runs
        if str(item.get("status")) == "completed"
        and str(item.get("conclusion") or "") not in {"", "cancelled", "skipped"}
    ]
    window = max(1, int(policy.get("window_runs", 30)))
    completed = completed[:window]
    failures = [
        item
        for item in completed
        if str(item.get("conclusion")) in {"failure", "timed_out", "action_required"}
    ]
    denominator = len(completed)
    failure_rate = len(failures) / denominator if denominator else 0.0

    consecutive = 0
    for item in completed:
        if str(item.get("conclusion")) in {"failure", "timed_out", "action_required"}:
            consecutive += 1
        else:
            break

    min_runs = int(policy.get("min_completed_runs", 10))
    rate_threshold = float(policy.get("failure_rate_threshold", 0.25))
    streak_threshold = int(policy.get("consecutive_failure_threshold", 3))
    active = (
        denominator >= min_runs
        and (
            failure_rate >= rate_threshold
            or consecutive >= streak_threshold
        )
    )

    return MaintenanceSignal(
        key="ci-reliability",
        active=active,
        severity="high" if consecutive >= streak_threshold else "medium",
        title="[ci] Workflow reliability regression",
        evidence={
            "completed_runs": denominator,
            "failure_count": len(failures),
            "failure_rate": round(failure_rate, 6),
            "consecutive_failures": consecutive,
            "failure_run_ids": [
                item.get("id")
                for item in failures[:10]
            ],
        },
    )


def fork_sync_signal(
    comparisons: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> MaintenanceSignal:
    threshold = int(policy.get("behind_commit_threshold", 20))
    limit = int(policy.get("max_reported_forks", 10))
    behind = []
    for item in comparisons:
        count = int(item.get("behind_by") or 0)
        if count < threshold:
            continue
        behind.append(
            {
                "fork": item.get("fork"),
                "upstream": item.get("upstream"),
                "branch": item.get("branch"),
                "behind_by": count,
                "ahead_by": int(item.get("ahead_by") or 0),
                "status": item.get("status"),
            }
        )

    behind.sort(
        key=lambda item: (
            -int(item.get("behind_by") or 0),
            str(item.get("fork") or ""),
        )
    )
    return MaintenanceSignal(
        key="fork-sync",
        active=bool(behind),
        severity="medium",
        title="[fork] Discovery forks behind upstream",
        evidence={
            "threshold": threshold,
            "affected_count": len(behind),
            "forks": behind[:limit],
        },
    )


def stale_work_signal(
    items: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    now: datetime,
) -> MaintenanceSignal:
    issue_days = float(policy.get("issue_days", 14))
    pr_days = float(policy.get("pull_request_days", 7))
    threshold = int(policy.get("incident_count_threshold", 3))
    limit = int(policy.get("max_reported_items", 10))
    stale = []

    for item in items:
        if str(item.get("state") or "").lower() not in {"open", "opened"}:
            continue
        kind = "pull_request" if bool(item.get("is_pull_request")) else "issue"
        updated = parse_time(
            str(item.get("updated_at") or item.get("created_at") or "")
        )
        if updated is None:
            continue
        age_days = (now - updated).total_seconds() / 86400.0
        limit_days = pr_days if kind == "pull_request" else issue_days
        if age_days < limit_days:
            continue
        stale.append(
            {
                "kind": kind,
                "id": item.get("id") or item.get("number") or item.get("iid"),
                "title": item.get("title"),
                "updated_at": updated.isoformat(),
                "age_days": round(age_days, 2),
                "url": item.get("url") or item.get("web_url"),
            }
        )

    stale.sort(
        key=lambda item: (
            -float(item.get("age_days") or 0.0),
            str(item.get("title") or ""),
        )
    )
    return MaintenanceSignal(
        key="stale-work",
        active=len(stale) >= threshold,
        severity="low" if len(stale) < threshold * 2 else "medium",
        title="[maintenance] Stale engineering work items",
        evidence={
            "threshold": threshold,
            "stale_count": len(stale),
            "items": stale[:limit],
        },
    )


def action_reference_findings(
    root: Path,
    policy: Mapping[str, Any],
) -> list[dict[str, Any]]:
    forbidden = {
        str(value)
        for value in policy.get("forbid_floating", ["main", "master", "HEAD"])
    }
    limit = int(policy.get("max_reported_items", 20))
    findings = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return findings

    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        for match in USES_RE.finditer(text):
            value = match.group(1).strip()
            if value.startswith("./") or "@" not in value:
                continue
            action, ref = value.rsplit("@", 1)
            if ref not in forbidden:
                continue
            findings.append(
                {
                    "path": str(path),
                    "action": action,
                    "ref": ref,
                    "message": "third-party action uses a floating branch reference",
                }
            )
            if len(findings) >= limit:
                return findings
    return findings


def workflow_reference_signal(
    root: Path,
    policy: Mapping[str, Any],
) -> MaintenanceSignal:
    findings = action_reference_findings(root, policy)
    return MaintenanceSignal(
        key="workflow-refs",
        active=bool(findings),
        severity="high",
        title="[maintenance] Floating workflow action references",
        evidence={
            "finding_count": len(findings),
            "findings": findings,
        },
    )


def maintenance_summary(
    *,
    ci: MaintenanceSignal | None = None,
    forks: MaintenanceSignal | None = None,
    stale_work: MaintenanceSignal | None = None,
    workflow_refs: MaintenanceSignal | None = None,
) -> dict[str, Any]:
    signals = [
        item
        for item in (ci, forks, stale_work, workflow_refs)
        if item is not None
    ]
    return {
        "active_count": sum(int(item.active) for item in signals),
        "signals": [
            {
                "key": item.key,
                "active": item.active,
                "severity": item.severity,
                "title": item.title,
                "evidence": item.evidence,
            }
            for item in signals
        ],
    }
