from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from upstreamradar.health import (
    benchmark_incident_evidence,
    decide_incident,
    security_incident_evidence,
)


UTC = timezone.utc
API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_PAT", "")
CONFIG_PATH = Path("config/activity_matrix.json")
STATE_PATH = Path("state/engineering_health_github.json")


def request(path: str, method: str = "GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "UpstreamRadar-Engineering-Health",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{API}{path}", method=method, headers=headers, data=data)
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


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


def issue(number: int):
    owner, repo = REPOSITORY.split("/", 1)
    return request(f"/repos/{owner}/{repo}/issues/{number}")


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


def set_state(number: int, state: str) -> None:
    owner, repo = REPOSITORY.split("/", 1)
    request(
        f"/repos/{owner}/{repo}/issues/{number}",
        method="PATCH",
        payload={"state": state},
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
            "external_id": created["number"],
            "url": created.get("html_url"),
            "status": "open",
            "fingerprint": decision.fingerprint,
            "last_action_at": now.isoformat(),
        }
        return 1

    assert record is not None
    number = int(record["external_id"])
    if decision.action == "update":
        comment(
            number,
            "Engineering-health evidence changed.\n\n"
            f"Fingerprint: {decision.fingerprint}\n\n{body}",
        )
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    if decision.action == "close":
        comment(
            number,
            "Engineering Health recovered. The triggering condition is no "
            "longer present in the daily evidence. Closing automatically.",
        )
        set_state(number, "closed")
        record["status"] = "closed"
        record["fingerprint"] = decision.fingerprint
        record["last_action_at"] = now.isoformat()
        return 1

    return 0


def main() -> int:
    if not TOKEN:
        print("ENGINEERING_HEALTH=SKIP UPSTREAMRADAR_PAT missing")
        return 0

    now = datetime.now(UTC).replace(microsecond=0)
    day = now.date().isoformat()
    benchmark_path = Path(f"reports/benchmarks/github-{day}.json")
    security_path = Path(f"reports/security/github-{day}.json")
    summary_path = Path(f"reports/health/github-{day}.json")
    baseline_path = Path("state/benchmark_github.json")

    if benchmark_path.exists() and security_path.exists() and summary_path.exists():
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
    print(
        f"ENGINEERING_HEALTH=PASS day={day} actions={actions} "
        f"benchmark_active={benchmark_active} security_active={security_active}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
