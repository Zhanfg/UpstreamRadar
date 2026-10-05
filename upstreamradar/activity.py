from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class ActivityEvidence:
    platform: str
    observed_at: str
    changed_count: int
    error_count: int
    coverage_score: float
    content_score: float
    top_name: str | None = None
    top_impact: float = 0.0
    top_fields: tuple[str, ...] = ()
    top_reasons: tuple[str, ...] = ()
    content_opportunities: int = 0
    fork_queue_count: int = 0


@dataclass(frozen=True)
class ActivityAction:
    kind: str
    key: str
    priority: float
    reason: str
    title: str
    body: str


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)
    except ValueError:
        return None


def recent_count(history: Sequence[Mapping[str, Any]], *, kind: str, now: datetime, hours: float) -> int:
    cutoff = now - timedelta(hours=hours)
    count = 0
    for item in history:
        if item.get('kind') != kind:
            continue
        created = parse_time(str(item.get('created_at') or ''))
        if created is not None and created >= cutoff:
            count += 1
    return count


def key_on_cooldown(history: Sequence[Mapping[str, Any]], *, kind: str, key: str, now: datetime, cooldown_hours: float) -> bool:
    cutoff = now - timedelta(hours=cooldown_hours)
    for item in reversed(history):
        if item.get('kind') != kind or item.get('key') != key:
            continue
        created = parse_time(str(item.get('created_at') or ''))
        if created is not None and created >= cutoff:
            return True
    return False


def _budget_available(history: Sequence[Mapping[str, Any]], config: Mapping[str, Any], *, kind: str, now: datetime) -> bool:
    limit = int(config.get('daily_budget', {}).get(kind, 0))
    if limit <= 0:
        return False
    return recent_count(history, kind=kind, now=now, hours=24) < limit


def _surface_enabled(config: Mapping[str, Any], platform: str, name: str) -> bool:
    return bool(config.get('surfaces', {}).get(platform, {}).get(name, False))


