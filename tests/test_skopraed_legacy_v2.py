import unittest

from upstreamradar.content import build_content_plan
from upstreamradar.engine import SkopraedConfig, SkopraedScheduler, RepositorySignal


class SkopraedLegacyV2Tests(unittest.TestCase):
    def setUp(self):
        self.scheduler = SkopraedScheduler(SkopraedConfig(beam_width=96))

    def record(self, name, *, history, impact, observations=12, failures=0, content=5.0):
        hits = sum(int(bool(value)) for value in history)
        misses = len(history) - hits
        return RepositorySignal(
            name=name,
            ecosystem="test",
            cost=2,
            freshness_hours=1,
            commit_velocity=8,
            release_velocity=4,
            issue_velocity=5,
            security_signal=5,
            breakage_risk=4,
            dependency_importance=6,
            maintainer_activity=7,
            novelty=5,
            recent_change_hits=hits,
            recent_change_misses=misses,
            change_history=tuple(history),
            impact_history=tuple(impact),
            observation_count=observations,
            content_signal=content,
            source_reliability=1.0,
            failure_streak=failures,
        )

    def test_regime_shift_scores_above_flat_history(self):
        flat = self.record(
            "flat",
            history=(0, 0, 0, 0, 0, 0),
            impact=(1, 1, 1, 1, 1, 1),
        )
        shift = self.record(
            "shift",
            history=(0, 0, 0, 1, 1, 1),
            impact=(0, 0, 0, 7, 9, 10),
        )
        scores = {score.name: score for score in self.scheduler.score((flat, shift))}
        self.assertGreater(scores["shift"].change_point, scores["flat"].change_point)
        self.assertIn("regime-shift", scores["shift"].reasons)

    def test_failure_streak_reduces_reliability_and_utility(self):
        healthy = self.record(
            "healthy",
            history=(0, 1, 0, 1),
            impact=(0, 5, 0, 5),
            failures=0,
        )
        failing = self.record(
            "failing",
            history=(0, 1, 0, 1),
            impact=(0, 5, 0, 5),
            failures=6,
        )
        scores = {score.name: score for score in self.scheduler.score((healthy, failing))}
        self.assertGreater(scores["healthy"].reliability, scores["failing"].reliability)
        self.assertGreater(scores["healthy"].base_utility, scores["failing"].base_utility)

    def test_exploration_decays_with_observation_count(self):
        new = self.record(
            "new",
            history=(0, 1),
            impact=(0, 5),
            observations=1,
        )
        known = self.record(
            "known",
            history=(0, 1),
            impact=(0, 5),
            observations=100,
        )
        scores = {score.name: score for score in self.scheduler.score((new, known))}
        self.assertGreater(scores["new"].exploration, scores["known"].exploration)

    def test_schedule_exposes_coverage_and_content_quality(self):
        records = (
            self.record("kernel", history=(0, 0, 1, 1), impact=(0, 0, 8, 9), content=9),
            RepositorySignal(
                name="framework",
                ecosystem="android",
                cost=2,
                freshness_hours=2,
                commit_velocity=7,
                dependency_importance=7,
                change_history=(0, 1, 1, 0),
                impact_history=(0, 5, 7, 0),
                observation_count=10,
                content_signal=7,
            ),
            RepositorySignal(
                name="agent",
                ecosystem="ai",
                cost=2,
                freshness_hours=3,
                commit_velocity=6,
                novelty=9,
                change_history=(0, 1, 0, 1),
                impact_history=(0, 4, 0, 5),
                observation_count=6,
                content_signal=6,
            ),
        )
        result = self.scheduler.schedule(
            records,
            budget=4,
            dependencies={"framework": ("kernel",)},
        )
        self.assertLessEqual(result.total_cost, 4)
        self.assertGreater(result.coverage_score, 0.0)
        self.assertGreater(result.content_score, 0.0)

    def test_content_plan_is_evidence_first(self):
        records = (
            self.record(
                "interesting",
                history=(0, 0, 1, 1, 1),
                impact=(0, 0, 6, 8, 10),
                content=9,
            ),
            self.record(
                "quiet",
                history=(0, 0, 0, 0, 0),
                impact=(0, 0, 0, 0, 0),
                content=1,
            ),
        )
        scores = self.scheduler.score(records)
        plan = build_content_plan(scores, limit=2)
        self.assertEqual(plan[0].name, "interesting")
        self.assertTrue(plan[0].evidence)
        self.assertTrue(plan[0].angle)

    def test_v1_config_names_remain_supported(self):
        config = SkopraedConfig(
            pagerank_damping=0.83,
            pagerank_steps=20,
            beam_width=32,
        )
        scheduler = SkopraedScheduler(config)
        result = scheduler.schedule(
            (self.record("one", history=(0, 1), impact=(0, 4)),),
            budget=2,
        )
        self.assertEqual(len(result.selected), 1)


if __name__ == "__main__":
    unittest.main()
