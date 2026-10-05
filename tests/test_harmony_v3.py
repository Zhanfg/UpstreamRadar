import json
import math
import unittest
from dataclasses import asdict
from pathlib import Path

from upstreamradar.engine import HarmonyScheduler, RepositorySignal


class HarmonyV3ContractTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = HarmonyScheduler()
        self.vectors = json.loads(
            Path("tests/fixtures/harmony_v3_vectors.json").read_text(encoding="utf-8")
        )["vectors"]

    def test_surprise_vector_ordering(self):
        high, low = self.vectors["surprise"]
        high_score = self.scheduler._bayesian_surprise(
            RepositorySignal(
                name="high",
                ecosystem="test",
                cost=1,
                freshness_hours=0,
                change_history=(1, 1, 1, 1, 0),
            ),
            high["predicted"],
        )
        low_score = self.scheduler._bayesian_surprise(
            RepositorySignal(
                name="low",
                ecosystem="test",
                cost=1,
                freshness_hours=0,
                change_history=(0, 0, 0, 0, 1),
            ),
            low["predicted"],
        )
        self.assertGreater(high_score, low_score)

    def test_tail_risk_uses_true_upper_quantile(self):
        record = RepositorySignal(
            name="risk",
            ecosystem="test",
            cost=1,
            freshness_hours=0,
            impact_history=(1.0, 2.0, 3.0, 9.0),
        )
        raw_cvar = self.scheduler._tail_risk(record)
        self.assertGreater(raw_cvar, 0.35)

    def test_score_contract_contains_v3_dimensions(self):
        score = self.scheduler.score([
            RepositorySignal(
                name="repo",
                ecosystem="test",
                cost=1,
                freshness_hours=1,
                recent_change_hits=2,
                recent_change_misses=1,
                change_history=(0, 1, 1),
                impact_history=(1.0, 4.0, 8.0),
                dependency_importance=5,
                novelty=6,
            )
        ])[0]
        data = asdict(score)
        for key in (
            "bayesian_surprise",
            "structural_novelty",
            "tail_risk",
            "risk_adjusted_utility",
            "base_utility",
        ):
            self.assertIn(key, data)
            self.assertTrue(math.isfinite(data[key]))

    def test_empirical_bayes_priors_are_valid(self):
        records = [
            RepositorySignal(
                name="a", ecosystem="eco", cost=1, freshness_hours=0,
                recent_change_hits=8, recent_change_misses=2,
            ),
            RepositorySignal(
                name="b", ecosystem="eco", cost=1, freshness_hours=0,
                recent_change_hits=0, recent_change_misses=0,
            ),
            RepositorySignal(
                name="c", ecosystem="other", cost=1, freshness_hours=0,
                recent_change_hits=1, recent_change_misses=9,
            ),
        ]
        priors = self.scheduler._empirical_bayes_priors(records)
        for alpha, beta in priors.values():
            self.assertGreater(alpha, 0)
            self.assertGreater(beta, 0)


if __name__ == "__main__":
    unittest.main()
