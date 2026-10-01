from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping, Sequence


UTC = timezone.utc


@dataclass(frozen=True)
class DownstreamPlan:
    key: str
    source_platform: str
    upstream: str
    downstream: str
    semantic_impact: float
    fields: tuple[str, ...]
    reasons: tuple[str, ...]
    checklist: tuple[str, ...]
    priority: float
    evidence_hash: str
    title: str
    body: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["fields"] = list(self.fields)
        data["reasons"] = list(self.reasons)
        data["checklist"] = list(self.checklist)
        return data


@dataclass(frozen=True)
class ActionDecision:
    action: str
    reason: str


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def stable_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return sha256(raw.encode("utf-8")).hexdigest()[:20]


def _detail_name(detail: Mapping[str, Any]) -> str:
    return str(detail.get("full_name") or detail.get("project") or "")


def _content_reasons(run: Mapping[str, Any]) -> dict[str, tuple[str, ...]]:
    result: dict[str, tuple[str, ...]] = {}
    for item in run.get("content_plan", []) or []:
        name = str(item.get("name") or "")
        if not name:
            continue
        result[name] = tuple(str(value) for value in item.get("reasons", []) or [])
    return result


def _target_index(config: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    result: dict[str, list[Mapping[str, Any]]] = {}
    for target in config.get("targets", []) or []:
        for source in target.get("sources", []) or []:
            result.setdefault(str(source), []).append(target)
    return result


def plan_downstream_impacts(
    run: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
) -> tuple[DownstreamPlan, ...]:
    policy = config.get("policy", {})
    min_impact = float(policy.get("min_semantic_impact", 6.0))
    critical = float(policy.get("critical_impact", 8.0))
    max_plans = int(policy.get("max_plans_per_run", 10))
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

    reasons_by_name = _content_reasons(run)
    targets_by_source = _target_index(config)
    observed_at = str(run.get("observed_at") or "")
    plans: list[DownstreamPlan] = []

    for detail in run.get("changed_details", []) or []:
        upstream = _detail_name(detail)
        if not upstream or upstream not in targets_by_source:
            continue

        impact = float(detail.get("semantic_impact", 0.0) or 0.0)
        fields = tuple(str(value) for value in detail.get("fields", []) or [])
        if impact < min_impact:
            continue
        if impact < critical and not important.intersection(fields):
            continue

        reasons = reasons_by_name.get(upstream, ())
        for target in targets_by_source[upstream]:
            downstream = str(target.get("repo") or "")
            if not downstream:
                continue
            checklist = tuple(str(value) for value in target.get("checklist", []) or [])
            evidence = {
                "source_platform": platform,
                "upstream": upstream,
                "downstream": downstream,
                "semantic_impact": round(impact, 4),
                "fields": fields,
                "reasons": reasons,
            }
            evidence_hash = stable_hash(evidence)
            priority = min(
                1.0,
                impact / 10.0
                + 0.08 * int("regime-shift" in reasons)
                + 0.08 * int("security-focus" in reasons),
            )
            source_url = (
                f"https://github.com/{upstream}"
                if platform == "github"
                else f"https://gitlab.com/{upstream}"
            )
            checklist_text = "\n".join(
                f"- [ ] {item}"
                for item in checklist
            ) or "- [ ] review downstream compatibility"

            title = f"[upstream-impact] Assess {upstream} change"
            body = (
                "UpstreamRadar detected a material upstream change that is "
                "explicitly mapped to this downstream project.\n\n"
                f"- upstream: {upstream}\n"
                f"- source platform: {platform}\n"
                f"- upstream URL: {source_url}\n"
                f"- observed at: {observed_at}\n"
                f"- semantic impact: {impact:.2f}\n"
                f"- changed fields: {', '.join(fields) or 'snapshot'}\n"
                f"- HARMONY reasons: {', '.join(reasons) or 'none'}\n"
                f"- evidence hash: {evidence_hash}\n\n"
                "Suggested validation:\n\n"
                f"{checklist_text}\n\n"
                "This task is generated only from an explicit upstream-to-"
                "downstream mapping and measured semantic impact."
            )
            plans.append(
                DownstreamPlan(
                    key=f"{platform}:{upstream}->{downstream}",
                    source_platform=platform,
                    upstream=upstream,
                    downstream=downstream,
                    semantic_impact=impact,
                    fields=fields,
                    reasons=reasons,
                    checklist=checklist,
                    priority=priority,
                    evidence_hash=evidence_hash,
                    title=title,
                    body=body,
                )
            )

    plans.sort(
        key=lambda item: (
            -item.priority,
            -item.semantic_impact,
            item.downstream,
            item.upstream,
        )
    )
    return tuple(plans[: max(0, max_plans)])


def decide_action(
    record: Mapping[str, Any] | None,
    plan: DownstreamPlan,
    policy: Mapping[str, Any],
    *,
    now: datetime,
) -> ActionDecision:
    if record is None:
        return ActionDecision("create", "first material mapped impact")

    if str(record.get("evidence_hash") or "") == plan.evidence_hash:
        return ActionDecision("none", "evidence unchanged")

    last_action = parse_time(str(record.get("last_action_at") or ""))
    update_cooldown = timedelta(
        hours=float(policy.get("update_cooldown_hours", 24))
    )
    create_cooldown = timedelta(
        hours=float(policy.get("create_cooldown_hours", 168))
    )
    elapsed = now - last_action if last_action is not None else None

    if str(record.get("status") or "open") == "open":
        if elapsed is None or elapsed >= update_cooldown:
            return ActionDecision("update", "new evidence for open downstream task")
        return ActionDecision("none", "update cooldown active")

    if elapsed is None or elapsed >= create_cooldown:
        return ActionDecision("create", "new evidence after closed-task cooldown")
    return ActionDecision("none", "create cooldown active")


def recent_action_count(
    history: Sequence[Mapping[str, Any]],
    *,
    now: datetime,
    hours: float = 24,
) -> int:
    cutoff = now - timedelta(hours=hours)
    total = 0
    for item in history:
        created = parse_time(str(item.get("created_at") or ""))
        if created is not None and created >= cutoff:
            total += 1
    return total
