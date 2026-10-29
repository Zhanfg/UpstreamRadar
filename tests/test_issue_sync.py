import io
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from scripts.dedupe_github_issues import render_plan
from scripts.sync_radar_failure_issues import issues_to_open
from upstreamradar.issue_sync import (
    DedupeAction,
    closing_comment,
    dedupe_close_payload,
    incident_marker,
    list_open_issues,
    marker_key,
    newest_open_issue,
    plan_duplicate_closes,
    plan_issue_sync,
    read_fingerprint,
    reconcile_github_incident,
    updated_body_markers,
    validate_pr_url,
)


NOW = datetime(2026, 10, 28, 12, tzinfo=timezone.utc)
TITLE = "[governance] GitHub/GitLab shared-core drift"
KEY = "cross-platform-parity"
PR = "https://github.com/Zhanfg/UpstreamRadar/pull/340"


def issue(
    number: int,
    *,
    title: str = TITLE,
    created_at: str | None = None,
    body: str = "",
    login: str = "github-actions[bot]",
    state: str = "open",
    pull_request: bool = False,
):
    payload = {
        "number": number,
        "title": title,
        "state": state,
        "body": body,
        "created_at": created_at or f"2026-10-{number % 28 + 1:02d}T00:00:00Z",
        "html_url": f"https://github.com/Zhanfg/UpstreamRadar/issues/{number}",
        "user": {"login": login},
    }
    if pull_request:
        payload["pull_request"] = {"url": "https://example.invalid/pr"}
    return payload


