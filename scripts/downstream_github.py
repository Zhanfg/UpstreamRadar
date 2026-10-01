from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from upstreamradar.downstream import (
    decide_action,
    plan_downstream_impacts,
    recent_action_count,
)


UTC = timezone.utc
API = "https://api.github.com"
TOKEN = os.environ.get("UPSTREAMRADAR_PAT", "")
CONFIG_PATH = Path("config/downstream_projects.json")
STATE_PATH = Path("state/downstream_github.json")


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
        "User-Agent": "UpstreamRadar-Downstream-Impact",
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


def latest_run() -> dict:
    paths = sorted(Path("data/runs").glob("*/*.json"))
    if not paths:
        raise RuntimeError("no GitHub radar run journal found")
    return load(paths[-1], {})


def issue(repo: str, number: int):
    return request(f"/repos/{repo}/issues/{number}", allow_404=True)


def create_issue(repo: str, title: str, body: str):
    return request(
        f"/repos/{repo}/issues",
        method="POST",
        payload={"title": title, "body": body},
    )


def comment(repo: str, number: int, body: str) -> None:
    request(
        f"/repos/{repo}/issues/{number}/comments",
        method="POST",
        payload={"body": body},
    )


def main() -> int:
    if not TOKEN:
        print("DOWNSTREAM=SKIP UPSTREAMRADAR_PAT missing")
        return 0

    now = now_utc()
    run = latest_run()
    config = load(CONFIG_PATH, {})
    policy = config.get("policy", {})
    plans = plan_downstream_impacts(run, config, platform="github")

    if os.environ.get("DOWNSTREAM_DRY_RUN") == "1":
        print(json.dumps([plan.to_dict() for plan in plans], ensure_ascii=False))
        print(f"DOWNSTREAM=DRY_RUN plans={len(plans)}")
        return 0

    state = load(
        STATE_PATH,
        {"version": 1, "items": {}, "history": []},
    )
    items = state.setdefault("items", {})
    history = state.setdefault("history", [])
    daily_limit = int(policy.get("max_actions_per_day", 3))
    run_limit = int(policy.get("max_actions_per_run", 2))
    daily_used = recent_action_count(history, now=now)
    actions = 0
    action_records = []

    for plan in plans:
        if actions >= run_limit or daily_used >= daily_limit:
            break

        record = items.get(plan.key)
        if record and record.get("issue_number"):
            current = issue(
                str(record.get("repo") or plan.downstream),
                int(record["issue_number"]),
            )
            if current is None:
                record["status"] = "closed"
            else:
                record["status"] = (
                    "open" if current.get("state") == "open" else "closed"
                )

        decision = decide_action(record, plan, policy, now=now)
        if decision.action == "none":
            continue

        if decision.action == "create":
            created = create_issue(
                plan.downstream,
                plan.title,
                plan.body,
            )
            record = {
                "repo": plan.downstream,
                "issue_number": created["number"],
                "issue_url": created.get("html_url"),
                "status": "open",
                "evidence_hash": plan.evidence_hash,
                "last_action_at": now.isoformat(),
                "upstream": plan.upstream,
            }
            items[plan.key] = record
            action_records.append(
                {
                    "action": "create",
                    "key": plan.key,
                    "repo": plan.downstream,
                    "issue_number": created["number"],
                    "evidence_hash": plan.evidence_hash,
                }
            )
        elif decision.action == "update" and record is not None:
            comment(
                plan.downstream,
                int(record["issue_number"]),
                "UpstreamRadar observed new material evidence for this "
                "downstream-impact task.\n\n" + plan.body,
            )
            record["evidence_hash"] = plan.evidence_hash
            record["last_action_at"] = now.isoformat()
            action_records.append(
                {
                    "action": "update",
                    "key": plan.key,
                    "repo": plan.downstream,
                    "issue_number": record["issue_number"],
                    "evidence_hash": plan.evidence_hash,
                }
            )
        else:
            continue

        history.append(
            {
                **action_records[-1],
                "created_at": now.isoformat(),
            }
        )
        actions += 1
        daily_used += 1

    if actions == 0:
        print(f"DOWNSTREAM=PASS plans={len(plans)} actions=0")
        return 0

    state["history"] = history[-300:]
    state["last_run_at"] = now.isoformat()
    write(STATE_PATH, state)
    report_path = Path(
        f"reports/downstream/github-{now.strftime('%Y%m%d-%H%M%S')}.json"
    )
    write(
        report_path,
        {
            "observed_at": now.isoformat(),
            "source_platform": "github",
            "plan_count": len(plans),
            "actions": action_records,
        },
    )
    print(f"DOWNSTREAM=PASS plans={len(plans)} actions={actions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
