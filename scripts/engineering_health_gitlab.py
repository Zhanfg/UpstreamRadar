from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from upstreamradar.health import (
    benchmark_incident_evidence,
    decide_incident,
    security_incident_evidence,
)


UTC = timezone.utc
API = (os.environ.get("CI_API_V4_URL") or "https://gitlab.com/api/v4").rstrip("/")
PROJECT_ID = str(os.environ.get("CI_PROJECT_ID", "87037475"))
BRANCH = os.environ.get("CI_DEFAULT_BRANCH", "main")
TOKEN = os.environ.get("UPSTREAMRADAR_GITLAB_PAT", "")
CONFIG_PATH = Path("config/activity_matrix.json")
STATE_PATH = Path("state/engineering_health_gitlab.json")


def request(path: str, method: str = "GET", payload=None, *, allow_404=False):
    headers = {
        "PRIVATE-TOKEN": TOKEN,
        "User-Agent": "UpstreamRadar-Engineering-Health",
    }
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


def run(args: list[str]) -> int:
    return int(subprocess.run(args, text=True).returncode)


def remote_file(path: str):
    return request(
        f"/projects/{PROJECT_ID}/repository/files/"
        f"{quote(path, safe='')}?ref={quote(BRANCH, safe='')}",
        allow_404=True,
    )


def issue_by_iid(iid: int):
    return request(f"/projects/{PROJECT_ID}/issues/{iid}", allow_404=True)


def create_issue(title: str, body: str):
    return request(
        f"/projects/{PROJECT_ID}/issues",
        method="POST",
        payload={"title": title, "description": body},
    )


def note(iid: int, body: str) -> None:
    request(
        f"/projects/{PROJECT_ID}/issues/{iid}/notes",
        method="POST",
        payload={"body": body},
    )


def set_state(iid: int, state_event: str) -> None:
    request(
        f"/projects/{PROJECT_ID}/issues/{iid}",
        method="PUT",
        payload={"state_event": state_event},
    )


def incident_body(kind: str, evidence: dict) -> str:
    if kind == "benchmark":
        return (
            "Activity Matrix v2 detected a measured SKOPRÆD engineering-health "
            "regression.\n\n"
            f"- median_ms: {evidence.get('median_ms')}\n"
            f"- previous_median_ms: {evidence.get('previous_median_ms')}\n"
            f"- runtime_regressed: {evidence.get('regressed')}\n"
            f"- determinism_regressed: {evidence.get('determinism_regressed')}\n"
            f"- selection_hash: {evidence.get('selection_hash')}\n\n"
            "This issue is driven by daily benchmark evidence and will close "
            "automatically after recovery."
        )

    findings = evidence.get("findings", [])
    lines = [
        "Activity Matrix v2 detected high-severity repository posture findings.",
        "",
        f"- critical: {evidence.get('critical', 0)}",
        f"- high: {evidence.get('high', 0)}",
        "",
    ]
    lines.extend(
        f"- {item.get('severity')} {item.get('kind')}: "
        f"{item.get('path')} — {item.get('message')}"
        for item in findings
    )
    lines += [
        "",
        "This issue is driven by daily security-posture evidence and will close "
        "automatically after recovery.",
    ]
    return "\n".join(lines)


def reconcile(
    state: dict,
    *,
    key: str,
    title: str,
    active: bool,
    evidence: dict,
    now: datetime,
    cooldown_hours: float,
) -> int:
    incidents = state.setdefault("incidents", {})
    record = incidents.get(key)
    decision = decide_incident(
        record,
        active=active,
        evidence=evidence,
        now=now,
        cooldown_hours=cooldown_hours,
    )
    if decision.action == "none":
        return 0

    body = incident_body(key, evidence)
    if decision.action == "create":
        created = create_issue(title, body)
        incidents[key] = {
            "external_id": created["iid"],
            "url": created.get("web_url"),
            "status": "open",
            "fingerprint": decision.fingerprint,
            "last_action_at": now.isoformat(),
        }
        return 1

    assert record is not None
    iid = int(record["external_id"])
    current = issue_by_iid(iid)
    if current is None:
        record.clear()
        return 0

    if decision.action == "update":
        note(
            iid,
            "Engineering-health evidence changed.\n\n"
            f"Fingerprint: {decision.fingerprint}\n\n{body}",
        )
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    if decision.action == "close":
        note(
            iid,
            "Engineering Health recovered. The triggering condition is no "
            "longer present in the daily evidence. Closing automatically.",
        )
        set_state(iid, "close")
        record["status"] = "closed"
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    return 0