class IssueSyncTests(unittest.TestCase):
    def test_markers_round_trip_and_stay_idempotent(self):
        body = updated_body_markers("Evidence\n", KEY, "abc123def456")
        self.assertEqual(marker_key(body), KEY)
        self.assertEqual(read_fingerprint(body), "abc123def456")
        self.assertEqual(updated_body_markers(body, KEY, "abc123def456"), body)
        self.assertIn(incident_marker(KEY), body)
        replaced = updated_body_markers(body, KEY, "fedcba9876543210")
        self.assertEqual(read_fingerprint(replaced), "fedcba9876543210")
        self.assertEqual(replaced.count("upstreamradar-incident"), 1)
        self.assertEqual(replaced.count("upstreamradar-fingerprint"), 1)

    def test_newest_match_ignores_pull_requests_and_prefers_bot_copies(self):
        human = issue(30, login="Zhanfg", created_at="2026-10-28T08:00:00Z")
        older = issue(12, created_at="2026-10-20T08:00:00Z")
        newer = issue(18, created_at="2026-10-27T08:00:00Z")
        closed = issue(40, state="closed", created_at="2026-10-29T08:00:00Z")
        pull = issue(41, pull_request=True, created_at="2026-10-29T09:00:00Z")
        found = newest_open_issue(
            [human, older, newer, closed, pull],
            title=TITLE,
            key=KEY,
        )
        self.assertEqual(found["number"], 18)

    def test_marker_matches_when_the_title_differs(self):
        marked = issue(
            7,
            title="renamed",
            body=updated_body_markers("old", KEY, "abc123def456"),
            created_at="2026-10-01T00:00:00Z",
        )
        found = newest_open_issue([marked], title=TITLE, key=KEY)
        self.assertEqual(found["number"], 7)

    def test_create_adopts_an_existing_open_issue(self):
        plan = plan_issue_sync(
            "create",
            [issue(4, created_at="2026-10-01T00:00:00Z"), issue(9, created_at="2026-10-22T00:00:00Z")],
            title=TITLE,
            key=KEY,
        )
        self.assertEqual(plan.action, "comment")
        self.assertEqual(plan.issue_number, 9)
        self.assertTrue(plan.adopted)
        self.assertEqual(plan.close_numbers, ())

    def test_create_when_nothing_matches(self):
        plan = plan_issue_sync("create", [issue(3, title="other")], title=TITLE, key=KEY)
        self.assertEqual(plan.action, "create")
        self.assertFalse(plan.adopted)

    def test_update_targets_the_newest_open_copy(self):
        plan = plan_issue_sync(
            "update",
            [issue(2, created_at="2026-10-02T00:00:00Z"), issue(5, created_at="2026-10-21T00:00:00Z")],
            title=TITLE,
            key=KEY,
            tracked_number=2,
        )
        self.assertEqual(plan.action, "comment")
        self.assertEqual(plan.issue_number, 5)
        self.assertFalse(plan.adopted)

    def test_recovery_closes_only_the_tracked_issue(self):
        plan = plan_issue_sync(
            "close",
            [issue(2), issue(5)],
            title=TITLE,
            key=KEY,
            tracked_number=2,
        )
        self.assertEqual(plan.action, "close")
        self.assertEqual(plan.close_numbers, (2,))

    def test_duplicate_plan_keeps_newest_and_skips_humans(self):
        issues = [
            issue(10, created_at="2026-10-20T00:00:00Z"),
            issue(11, created_at="2026-10-28T00:00:00Z"),
            issue(12, title="[ci] Workflow reliability regression", created_at="2026-10-28T01:00:00Z"),
            issue(13, login="Zhanfg", created_at="2026-10-29T00:00:00Z"),
            issue(14, title="[ci] Workflow reliability regression", pull_request=True),
            issue(15, login="dependabot[bot]", title="[ci] Workflow reliability regression"),
        ]
        actions = plan_duplicate_closes(issues)
        self.assertEqual(
            actions,
            (DedupeAction(number=10, kept=11, title=TITLE),),
        )
        self.assertNotIn(11, [item.number for item in actions])

    def test_same_timestamp_keeps_the_higher_issue_number(self):
        actions = plan_duplicate_closes(
            [
                issue(3, created_at="2026-10-28T00:00:00Z"),
                issue(8, created_at="2026-10-28T00:00:00Z"),
            ]
        )
        self.assertEqual(actions[0].number, 3)
        self.assertEqual(actions[0].kept, 8)

    def test_closing_comment_and_state_reason(self):
        self.assertEqual(
            closing_comment(11, PR),
            "Duplicate of #11, auto-generated by the radar workflow; "
            f"closing during dedupe. Generator fixed in {PR}.",
        )
        self.assertEqual(
            dedupe_close_payload(),
            {"state": "closed", "state_reason": "not_planned"},
        )
        with self.assertRaises(ValueError):
            validate_pr_url("https://example.invalid/pull/1")
        text = render_plan((DedupeAction(number=10, kept=11, title=TITLE),))
        self.assertIn("KEEP #11", text)
        self.assertIn("CLOSE #10", text)
        self.assertIn("not_planned", text)

    def test_listing_paginates_and_refuses_a_truncated_result(self):
        pages = {
            1: [{"number": index} for index in range(1, 101)],
            2: [{"number": 101}],
        }

        def fake_request(path, method="GET", payload=None):
            page = int(path.rsplit("page=", 1)[1])
            return pages.get(page, [])

        listed = list_open_issues(fake_request, "Zhanfg/UpstreamRadar", per_page=100)
        self.assertEqual(len(listed), 101)

        def always_full(path, method="GET", payload=None):
            return [{"number": 1}] * 2

        with self.assertRaises(RuntimeError):
            list_open_issues(
                always_full,
                "Zhanfg/UpstreamRadar",
                per_page=2,
                page_limit=1,
            )

    def test_reconcile_reuses_an_open_issue_instead_of_creating_one(self):
        state = {"incidents": {}}
        calls = []

        def create_issue(title, body):
            calls.append(("create", title))
            raise AssertionError("create must not run when an open issue matches")

        def comment(number, body):
            calls.append(("comment", number, body))

        def update_body(number, body):
            calls.append(("body", number, body))

        existing = issue(22, body="original evidence", created_at="2026-10-22T00:00:00Z")
        changed = reconcile_github_incident(
            state,
            key=KEY,
            title=TITLE,
            active=True,
            evidence={"mismatch_count": 2},
            now=NOW,
            cooldown_hours=12,
            open_issues=[existing],
            body="latest evidence",
            create_issue=create_issue,
            comment=comment,
            close_issue=lambda number: calls.append(("close", number)),
            update_body=update_body,
            update_comment="Governance evidence changed.",
            adopt_comment="Open governance incident reused.",
            close_comment="recovered",
        )
        self.assertEqual(changed, 1)
        self.assertEqual(state["incidents"][KEY]["external_id"], 22)
        self.assertEqual(state["incidents"][KEY]["status"], "open")
        self.assertEqual(calls[0][0], "body")
        self.assertEqual(marker_key(calls[0][2]), KEY)
        self.assertEqual(calls[1][0], "comment")
        self.assertIn("Open governance incident reused.", calls[1][2])
        self.assertNotIn(("create", TITLE), calls)

    def test_reconcile_skips_a_second_comment_when_the_fingerprint_matches(self):
        evidence = {"mismatch_count": 2}
        seeded = {"incidents": {}}
        existing = issue(22, body="original", created_at="2026-10-22T00:00:00Z")
        calls = []

        def comment(number, body):
            calls.append(body)

        def update_body(number, body):
            existing["body"] = body
            calls.append(("body", body))

        reconcile_github_incident(
            seeded,
            key=KEY,
            title=TITLE,
            active=True,
            evidence=evidence,
            now=NOW,
            cooldown_hours=12,
            open_issues=[existing],
            body="latest evidence",
            create_issue=lambda title, body: {"number": 99},
            comment=comment,
            close_issue=lambda number: None,
            update_body=update_body,
            update_comment="Governance evidence changed.",
            adopt_comment="Open governance incident reused.",
            close_comment="recovered",
        )
        calls.clear()
        lost_state = {"incidents": {}}
        again = reconcile_github_incident(
            lost_state,
            key=KEY,
            title=TITLE,
            active=True,
            evidence=evidence,
            now=NOW + timedelta(hours=1),
            cooldown_hours=12,
            open_issues=[existing],
            body="latest evidence",
            create_issue=lambda title, body: (_ for _ in ()).throw(AssertionError("create")),
            comment=lambda number, body: calls.append(("comment", body)),
            close_issue=lambda number: None,
            update_body=lambda number, body: calls.append(("body", body)),
            update_comment="Governance evidence changed.",
            adopt_comment="Open governance incident reused.",
            close_comment="recovered",
        )
        self.assertEqual(again, 0)
        self.assertEqual(calls, [])
        self.assertEqual(lost_state["incidents"][KEY]["external_id"], 22)
        self.assertEqual(lost_state["incidents"][KEY]["status"], "open")

    def test_reconcile_closes_the_tracked_issue_when_the_signal_recovers(self):
        fingerprint_body = updated_body_markers("evidence", KEY, "abc123def456")
        state = {
            "incidents": {
                KEY: {
                    "external_id": 8,
                    "status": "open",
                    "fingerprint": "abc123def456",
                    "last_action_at": (NOW - timedelta(hours=1)).isoformat(),
                }
            }
        }
        calls = []
        changed = reconcile_github_incident(
            state,
            key=KEY,
            title=TITLE,
            active=False,
            evidence={"mismatch_count": 0},
            now=NOW,
            cooldown_hours=12,
            open_issues=[issue(8, body=fingerprint_body), issue(9)],
            body="clear",
            create_issue=lambda title, body: {"number": 100},
            comment=lambda number, body: calls.append(("comment", number, body)),
            close_issue=lambda number: calls.append(("close", number)),
            update_body=lambda number, body: calls.append(("body", number)),
            update_comment="Governance evidence changed.",
            adopt_comment="Open governance incident reused.",
            close_comment="Activity Matrix Governance recovered.",
        )
        self.assertEqual(changed, 1)
        self.assertEqual(calls, [("comment", 8, "Activity Matrix Governance recovered."), ("close", 8)])
        self.assertEqual(state["incidents"][KEY]["status"], "closed")
        self.assertNotIn(9, [item[1] for item in calls if item[0] == "close"])

    def test_radar_failure_plan_reuses_an_exact_open_title(self):
        anomalies = [
            {"full_name": "openai/openai-python", "error_streak": 4, "message": "HTTPError: 503"},
            {"full_name": "openai/openai-python", "error_streak": 4, "message": "HTTPError: 503"},
            {"full_name": "git/git", "error_streak": 3, "message": "URLError"},
        ]
        open_issues = [
            issue(
                4,
                title="[radar] Repeated collection failure: openai/openai-python",
                login="Zhanfg",
            )
        ]
        planned = issues_to_open(anomalies, open_issues)
        self.assertEqual(len(planned), 1)
        self.assertEqual(planned[0]["title"], "[radar] Repeated collection failure: git/git")
        self.assertEqual(marker_key(planned[0]["body"]), "radar:git/git")

    def test_activity_executor_comments_on_the_newest_copy(self):
        from scripts import run_github_activity as activity_script
        from upstreamradar.activity import ActivityAction

        action = ActivityAction(
            kind="impact_issue",
            key="impact:example/kernel",
            priority=0.8,
            reason="test evidence",
            title="[impact] Investigate example/kernel",
            body="evidence",
        )
        older = issue(
            3,
            title=action.title,
            created_at="2026-10-01T00:00:00Z",
        )
        newer = issue(
            9,
            title=action.title,
            created_at=(datetime.now(timezone.utc) - timedelta(hours=30)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        )
        calls = []

        def fake_request(path, method="GET", payload=None):
            calls.append((path, method, payload))
            if path.endswith("/milestones?state=all&per_page=100"):
                return []
            if path.endswith("/issues/9/comments") and method == "POST":
                return {"id": 50}
            raise AssertionError(f"unexpected request: {path} {method}")

        with patch.object(activity_script, "open_issues", return_value=[older, newer]), patch.object(
            activity_script, "request", side_effect=fake_request
        ):
            record = activity_script.execute_issue(action, "2026-10-28T12:00:00+00:00")

        self.assertEqual(record["status"], "commented")
        self.assertTrue(any(path.endswith("/issues/9/comments") for path, _, _ in calls))
        self.assertFalse(any("/issues/3/" in path for path, _, _ in calls))


class DedupeCommandTests(unittest.TestCase):
    def test_apply_closes_with_not_planned_and_does_not_delete(self):
        from scripts import dedupe_github_issues as dedupe

        issues = [
            issue(10, created_at="2026-10-20T00:00:00Z"),
            issue(11, created_at="2026-10-28T00:00:00Z"),
        ]
        payloads = []

        def fake_request(path, method="GET", payload=None):
            payloads.append((path, method, payload))
            if method == "GET":
                return issues
            if path.endswith("/comments"):
                return {"id": 1}
            if method == "PATCH":
                return {"state": "closed"}
            raise AssertionError(method)

        with patch.object(dedupe, "TOKEN", "YOUR_TOKEN_HERE"), patch.object(
            dedupe, "request", side_effect=fake_request
        ), redirect_stdout(io.StringIO()):
            code = dedupe.main(
                ["--apply", "--pr-url", PR]
            )

        self.assertEqual(code, 0)
        methods = [method for _, method, _ in payloads]
        self.assertNotIn("DELETE", methods)
        patch_payloads = [payload for _, method, payload in payloads if method == "PATCH"]
        self.assertEqual(patch_payloads, [{"state": "closed", "state_reason": "not_planned"}])
        self.assertTrue(any(path.endswith("/issues/10/comments") for path, method, _ in payloads if method == "POST"))
        self.assertFalse(any("/issues/11" in path and method == "PATCH" for path, method, _ in payloads))

    def test_dry_run_does_not_write(self):
        from scripts import dedupe_github_issues as dedupe

        def fake_request(path, method="GET", payload=None):
            self.assertEqual(method, "GET")
            return [issue(1), issue(2, created_at="2026-10-28T00:00:00Z")]

        with patch.object(dedupe, "TOKEN", "YOUR_TOKEN_HERE"), patch.object(
            dedupe, "request", side_effect=fake_request
        ), redirect_stdout(io.StringIO()):
            code = dedupe.main(["--pr-url", PR])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
