import unittest
from datetime import datetime, timezone

from upstreamradar.activity import ActivityEvidence, plan_actions


CONFIG = {
    'daily_budget': {
        'impact_issue': 2,
        'benchmark': 2,
        'wiki': 1,
        'release': 1,
    },
    'cooldown_hours': {
        'impact_issue': 72,
        'benchmark': 12,
        'wiki': 24,
        'release': 168,
    },
    'thresholds': {
        'impact_issue': 4.0,
        'benchmark_changed': 1,
        'wiki_changed': 3,
        'wiki_content_score': 0.65,
        'release_changed': 10,
        'release_impact': 4.0,
    },
    'surfaces': {
        'github': {
            'issues': True,
            'benchmark': True,
            'wiki': True,
            'release': True,
        }
    },
}


class ActivityMatrixTests(unittest.TestCase):
    def evidence(self, **overrides):
        base = dict(
            platform='github',
            observed_at='2026-10-01T08:00:00Z',
            changed_count=14,
            error_count=0,
            coverage_score=0.78,
            content_score=0.82,
            top_name='example/kernel',
            top_impact=6.2,
            top_fields=('latest_release', 'pushed_at'),
            top_reasons=('regime-shift', 'security-focus'),
            content_opportunities=6,
            fork_queue_count=5,
        )
        base.update(overrides)
        return ActivityEvidence(**base)

    def test_major_real_change_spans_multiple_surfaces(self):
        actions = plan_actions(
            self.evidence(),
            [],
            CONFIG,
            now=datetime(2026, 10, 1, 8, tzinfo=timezone.utc),
        )
        self.assertEqual(
            {item.kind for item in actions},
            {'impact_issue', 'benchmark', 'wiki', 'release', 'milestone'},
        )

    def test_low_information_cycle_only_benchmarks(self):
        actions = plan_actions(
            self.evidence(changed_count=1, content_score=0.2, top_impact=0.5, top_reasons=()),
            [],
            CONFIG,
            now=datetime(2026, 10, 1, 8, tzinfo=timezone.utc),
        )
        self.assertEqual([item.kind for item in actions], ['benchmark'])

    def test_cooldown_prevents_repeated_issue_and_release(self):
        history = [
            {
                'kind': 'impact_issue',
                'key': 'impact:example/kernel',
                'created_at': '2026-09-30T08:00:00Z',
            },
            {
                'kind': 'release',
                'key': 'release:intelligence',
                'created_at': '2026-09-29T08:00:00Z',
            },
        ]
        actions = plan_actions(
            self.evidence(),
            history,
            CONFIG,
            now=datetime(2026, 10, 1, 8, tzinfo=timezone.utc),
        )
        kinds = {item.kind for item in actions}
        self.assertNotIn('impact_issue', kinds)
        self.assertNotIn('release', kinds)
        self.assertIn('benchmark', kinds)

    def test_daily_budget_blocks_wiki_spam(self):
        history = [
            {
                'kind': 'wiki',
                'key': 'wiki:2026-10-01',
                'created_at': '2026-10-01T01:00:00Z',
            }
        ]
        actions = plan_actions(
            self.evidence(),
            history,
            CONFIG,
            now=datetime(2026, 10, 1, 8, tzinfo=timezone.utc),
        )
        self.assertNotIn('wiki', {item.kind for item in actions})


if __name__ == '__main__':
    unittest.main()
