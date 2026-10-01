import unittest
from datetime import datetime, timedelta, timezone

from upstreamradar.downstream import (
    decide_action,
    plan_downstream_impacts,
    recent_action_count,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)
CONFIG = {
    "policy": {
        "min_semantic_impact": 6.0,
        "critical_impact": 8.0,
        "important_fields": ["latest_release", "latest_commit", "default_branch"],
        "max_plans_per_run": 10,
        "update_cooldown_hours": 24,
        "create_cooldown_hours": 168,
    },
    "targets": [
        {
            "repo": "Zhanfg/mihomo",
            "sources": ["MetaCubeX/mihomo"],
            "checklist": ["re-run TUN compatibility", "re-run switch stress tests"],
        },
        {
            "repo": "Zhanfg/Bettbox",
            "sources": ["MetaCubeX/mihomo"],
            "checklist": ["re-run rootless VPN stability"],
        },
    ],
}


class DownstreamImpactTests(unittest.TestCase):
    def sample_run(self, *, impact=7.0, fields=None):
        return {
            "observed_at": "2026-10-01T11:00:00Z",
            "changed_details": [
                {
                    "full_name": "MetaCubeX/mihomo",
                    "semantic_impact": impact,
                    "fields": fields or ["latest_release", "pushed_at"],
                }
            ],
            "content_plan": [
                {
                    "name": "MetaCubeX/mihomo",
                    "reasons": ["regime-shift", "high-content-yield"],
                }
            ],
        }

    def test_explicit_mapping_generates_only_mapped_targets(self):
        plans = plan_downstream_impacts(
            self.sample_run(),
            CONFIG,
            platform="github",
        )
        self.assertEqual(
            {plan.downstream for plan in plans},
            {"Zhanfg/mihomo", "Zhanfg/Bettbox"},
        )
        self.assertTrue(all(plan.upstream == "MetaCubeX/mihomo" for plan in plans))

    def test_low_impact_is_ignored(self):
        plans = plan_downstream_impacts(
            self.sample_run(impact=4.0),
            CONFIG,
            platform="github",
        )
        self.assertEqual(plans, ())

    def test_non_important_fields_require_critical_impact(self):
        plans = plan_downstream_impacts(
            self.sample_run(impact=7.0, fields=["stars", "forks"]),
            CONFIG,
            platform="github",
        )
        self.assertEqual(plans, ())

        critical = plan_downstream_impacts(
            self.sample_run(impact=8.2, fields=["stars", "forks"]),
            CONFIG,
            platform="github",
        )
        self.assertEqual(len(critical), 2)

    def test_same_evidence_is_deduplicated(self):
        plan = plan_downstream_impacts(
            self.sample_run(),
            CONFIG,
            platform="github",
        )[0]
        record = {
            "status": "open",
            "evidence_hash": plan.evidence_hash,
            "last_action_at": (NOW - timedelta(days=2)).isoformat(),
        }
        decision = decide_action(record, plan, CONFIG["policy"], now=NOW)
        self.assertEqual(decision.action, "none")

    def test_changed_open_issue_updates_after_cooldown(self):
        plan = plan_downstream_impacts(
            self.sample_run(),
            CONFIG,
            platform="github",
        )[0]
        record = {
            "status": "open",
            "evidence_hash": "old",
            "last_action_at": (NOW - timedelta(hours=25)).isoformat(),
        }
        decision = decide_action(record, plan, CONFIG["policy"], now=NOW)
        self.assertEqual(decision.action, "update")

    def test_closed_issue_requires_longer_create_cooldown(self):
        plan = plan_downstream_impacts(
            self.sample_run(),
            CONFIG,
            platform="github",
        )[0]
        recent = {
            "status": "closed",
            "evidence_hash": "old",
            "last_action_at": (NOW - timedelta(days=2)).isoformat(),
        }
        self.assertEqual(
            decide_action(recent, plan, CONFIG["policy"], now=NOW).action,
            "none",
        )

        old = {
            **recent,
            "last_action_at": (NOW - timedelta(days=8)).isoformat(),
        }
        self.assertEqual(
            decide_action(old, plan, CONFIG["policy"], now=NOW).action,
            "create",
        )

    def test_recent_action_count_uses_rolling_window(self):
        history = [
            {"created_at": (NOW - timedelta(hours=2)).isoformat()},
            {"created_at": (NOW - timedelta(hours=30)).isoformat()},
        ]
        self.assertEqual(recent_action_count(history, now=NOW), 1)


if __name__ == "__main__":
    unittest.main()
