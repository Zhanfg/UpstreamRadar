from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from upstreamradar.health import decide_incident
from upstreamradar.maintenance import (
    ci_reliability,
    fork_sync_signal,
    maintenance_summary,
    stale_work_signal,
    workflow_reference_signal,
)


UTC = timezone.utc
API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_PAT", "")
CONFIG_PATH = Path("config/activity_matrix.json")
STATE_PATH = Path("state/maintenance_github.json")
FORK_HISTORY_PATH = Path("state/forks_github.json")


def now_utc() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def request(path: str, method: str = "GET", payload=None, *, allow_404=False):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "UpstreamRadar-Maintenance-Intelligence",
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


def recent_runs(limit: int) -> list[dict]:
    owner, repo = REPOSITORY.split("/", 1)
    response = request(
        f"/repos/{owner}/{repo}/actions/runs?per_page={max(1, min(100, limit))}"
    )
    return list((response or {}).get("workflow_runs", []))


def open_work_items() -> list[dict]:
    owner, repo = REPOSITORY.split("/", 1)
    items = request(f"/repos/{owner}/{repo}/issues?state=open&per_page=100") or []
    return [
        {
            "id": item.get("id"),
            "number": item.get("number"),
            "title": item.get("title"),
            "state": item.get("state"),
            "created_at": item.get("created_at"),
            "updated_at": item.get("updated_at"),
            "url": item.get("html_url"),
            "is_pull_request": "pull_request" in item,
        }
        for item in items
    ]


def compare_fork(entry: dict) -> dict:
    fork_name = str(entry.get("fork_full_name") or "")
    upstream = str(entry.get("full_name") or "")
    if not fork_name or not upstream:
        return {
            "fork": fork_name,
            "upstream": upstream,
            "status": "invalid-history",
            "behind_by": 0,
            "ahead_by": 0,
        }

    fork_repo = request(f"/repos/{fork_name}", allow_404=True) or {}
    parent = fork_repo.get("parent") or {}
    branch = str(
        fork_repo.get("default_branch")
        or parent.get("default_branch")
        or "main"
    )
    upstream_owner = upstream.split("/", 1)[0]
    fork_owner = fork_name.split("/", 1)[0]
    compare_spec = quote(
        f"{upstream_owner}:{branch}...{fork_owner}:{branch}",
        safe=":.",
    )

    comparison = request(
        f"/repos/{fork_name}/compare/{compare_spec}",
        allow_404=True,
    )
    if comparison is None:
        return {
            "fork": fork_name,
            "upstream": upstream,
            "branch": branch,
            "status": "compare-unavailable",
            "behind_by": 0,
            "ahead_by": 0,
        }

    return {
        "fork": fork_name,
        "upstream": upstream,
        "branch": branch,
        "status": comparison.get("status"),
        "behind_by": int(comparison.get("behind_by") or 0),
        "ahead_by": int(comparison.get("ahead_by") or 0),
    }


def fork_comparisons() -> list[dict]:
    history = load(FORK_HISTORY_PATH, [])
    return [
        compare_fork(item)
        for item in history
        if item.get("status") == "forked"
        and item.get("platform") == "github"
    ]


def issue_body(signal) -> str:
    evidence = json.dumps(
        signal.evidence,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return (
        "Activity Matrix v3 detected a maintenance condition backed by current "
        "repository evidence.\n\n"
        f"- signal: {signal.key}\n"
        f"- severity: {signal.severity}\n\n"
        "Evidence:\n\n"
        f"{evidence}\n\n"
        "This issue is deduplicated by evidence fingerprint and will close "
        "automatically when the condition recovers."
    )


def create_issue(title: str, body: str):
    owner, repo = REPOSITORY.split("/", 1)
    return request(
        f"/repos/{owner}/{repo}/issues",
        method="POST",
        payload={"title": title, "body": body},
    )


def comment(number: int, body: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}/comments",
        method="POST",
        payload={"body": body},
    )


def set_issue_state(number: int, state: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}",
        method="PATCH",
        payload={"state": state},
    )


def reconcile(
    state: dict,
    signal,
    *,
    now: datetime,
    cooldown_hours: float,
) -> int:
    incidents = state.setdefault("incidents", {})
    record = incidents.get(signal.key)
    decision = decide_incident(
        record,
        active=signal.active,
        evidence=signal.evidence,
        now=now,
        cooldown_hours=cooldown_hours,
    )

    if decision.action == "none":
        return 0

    body = issue_body(signal)
    if decision.action == "create":
        created = create_issue(signal.title, body)
        incidents[signal.key] = {
            "external_id": created["number"],
            "url": created.get("html_url"),
            "status": "open",
            "fingerprint": decision.fingerprint,
            "last_action_at": now.isoformat(),
        }
        return 1

    if record is None:
        return 0
    number = int(record["external_id"])

    if decision.action == "update":
        comment(
            number,
            "Maintenance evidence changed.\n\n"
            f"Fingerprint: {decision.fingerprint}\n\n{body}",
        )
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    if decision.action == "close":
        comment(
            number,
            "Maintenance Intelligence recovered: the triggering condition is no "
            "longer active. Closing automatically.",
        )
        set_issue_state(number, "closed")
        record["status"] = "closed"
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    return 0


def main() -> int:
    if not TOKEN:
        print("MAINTENANCE=SKIP UPSTREAMRADAR_PAT missing")
        return 0

    now = now_utc()
    day = now.date().isoformat()
    report_path = Path(f"reports/maintenance/github-{day}.json")
    if report_path.exists():
        print(f"MAINTENANCE=SKIP day={day} already-published")
        return 0

    config = load(CONFIG_PATH, {})
    policy = config.get("maintenance_intelligence", {})
    state = load(STATE_PATH, {"version": 1, "incidents": {}})

    ci_policy = policy.get("ci", {})
    ci_signal = ci_reliability(
        recent_runs(int(ci_policy.get("window_runs", 30))),
        ci_policy,
    )

    fork_policy = policy.get("fork_sync", {})
    comparisons = (
        fork_comparisons()
        if fork_policy.get("enabled", True)
        else []
    )
    fork_signal = fork_sync_signal(comparisons, fork_policy)

    stale_signal = stale_work_signal(
        open_work_items(),
        policy.get("stale_work", {}),
        now=now,
    )
    ref_signal = workflow_reference_signal(
        Path("."),
        policy.get("workflow_refs", {}),
    )

    signals = [ci_signal, fork_signal, stale_signal, ref_signal]
    dry_run = os.environ.get("MAINTENANCE_DRY_RUN") == "1"
    cooldown = float(policy.get("incident_cooldown_hours", 12))
    actions = 0
    if not dry_run:
        actions = sum(
            reconcile(
                state,
                signal,
                now=now,
                cooldown_hours=cooldown,
            )
            for signal in signals
        )

    report = {
        "observed_at": now.isoformat(),
        "platform": "github",
        "platform_actions": actions,
        "fork_comparisons": comparisons,
        **maintenance_summary(
            ci=ci_signal,
            forks=fork_signal,
            stale_work=stale_signal,
            workflow_refs=ref_signal,
        ),
    }

    if not dry_run:
        state["last_run_at"] = now.isoformat()
        write(STATE_PATH, state)
        write(report_path, report)

    print(
        f"MAINTENANCE={'DRY_RUN' if dry_run else 'PASS'} "
        f"active={report['active_count']} "
        f"actions={actions} forks={len(comparisons)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
