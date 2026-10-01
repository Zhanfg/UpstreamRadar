from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from upstreamradar.activity import (
    cycle_title,
    plan_all,
    release_notes,
    release_tag,
    weekly_release_due,
)


UTC = timezone.utc
API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_TOKEN", "")
MODEL_PATH = Path("state/model.json")
CONFIG_PATH = Path("config/activity_fabric.json")
STATE_PATH = Path("state/activity_github.json")
REPORT_PATH = Path("reports/activity/github.md")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)
    except ValueError:
        return None


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def request(path: str, method: str = "GET", payload=None, *, allow_404=False):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "UpstreamRadar-Activity-Fabric",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{API}{path}", method=method, headers=headers, data=data)
    try:
        with urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        raise


def ensure_label(name: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    current = request(
        f"/repos/{owner}/{repo}/labels/{quote(name, safe='')}",
        allow_404=True,
    )
    if current is not None:
        return
    palette = {
        "activity:signal": "8250df",
        "activity:scheduler": "d93f0b",
        "triage": "fbca04",
        "reliability": "1d76db",
        "priority:high": "b60205",
        "priority:medium": "d4c5f9",
    }
    request(
        f"/repos/{owner}/{repo}/labels",
        method="POST",
        payload={"name": name, "color": palette.get(name, "6f42c1")},
    )


def ensure_milestone(title: str):
    owner, repo = REPOSITORY.split("/", 1)
    items = request(f"/repos/{owner}/{repo}/milestones?state=all&per_page=100") or []
    for item in items:
        if item.get("title") == title:
            return item
    return request(
        f"/repos/{owner}/{repo}/milestones",
        method="POST",
        payload={
            "title": title,
            "description": (
                "Evidence-backed UpstreamRadar engineering cycle. "
                "Issues are added only when telemetry crosses configured thresholds."
            ),
        },
    )


def create_issue(candidate, milestone_number: int | None):
    owner, repo = REPOSITORY.split("/", 1)
    for label in candidate.labels:
        ensure_label(label)
    payload = {
        "title": candidate.title,
        "body": candidate.body,
        "labels": list(candidate.labels),
    }
    if milestone_number is not None:
        payload["milestone"] = milestone_number
    return request(f"/repos/{owner}/{repo}/issues", method="POST", payload=payload)


def comment_issue(number: int, body: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}/comments",
        method="POST",
        payload={"body": body},
    )


def update_issue_state(number: int, state: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}",
        method="PATCH",
        payload={"state": state},
    )


def fetch_issue(number: int):
    owner, repo = REPOSITORY.split("/", 1)
    return request(f"/repos/{owner}/{repo}/issues/{number}", allow_404=True)


def ensure_release(model: dict, config: dict, now: datetime):
    due, metrics = weekly_release_due(model, config, now=now)
    if not due:
        return None

    tag = release_tag(now, config)
    owner, repo = REPOSITORY.split("/", 1)
    existing = request(
        f"/repos/{owner}/{repo}/releases/tags/{quote(tag, safe='')}",
        allow_404=True,
    )
    if existing is not None:
        return None

    body = release_notes(model, config, platform="github", now=now)
    created = request(
        f"/repos/{owner}/{repo}/releases",
        method="POST",
        payload={
            "tag_name": tag,
            "target_commitish": "main",
            "name": f"UpstreamRadar {tag}",
            "body": body,
            "draft": False,
            "prerelease": False,
        },
    )
    return {
        "tag": tag,
        "url": created.get("html_url"),
        "metrics": metrics,
    }


def _actions_last_day(history: list[dict], now: datetime, kind: str) -> int:
    cutoff = now - timedelta(hours=24)
    total = 0
    for item in history:
        if item.get("kind") != kind:
            continue
        when = parse_time(item.get("at"))
        if when is not None and when >= cutoff:
            total += 1
    return total


