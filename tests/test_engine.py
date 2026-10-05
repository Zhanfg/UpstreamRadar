import unittest

from upstreamradar.engine import HarmonyConfig, HarmonyScheduler, RepositorySignal


class HarmonySchedulerTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = HarmonyScheduler(HarmonyConfig(beam_width=128))
        self.records = [
            RepositorySignal(
                name="android-kernel",
                ecosystem="android",
                cost=4,
                freshness_hours=2,
                commit_velocity=14,
                release_velocity=3,
                issue_velocity=7,
                security_signal=9,
                breakage_risk=8,
                dependency_importance=10,
                maintainer_activity=9,
                novelty=7,
                recent_change_hits=8,
                recent_change_misses=2,
            ),
            RepositorySignal(
                name="framework",
                ecosystem="android",
                cost=3,
                freshness_hours=6,
                commit_velocity=10,
                release_velocity=2,
                issue_velocity=6,
                security_signal=4,
                breakage_risk=7,
                dependency_importance=8,
                maintainer_activity=8,
                novelty=6,
                recent_change_hits=6,
                recent_change_misses=3,
            ),
            RepositorySignal(
                name="linux",
                ecosystem="kernel",
                cost=5,
                freshness_hours=1,
                commit_velocity=18,
                release_velocity=4,
                issue_velocity=5,
                security_signal=8,
                breakage_risk=8,
                dependency_importance=10,
                maintainer_activity=10,
                novelty=8,
                recent_change_hits=9,
                recent_change_misses=1,
            ),
            RepositorySignal(
                name="net-next",
                ecosystem="kernel",
                cost=2,
                freshness_hours=3,
                commit_velocity=12,
                release_velocity=1,
                issue_velocity=5,
                security_signal=5,
                breakage_risk=6,
                dependency_importance=7,
                maintainer_activity=9,
                novelty=7,
                recent_change_hits=7,
                recent_change_misses=2,
            ),
            RepositorySignal(
                name="agent-runtime",
                ecosystem="ai",
                cost=3,
                freshness_hours=10,
                commit_velocity=9,
                release_velocity=5,
                issue_velocity=8,
                security_signal=3,
                breakage_risk=5,
                dependency_importance=5,
                maintainer_activity=7,
                novelty=10,
                recent_change_hits=5,
                recent_change_misses=5,
            ),
            RepositorySignal(
                name="tool-protocol",
                ecosystem="ai",
                cost=2,
                freshness_hours=12,
                commit_velocity=7,
                release_velocity=4,
                issue_velocity=6,
                security_signal=2,
                breakage_risk=4,
                dependency_importance=6,
                maintainer_activity=6,
                novelty=9,
                recent_change_hits=4,
                recent_change_misses=6,
            ),
        ]
        self.dependencies = {
            "framework": ["android-kernel"],
            "android-kernel": ["linux"],
            "net-next": ["linux"],
            "agent-runtime": ["tool-protocol"],
        }

    def test_score_is_deterministic_and_finite(self):
        first = self.scheduler.score(self.records, self.dependencies)
        second = self.scheduler.score(self.records, self.dependencies)
        self.assertEqual(first, second)
        self.assertEqual(len(first), len(self.records))
        self.assertTrue(all(s.base_utility > 0 for s in first))

    def test_dependency_hub_receives_graph_influence(self):
        scores = {
            score.name: score
            for score in self.scheduler.score(self.records, self.dependencies)
        }
        self.assertGreater(
            scores["linux"].graph_influence,
            scores["agent-runtime"].graph_influence,
        )

    def test_v3_evidence_dimensions_are_bounded(self):
        scores = self.scheduler.score(self.records, self.dependencies)
        for score in scores:
            self.assertGreaterEqual(score.bayesian_surprise, 0.0)
            self.assertLessEqual(score.bayesian_surprise, 1.0)
            self.assertGreaterEqual(score.structural_novelty, 0.0)
            self.assertLessEqual(score.structural_novelty, 1.0)
            self.assertGreaterEqual(score.tail_risk, 0.0)
            self.assertLessEqual(score.tail_risk, 1.0)
            self.assertGreater(score.risk_adjusted_utility, 0.0)

    def test_high_failure_streak_increases_tail_risk(self):
        stable = RepositorySignal(
            name="stable",
            ecosystem="test",
            cost=1,
            freshness_hours=1,
            security_signal=2,
            breakage_risk=2,
            impact_history=(1, 1, 2, 1),
            failure_streak=0,
        )
        unstable = RepositorySignal(
            name="unstable",
            ecosystem="test",
            cost=1,
            freshness_hours=1,
            security_signal=2,
            breakage_risk=2,
            impact_history=(1, 1, 2, 1),
            failure_streak=7,
        )
        scores = {item.name: item for item in self.scheduler.score([stable, unstable])}
        self.assertGreater(scores["unstable"].tail_risk, scores["stable"].tail_risk)

    def test_structural_novelty_rewards_rare_dependency_shape(self):
        records = [
            RepositorySignal(name="a", ecosystem="x", cost=1, freshness_hours=1, novelty=5),
            RepositorySignal(name="b", ecosystem="x", cost=1, freshness_hours=1, novelty=5),
            RepositorySignal(name="c", ecosystem="x", cost=1, freshness_hours=1, novelty=5),
        ]
        deps = {"a": ["shared"], "b": ["shared"], "c": ["rare", "unique"]}
        scores = {item.name: item for item in self.scheduler.score(records, deps)}
        self.assertGreater(scores["c"].structural_novelty, scores["a"].structural_novelty)

    def test_budget_and_ecosystem_constraints(self):
        result = self.scheduler.schedule(
            self.records,
            budget=12,
            dependencies=self.dependencies,
            min_per_ecosystem={"android": 1, "kernel": 1, "ai": 1},
            max_per_ecosystem={"android": 2, "kernel": 2, "ai": 2},
        )
        self.assertLessEqual(result.total_cost, 12)
        self.assertGreaterEqual(result.ecosystem_counts["android"], 1)
        self.assertGreaterEqual(result.ecosystem_counts["kernel"], 1)
        self.assertGreaterEqual(result.ecosystem_counts["ai"], 1)
        self.assertGreater(result.explored_states, 1)

    def test_impossible_minimums_raise(self):
        with self.assertRaises(ValueError):
            self.scheduler.schedule(
                self.records,
                budget=2,
                dependencies=self.dependencies,
                min_per_ecosystem={"android": 1, "kernel": 1, "ai": 1},
            )

    def test_duplicate_names_raise(self):
        duplicated = [self.records[0], self.records[0]]
        with self.assertRaises(ValueError):
            self.scheduler.score(duplicated)

    def test_zero_budget_returns_empty_schedule(self):
        result = self.scheduler.schedule(
            self.records,
            budget=0,
            dependencies=self.dependencies,
        )
        self.assertEqual(result.selected, ())
        self.assertEqual(result.total_cost, 0)


if __name__ == "__main__":
    unittest.main()
