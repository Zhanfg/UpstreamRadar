from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence


UTC = timezone.utc


@dataclass(frozen=True)
class GovernanceSignal:
    key: str
    active: bool
    severity: str
    title: str
    evidence: dict[str, Any]


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def data_quality_signal(
    records: Mapping[str, Mapping[str, Any]],
    policy: Mapping[str, Any],
    *,
    now: datetime,
) -> GovernanceSignal:
    stale_hours = float(policy.get("stale_hours", 36))
    min_records = int(policy.get("min_records_for_stale_ratio", 10))
    stale_fraction_threshold = float(policy.get("stale_fraction_threshold", 0.2))
    error_threshold = int(policy.get("error_streak_threshold", 3))
    max_error_records = int(policy.get("max_error_streak_records", 1))
    max_invalid = int(policy.get("max_invalid_records", 0))
    max_window = int(policy.get("max_window_items", 48))
    limit = int(policy.get("max_reported_items", 20))

    stale: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    invalid: list[dict[str, Any]] = []

    cutoff = now - timedelta(hours=max(0.0, stale_hours))
    for name, model in records.items():
        checked = parse_time(str(model.get("last_checked_at") or ""))
        if checked is None or checked < cutoff:
            stale.append(
                {
                    "name": name,
                    "last_checked_at": model.get("last_checked_at"),
                }
            )

        error_streak = int(model.get("error_streak", 0) or 0)
        if error_streak >= error_threshold:
            errors.append(
                {
                    "name": name,
                    "error_streak": error_streak,
                    "last_error": model.get("last_error"),
                }
            )

        checks = int(model.get("checks", 0) or 0)
        successful = int(model.get("successful_checks", max(0, checks)) or 0)
        failed = int(model.get("failed_checks", max(0, checks - successful)) or 0)
        problems = []
        if checks < 0 or successful < 0 or failed < 0:
            problems.append("negative-counters")
        if successful > checks:
            problems.append("successful-checks-exceed-checks")
        if failed > checks:
            problems.append("failed-checks-exceed-checks")
        if len(model.get("change_window", []) or []) > max_window:
            problems.append("change-window-unbounded")
        if len(model.get("impact_window", []) or []) > max_window:
            problems.append("impact-window-unbounded")
        if problems:
            invalid.append({"name": name, "problems": problems})

    total = len(records)
    stale_fraction = len(stale) / total if total else 0.0
    stale_active = total >= min_records and stale_fraction >= stale_fraction_threshold
    active = (
        stale_active
        or len(errors) > max_error_records
        or len(invalid) > max_invalid
    )

    severity = "high" if invalid or len(errors) > max_error_records else "medium"
    return GovernanceSignal(
        key="data-quality",
        active=active,
        severity=severity,
        title="[governance] Radar state data-quality regression",
        evidence={
            "record_count": total,
            "stale_count": len(stale),
            "stale_fraction": round(stale_fraction, 6),
            "stale_threshold_hours": stale_hours,
            "error_streak_count": len(errors),
            "invalid_count": len(invalid),
            "stale": stale[:limit],
            "error_streaks": errors[:limit],
            "invalid": invalid[:limit],
        },
    )


def state_growth_signal(
    files: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> GovernanceSignal:
    per_file = int(policy.get("per_file_bytes", 2 * 1024 * 1024))
    total_limit = int(policy.get("total_bytes", 12 * 1024 * 1024))
    limit = int(policy.get("max_reported_items", 20))

    normalized = [
        {
            "path": str(item.get("path") or ""),
            "bytes": int(item.get("bytes") or 0),
        }
        for item in files
    ]
    oversized = [item for item in normalized if item["bytes"] > per_file]
    oversized.sort(key=lambda item: (-item["bytes"], item["path"]))
    total = sum(item["bytes"] for item in normalized)
    active = bool(oversized) or total > total_limit

    return GovernanceSignal(
        key="state-growth",
        active=active,
        severity="medium",
        title="[governance] Radar state storage growth",
        evidence={
            "file_count": len(normalized),
            "total_bytes": total,
            "total_limit_bytes": total_limit,
            "per_file_limit_bytes": per_file,
            "oversized_count": len(oversized),
            "oversized": oversized[:limit],
            "largest": sorted(
                normalized,
                key=lambda item: (-item["bytes"], item["path"]),
            )[:limit],
        },
    )


def parity_signal(
    entries: Sequence[Mapping[str, Any]],
    policy: Mapping[str, Any],
) -> GovernanceSignal:
    limit = int(policy.get("max_reported_items", 20))
    max_mismatches = int(policy.get("max_mismatches", 0))
    mismatches = [
        {
            "path": str(item.get("path") or ""),
            "local_length": int(item.get("local_length") or 0),
            "remote_length": int(item.get("remote_length") or 0),
            "status": str(item.get("status") or "mismatch"),
        }
        for item in entries
        if not bool(item.get("same"))
    ]
    mismatches.sort(key=lambda item: item["path"])
    return GovernanceSignal(
        key="cross-platform-parity",
        active=len(mismatches) > max_mismatches,
        severity="high",
        title="[governance] GitHub/GitLab shared-core drift",
        evidence={
            "checked_count": len(entries),
            "mismatch_count": len(mismatches),
            "max_mismatches": max_mismatches,
            "mismatches": mismatches[:limit],
        },
    )


def governance_summary(signals: Sequence[GovernanceSignal]) -> dict[str, Any]:
    return {
        "active_count": sum(int(signal.active) for signal in signals),
        "signals": [
            {
                "key": signal.key,
                "active": signal.active,
                "severity": signal.severity,
                "title": signal.title,
                "evidence": signal.evidence,
            }
            for signal in signals
        ],
    }
