from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ForkPlan:
    platform: str
    full_name: str
    source_id: str
    category: str
    score: float
    destination: str
    collection: str


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def resolve_destination(
    config: Mapping[str, Any],
    *,
    platform: str,
    personal_namespace: str | None = None,
) -> str | None:
    destinations = config.get("destinations", {})
    if platform == "github":
        configured = destinations.get("github_organization")
    elif platform == "gitlab":
        configured = destinations.get("gitlab_namespace_path")
    else:
        raise ValueError(f"unsupported platform: {platform}")

    if configured:
        return str(configured)

    if destinations.get("personal_fallback") and personal_namespace:
        return personal_namespace

    return None


def fork_capacity(
    history: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime | None = None,
) -> tuple[int, int]:
    now = now or datetime.now(timezone.utc)
    policy = config.get("fork_policy", {})
    daily_limit = int(policy.get("max_forks_per_day_per_platform", 1))
    weekly_limit = int(policy.get("max_forks_per_week_per_platform", 5))

    day_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)
    recent = [
        item
        for item in history
        if item.get("platform") == platform
        and item.get("status") == "forked"
        and _parse_time(item.get("created_at")) is not None
    ]
    daily = sum(_parse_time(item.get("created_at")) >= day_start for item in recent)
    weekly = sum(_parse_time(item.get("created_at")) >= week_start for item in recent)

    return max(0, daily_limit - daily), max(0, weekly_limit - weekly)


def select_fork_batch(
    queue: Sequence[Mapping[str, Any]],
    history: Sequence[Mapping[str, Any]],
    config: Mapping[str, Any],
    *,
    platform: str,
    personal_namespace: str | None = None,
    now: datetime | None = None,
) -> tuple[ForkPlan, ...]:
    destination = resolve_destination(
        config,
        platform=platform,
        personal_namespace=personal_namespace,
    )
    if not destination:
        return ()

    daily, weekly = fork_capacity(
        history,
        config,
        platform=platform,
        now=now,
    )
    limit = min(daily, weekly)
    if limit <= 0:
        return ()

    already = {
        str(item.get("full_name", "")).lower()
        for item in history
        if item.get("status") in {"forked", "pending"}
    }
    collections = config.get("destinations", {}).get("category_collections", {})

    plans = []
    for item in sorted(
        queue,
        key=lambda row: (-float(row.get("score", 0.0)), str(row.get("full_name", ""))),
    ):
        if item.get("platform") != platform:
            continue
        full_name = str(item.get("full_name", ""))
        if not full_name or full_name.lower() in already:
            continue
        if not item.get("auto_fork_eligible"):
            continue
        category = str(item.get("category") or "other")
        plans.append(
            ForkPlan(
                platform=platform,
                full_name=full_name,
                source_id=str(item.get("source_id") or full_name),
                category=category,
                score=float(item.get("score", 0.0)),
                destination=destination,
                collection=str(collections.get(category, category)),
            )
        )
        if len(plans) >= limit:
            break

    return tuple(plans)