def plan_actions(evidence: ActivityEvidence, history: Sequence[Mapping[str, Any]], config: Mapping[str, Any], *, now: datetime | None = None) -> tuple[ActivityAction, ...]:
    now = now or datetime.now(timezone.utc)
    thresholds = config.get('thresholds', {})
    cooldowns = config.get('cooldown_hours', {})
    actions: list[ActivityAction] = []

    strong_signal = bool({'regime-shift', 'security-focus'}.intersection(evidence.top_reasons))

    if _surface_enabled(config, evidence.platform, 'issues') and evidence.top_name and (evidence.top_impact >= float(thresholds.get('impact_issue', 4.0)) or strong_signal):
        key = f'impact:{evidence.top_name}'
        if _budget_available(history, config, kind='impact_issue', now=now) and not key_on_cooldown(history, kind='impact_issue', key=key, now=now, cooldown_hours=float(cooldowns.get('impact_issue', 72))):
            fields = ', '.join(evidence.top_fields) or 'snapshot'
            actions.append(ActivityAction(
                kind='impact_issue',
                key=key,
                priority=min(1.0, evidence.top_impact / 10.0),
                reason='high semantic-impact upstream transition',
                title=f'[impact] Investigate {evidence.top_name}',
                body=(
                    'Automated evidence-triggered investigation.\n\n'
                    f'- upstream: {evidence.top_name}\n'
                    f'- semantic impact: {evidence.top_impact:.2f}\n'
                    f'- changed fields: {fields}\n'
                    f'- SKOPRÆD reasons: {", ".join(evidence.top_reasons) or "none"}\n'
                    f'- content score: {evidence.content_score:.3f}\n'
                    f'- portfolio coverage: {evidence.coverage_score:.3f}\n\n'
                    'This issue is generated from observed upstream state, not synthetic activity.'
                ),
            ))

    if _surface_enabled(config, evidence.platform, 'benchmark') and evidence.changed_count >= int(thresholds.get('benchmark_changed', 1)):
        key = f'benchmark:{now.date().isoformat()}:{now.hour // 12}'
        if _budget_available(history, config, kind='benchmark', now=now) and not key_on_cooldown(history, kind='benchmark', key=key, now=now, cooldown_hours=float(cooldowns.get('benchmark', 12))):
            actions.append(ActivityAction(
                kind='benchmark',
                key=key,
                priority=min(1.0, 0.35 + evidence.changed_count / 30.0),
                reason='real radar changes available for scheduler-quality measurement',
                title='Activity Matrix benchmark snapshot',
                body=(
                    f'changed={evidence.changed_count}\n'
                    f'errors={evidence.error_count}\n'
                    f'coverage={evidence.coverage_score:.4f}\n'
                    f'content={evidence.content_score:.4f}\n'
                    f'fork_queue={evidence.fork_queue_count}\n'
                ),
            ))

    if _surface_enabled(config, evidence.platform, 'wiki') and evidence.changed_count >= int(thresholds.get('wiki_changed', 3)) and evidence.content_score >= float(thresholds.get('wiki_content_score', 0.65)):
        key = f'wiki:{now.date().isoformat()}'
        if _budget_available(history, config, kind='wiki', now=now) and not key_on_cooldown(history, kind='wiki', key=key, now=now, cooldown_hours=float(cooldowns.get('wiki', 24))):
            top = ''
            if evidence.top_name:
                top = f'Top semantic change: {evidence.top_name} (impact={evidence.top_impact:.2f}; fields={", ".join(evidence.top_fields) or "snapshot"})\n'
            actions.append(ActivityAction(
                kind='wiki',
                key=key,
                priority=min(1.0, evidence.content_score),
                reason='daily evidence is rich enough for a durable knowledge page',
                title=f'Radar Intelligence {now.date().isoformat()}',
                body=(
                    f'# Radar Intelligence — {now.date().isoformat()}\n\n'
                    f'- changed upstreams: {evidence.changed_count}\n'
                    f'- errors: {evidence.error_count}\n'
                    f'- portfolio coverage: {evidence.coverage_score:.3f}\n'
                    f'- content score: {evidence.content_score:.3f}\n'
                    f'- content opportunities: {evidence.content_opportunities}\n'
                    f'- fork queue: {evidence.fork_queue_count}\n\n'
                    + top + '\nGenerated from real UpstreamRadar observations.'
                ),
            ))

    if _surface_enabled(config, evidence.platform, 'release') and evidence.changed_count >= int(thresholds.get('release_changed', 10)) and (evidence.top_impact >= float(thresholds.get('release_impact', 4.0)) or strong_signal):
        key = 'release:intelligence'
        if _budget_available(history, config, kind='release', now=now) and not key_on_cooldown(history, kind='release', key=key, now=now, cooldown_hours=float(cooldowns.get('release', 168))):
            tag = f'radar-{now.strftime("%Y.%m.%d")}'
            actions.append(ActivityAction(
                kind='release',
                key=key,
                priority=1.0,
                reason='weekly threshold reached with a major semantic change',
                title=f'UpstreamRadar Intelligence {now.date().isoformat()}',
                body=(
                    f'Automated evidence-backed intelligence release {tag}.\n\n'
                    f'- changed upstreams: {evidence.changed_count}\n'
                    f'- top change: {evidence.top_name} (impact={evidence.top_impact:.2f})\n'
                    f'- SKOPRÆD reasons: {", ".join(evidence.top_reasons) or "none"}\n'
                    f'- coverage: {evidence.coverage_score:.3f}\n'
                    f'- content score: {evidence.content_score:.3f}\n'
                    f'- fork queue: {evidence.fork_queue_count}\n'
                ),
            ))

    if _surface_enabled(config, evidence.platform, 'milestone') and any(item.kind == 'impact_issue' for item in actions):
        key = f'milestone:{now.strftime("%Y-%m")}'
        if _budget_available(history, config, kind='milestone', now=now) and not any(item.get('kind') == 'milestone' and item.get('key') == key for item in history):
            actions.append(ActivityAction(
                kind='milestone',
                key=key,
                priority=0.55,
                reason='monthly intelligence work has actionable impact investigations',
                title=f'Intelligence Cycle {now.strftime("%Y-%m")}',
                body='Automated monthly milestone for evidence-backed impact investigations and follow-up work.',
            ))

    actions.sort(key=lambda item: (-item.priority, item.kind, item.key))
    return tuple(actions)


def history_record(action: ActivityAction, *, status: str, created_at: str, external_id: str | None = None) -> dict[str, Any]:
    return {
        'kind': action.kind,
        'key': action.key,
        'status': status,
        'created_at': created_at,
        'external_id': external_id,
        'title': action.title,
        'reason': action.reason,
    }
