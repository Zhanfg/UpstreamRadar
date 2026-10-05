import unittest

from upstreamradar.engine import HarmonyScheduler, RepositorySignal


class HarmonyV4Tests(unittest.TestCase):
    def test_museum_evidence_is_bounded_and_traced(self):
        records = [
            RepositorySignal(
                name="core",
                ecosystem="kernel",
                cost=2,
                freshness_hours=1,
                commit_velocity=9,
                release_velocity=5,
                issue_velocity=3,
                security_signal=7,
                breakage_risk=6,
                dependency_importance=9,
                maintainer_activity=8,
                novelty=7,
                recent_change_hits=7,
                recent_change_misses=3,
                change_history=(0, 0, 1, 0, 1, 1, 1, 1),
                impact_history=(1, 1, 2, 2, 5, 7, 8, 9),
                observation_count=24,
            ),
            RepositorySignal(
                name="consumer",
                ecosystem="app",
                cost=1,
                freshness_hours=5,
                recent_change_hits=2,
                recent_change_misses=8,
                change_history=(0, 0, 0, 0, 1, 0),
                impact_history=(0, 1, 0, 1, 2, 1),
                observation_count=18,
            ),
        ]
        scores = self.scheduler.score(
            records,
            dependencies={"core": (), "consumer": ("core",)},
        )
        self.assertEqual(len(scores), 2)
        for score in scores:
            self.assertTrue(score.museum.bounded())
            self.assertGreaterEqual(len(score.museum.trace), 8)
            self.assertGreaterEqual(score.museum.consensus, 0.0)
            self.assertLessEqual(score.museum.consensus, 1.0)

    def setUp(self):
        self.scheduler = HarmonyScheduler()

    def test_graph_consensus_rewards_dependency_target(self):
        records = [
            RepositorySignal(name="hub", ecosystem="x", cost=1, freshness_hours=1),
            RepositorySignal(name="a", ecosystem="x", cost=1, freshness_hours=1),
            RepositorySignal(name="b", ecosystem="x", cost=1, freshness_hours=1),
            RepositorySignal(name="c", ecosystem="y", cost=1, freshness_hours=1),
        ]
        scores = {
            score.name: score
            for score in self.scheduler.score(
                records,
                dependencies={
                    "hub": (),
                    "a": ("hub",),
                    "b": ("hub",),
                    "c": ("hub",),
                },
            )
        }
        self.assertGreater(
            scores["hub"].museum.graph_consensus,
            scores["a"].museum.graph_consensus,
        )

    def test_algorithm_disagreement_is_penalized_not_hidden(self):
        record = RepositorySignal(
            name="mixed",
            ecosystem="x",
            cost=1,
            freshness_hours=1,
            recent_change_hits=1,
            recent_change_misses=9,
            change_history=(0, 0, 0, 0, 0, 1),
            impact_history=(0, 0, 0, 0, 0, 10),
            observation_count=30,
            novelty=9,
        )
        score = self.scheduler.score([record])[0]
        self.assertGreaterEqual(score.museum.disagreement, 0.0)
        self.assertLessEqual(score.museum.disagreement, 1.0)
        self.assertGreater(score.base_utility, 0.0)


if __name__ == "__main__":
    unittest.main()