def publish(files: dict[str, str], day: str) -> None:
    actions = []
    for path, content in files.items():
        actions.append(
            {
                "action": "update" if remote_file(path) else "create",
                "file_path": path,
                "content": content,
            }
        )
    request(
        f"/projects/{PROJECT_ID}/repository/commits",
        method="POST",
        payload={
            "branch": BRANCH,
            "commit_message": (
                f"[health] GitLab engineering evidence {day}\n\n[skip ci]"
            ),
            "actions": actions,
        },
    )


def main() -> int:
    if not TOKEN:
        print("ENGINEERING_HEALTH=SKIP GitLab token missing")
        return 0

    now = datetime.now(UTC).replace(microsecond=0)
    day = now.date().isoformat()
    benchmark_path = Path(f"reports/benchmarks/gitlab-{day}.json")
    security_path = Path(f"reports/security/gitlab-{day}.json")
    summary_path = Path(f"reports/health/gitlab-{day}.json")
    baseline_path = Path("state/benchmark_gitlab.json")

    if (
        remote_file(str(benchmark_path))
        and remote_file(str(security_path))
        and remote_file(str(summary_path))
    ):
        print(f"ENGINEERING_HEALTH=SKIP day={day} already-published")
        return 0

    benchmark_rc = run(
        [
            sys.executable,
            "-m",
            "scripts.benchmark_skopraed",
            "--baseline",
            str(baseline_path),
            "--output",
            str(benchmark_path),
        ]
    )
    security_rc = run(
        [
            sys.executable,
            "-m",
            "scripts.security_posture",
            "--output",
            str(security_path),
        ]
    )

    benchmark = load(benchmark_path, {})
    security = load(security_path, {})
    config = load(CONFIG_PATH, {})
    state = load(STATE_PATH, {"version": 1, "incidents": {}})
    health = config.get("engineering_health", {})
    cooldown = float(health.get("incident_cooldown_hours", 12))

    benchmark_evidence = benchmark_incident_evidence(benchmark)
    security_evidence = security_incident_evidence(security)
    benchmark_active = bool(
        benchmark_evidence["regressed"]
        or benchmark_evidence["determinism_regressed"]
    )
    security_active = (
        int(security_evidence["critical"]) + int(security_evidence["high"]) > 0
    )

    actions = 0
    actions += reconcile(
        state,
        key="benchmark",
        title="[benchmark] SKOPRÆD engineering health regression",
        active=benchmark_active,
        evidence=benchmark_evidence,
        now=now,
        cooldown_hours=cooldown,
    )
    actions += reconcile(
        state,
        key="security",
        title="[security] Repository posture regression",
        active=security_active,
        evidence=security_evidence,
        now=now,
        cooldown_hours=cooldown,
    )

    state["last_run_at"] = now.isoformat()
    write(STATE_PATH, state)
    write(
        summary_path,
        {
            "observed_at": now.isoformat(),
            "benchmark_active": benchmark_active,
            "security_active": security_active,
            "platform_actions": actions,
            "benchmark_return_code": benchmark_rc,
            "security_return_code": security_rc,
            "benchmark": benchmark_evidence,
            "security": security_evidence,
        },
    )

    publish(
        {
            str(benchmark_path): benchmark_path.read_text(encoding="utf-8"),
            str(security_path): security_path.read_text(encoding="utf-8"),
            str(summary_path): summary_path.read_text(encoding="utf-8"),
            str(baseline_path): baseline_path.read_text(encoding="utf-8"),
            str(STATE_PATH): STATE_PATH.read_text(encoding="utf-8"),
        },
        day,
    )
    print(
        f"ENGINEERING_HEALTH=PASS day={day} actions={actions} "
        f"benchmark_active={benchmark_active} security_active={security_active}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
