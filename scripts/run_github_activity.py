from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from upstreamradar.activity import ActivityAction, ActivityEvidence, history_record, plan_actions


API = 'https://api.github.com'
TOKEN = os.environ.get('UPSTREAMRADAR_PAT', '')
REPOSITORY = os.environ.get('GITHUB_REPOSITORY', 'Zhanfg/UpstreamRadar')
CONFIG_PATH = Path('config/activity_matrix.json')
HISTORY_PATH = Path('state/activity_github.json')
PLAN_PATH = Path('.activity/github_plan.json')
WIKI_BODY_PATH = Path('.activity/github_wiki.md')
WIKI_SLUG_PATH = Path('.activity/github_wiki_slug.txt')


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding='utf-8'))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def request(path: str, method: str = 'GET', payload=None):
    headers = {
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'UpstreamRadar-Activity-Matrix',
        'X-GitHub-Api-Version': '2022-11-28',
    }
    if TOKEN:
        headers['Authorization'] = f'Bearer {TOKEN}'
    data = None
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = Request(f'{API}{path}', method=method, headers=headers, data=data)
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode('utf-8')
        return json.loads(raw) if raw else None


def latest_run() -> dict:
    paths = sorted(Path('data/runs').glob('*/*.json'))
    if not paths:
        raise RuntimeError('no GitHub radar run journal found')
    return load_json(paths[-1], {})


def fork_queue_count() -> int:
    queue = load_json(Path('discovery/github_fork_queue.json'), [])
    return len(queue) if isinstance(queue, list) else 0


def evidence_from_run(run: dict) -> ActivityEvidence:
    details = list(run.get('changed_details') or [])
    by_name = {str(item.get('full_name')): item for item in details}
    content = list(run.get('content_plan') or [])

    top_name = None
    top_reasons: tuple[str, ...] = ()
    if content:
        preferred = sorted(
            content,
            key=lambda item: (
                -int(bool({'regime-shift', 'security-focus'}.intersection(item.get('reasons') or []))),
                -float(item.get('priority', 0.0)),
                str(item.get('name') or ''),
            ),
        )[0]
        top_name = str(preferred.get('name') or '') or None
        top_reasons = tuple(str(value) for value in preferred.get('reasons') or [])

    if top_name is None and details:
        top_name = str(details[0].get('full_name') or '') or None

    top_detail = by_name.get(top_name or '', {})
    top_impact = float(top_detail.get('semantic_impact', 0.0))
    top_fields = tuple(str(value) for value in top_detail.get('fields') or [])

    return ActivityEvidence(
        platform='github',
        observed_at=str(run.get('observed_at') or ''),
        changed_count=len(run.get('changed') or []),
        error_count=len(run.get('errors') or []),
        coverage_score=float(run.get('coverage_score', 0.0)),
        content_score=float(run.get('content_score', 0.0)),
        top_name=top_name,
        top_impact=top_impact,
        top_fields=top_fields,
        top_reasons=top_reasons,
        content_opportunities=len(content),
        fork_queue_count=fork_queue_count(),
    )


def open_issues() -> list[dict]:
    return request(f'/repos/{REPOSITORY}/issues?state=open&per_page=100') or []


def execute_issue(action: ActivityAction, now_iso: str) -> dict:
    existing = next(
        (item for item in open_issues() if 'pull_request' not in item and item.get('title') == action.title),
        None,
    )
    if existing is not None:
        note = request(
            f'/repos/{REPOSITORY}/issues/{existing["number"]}/comments',
            method='POST',
            payload={'body': action.body + '\n\nActivity Matrix follow-up observation.'},
        )
        return history_record(
            ActivityAction(
                kind='issue_note', key=action.key, priority=action.priority,
                reason=action.reason, title=action.title, body=action.body,
            ),
            status='commented',
            created_at=now_iso,
            external_id=str(note.get('id')),
        )

    created = request(
        f'/repos/{REPOSITORY}/issues',
        method='POST',
        payload={'title': action.title, 'body': action.body},
    )
    return history_record(action, status='created', created_at=now_iso, external_id=str(created.get('number')))


def execute_release(action: ActivityAction, now: datetime, now_iso: str) -> dict:
    tag = f'radar-{now.strftime("%Y.%m.%d")}'
    existing = request(f'/repos/{REPOSITORY}/releases?per_page=100') or []
    for release in existing:
        if release.get('tag_name') == tag:
            return history_record(action, status='exists', created_at=now_iso, external_id=str(release.get('id')))
    created = request(
        f'/repos/{REPOSITORY}/releases',
        method='POST',
        payload={
            'tag_name': tag,
            'target_commitish': 'main',
            'name': action.title,
            'body': action.body,
            'draft': False,
            'prerelease': False,
        },
    )
    return history_record(action, status='created', created_at=now_iso, external_id=str(created.get('id')))


