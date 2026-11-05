import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import downstream_github


def _http_error(status: int, reason: str, body: bytes) -> HTTPError:
    return HTTPError(
        url="https://api.github.com/repos/example/issues",
        code=status,
        msg=reason,
        hdrs=None,
        fp=io.BytesIO(body),
    )


class _Response:
    def __init__(self, payload):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DownstreamGitHubExecutorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.addCleanup(os.chdir, os.getcwd())
        os.chdir(self.root)
        self._write_inputs()

    def _write_inputs(self):
        run = {
            "observed_at": "2026-11-04T01:45:26Z",
            "changed_details": [
                {
                    "full_name": "llvm/llvm-project",
                    "semantic_impact": 8.55,
                    "fields": ["latest_release"],
                }
            ],
            "content_plan": [],
        }
        config = {
            "policy": {
                "min_semantic_impact": 6,
                "critical_impact": 8,
                "important_fields": ["latest_release"],
                "max_plans_per_run": 10,
                "max_actions_per_day": 3,
                "max_actions_per_run": 2,
                "update_cooldown_hours": 24,
                "create_cooldown_hours": 168,
            },
            "targets": [
                {
                    "repo": "Zhanfg/OnePlus13-kernel",
                    "sources": ["llvm/llvm-project"],
                    "checklist": ["re-run kernel build"],
                },
                {
                    "repo": "Zhanfg/susfs4ksu",
                    "sources": ["llvm/llvm-project"],
                    "checklist": ["review compatibility"],
                },
            ],
        }
        run_path = self.root / "data" / "runs" / "2026-11-04" / "0945.json"
        run_path.parent.mkdir(parents=True, exist_ok=True)
        run_path.write_text(json.dumps(run), encoding="utf-8")
        config_path = self.root / "config" / "downstream_projects.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(json.dumps(config), encoding="utf-8")

    def _run(self, urlopen):
        buffer = io.StringIO()
        with patch.object(downstream_github, "TOKEN", "test-token-value"), patch.object(
            downstream_github, "urlopen", side_effect=urlopen
        ), patch("sys.stdout", buffer):
            result = downstream_github.main()
        return result, buffer.getvalue()

    def test_403_skips_that_impact_and_continues(self):
        def urlopen(req, timeout=30):
            target = req.full_url
            if target.endswith("/repos/Zhanfg/OnePlus13-kernel/issues"):
                body = json.dumps(
                    {
                        "message": (
                            "Resource not accessible by personal access token "
                            "github_pat_should_not_appear"
                        )
                    }
                ).encode("utf-8")
                raise _http_error(403, "Forbidden", body)
            if target.endswith("/repos/Zhanfg/susfs4ksu/issues"):
                return _Response(
                    {
                        "number": 7,
                        "html_url": "https://github.com/Zhanfg/susfs4ksu/issues/7",
                    }
                )
            raise AssertionError(target)

        code, output = self._run(urlopen)

        self.assertEqual(code, 0)
        self.assertIn(
            "DOWNSTREAM=WARN skip issue creation status=403 "
            "impact=github:llvm/llvm-project->Zhanfg/OnePlus13-kernel "
            "repo=Zhanfg/OnePlus13-kernel token=<REDACTED>",
            output,
        )
        self.assertIn("detail=Resource not accessible by personal access token <REDACTED>", output)
        self.assertNotIn("github_pat_should_not_appear", output)
        self.assertNotIn("test-token-value", output)
        self.assertIn(
            "DOWNSTREAM=PASS plans=2 actions=1 skipped_permission=1",
            output,
        )
        state = json.loads(
            (self.root / "state" / "downstream_github.json").read_text(encoding="utf-8")
        )
        self.assertEqual(set(state["items"]), {"github:llvm/llvm-project->Zhanfg/susfs4ksu"})
        self.assertNotIn("OnePlus13-kernel", json.dumps(state["items"]))

    def test_401_and_404_also_skip_without_failing_the_run(self):
        for status, reason in ((401, "Unauthorized"), (404, "Not Found")):
            with self.subTest(status=status):
                self._write_inputs()
                state_path = self.root / "state" / "downstream_github.json"
                if state_path.exists():
                    state_path.unlink()

                def urlopen(req, timeout=30, status=status, reason=reason):
                    raise _http_error(
                        status,
                        reason,
                        b'{"message":"Not Found"}',
                    )

                code, output = self._run(urlopen)
                self.assertEqual(code, 0)
                self.assertIn(f"status={status}", output)
                self.assertIn("repo=Zhanfg/OnePlus13-kernel", output)
                self.assertIn("skipped_permission=2", output)
                self.assertFalse(state_path.exists())

    def test_500_still_fails(self):
        def urlopen(req, timeout=30):
            raise _http_error(500, "Internal Server Error", b'{"message":"boom"}')

        buffer = io.StringIO()
        with patch.object(downstream_github, "TOKEN", "test-token-value"), patch.object(
            downstream_github, "urlopen", side_effect=urlopen
        ), patch("sys.stdout", buffer):
            with self.assertRaises(HTTPError) as caught:
                downstream_github.main()
        self.assertEqual(caught.exception.code, 500)
        output = buffer.getvalue()
        self.assertNotIn("DOWNSTREAM=WARN", output)
        self.assertNotIn("DOWNSTREAM=PASS", output)
        self.assertFalse((self.root / "state" / "downstream_github.json").exists())

    def test_403_then_500_does_not_hide_the_server_error(self):
        def urlopen(req, timeout=30):
            if req.full_url.endswith("/repos/Zhanfg/OnePlus13-kernel/issues"):
                raise _http_error(403, "Forbidden", b'{"message":"Resource not accessible by personal access token"}')
            raise _http_error(500, "Internal Server Error", b'{"message":"boom"}')

        buffer = io.StringIO()
        with patch.object(downstream_github, "TOKEN", "test-token-value"), patch.object(
            downstream_github, "urlopen", side_effect=urlopen
        ), patch("sys.stdout", buffer):
            with self.assertRaises(HTTPError) as caught:
                downstream_github.main()
        self.assertEqual(caught.exception.code, 500)
        output = buffer.getvalue()
        self.assertIn("status=403", output)
        self.assertIn("repo=Zhanfg/OnePlus13-kernel", output)
        self.assertNotIn("DOWNSTREAM=PASS", output)
