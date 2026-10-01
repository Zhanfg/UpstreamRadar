import unittest
from datetime import datetime, timezone

from upstreamradar.activity import (
    current_cycle,
    plan_all,
    plan_scheduler_issue,
    plan_signal_issues,
    release_tag,
    weekly_release_due,
)


NOW = datetime(2026, 10, 1, 8, 0, tzinfo=timezone.utc)
CONFIG = {
    "signals": {
        "major_impact": 6.5,
        "critical_impact": 8.0,
        "recent_hours": 18,
        "max_new_issues_per_run": 2,
        "important_fields": [
            "latest_release",
            "latest_commit",
            "default_branch",
            "archived",
            "disabled",
            "license",
        ],
    },
    "scheduler": {"delay_multiplier": 2.5, "delay_hours": 4.0},
    "releases": {
        "enabled": True,
        "min_changed_observations": 50,
        "min_runs": 3,
        "tag_prefix": "radar",
    },
    "milestones": {"title_prefix": "Radar Cycle"},
}


def model(impact, delta, *, checked="2026-10-01T07:30:00Z", ewma=2.0, issues=0.1):
    return {
        "last_checked_at": checked,
        "last_semantic_impact": impact,
        "last_semantic_delta": list(delta),
        "ewma_impact": ewma,
        "ewma_issue_delta": issues,
        "breakage_risk": 0.0,
    }


class ActivityPlannerTests(unittest.TestCase):
    def test_material_gitlab_change_becomes_signal_issue(self):
        project = model(
            6.6,
            ("latest_commit", "last_activity_at", "open_issues"),
            checked="2026-10-01T06:23:40Z",
            ewma=6.7,
            issues=8.7,
        )
        state = {"projects": {"gitlab-org/gitlab": project}}
        items = plan_signal_issues(state, CONFIG, platform="gitlab", now=NOW)
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].target, "gitlab-org/gitlab")
        self.assertIn("activity:signal", items[0].labels)

    def test_crowd_only_noise_does_not_open_issue_below_critical(self):
        repo = model(6.7, ("stars", "forks", "watchers"))
        state = {"repositories": {"example/noise": repo}}
        items = plan_signal_issues(state, CONFIG, platform="github", now=NOW)
        self.assertEqual(items, ())

    def test_critical_impact_can_override_field_gate(self):
        repo = model(8.2, ("stars", "forks", "watchers"), ewma=7.0, issues=4.0)
        state = {"repositories": {"example/critical": repo}}
        items = plan_signal_issues(state, CONFIG, platform="github", now=NOW)
        self.assertEqual(len(items), 1)
        self.assertIn("priority:high", items[0].labels)

    def test_scheduler_delay_requires_both_thresholds(self):
        delayed_scheduler = {
            "last_catch_up_multiplier": 2.5,
            "last_elapsed_hours": 5.9,
            "last_run_at": "2026-10-01T06:00:00Z",
        }
        delayed = {"scheduler": delayed_scheduler}
        self.assertIsNotNone(
            plan_scheduler_issue(delayed, CONFIG, platform="gitlab", now=NOW)
        )

        recovered_scheduler = {
            "last_catch_up_multiplier": 1.4,
            "last_elapsed_hours": 1.1,
            "last_run_at": "2026-10-01T07:00:00Z",
        }
        recovered = {"scheduler": recovered_scheduler}
        self.assertIsNone(
            plan_scheduler_issue(recovered, CONFIG, platform="gitlab", now=NOW)
        )

    def test_weekly_release_requires_real_volume(self):
        daily = {
            "2026-09-29": {"runs": 2, "scanned": 22, "changed": 12, "errors": 0},
            "2026-09-30": {"runs": 16, "scanned": 181, "changed": 65, "errors": 0},
            "2026-10-01": {"runs": 4, "scanned": 48, "changed": 39, "errors": 0},
        }
        due, metrics = weekly_release_due({"daily": daily}, CONFIG, now=NOW)
        self.assertTrue(due)
        self.assertEqual(metrics["changed"], 116)
        self.assertEqual(metrics["runs"], 22)

    def test_weekly_release_does_not_emit_for_empty_period(self):
        daily = {
            "2026-10-01": {"runs": 1, "scanned": 8, "changed": 3, "errors": 0}
        }
        due, metrics = weekly_release_due({"daily": daily}, CONFIG, now=NOW)
        self.assertFalse(due)
        self.assertEqual(metrics["changed"], 3)

    def test_cycle_and_tag_are_deterministic(self):
        self.assertEqual(current_cycle(NOW), "2026-W40")
        self.assertEqual(release_tag(NOW, CONFIG), "radar-2026-W40")

    def test_plan_all_orders_highest_priority_first(self):
        high = model(
            9.0,
            ("latest_commit",),
            checked="2026-10-01T07:00:00Z",
            ewma=8.0,
            issues=6.0,
        )
        medium = model(
            6.6,
            ("latest_commit",),
            checked="2026-10-01T07:00:00Z",
            ewma=5.0,
            issues=1.0,
        )
        state = {
            "projects": {"a/high": high, "b/medium": medium},
            "scheduler": {
                "last_catch_up_multiplier": 1.0,
                "last_elapsed_hours": 0.5,
            },
        }
        items = plan_all(state, CONFIG, platform="gitlab", now=NOW)
        self.assertEqual(items[0].target, "a/high")
        self.assertGreater(items[0].priority, items[1].priority)


if __name__ == "__main__":
    unittest.main()
