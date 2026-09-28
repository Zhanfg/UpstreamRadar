import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from upstreamradar.collector import (
    bounded_window,
    run_probability,
    should_run,
    stable_snapshot,
)


class CollectorPureLogicTests(unittest.TestCase):
    def test_probability_profile(self):
        self.assertEqual(run_probability(2), 0.40)
        self.assertEqual(run_probability(7), 0.70)
        self.assertEqual(run_probability(12), 0.95)
        self.assertEqual(run_probability(20), 0.85)
        self.assertEqual(run_probability(23), 0.60)

    def test_gate_is_deterministic_for_same_slot(self):
        now = datetime(2026, 9, 29, 4, 7, tzinfo=timezone.utc)
        first = should_run(now)
        second = should_run(now)
        self.assertEqual(first, second)

    def test_force_bypasses_gate(self):
        now = datetime(2026, 9, 29, 4, 7, tzinfo=timezone.utc)
        permitted, probability, sample = should_run(now, force=True)
        self.assertTrue(permitted)
        self.assertEqual(probability, 1.0)
        self.assertEqual(sample, 0.0)

    def test_snapshot_comparison_ignores_observation_timestamp(self):
        left = {"full_name": "a/b", "stars": 10, "observed_at": "one"}
        right = {"full_name": "a/b", "stars": 10, "observed_at": "two"}
        self.assertEqual(stable_snapshot(left), stable_snapshot(right))

    def test_bounded_window(self):
        values = bounded_window([0, 1, 1], 0, limit=3)
        self.assertEqual(values, [1, 1, 0])


if __name__ == "__main__":
    unittest.main()
