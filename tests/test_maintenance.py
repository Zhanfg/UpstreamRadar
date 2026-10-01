import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from upstreamradar.maintenance import (
    action_reference_findings,
    ci_reliability,
    fork_sync_signal,
    stale_work_signal,
    workflow_reference_signal,
)


class MaintenanceIntelligenceTests(unittest.TestCase):
    def test_ci_reliability_detects_failure_rate(self):
        runs = [
            {
                "id": index,
                "status": "completed",
                "conclusion": "failure" if index < 3 else "success",
            }
            for index in range(10)
        ]
        signal = ci_reliability(
            runs,
            {
                "window_runs": 30,
                "min_completed_runs": 10,
                "failure_rate_threshold": 0.25,
                "consecutive_failure_threshold": 3,
            },
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.evidence["failure_count"], 3)
        self.assertEqual(signal.evidence["consecutive_failures"], 3)

    def test_ci_reliability_stays_quiet_when_healthy(self):
        runs = [
            {
                "id": index,
                "status": "completed",
                "conclusion": "failure" if index == 4 else "success",
            }
            for index in range(12)
        ]
        signal = ci_reliability(
            runs,
            {
                "window_runs": 30,
                "min_completed_runs": 10,
                "failure_rate_threshold": 0.25,
                "consecutive_failure_threshold": 3,
            },
        )
        self.assertFalse(signal.active)

    def test_fork_sync_detects_material_lag(self):
        signal = fork_sync_signal(
            [
                {
                    "fork": "org/a",
                    "upstream": "up/a",
                    "branch": "main",
                    "behind_by": 25,
                    "ahead_by": 0,
                    "status": "behind",
                },
                {
                    "fork": "org/b",
                    "upstream": "up/b",
                    "branch": "main",
                    "behind_by": 3,
                    "ahead_by": 0,
                    "status": "behind",
                },
            ],
            {
                "behind_commit_threshold": 20,
                "max_reported_forks": 10,
            },
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.evidence["affected_count"], 1)

    def test_stale_work_uses_different_issue_and_pr_windows(self):
        now = datetime(2026, 10, 1, 12, tzinfo=timezone.utc)
        items = [
            {
                "number": 1,
                "state": "open",
                "title": "old issue",
                "updated_at": "2026-09-01T00:00:00Z",
                "is_pull_request": False,
            },
            {
                "number": 2,
                "state": "open",
                "title": "old pr",
                "updated_at": "2026-09-20T00:00:00Z",
                "is_pull_request": True,
            },
            {
                "number": 3,
                "state": "open",
                "title": "fresh issue",
                "updated_at": "2026-09-30T00:00:00Z",
                "is_pull_request": False,
            },
        ]
        signal = stale_work_signal(
            items,
            {
                "issue_days": 14,
                "pull_request_days": 7,
                "incident_count_threshold": 2,
                "max_reported_items": 10,
            },
            now=now,
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.evidence["stale_count"], 2)

    def test_workflow_reference_scan_only_flags_floating_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "ci.yml").write_text(
                "jobs:\n"
                "  x:\n"
                "    steps:\n"
                "      - uses: actions/checkout@v4\n"
                "      - uses: vendor/action@main\n",
                encoding="utf-8",
            )
            findings = action_reference_findings(
                root,
                {
                    "forbid_floating": ["main", "master", "HEAD"],
                    "max_reported_items": 20,
                },
            )
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["action"], "vendor/action")

            signal = workflow_reference_signal(
                root,
                {
                    "forbid_floating": ["main", "master", "HEAD"],
                    "max_reported_items": 20,
                },
            )
            self.assertTrue(signal.active)


if __name__ == "__main__":
    unittest.main()
