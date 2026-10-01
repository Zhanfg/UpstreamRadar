from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from upstreamradar.governance import (
    data_quality_signal,
    governance_summary,
    parity_signal,
    state_growth_signal,
)
from upstreamradar.health import decide_incident


UTC = timezone.utc
API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_PAT", "")
CONFIG_PATH = Path("config/activity_matrix.json")
MODEL_PATH = Path("state/model.json")
STATE_PATH = Path("state/governance_github.json")


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
        "User-Agent": "UpstreamRadar-Governance",
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


def gitlab_raw(path: str) -> str | None:
    encoded = quote(path, safe="")
    url = (
        "https://gitlab.com/api/v4/projects/87037475/repository/files/"
        f"{encoded}/raw?ref=main"
    )
    req = Request(url, headers={"User-Agent": "UpstreamRadar-Governance"})
    try:
        with urlopen(req, timeout=30) as response:
            return response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError, OSError):
        return None


def parity_entries(paths: list[str]) -> list[dict]:
    entries = []
    for path in paths:
        local_path = Path(path)
        local = local_path.read_text(encoding="utf-8") if local_path.exists() else None
        remote = gitlab_raw(path)
        status = "match"
        if local is None and remote is None:
            status = "missing-both"
        elif local is None:
            status = "missing-local"
        elif remote is None:
            status = "missing-remote"
        elif local != remote:
            status = "content-mismatch"
        entries.append(
            {
                "path": path,
                "same": local is not None and remote is not None and local == remote,
                "status": status,
                "local_length": len(local or ""),
                "remote_length": len(remote or ""),
            }
        )
    return entries


def state_files() -> list[dict]:
    return [
        {"path": str(path), "bytes": path.stat().st_size}
        for path in sorted(Path("state").glob("*.json"))
        if path.is_file()
    ]


def issue_body(signal) -> str:
    evidence = json.dumps(
        signal.evidence,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )
    return (
        "Activity Matrix v4 Governance detected a real repository-governance "
        "condition.\n\n"
        f"- signal: {signal.key}\n"
        f"- severity: {signal.severity}\n\n"
        "Evidence:\n\n"
        f"{evidence}\n\n"
        "This incident is fingerprint-deduplicated and closes automatically "
        "after the condition recovers."
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


def close_issue(number: int) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}",
        method="PATCH",
        payload={"state": "closed"},
    )


def reconcile(state: dict, signal, *, now: datetime, cooldown_hours: float) -> int:
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
            "Governance evidence changed.\n\n"
            f"Fingerprint: {decision.fingerprint}\n\n{body}",
        )
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    if decision.action == "close":
        comment(
            number,
            "Activity Matrix Governance recovered: the triggering condition "
            "is no longer active. Closing automatically.",
        )
        close_issue(number)
        record["status"] = "closed"
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    return 0


def main() -> int:
    if not TOKEN:
        print("GOVERNANCE=SKIP UPSTREAMRADAR_PAT missing")
        return 0

    now = now_utc()
    day = now.date().isoformat()
    report_path = Path(f"reports/governance/github-{day}.json")
    if report_path.exists():
        print(f"GOVERNANCE=SKIP day={day} already-published")
        return 0

    config = load(CONFIG_PATH, {})
    policy = config.get("governance", {})
    model = load(MODEL_PATH, {})
    repositories = model.get("repositories", {})
    parity_policy = policy.get("parity", {})

    signals = [
        data_quality_signal(
            repositories,
            policy.get("data_quality", {}),
            now=now,
        ),
        state_growth_signal(
            state_files(),
            policy.get("state_growth", {}),
        ),
    ]
    entries = []
    if parity_policy.get("enabled", True):
        entries = parity_entries(list(parity_policy.get("shared_paths", [])))
        signals.append(parity_signal(entries, parity_policy))

    state = load(STATE_PATH, {"version": 1, "incidents": {}})
    cooldown = float(policy.get("incident_cooldown_hours", 12))
    actions = sum(
        reconcile(state, signal, now=now, cooldown_hours=cooldown)
        for signal in signals
    )

    report = {
        "observed_at": now.isoformat(),
        "platform": "github",
        "platform_actions": actions,
        "parity_entries": entries,
        **governance_summary(signals),
    }
    state["last_run_at"] = now.isoformat()
    write(STATE_PATH, state)
    write(report_path, report)

    print(
        f"GOVERNANCE=PASS active={report['active_count']} "
        f"actions={actions} parity_checked={len(entries)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
