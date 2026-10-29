"""Idempotent GitHub incident issues and one-shot duplicate cleanup.

Scheduled jobs used to open a new issue whenever the local incident record
was missing. These helpers identify an existing open issue by a hidden
marker or by exact title before anything is created.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any, Callable, Mapping, Sequence

from upstreamradar.health import decide_incident, parse_time


UTC = timezone.utc
BOT_LOGINS = frozenset({"github-actions[bot]"})
_INCIDENT_RE = re.compile(r"<!-- upstreamradar-incident:([^\n]*?) -->")
_FINGERPRINT_RE = re.compile(
    r"<!-- upstreamradar-fingerprint:([0-9a-f]{8,64}) -->"
)
_MARKER_KEY_RE = re.compile(r"^[^\n>]+\Z")


@dataclass(frozen=True)
class SyncPlan:
    action: str
    issue_number: int | None
    close_numbers: tuple[int, ...]
    adopted: bool


@dataclass(frozen=True)
class DedupeAction:
    number: int
    kept: int
    title: str


def incident_marker(key: str) -> str:
    cleaned = str(key).strip()
    if not cleaned or _MARKER_KEY_RE.fullmatch(cleaned) is None:
        raise ValueError(f"invalid incident key: {key!r}")
    return f"<!-- upstreamradar-incident:{cleaned} -->"


def fingerprint_marker(fingerprint: str) -> str:
    cleaned = str(fingerprint).strip()
    if re.fullmatch(r"[0-9a-f]{8,64}", cleaned) is None:
        raise ValueError(f"invalid fingerprint: {fingerprint!r}")
    return f"<!-- upstreamradar-fingerprint:{cleaned} -->"


def marker_key(body: str | None) -> str | None:
    if not body:
        return None
    match = _INCIDENT_RE.search(body)
    if match is None:
        return None
    key = match.group(1).strip()
    return key or None


def read_fingerprint(body: str | None) -> str | None:
    if not body:
        return None
    match = _FINGERPRINT_RE.search(body)
    if match is None:
        return None
    return match.group(1)


def updated_body_markers(
    body: str | None,
    key: str,
    fingerprint: str | None = None,
) -> str:
    text = _INCIDENT_RE.sub("", body or "")
    text = _FINGERPRINT_RE.sub("", text).rstrip()
    suffix = incident_marker(key)
    if fingerprint:
        suffix += "\n" + fingerprint_marker(fingerprint)
    if text:
        return text + "\n\n" + suffix + "\n"
    return suffix + "\n"


def with_marker(body: str, key: str) -> str:
    return updated_body_markers(body, key, None)


def issue_number(issue: Mapping[str, Any]) -> int | None:
    try:
        number = int(issue.get("number"))
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def is_pull_request(issue: Mapping[str, Any]) -> bool:
    return "pull_request" in issue


def is_open_issue(issue: Mapping[str, Any]) -> bool:
    return str(issue.get("state") or "open") == "open" and not is_pull_request(
        issue
    )


def author_login(issue: Mapping[str, Any]) -> str:
    user = issue.get("user") or {}
    if isinstance(user, Mapping):
        return str(user.get("login") or "")
    return ""


def is_bot_issue(issue: Mapping[str, Any]) -> bool:
    return author_login(issue) in BOT_LOGINS


def is_generated_issue(issue: Mapping[str, Any]) -> bool:
    return is_bot_issue(issue) or marker_key(str(issue.get("body") or "")) is not None


def recency_key(issue: Mapping[str, Any]) -> tuple[datetime, int]:
    when = parse_time(str(issue.get("created_at") or ""))
    if when is None:
        when = datetime.min.replace(tzinfo=UTC)
    return (when, issue_number(issue) or 0)


def matching_open_issues(
    issues: Sequence[Mapping[str, Any]],
    *,
    title: str,
    key: str,
) -> list[Mapping[str, Any]]:
    marker = incident_marker(key)
    found: list[Mapping[str, Any]] = []
    for issue in issues:
        if not is_open_issue(issue):
            continue
        body = str(issue.get("body") or "")
        if marker_key(body) == key or marker in body:
            found.append(issue)
            continue
        if str(issue.get("title") or "") == title:
            found.append(issue)
    found.sort(key=recency_key)
    return found


def newest_open_issue(
    issues: Sequence[Mapping[str, Any]],
    *,
    title: str,
    key: str,
) -> Mapping[str, Any] | None:
    matches = matching_open_issues(issues, title=title, key=key)
    if not matches:
        return None
    preferred = [issue for issue in matches if is_generated_issue(issue)]
    pool = preferred or matches
    return pool[-1]


def _open_number(issues: Sequence[Mapping[str, Any]], number: int | None) -> bool:
    if number is None:
        return False
    return any(
        is_open_issue(issue) and issue_number(issue) == number for issue in issues
    )


def plan_issue_sync(
    decision_action: str,
    issues: Sequence[Mapping[str, Any]],
    *,
    title: str,
    key: str,
    tracked_number: int | None = None,
) -> SyncPlan:
    newest = newest_open_issue(issues, title=title, key=key)
    newest_number = issue_number(newest) if newest is not None else None

    if decision_action in {"create", "update"}:
        if newest_number is not None:
            return SyncPlan(
                action="comment",
                issue_number=newest_number,
                close_numbers=(),
                adopted=decision_action == "create",
            )
        return SyncPlan("create", None, (), False)

    if decision_action == "close":
        target = tracked_number if _open_number(issues, tracked_number) else None
        if target is None:
            return SyncPlan("none", tracked_number, (), False)
        return SyncPlan("close", target, (target,), False)

    return SyncPlan("none", newest_number or tracked_number, (), False)


def list_open_issues(
    request: Callable[..., Any],
    repository: str,
    *,
    per_page: int = 100,
    page_limit: int = 20,
) -> list[dict[str, Any]]:
    if per_page < 1 or page_limit < 1:
        raise ValueError("pagination bounds must be positive")
    if "/" not in repository:
        raise ValueError(f"invalid repository: {repository}")
    owner, repo = repository.split("/", 1)
    collected: list[dict[str, Any]] = []
    for page in range(1, page_limit + 1):
        path = (
            f"/repos/{owner}/{repo}/issues"
            f"?state=open&per_page={per_page}&page={page}"
        )
        batch = request(path) or []
        if not isinstance(batch, list):
            raise RuntimeError("GitHub issues list returned a non-list response")
        collected.extend(item for item in batch if isinstance(item, dict))
        if len(batch) < per_page:
            return collected
    raise RuntimeError(
        "open issue listing truncated; refusing to open another incident"
    )


def reconcile_github_incident(
    state: dict[str, Any],
    *,
    key: str,
    title: str,
    active: bool,
    evidence: Mapping[str, Any],
    now: datetime,
    cooldown_hours: float,
    open_issues: Sequence[Mapping[str, Any]],
    body: str,
    create_issue: Callable[[str, str], Mapping[str, Any]],
    comment: Callable[[int, str], None],
    close_issue: Callable[[int], None],
    update_body: Callable[[int, str], None],
    update_comment: str,
    adopt_comment: str,
    close_comment: str,
) -> int:
    incidents = state.setdefault("incidents", {})
    record = incidents.get(key)
    tracked_number = None
    if isinstance(record, Mapping) and record.get("external_id"):
        tracked_number = issue_number({"number": record.get("external_id")})
        if (
            str(record.get("status") or "") == "open"
            and not _open_number(open_issues, tracked_number)
        ):
            record = dict(record)
            record["status"] = "closed"
            incidents[key] = record

    decision = decide_incident(
        record if isinstance(record, Mapping) else None,
        active=active,
        evidence=evidence,
        now=now,
        cooldown_hours=cooldown_hours,
    )
    if decision.action == "none":
        return 0

    plan = plan_issue_sync(
        decision.action,
        open_issues,
        title=title,
        key=key,
        tracked_number=tracked_number,
    )

    def remember(number: int, status: str, url: str | None = None) -> None:
        current = next(
            (
                issue
                for issue in open_issues
                if issue_number(issue) == number
            ),
            None,
        )
        incidents[key] = {
            "external_id": number,
            "url": url or (current or {}).get("html_url"),
            "status": status,
            "fingerprint": decision.fingerprint,
            "last_action_at": now.isoformat(),
        }

    if plan.action == "none":
        if decision.action == "close" and isinstance(incidents.get(key), dict):
            incidents[key]["status"] = "closed"
            incidents[key]["fingerprint"] = decision.fingerprint
            incidents[key]["last_action_at"] = now.isoformat()
            return 1
        return 0

    if plan.action == "create":
        created = create_issue(
            title,
            updated_body_markers(body, key, decision.fingerprint),
        )
        remember(
            int(created["number"]),
            "open",
            created.get("html_url") if isinstance(created, Mapping) else None,
        )
        return 1

    if plan.action == "comment":
        number = int(plan.issue_number)
        current = next(
            (issue for issue in open_issues if issue_number(issue) == number),
            None,
        )
        current_body = str((current or {}).get("body") or "")
        patched = updated_body_markers(current_body, key, decision.fingerprint)
        same_evidence = (
            plan.adopted
            and marker_key(current_body) == key
            and read_fingerprint(current_body) == decision.fingerprint
        )
        if same_evidence and patched == current_body:
            remember(number, "open", (current or {}).get("html_url"))
            return 0
        if patched != current_body:
            update_body(number, patched)
        if not same_evidence:
            label = adopt_comment if plan.adopted else update_comment
            comment(
                number,
                f"{label}\n\nFingerprint: {decision.fingerprint}\n\n"
                f"{updated_body_markers(body, key, decision.fingerprint)}",
            )
        remember(number, "open", (current or {}).get("html_url"))
        return 1

    if plan.action == "close":
        for number in plan.close_numbers:
            comment(number, close_comment)
            close_issue(number)
        remember(int(plan.issue_number), "closed")
        return 1

    return 0


def validate_pr_url(url: str) -> str:
    cleaned = str(url or "").strip()
    if not cleaned or any(character.isspace() for character in cleaned):
        raise ValueError("pr_url must be a single https://github.com pull request URL")
    if not cleaned.startswith("https://github.com/") or "/pull/" not in cleaned:
        raise ValueError(
            "pr_url must be an https://github.com/<owner>/<repo>/pull/<number> URL"
        )
    if len(cleaned) > 300:
        raise ValueError("pr_url is too long")
    return cleaned


def closing_comment(kept: int, pr_url: str) -> str:
    url = validate_pr_url(pr_url)
    return (
        f"Duplicate of #{int(kept)}, auto-generated by the radar workflow; "
        f"closing during dedupe. Generator fixed in {url}."
    )


def dedupe_close_payload() -> dict[str, str]:
    return {"state": "closed", "state_reason": "not_planned"}


def plan_duplicate_closes(
    issues: Sequence[Mapping[str, Any]],
) -> tuple[DedupeAction, ...]:
    groups: dict[str, dict[int, Mapping[str, Any]]] = {}
    for issue in issues:
        if not is_open_issue(issue) or not is_generated_issue(issue):
            continue
        title = str(issue.get("title") or "")
        number = issue_number(issue)
        if not title or number is None:
            continue
        groups.setdefault(title, {})[number] = issue

    actions: list[DedupeAction] = []
    for title in sorted(groups):
        ordered = sorted(groups[title].values(), key=recency_key)
        if len(ordered) < 2:
            continue
        kept = issue_number(ordered[-1])
        if kept is None:
            continue
        for issue in ordered[:-1]:
            number = issue_number(issue)
            if number is None or number == kept:
                continue
            actions.append(DedupeAction(number=number, kept=kept, title=title))
    return tuple(actions)
