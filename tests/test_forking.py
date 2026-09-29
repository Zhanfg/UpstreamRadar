import unittest
from datetime import datetime, timezone

from upstreamradar.forking import fork_capacity, resolve_destination, select_fork_batch


CONFIG = {
    "fork_policy": {
        "max_forks_per_day_per_platform": 1,
        "max_forks_per_week_per_platform": 5,
    },
    "destinations": {
        "github_organization": None,
        "gitlab_namespace_path": None,
        "personal_fallback": False,
        "category_collections": {"networking": "networking"},
    },
}


class ForkPlanningTests(unittest.TestCase):
    def test_no_namespace_means_no_fork_plan(self):
        queue = [{
            "platform": "github",
            "full_name": "example/proxy",
            "source_id": "1",
            "category": "networking",
            "score": 0.95,
            "auto_fork_eligible": True,
        }]
        self.assertEqual(
            select_fork_batch(queue, [], CONFIG, platform="github"),
            (),
        )

    def test_verified_namespace_configuration_targets_both_platforms(self):
        import json
        from pathlib import Path

        config = json.loads(Path("config/discovery.json").read_text())
        self.assertEqual(
            config["destinations"]["github_organization"],
            "yuezhou-build",
        )
        self.assertEqual(
            config["destinations"]["gitlab_namespace_path"],
            "axymorrsen-labs",
        )
        self.assertFalse(config["destinations"]["personal_fallback"])

    def test_personal_fallback_must_be_explicit(self):
        config = {
            **CONFIG,
            "destinations": {
                **CONFIG["destinations"],
                "personal_fallback": True,
            },
        }
        self.assertEqual(
            resolve_destination(
                config,
                platform="github",
                personal_namespace="user",
            ),
            "user",
        )

    def test_daily_limit_blocks_second_fork(self):
        now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        history = [{
            "platform": "github",
            "full_name": "a/b",
            "status": "forked",
            "created_at": "2026-09-29T10:00:00Z",
        }]
        self.assertEqual(
            fork_capacity(history, CONFIG, platform="github", now=now)[0],
            0,
        )

    def test_selects_highest_score_with_collection(self):
        now = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
        config = {
            **CONFIG,
            "destinations": {
                **CONFIG["destinations"],
                "github_organization": "example-org",
            },
        }
        queue = [
            {
                "platform": "github",
                "full_name": "low/proxy",
                "source_id": "1",
                "category": "networking",
                "score": 0.88,
                "auto_fork_eligible": True,
            },
            {
                "platform": "github",
                "full_name": "high/proxy",
                "source_id": "2",
                "category": "networking",
                "score": 0.96,
                "auto_fork_eligible": True,
            },
        ]
        plans = select_fork_batch(
            queue,
            [],
            config,
            platform="github",
            now=now,
        )
        self.assertEqual(len(plans), 1)
        self.assertEqual(plans[0].full_name, "high/proxy")
        self.assertEqual(plans[0].collection, "networking")


if __name__ == "__main__":
    unittest.main()
