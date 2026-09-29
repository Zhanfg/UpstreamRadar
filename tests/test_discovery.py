import unittest
from datetime import datetime, timezone

from upstreamradar.discovery import (
    classify,
    merge_candidates,
    score_repository,
    should_auto_fork,
)

CONFIG = {
    "fork_policy": {
        "auto_fork_threshold": 0.80,
        "min_stars": 8,
        "max_age_days_since_push": 180,
        "prefer_known_license": True,
    },
    "categories": [
        {"id": "networking", "keywords": ["proxy", "quic", "tun"], "weight": 1.0},
        {"id": "ai-agents", "keywords": ["agent", "mcp"], "weight": 0.95},
    ],
    "exclusions": {"keywords": [], "name_prefixes": ["awesome-"]},
}


class DiscoveryTests(unittest.TestCase):
    def test_classifies_direction(self):
        category, score, matches = classify(
            {"name": "fast-quic-proxy", "description": "Userspace TUN proxy"},
            CONFIG,
        )
        self.assertEqual(category, "networking")
        self.assertGreater(score, 0)
        self.assertIn("proxy", matches)

    def test_recent_relevant_repo_scores_and_can_fork(self):
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        repo = {
            "id": 1,
            "name": "quic-proxy",
            "full_name": "example/quic-proxy",
            "description": "High performance QUIC TUN proxy",
            "html_url": "https://github.com/example/quic-proxy",
            "stargazers_count": 800,
            "forks_count": 120,
            "pushed_at": "2026-09-28T00:00:00Z",
            "license": {"spdx_id": "Apache-2.0"},
            "fork": False,
            "archived": False,
        }
        candidate = score_repository(repo, CONFIG, platform="github", now=now)
        self.assertIsNotNone(candidate)
        self.assertTrue(should_auto_fork(candidate, CONFIG, now=now))

    def test_unknown_license_blocks_auto_fork(self):
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        repo = {
            "id": 2,
            "name": "mcp-agent",
            "full_name": "example/mcp-agent",
            "description": "MCP coding agent orchestration runtime",
            "html_url": "https://github.com/example/mcp-agent",
            "stargazers_count": 900,
            "forks_count": 200,
            "pushed_at": "2026-09-28T00:00:00Z",
            "fork": False,
        }
        candidate = score_repository(repo, CONFIG, platform="github", now=now)
        self.assertIsNotNone(candidate)
        self.assertFalse(should_auto_fork(candidate, CONFIG, now=now))

    def test_excludes_awesome_lists(self):
        self.assertIsNone(
            score_repository(
                {
                    "name": "awesome-proxy",
                    "description": "proxy links",
                    "stargazers_count": 5000,
                },
                CONFIG,
                platform="github",
            )
        )

    def test_merge_deduplicates(self):
        now = datetime(2026, 9, 29, tzinfo=timezone.utc)
        base = {
            "name": "quic-proxy",
            "full_name": "example/quic-proxy",
            "description": "QUIC TUN proxy",
            "html_url": "x",
            "stargazers_count": 100,
            "forks_count": 20,
            "pushed_at": "2026-09-28T00:00:00Z",
            "license": {"spdx_id": "MIT"},
        }
        a = score_repository(base, CONFIG, platform="github", now=now)
        b = score_repository(dict(base, stargazers_count=200), CONFIG, platform="github", now=now)
        merged = merge_candidates((a, b))
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].stars, 200)


if __name__ == "__main__":
    unittest.main()
