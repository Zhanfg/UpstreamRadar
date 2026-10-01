import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from scripts import run_github_activity as activity_script
from upstreamradar.activity import ActivityAction


class GitHubActivityExecutorTests(unittest.TestCase):
    def issue_action(self):
        return ActivityAction(
            kind="impact_issue",
            key="impact:example/kernel",
            priority=0.8,
            reason="test evidence",
            title="[impact] Investigate example/kernel",
            body="evidence",
        )

    def test_recent_existing_issue_is_not_commented_again(self):
        now = datetime.now(timezone.utc).replace(microsecond=0)
        issue = {
            "number": 42,
            "title": "[impact] Investigate example/kernel",
            "created_at": now.isoformat().replace("+00:00", "Z"),
            "milestone": None,
        }
        milestone = {"number": 7, "title": f"Intelligence Cycle {now.strftime('%Y-%m')}"}
        calls = []

        def fake_request(path, method="GET", payload=None):
            calls.append((path, method, payload))
            if path.endswith("/milestones?state=all&per_page=100"):
                return [milestone]
            if path.endswith("/issues/42") and method == "PATCH":
                return {**issue, "milestone": milestone}
            raise AssertionError(f"unexpected request: {path} {method}")

        with patch.object(activity_script, "open_issues", return_value=[issue]), patch.object(
            activity_script, "request", side_effect=fake_request
        ):
            record = activity_script.execute_issue(
                self.issue_action(),
                now.isoformat(),
            )

        self.assertEqual(record["status"], "exists")
        self.assertEqual(record["external_id"], "42")
        self.assertTrue(any(method == "PATCH" for _, method, _ in calls))
        self.assertFalse(any(path.endswith("/comments") for path, _, _ in calls))

    def test_wiki_action_always_writes_durable_fallback(self):
        action = ActivityAction(
            kind="wiki",
            key="wiki:2026-10-01",
            priority=0.7,
            reason="test evidence",
            title="Radar Intelligence 2026-10-01",
            body="# Evidence\n",
        )
        now = datetime(2026, 10, 1, 10, tzinfo=timezone.utc)

        with tempfile.TemporaryDirectory() as directory:
            previous = os.getcwd()
            os.chdir(directory)
            try:
                record = activity_script.execute_wiki(
                    action,
                    now,
                    now.isoformat(),
                )
                fallback = Path(
                    "reports/activity/wiki/github/2026-10-01.md"
                )
                self.assertTrue(fallback.exists())
                self.assertIn("# Evidence", fallback.read_text())
                self.assertEqual(record["status"], "prepared")
            finally:
                os.chdir(previous)


if __name__ == "__main__":
    unittest.main()
