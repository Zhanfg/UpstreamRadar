import unittest

from upstreamradar.reviewer import DiffFile, analyze, parse_unified_diff, summarize


class ReviewerTests(unittest.TestCase):
    def test_parse_diff(self):
        diff = """diff --git a/upstreamradar/a.py b/upstreamradar/a.py
--- a/upstreamradar/a.py
+++ b/upstreamradar/a.py
@@ -1 +1,2 @@
-old = 1
+new = 2
+print(new)
"""
        files = parse_unified_diff(diff)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].path, "upstreamradar/a.py")
        self.assertEqual(files[0].added, ("new = 2", "print(new)"))
        self.assertEqual(files[0].deleted, ("old = 1",))

    def test_detects_dangerous_patterns_and_missing_tests(self):
        files = (
            DiffFile(
                "upstreamradar/a.py",
                (
                    "value = " + "ev" + "al(user_input)",
                    "subprocess.run(cmd, shell=" + "True)",
                    "except " + "Exception:",
                ),
                (),
            ),
        )
        findings = analyze(files)
        rules = {finding.rule for finding in findings}
        self.assertIn("python-eval", rules)
        self.assertIn("shell-true", rules)
        self.assertIn("broad-except", rules)
        self.assertIn("source-without-tests", rules)

    def test_secret_detection(self):
        secret_line = 'API_KEY = "' + "sk-" + 'abcdefghijklmnopqrstuvwxyz12345"'
        files = (
            DiffFile("config.py", (secret_line,), ()),
        )
        self.assertIn("possible-secret", {f.rule for f in analyze(files)})

    def test_documentation_examples_do_not_trigger_code_rules(self):
        documentation_line = "Use " + "ev" + "al(x) only in a sandbox."
        files = (
            DiffFile("docs/example.md", (documentation_line,), ()),
        )
        self.assertNotIn("python-eval", {f.rule for f in analyze(files)})

    def test_tests_suppress_missing_test_finding(self):
        files = (
            DiffFile("upstreamradar/a.py", ("def f():", "    return 1"), ()),
            DiffFile("tests/test_a.py", ("def test_f():", "    assert True"), ()),
        )
        self.assertNotIn("source-without-tests", {f.rule for f in analyze(files)})

    def test_report_is_explicitly_automated(self):
        report = summarize((), (), "abc123")
        self.assertIn("Automated Code Review", report)
        self.assertIn("not a human approval", report)
        self.assertIn("upstreamradar-review:abc123", report)


if __name__ == "__main__":
    unittest.main()
