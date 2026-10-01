import unittest
from datetime import datetime, timedelta, timezone

from upstreamradar.governance import (
    data_quality_signal,
    governance_summary,
    parity_signal,
    state_growth_signal,
)


NOW = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


class GovernanceTests(unittest.TestCase):
    def test_healthy_data_quality_stays_quiet(self):
        records = {
            f"repo-{index}": {
                "checks": 20,
                "successful_checks": 20,
                "failed_checks": 0,
                "error_streak": 0,
                "last_checked_at": (
                    NOW - timedelta(hours=index % 4)
                ).isoformat(),
                "change_window": [0, 1] * 8,
                "impact_window": [0.0, 5.0] * 8,
            }
            for index in range(20)
        }
        signal = data_quality_signal(
            records,
            {
                "stale_hours": 36,
                "min_records_for_stale_ratio": 10,
                "stale_fraction_threshold": 0.2,
                "error_streak_threshold": 3,
                "max_error_streak_records": 1,
                "max_invalid_records": 0,
                "max_window_items": 48,
            },
            now=NOW,
        )
        self.assertFalse(signal.active)
        self.assertEqual(signal.evidence["invalid_count"], 0)

    def test_data_quality_detects_stale_error_and_invalid_records(self):
        records = {
            "stale": {
                "checks": 5,
                "successful_checks": 5,
                "last_checked_at": (NOW - timedelta(hours=72)).isoformat(),
            },
            "error": {
                "checks": 5,
                "successful_checks": 5,
                "error_streak": 5,
                "last_checked_at": NOW.isoformat(),
            },
            "invalid": {
                "checks": 2,
                "successful_checks": 3,
                "last_checked_at": NOW.isoformat(),
                "change_window": [1] * 60,
            },
        }
        signal = data_quality_signal(
            records,
            {
                "stale_hours": 36,
                "min_records_for_stale_ratio": 1,
                "stale_fraction_threshold": 0.2,
                "error_streak_threshold": 3,
                "max_error_streak_records": 0,
                "max_invalid_records": 0,
                "max_window_items": 48,
            },
            now=NOW,
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.severity, "high")
        self.assertEqual(signal.evidence["error_streak_count"], 1)
        self.assertEqual(signal.evidence["invalid_count"], 1)

    def test_state_growth_detects_total_and_per_file_limits(self):
        signal = state_growth_signal(
            [
                {"path": "state/a.json", "bytes": 900},
                {"path": "state/b.json", "bytes": 2500},
            ],
            {
                "per_file_bytes": 2000,
                "total_bytes": 3000,
                "max_reported_items": 20,
            },
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.evidence["oversized_count"], 1)
        self.assertEqual(signal.evidence["total_bytes"], 3400)

    def test_small_state_stays_quiet(self):
        signal = state_growth_signal(
            [
                {"path": "state/a.json", "bytes": 900},
                {"path": "state/b.json", "bytes": 1000},
            ],
            {
                "per_file_bytes": 2000,
                "total_bytes": 3000,
            },
        )
        self.assertFalse(signal.active)

    def test_parity_detects_shared_core_drift(self):
        signal = parity_signal(
            [
                {
                    "path": "upstreamradar/engine.py",
                    "same": True,
                    "status": "match",
                    "local_length": 100,
                    "remote_length": 100,
                },
                {
                    "path": "config/activity_matrix.json",
                    "same": False,
                    "status": "content-mismatch",
                    "local_length": 200,
                    "remote_length": 220,
                },
            ],
            {
                "max_mismatches": 0,
                "max_reported_items": 20,
            },
        )
        self.assertTrue(signal.active)
        self.assertEqual(signal.evidence["mismatch_count"], 1)
        self.assertEqual(
            signal.evidence["mismatches"][0]["path"],
            "config/activity_matrix.json",
        )

    def test_parity_stays_quiet_when_shared_core_matches(self):
        entries = [
            {
                "path": name,
                "same": True,
                "status": "match",
                "local_length": 100,
                "remote_length": 100,
            }
            for name in ("engine.py", "activity.py", "health.py")
        ]
        signal = parity_signal(entries, {"max_mismatches": 0})
        self.assertFalse(signal.active)

    def test_summary_counts_active_signals(self):
        healthy = state_growth_signal(
            [{"path": "a", "bytes": 10}],
            {"per_file_bytes": 100, "total_bytes": 100},
        )
        drift = parity_signal(
            [{
                "path": "x",
                "same": False,
                "status": "content-mismatch",
                "local_length": 1,
                "remote_length": 2,
            }],
            {"max_mismatches": 0},
        )
        summary = governance_summary([healthy, drift])
        self.assertEqual(summary["active_count"], 1)
        self.assertEqual(len(summary["signals"]), 2)


if __name__ == "__main__":
    unittest.main()