def execute_milestone(action: ActivityAction, now_iso: str) -> dict:
    milestones = request(f'/repos/{REPOSITORY}/milestones?state=all&per_page=100') or []
    for item in milestones:
        if item.get('title') == action.title:
            return history_record(action, status='exists', created_at=now_iso, external_id=str(item.get('number')))
    created = request(
        f'/repos/{REPOSITORY}/milestones',
        method='POST',
        payload={'title': action.title, 'description': action.body},
    )
    return history_record(action, status='created', created_at=now_iso, external_id=str(created.get('number')))


def execute_benchmark(action: ActivityAction, evidence: ActivityEvidence, now: datetime, now_iso: str) -> dict:
    path = Path('reports/activity/benchmarks/github') / f'{now.strftime("%Y%m%d-%H%M%S")}.json'
    write_json(path, {'evidence': asdict(evidence), 'action': asdict(action), 'created_at': now_iso})
    return history_record(action, status='recorded', created_at=now_iso, external_id=str(path))


def execute_wiki(action: ActivityAction, now: datetime, now_iso: str) -> dict:
    WIKI_BODY_PATH.parent.mkdir(parents=True, exist_ok=True)
    WIKI_BODY_PATH.write_text(action.body + '\n', encoding='utf-8')
    slug = f'Radar-Intelligence-{now.strftime("%Y-%m-%d")}'
    WIKI_SLUG_PATH.write_text(slug + '\n', encoding='utf-8')
    return history_record(action, status='prepared', created_at=now_iso, external_id=slug)


def render_report(evidence: ActivityEvidence, actions: list[ActivityAction], records: list[dict], now: datetime) -> str:
    lines = [
        f'# Activity Matrix — GitHub — {now.date().isoformat()}',
        '',
        f'- observed at: {evidence.observed_at}',
        f'- changed upstreams: **{evidence.changed_count}**',
        f'- errors: **{evidence.error_count}**',
        f'- coverage: **{evidence.coverage_score:.3f}**',
        f'- content score: **{evidence.content_score:.3f}**',
        f'- fork queue: **{evidence.fork_queue_count}**',
        '',
        '## Planned surfaces',
        '',
    ]
    if actions:
        for action in actions:
            lines.append(f'- **{action.kind}** — {action.reason}')
    else:
        lines.append('- No evidence-backed cross-surface action in this cycle.')
    lines += ['', '## Execution', '']
    for record in records:
        lines.append(f'- **{record.get("kind")}** — {record.get("status")} — {record.get("external_id") or "n/a"}')
    return '\n'.join(lines) + '\n'


def main() -> int:
    if not TOKEN:
        print('ACTIVITY=SKIP UPSTREAMRADAR_PAT missing')
        return 0

    config = load_json(CONFIG_PATH, {})
    history = load_json(HISTORY_PATH, [])
    run = latest_run()
    evidence = evidence_from_run(run)
    now = datetime.now(timezone.utc)
    now_iso = now.replace(microsecond=0).isoformat()
    actions = list(plan_actions(evidence, history, config, now=now))
    write_json(PLAN_PATH, {'evidence': asdict(evidence), 'actions': [asdict(item) for item in actions]})

    records = []
    for action in actions:
        try:
            if action.kind == 'impact_issue':
                record = execute_issue(action, now_iso)
            elif action.kind == 'release':
                record = execute_release(action, now, now_iso)
            elif action.kind == 'milestone':
                record = execute_milestone(action, now_iso)
            elif action.kind == 'benchmark':
                record = execute_benchmark(action, evidence, now, now_iso)
            elif action.kind == 'wiki':
                record = execute_wiki(action, now, now_iso)
            else:
                continue
            records.append(record)
            history.append(record)
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            failed = history_record(action, status=f'error:{type(exc).__name__}', created_at=now_iso)
            records.append(failed)
            history.append(failed)

    history = history[-500:]
    write_json(HISTORY_PATH, history)
    report_path = Path('reports/activity/github') / f'{now.date().isoformat()}.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_report(evidence, actions, records, now), encoding='utf-8')

    print(
        f'ACTIVITY=PASS planned={len(actions)} executed={len(records)} '
        f'changed={evidence.changed_count} content={evidence.content_score:.3f}'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
