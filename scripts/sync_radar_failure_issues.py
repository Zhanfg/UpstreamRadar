"""Open one issue per repeated radar collection failure.

An existing open issue with the same title or hidden marker is left in place.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from upstreamradar.issue_sync import (
    list_open_issues,
    newest_open_issue,
    updated_body_markers,
)


API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_PAT") or os.environ.get("GH_TOKEN") or ""
MANIFEST_PATH = Path(os.environ.get("RADAR_MANIFEST", ".radar/manifest.json"))


def request(path: str, method: str = "GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "UpstreamRadar-Radar-Issues",
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


def failure_title(full_name: str) -> str:
    return f"[radar] Repeated collection failure: {full_name}"


def failure_key(full_name: str) -> str:
    return f"radar:{full_name}"


def failure_body(full_name: str, streak: int, message: str) -> str:
    text = (
        "UpstreamRadar failed to collect this target for "
        f"**{streak} consecutive scheduled checks**.\n\n"
        f"- target: `{full_name}`\n"
        f"- latest error: `{message}`\n"
        "- detected by: automated SKOPRÆD collector\n\n"
        "This issue is generated only after repeated failures to avoid "
        "transient-error noise."
    )
    return updated_body_markers(text, failure_key(full_name))


def issues_to_open(anomalies: list[dict], open_issues: list[dict]) -> list[dict]:
    planned: list[dict] = []
    seen: set[str] = set()
    for item in anomalies:
        full_name = str(item.get("full_name") or "").strip()
        if not full_name or full_name in seen:
            continue
        seen.add(full_name)
        title = failure_title(full_name)
        key = failure_key(full_name)
        if newest_open_issue(open_issues, title=title, key=key) is not None:
            continue
        try:
            streak = int(item.get("error_streak") or 0)
        except (TypeError, ValueError):
            streak = 0
        planned.append(
            {
                "title": title,
                "key": key,
                "body": failure_body(
                    full_name,
                    streak,
                    str(item.get("message") or ""),
                ),
            }
        )
    return planned


def main() -> int:
    if not MANIFEST_PATH.exists():
        print("RADAR_ISSUES=SKIP manifest missing")
        return 0

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    anomalies = list(manifest.get("anomalies") or [])
    if not anomalies:
        print("RADAR_ISSUES=SKIP no anomalies")
        return 0
    if not TOKEN:
        print("RADAR_ISSUES=SKIP token missing")
        return 0

    open_issues = list_open_issues(request, REPOSITORY)
    planned = issues_to_open(anomalies, open_issues)
    owner, repo = REPOSITORY.split("/", 1)
    created = 0
    for item in planned:
        try:
            request(
                f"/repos/{owner}/{repo}/issues",
                method="POST",
                payload={"title": item["title"], "body": item["body"]},
            )
        except HTTPError:
            raise
        created += 1
        print(f"RADAR_ISSUES=OPEN {item['title']}")

    skipped = len({str(item.get("full_name") or "") for item in anomalies if item.get("full_name")}) - created
    print(f"RADAR_ISSUES=PASS created={created} reused={max(0, skipped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
