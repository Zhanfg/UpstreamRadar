"""Close older copies of generated GitHub issues.

Dry-run is the default. Pass --apply to comment and close. Nothing is deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from upstreamradar.issue_sync import (
    closing_comment,
    dedupe_close_payload,
    list_open_issues,
    plan_duplicate_closes,
    validate_pr_url,
)


API = "https://api.github.com"
REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "Zhanfg/UpstreamRadar")
TOKEN = os.environ.get("UPSTREAMRADAR_PAT") or os.environ.get("GITHUB_TOKEN") or ""


def request(path: str, method: str = "GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "UpstreamRadar-Issue-Dedupe",
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


def _apply_enabled(argv_flag: bool) -> bool:
    if argv_flag:
        return True
    return os.environ.get("DEDUPE_APPLY", "").strip().lower() in {"1", "true", "yes"}


def render_plan(actions) -> str:
    lines: list[str] = []
    current_kept = None
    for action in actions:
        if action.kept != current_kept:
            lines.append(f"KEEP #{action.kept} {action.title}")
            current_kept = action.kept
        lines.append(
            f"CLOSE #{action.number} duplicate of #{action.kept} "
            f"state_reason=not_planned"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Keep the newest open generated issue for each exact title and "
            "close older copies with state_reason not_planned."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="comment and close older duplicates; omit to print the plan only",
    )
    parser.add_argument(
        "--pr-url",
        default=os.environ.get("DEDUPE_PR_URL", ""),
        help="pull request URL cited in each closing comment",
    )
    args = parser.parse_args(argv)
    apply = _apply_enabled(args.apply)

    if not TOKEN:
        print("DEDUPE=FAIL token missing; set UPSTREAMRADAR_PAT or GITHUB_TOKEN", file=sys.stderr)
        return 2

    pr_url = str(args.pr_url or "").strip()
    if apply:
        try:
            pr_url = validate_pr_url(pr_url)
        except ValueError as exc:
            print(f"DEDUPE=FAIL {exc}", file=sys.stderr)
            return 2
    elif pr_url:
        try:
            pr_url = validate_pr_url(pr_url)
        except ValueError as exc:
            print(f"DEDUPE=FAIL {exc}", file=sys.stderr)
            return 2

    try:
        issues = list_open_issues(request, REPOSITORY)
    except (HTTPError, OSError, TimeoutError, json.JSONDecodeError, RuntimeError) as exc:
        print(f"DEDUPE=FAIL unable to list open issues: {type(exc).__name__}", file=sys.stderr)
        return 1

    actions = plan_duplicate_closes(issues)
    if actions:
        print(render_plan(actions))
    else:
        print("DEDUPE=EMPTY no duplicate generated issues")

    if not apply:
        print(f"DEDUPE=DRY_RUN close={len(actions)}")
        return 0

    owner, repo = REPOSITORY.split("/", 1)
    closed = 0
    for action in actions:
        comment = closing_comment(action.kept, pr_url)
        request(
            f"/repos/{owner}/{repo}/issues/{action.number}/comments",
            method="POST",
            payload={"body": comment},
        )
        request(
            f"/repos/{owner}/{repo}/issues/{action.number}",
            method="PATCH",
            payload=dedupe_close_payload(),
        )
        closed += 1
        print(f"CLOSED #{action.number} duplicate of #{action.kept}")

    print(f"DEDUPE=APPLIED closed={closed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