def render_report(state: dict, active, release_info, now: datetime) -> str:
    lines = [
        "# GitHub Activity Fabric",
        "",
        f"- reconciled at: {iso(now)}",
        f"- active planned activities: **{len(active)}**",
        f"- tracked issue lifecycles: **{len(state.get('items', {}))}**",
        f"- recorded platform actions: **{len(state.get('history', []))}**",
        "",
        "## Active evidence-backed activities",
        "",
    ]
    if active:
        for item in active:
            record = state.get("items", {}).get(item.key, {})
            lines.append(
                f"- **{item.kind}** — {item.title}; "
                f"priority={item.priority:.2f}; issue={record.get('issue_number', '-')}"
            )
    else:
        lines.append("- No current signal crossed an activity threshold.")

    lines += ["", "## Weekly release", ""]
    if release_info:
        lines.append(
            f"- created **{release_info['tag']}** from real weekly telemetry "
            f"({release_info['metrics']['changed']} changed observations)"
        )
    else:
        lines.append("- No new weekly release was required in this reconciliation.")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    if not TOKEN:
        print("ACTIVITY=SKIP UPSTREAMRADAR_TOKEN is not configured")
        return 0

    now = now_utc()
    model = load(MODEL_PATH, {})
    config = load(CONFIG_PATH, {})
    state = load(
        STATE_PATH,
        {
            "version": 1,
            "items": {},
            "history": [],
        },
    )
    items = state.setdefault("items", {})
    history = state.setdefault("history", [])
    planned = plan_all(model, config, platform="github", now=now)
    active_keys = {item.key for item in planned}

    caps = config.get("activity_caps", {})
    new_cap = int(caps.get("new_issues_per_day", 3))
    update_cap = int(caps.get("issue_updates_per_day", 6))
    new_used = _actions_last_day(history, now, "issue_created")
    update_used = _actions_last_day(history, now, "issue_updated")
    cooldown = timedelta(
        hours=float(config.get("signals", {}).get("update_cooldown_hours", 12))
    )
    resolve_after = timedelta(
        hours=float(config.get("signals", {}).get("resolve_after_hours", 24))
    )
    milestone = None
    milestone_number = None
    actions_taken = 0

    for candidate in planned:
        record = items.get(candidate.key)
        issue_number = record.get("issue_number") if record else None

        if issue_number is None:
            if new_used >= new_cap:
                continue
            if milestone is None and config.get("milestones", {}).get("enabled", True):
                milestone = ensure_milestone(cycle_title(now, config))
                milestone_number = milestone.get("number")
            issue = create_issue(candidate, milestone_number)
            record = {
                    "issue_number": issue["number"],
                    "issue_url": issue.get("html_url"),
                    "evidence_hash": candidate.evidence_hash,
                    "last_action_at": iso(now),
                    "status": "open",
                }
            items[candidate.key] = record
            history.append(
                {
                    "kind": "issue_created",
                    "key": candidate.key,
                    "at": iso(now),
                    "url": issue.get("html_url"),
                }
            )
            new_used += 1
            actions_taken += 1
            continue

        issue = fetch_issue(int(issue_number))
        if issue is None:
            record.pop("issue_number", None)
            continue

        previous_action = parse_time(record.get("last_action_at"))
        changed = record.get("evidence_hash") != candidate.evidence_hash
        cooled = previous_action is None or now - previous_action >= cooldown

        if issue.get("state") == "closed" and changed and cooled and update_used < update_cap:
            update_issue_state(int(issue_number), "open")
            comment_issue(
                int(issue_number),
                "Signal became material again with new evidence.\n\n"
                f"Evidence hash: {candidate.evidence_hash}\n\n{candidate.body}",
            )
            record["status"] = "open"
            record["last_action_at"] = iso(now)
            record["evidence_hash"] = candidate.evidence_hash
            history.append(
                {
                    "kind": "issue_updated",
                    "key": candidate.key,
                    "at": iso(now),
                    "action": "reopened",
                }
            )
            update_used += 1
            actions_taken += 1
        elif issue.get("state") == "open" and changed and cooled and update_used < update_cap:
            comment_issue(
                int(issue_number),
                "New telemetry changed the evidence for this investigation.\n\n"
                f"Evidence hash: {candidate.evidence_hash}\n\n{candidate.body}",
            )
            record["last_action_at"] = iso(now)
            record["evidence_hash"] = candidate.evidence_hash
            history.append(
                {
                    "kind": "issue_updated",
                    "key": candidate.key,
                    "at": iso(now),
                    "action": "evidence_comment",
                }
            )
            update_used += 1
            actions_taken += 1

    for key, record in list(items.items()):
        if key in active_keys:
            continue
        issue_number = record.get("issue_number")
        last_action = parse_time(record.get("last_action_at"))
        if issue_number is None or last_action is None or now - last_action < resolve_after:
            continue
        issue = fetch_issue(int(issue_number))
        if issue and issue.get("state") == "open" and update_used < update_cap:
            comment_issue(
                int(issue_number),
                "Activity Fabric recovery: the triggering telemetry has remained "
                "below the configured threshold for the recovery window. "
                "Closing this investigation automatically.",
            )
            update_issue_state(int(issue_number), "closed")
            record["status"] = "closed"
            record["last_action_at"] = iso(now)
            history.append(
                {
                    "kind": "issue_updated",
                    "key": key,
                    "at": iso(now),
                    "action": "auto_closed",
                }
            )
            update_used += 1
            actions_taken += 1

    release_info = ensure_release(model, config, now)
    if release_info:
        history.append(
            {
                "kind": "release_created",
                "key": release_info["tag"],
                "at": iso(now),
                "url": release_info["url"],
            }
        )
        actions_taken += 1

    if actions_taken > 0:
        state["last_reconciled_at"] = iso(now)
        state["history"] = history[-300:]
        save(STATE_PATH, state)
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            render_report(state, planned, release_info, now),
            encoding="utf-8",
        )
    print(
        f"ACTIVITY=PASS planned={len(planned)} actions={actions_taken} "
        f"tracked={len(items)} release={bool(release_info)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
