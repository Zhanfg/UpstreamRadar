import math
import unittest

from upstreamradar.engine import HarmonyConfig, HarmonyScheduler, RepositorySignal


class HarmonyV2StressTests(unittest.TestCase):
    @staticmethod
    def records(count=60):
        ecosystems = ("kernel", "android", "ai", "network", "security", "tooling")
        items = []
        for index in range(count):
            history = tuple(
                int(((index * 3 + step * 5) % 11) > 6)
                for step in range(12)
            )
            impact = tuple(
                float(((index * 7 + step * 3) % 10) if history[step] else 0)
                for step in range(12)
            )
            hits = sum(history)
            items.append(
                RepositorySignal(
                    name=f"repo-{index:03d}",
                    ecosystem=ecosystems[index % len(ecosystems)],
                    cost=1 + index % 4,
                    freshness_hours=float(index % 18),
                    commit_velocity=float((index * 7) % 19),
                    release_velocity=float((index * 5) % 9),
                    issue_velocity=float((index * 11) % 13),
                    security_signal=float((index * 3) % 10),
                    breakage_risk=float((index * 2) % 8),
                    dependency_importance=float((index * 5) % 10),
                    maintainer_activity=float((index * 13) % 17),
                    novelty=float((index * 17) % 10),
                    recent_change_hits=hits,
                    recent_change_misses=len(history) - hits,
                    change_history=history,
                    impact_history=impact,
                    observation_count=4 + index,
                    content_signal=sum(impact) / len(impact),
                    source_reliability=0.8 + 0.2 * ((index % 5) / 4),
                    failure_streak=index % 3,
                )
            )
        return tuple(items)

    @staticmethod
    def dependencies(records):
        names = [item.name for item in records]
        graph = {}
        for index, name in enumerate(names):
            graph[name] = (
                names[(index + 1) % len(names)],
                names[(index + 7) % len(names)],
                names[(index + 17) % len(names)],
            )
        return graph

    def test_large_schedule_is_permutation_invariant(self):
        records = self.records()
        dependencies = self.dependencies(records)
        scheduler = HarmonyScheduler(
            HarmonyConfig(
                beam_width=64,
                pagerank_steps=24,
            )
        )

        forward = scheduler.schedule(
            records,
            budget=34,
            dependencies=dependencies,
            max_per_ecosystem={
                "kernel": 5,
                "android": 5,
                "ai": 5,
                "network": 5,
                "security": 5,
                "tooling": 5,
            },
        )
        reverse = scheduler.schedule(
            tuple(reversed(records)),
            budget=34,
            dependencies=dependencies,
            max_per_ecosystem={
                "kernel": 5,
                "android": 5,
                "ai": 5,
                "network": 5,
                "security": 5,
                "tooling": 5,
            },
        )

        self.assertEqual(
            tuple(item.name for item in forward.selected),
            tuple(item.name for item in reverse.selected),
        )
        self.assertEqual(forward.total_cost, reverse.total_cost)
        self.assertAlmostEqual(forward.total_utility, reverse.total_utility, places=12)

    def test_large_schedule_metrics_remain_bounded_and_finite(self):
        records = self.records()
        scheduler = HarmonyScheduler(HarmonyConfig(beam_width=48, pagerank_steps=18))
        result = scheduler.schedule(
            records,
            budget=28,
            dependencies=self.dependencies(records),
        )

        self.assertTrue(math.isfinite(result.total_utility))
        self.assertGreaterEqual(result.coverage_score, 0.0)
        self.assertLessEqual(result.coverage_score, 1.0)
        self.assertGreaterEqual(result.content_score, 0.0)
        self.assertLessEqual(result.content_score, 1.0)
        for score in result.selected:
            self.assertTrue(math.isfinite(score.base_utility))
            self.assertGreaterEqual(score.reliability, 0.0)
            self.assertLessEqual(score.reliability, 1.0)

    def test_single_member_ecosystems_do_not_explode(self):
        records = tuple(
            RepositorySignal(
                name=f"solo-{index}",
                ecosystem=f"eco-{index}",
                cost=1,
                freshness_hours=0,
                commit_velocity=float(index * 1000),
                security_signal=float(index * 500),
                content_signal=float(index * 750),
                change_history=(0, 1, 1),
                impact_history=(0, 8, 10),
                observation_count=3,
            )
            for index in range(8)
        )
        scores = HarmonyScheduler().score(records)
        self.assertEqual(len(scores), len(records))
        for score in scores:
            self.assertTrue(math.isfinite(score.base_utility))
            self.assertGreaterEqual(score.base_utility, 0.0)


if __name__ == "__main__":
    unittest.main()
