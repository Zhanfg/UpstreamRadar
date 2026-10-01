from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
import json
from typing import Any, Mapping


UTC = timezone.utc


@dataclass(frozen=True)
class IncidentDecision:
    action: str
    fingerprint: str
    reason: str


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).astimezone(UTC)
    except ValueError:
        return None


def evidence_fingerprint(value: Mapping[str, Any]) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return sha256(raw.encode("utf-8")).hexdigest()[:20]


def decide_incident(
    record: Mapping[str, Any] | None,
    *,
    active: bool,
    evidence: Mapping[str, Any],
    now: datetime,
    cooldown_hours: float,
) -> IncidentDecision:
    fingerprint = evidence_fingerprint(evidence)
    current = dict(record or {})
    status = str(current.get("status") or "")
    external_id = current.get("external_id")

    if active:
        if not external_id or status == "closed":
            return IncidentDecision(
                action="create",
                fingerprint=fingerprint,
                reason="active condition has no open incident",
            )

        if current.get("fingerprint") == fingerprint:
            return IncidentDecision(
                action="none",
                fingerprint=fingerprint,
                reason="evidence unchanged",
            )

        last_action = parse_time(current.get("last_action_at"))
        cooldown = timedelta(hours=max(0.0, cooldown_hours))
        if last_action is not None and now - last_action < cooldown:
            return IncidentDecision(
                action="none",
                fingerprint=fingerprint,
                reason="evidence changed but incident cooldown is active",
            )

        return IncidentDecision(
            action="update",
            fingerprint=fingerprint,
            reason="material incident evidence changed",
        )

    if external_id and status == "open":
        return IncidentDecision(
            action="close",
            fingerprint=fingerprint,
            reason="condition recovered",
        )

    return IncidentDecision(
        action="none",
        fingerprint=fingerprint,
        reason="no active incident",
    )


def security_incident_evidence(report: Mapping[str, Any]) -> dict[str, Any]:
    counts = report.get("counts", {})
    findings = [
        {
            "severity": item.get("severity"),
            "kind": item.get("kind"),
            "path": item.get("path"),
            "message": item.get("message"),
        }
        for item in report.get("findings", [])
        if item.get("severity") in {"critical", "high"}
    ]
    return {
        "critical": int(counts.get("critical", 0)),
        "high": int(counts.get("high", 0)),
        "findings": findings[:10],
    }


def benchmark_incident_evidence(report: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "median_ms": report.get("median_ms"),
        "previous_median_ms": report.get("previous_median_ms"),
        "regressed": bool(report.get("regressed")),
        "determinism_regressed": bool(
            report.get("determinism_regressed")
        ),
        "selection_hash": report.get("selection_hash"),
    }
