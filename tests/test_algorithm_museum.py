import unittest

from upstreamradar.museum.bandit import (
    bayes_ucb,
    beta_quantile,
    kl_ucb,
    regularized_beta,
    ucb_v,
)
from upstreamradar.museum.change import (
    bernoulli_bocpd,
    change_consensus,
    adwin_score,
    cusum_score,
)
from upstreamradar.museum.graph import (
    brandes_betweenness,
    centrality_consensus,
    k_core_numbers,
    tarjan_scc,
)
from upstreamradar.museum.information import (
    jensen_shannon,
    maximum_mean_discrepancy,
    wasserstein_1d,
)
from upstreamradar.museum.optimization import (
    Item,
    celf_select,
    exact_knapsack,
    epsilon_pareto,
)
from upstreamradar.museum.registry import EXHIBITS
from upstreamradar.museum.robust import huber_location
from upstreamradar.museum.streaming import (
    BloomFilter,
    CountMinSketch,
    HyperLogLog,
    SpaceSaving,
)
from upstreamradar.museum.sketches import (
    minhash_signature,
    minhash_similarity,
)


class AlgorithmMuseumTests(unittest.TestCase):
    def test_registry_is_curated_and_unique(self):
        slugs = [item.slug for item in EXHIBITS]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertGreaterEqual(len(EXHIBITS), 15)
        self.assertTrue(all(item.family and item.role for item in EXHIBITS))
        self.assertTrue(any(not item.production for item in EXHIBITS))

    def test_huber_resists_single_extreme_outlier(self):
        values = [1.0, 1.1, 0.9, 1.05, 100.0]
        robust = huber_location(values)
        arithmetic = sum(values) / len(values)
        self.assertLess(abs(robust - 1.0), abs(arithmetic - 1.0))

    def test_change_detectors_respond_to_regime_shift(self):
        stable = [0.1] * 12
        shifted = [0.1] * 8 + [0.9] * 4
        self.assertGreater(cusum_score(shifted), cusum_score(stable))

        stable_bocpd = bernoulli_bocpd([0] * 12)
        shifted_bocpd = bernoulli_bocpd([0] * 8 + [1] * 4)
        self.assertGreater(
            shifted_bocpd.reset_probability,
            stable_bocpd.reset_probability,
        )

        consensus, trace = change_consensus(
            tuple(value * 10 for value in shifted),
            (0,) * 8 + (1,) * 4,
        )
        self.assertGreater(consensus, 0)
        names = {name for name, _ in trace}
        self.assertTrue(
            {"page-hinkley", "cusum", "bocpd-beta", "adwin", "theil-sen"}
            <= names
        )
        self.assertGreater(adwin_score(shifted), adwin_score(stable))

    def test_information_divergence_is_symmetric(self):
        left = [9, 1, 0, 0]
        right = [0, 0, 1, 9]
        self.assertAlmostEqual(
            jensen_shannon(left, right),
            jensen_shannon(right, left),
        )
        self.assertGreater(jensen_shannon(left, right), 0.5)
        self.assertGreater(
            wasserstein_1d([0.0, 0.1, 0.2], [0.8, 0.9, 1.0]),
            0.6,
        )
        self.assertGreater(
            maximum_mean_discrepancy([0.0, 0.1, 0.2], [0.8, 0.9, 1.0]),
            0.5,
        )

    def test_graph_gallery_detects_cycles_and_centrality(self):
        graph = {
            "a": ("b",),
            "b": ("c",),
            "c": ("a", "hub"),
            "leaf": ("hub",),
            "hub": (),
        }
        components = tarjan_scc(graph)
        self.assertIn(("a", "b", "c"), components)

        scores, traces = centrality_consensus(graph)
        self.assertGreater(scores["hub"], 0)
        self.assertIn("hub", traces)
        self.assertTrue(all(0 <= value <= 1 for value in scores.values()))
        between = brandes_betweenness(graph)
        cores = k_core_numbers(graph)
        self.assertTrue(all(0 <= value <= 1 for value in between.values()))
        self.assertTrue(all(0 <= value <= 1 for value in cores.values()))

    def test_bandit_indexes_are_bounded(self):
        self.assertTrue(0 <= ucb_v(0.2, 0.05, 10, 100) <= 1)
        self.assertTrue(0 <= kl_ucb(0.2, 10, 100) <= 1)
        self.assertGreaterEqual(kl_ucb(0.2, 2, 100), kl_ucb(0.2, 50, 100))

    def test_beta_distribution_and_bayes_ucb(self):
        self.assertAlmostEqual(regularized_beta(0.5, 1.0, 1.0), 0.5, places=6)
        self.assertAlmostEqual(beta_quantile(0.9, 1.0, 1.0), 0.9, places=5)
        self.assertTrue(0 <= bayes_ucb(3.0, 7.0, 100) <= 1)

    def test_minhash_is_deterministic_and_similarity_sensitive(self):
        a = minhash_signature(["x", "y", "z"])
        b = minhash_signature(["x", "y", "z"])
        c = minhash_signature(["other", "values"])
        self.assertEqual(a, b)
        self.assertEqual(minhash_similarity(a, b), 1.0)
        self.assertLess(minhash_similarity(a, c), 0.5)

    def test_streaming_sketch_gallery(self):
        bloom = BloomFilter(bits=2048, hashes=4)
        for value in ("a", "b", "c"):
            bloom.add(value)
        self.assertIn("a", bloom)
        self.assertIn("b", bloom)
        self.assertIn("c", bloom)

        cms = CountMinSketch(width=128, depth=4)
        for _ in range(20):
            cms.add("hot")
        for _ in range(3):
            cms.add("cold")
        self.assertGreaterEqual(cms.estimate("hot"), 20)
        self.assertGreater(cms.estimate("hot"), cms.estimate("cold"))

        hll = HyperLogLog(precision=10)
        for index in range(1000):
            hll.add(f"repo-{index}")
        estimate = hll.estimate()
        self.assertLess(abs(estimate - 1000) / 1000, 0.20)

        heavy = SpaceSaving(capacity=4)
        for value in ["hot"] * 20 + ["warm"] * 8 + ["x", "y", "z", "q"]:
            heavy.add(value)
        self.assertEqual(heavy.heavy_hitters()[0].key, "hot")

    def test_exact_knapsack_and_pareto_archive(self):
        items = [
            Item("a", 3, 5.0),
            Item("b", 2, 3.0),
            Item("c", 2, 4.0),
        ]
        selected = set(exact_knapsack(items, 4))
        self.assertEqual(selected, {"b", "c"})

        frontier = epsilon_pareto(
            [
                {"name": "a", "utility": 0.8, "novelty": 0.7, "risk": 0.4},
                {"name": "b", "utility": 0.7, "novelty": 0.6, "risk": 0.5},
                {"name": "c", "utility": 0.6, "novelty": 0.9, "risk": 0.2},
            ],
            maximize=("utility", "novelty"),
            minimize=("risk",),
        )
        names = {str(item["name"]) for item in frontier}
        self.assertNotIn("b", names)
        self.assertIn("a", names)
        self.assertIn("c", names)

        gains = {
            "a": {"x", "y"},
            "b": {"y", "z"},
            "c": {"q"},
        }
        def marginal(name, selected):
            covered = set()
            for chosen in selected:
                covered |= gains[chosen]
            return float(len(gains[name] - covered))
        celf = celf_select(items, 4, marginal)
        self.assertTrue(set(celf) <= {"a", "b", "c"})
        self.assertGreaterEqual(len(celf), 1)


if __name__ == "__main__":
    unittest.main()
