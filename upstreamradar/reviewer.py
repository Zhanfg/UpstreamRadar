from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ReviewFinding:
    severity: str
    rule: str
    path: str
    message: str
    evidence: str = ""


@dataclass(frozen=True)
class DiffFile:
    path: str
    added: tuple[str, ...]
    deleted: tuple[str, ...]


_SECRET_PATTERNS = (
    re.compile(r"(?i)(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)

_WORK_MARKERS = ("TO" + "DO", "FIX" + "ME", "HA" + "CK", "X" + "XX")

_RULES = (
    ("high", "python-eval", re.compile(r"\b(eval|exec)\s*\("), "dynamic code execution added"),
    ("high", "shell-true", re.compile(r"subprocess\.[A-Za-z_]+\([^\n]*shell\s*=\s*True"), "subprocess with shell=True added"),
    ("medium", "broad-except", re.compile(r"^\s*except\s+(Exception|BaseException)\s*(?:as\s+\w+)?\s*:"), "broad exception handler added"),
    (
        "low",
        "todo",
        re.compile(r"\b(" + "|".join(_WORK_MARKERS) + r")\b", re.IGNORECASE),
        "unfinished-work marker added",
    ),
)


def parse_unified_diff(text: str) -> tuple[DiffFile, ...]:
    files: list[DiffFile] = []
    current_path: str | None = None
    added: list[str] = []
    deleted: list[str] = []

    def flush() -> None:
        nonlocal current_path, added, deleted
        if current_path is not None:
            files.append(DiffFile(current_path, tuple(added), tuple(deleted)))
        current_path = None
        added = []
        deleted = []

    for raw in text.splitlines():
        if raw.startswith("diff --git "):
            flush()
            parts = raw.split()
            if len(parts) >= 4:
                current_path = parts[3][2:] if parts[3].startswith("b/") else parts[3]
            continue

        if current_path is None:
            continue

        if raw.startswith("+++") or raw.startswith("---"):
            continue
        if raw.startswith("+"):
            added.append(raw[1:])
        elif raw.startswith("-"):
            deleted.append(raw[1:])

    flush()
    return tuple(files)


def _max_python_indent_depth(lines: Sequence[str]) -> int:
    depth = 0
    for line in lines:
        stripped = line.lstrip(" ")
        if not stripped or stripped.startswith("#"):
            continue
        spaces = len(line) - len(stripped)
        depth = max(depth, spaces // 4)
    return depth


def _secret_findings(path: str, line: str) -> list[ReviewFinding]:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(line):
            return [
                ReviewFinding(
                    "critical",
                    "possible-secret",
                    path,
                    "possible credential or secret literal added; verify and redact before merge",
                    line.strip()[:160],
                )
            ]
    return []


def _code_rule_findings(path: str, line: str) -> list[ReviewFinding]:
    if not path.endswith(".py"):
        return []

    findings: list[ReviewFinding] = []
    for severity, rule, pattern, message in _RULES:
        if pattern.search(line):
            findings.append(
                ReviewFinding(
                    severity,
                    rule,
                    path,
                    message,
                    line.strip()[:160],
                )
            )
    return findings


def _file_level_findings(file: DiffFile) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []

    if file.path.endswith(".py"):
        depth = _max_python_indent_depth(file.added)
        if depth >= 6:
            findings.append(
                ReviewFinding(
                    "medium",
                    "deep-nesting",
                    file.path,
                    f"new Python code reaches indentation depth {depth}; consider extracting decision layers",
                )
            )

    if file.path.endswith((".yml", ".yaml")) and file.path.startswith(".github/workflows/"):
        joined = "\n".join(file.added)
        if "pull_request_target:" in joined and "actions/checkout@" in joined:
            findings.append(
                ReviewFinding(
                    "high",
                    "pr-target-checkout",
                    file.path,
                    "pull_request_target combined with checkout can expose repository secrets to untrusted PR code",
                )
            )

    return findings


def analyze(files: Sequence[DiffFile]) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    changed_paths = {file.path for file in files}
    source_changed = any(
        path.endswith(".py")
        and not path.startswith("tests/")
        and not path.startswith("examples/")
        for path in changed_paths
    )
    test_changed = any(
        path.startswith("tests/") or "/tests/" in path or path.endswith("_test.py")
        for path in changed_paths
    )

    for file in files:
        for line in file.added:
            findings.extend(_secret_findings(file.path, line))
            findings.extend(_code_rule_findings(file.path, line))
        findings.extend(_file_level_findings(file))

    if source_changed and not test_changed:
        findings.append(
            ReviewFinding(
                "medium",
                "source-without-tests",
                "<repository>",
                "source code changed but this diff does not modify tests",
            )
        )

    unique: dict[tuple[str, str, str, str], ReviewFinding] = {}
    for finding in findings:
        key = (finding.severity, finding.rule, finding.path, finding.evidence)
        unique[key] = finding

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (order.get(item.severity, 9), item.path, item.rule, item.evidence),
        )
    )


def summarize(files: Sequence[DiffFile], findings: Sequence[ReviewFinding], head_sha: str = "") -> str:
    added = sum(len(file.added) for file in files)
    deleted = sum(len(file.deleted) for file in files)
    by_severity = {}
    for finding in findings:
        by_severity[finding.severity] = by_severity.get(finding.severity, 0) + 1

    marker = f"<!-- upstreamradar-review:{head_sha} -->" if head_sha else "<!-- upstreamradar-review -->"
    lines = [
        marker,
        "## Automated Code Review",
        "",
        "This review was generated automatically by UpstreamRadar's repository-local reviewer. "
        "It is a heuristic engineering review, not a human approval.",
        "",
        "### Diff summary",
        "",
        f"- files changed: **{len(files)}**",
        f"- added lines inspected: **{added}**",
        f"- deleted lines observed: **{deleted}**",
    ]

    if not findings:
        lines.extend(
            [
                "",
                "### Findings",
                "",
                "No configured static-review rules were triggered.",
                "",
                "Status: **PASS (heuristic)**",
            ]
        )
        return "\n".join(lines) + "\n"

    lines.extend(["", "### Findings", ""])
    for finding in findings:
        evidence = f" — `{finding.evidence}`" if finding.evidence else ""
        lines.append(
            f"- **{finding.severity.upper()}** `{finding.rule}` in "
            f"`{finding.path}`: {finding.message}{evidence}"
        )

    blocking = sum(by_severity.get(level, 0) for level in ("critical", "high"))
    lines.extend(
        [
            "",
            f"High-severity findings: **{blocking}**",
            "",
            "Status: **REVIEW REQUIRED**" if blocking else "Status: **PASS WITH NOTES**",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a unified PR diff")
    parser.add_argument("--diff", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--head-sha", default="")
    args = parser.parse_args()

    text = Path(args.diff).read_text(encoding="utf-8", errors="replace")
    files = parse_unified_diff(text)
    findings = analyze(files)
    report = summarize(files, findings, args.head_sha)
    Path(args.output).write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
