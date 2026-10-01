from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


UTC = timezone.utc
SECRET_PATTERNS = (
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"glpat-[A-Za-z0-9_-]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),
)
ALLOWED_SUFFIXES = {".py", ".yml", ".yaml", ".toml", ".json", ".sh"}
EXCLUDED_PARTS = {"tests", "docs", ".git", "data", "reports"}


def finding(severity: str, kind: str, path: Path, message: str) -> dict:
    return {
        "severity": severity,
        "kind": kind,
        "path": str(path),
        "message": message,
    }


def workflow_checks(path: Path, text: str) -> tuple[tuple[bool, str, str, str], ...]:
    checks = [
        (
            "pull_request_target:" in text,
            "high",
            "pull_request_target",
            "pull_request_target is enabled and requires manual trust-boundary review",
        ),
        (
            bool(re.search(r"(?m)^\s*permissions:\s*write-all\s*$", text)),
            "high",
            "write_all",
            "workflow grants write-all permissions",
        ),
        (
            bool(re.search(r"\bcurl\b[^\n|]*\|\s*(?:bash|sh)\b", text)),
            "high",
            "pipe_to_shell",
            "workflow pipes downloaded content directly into a shell",
        ),
    ]
    if path.name.endswith((".yml", ".yaml")) and ".github" in path.parts:
        checks.append(
            (
                "permissions:" not in text,
                "medium",
                "implicit_permissions",
                "GitHub workflow does not declare an explicit permissions block",
            )
        )
    return tuple(checks)


def automation_findings(root: Path) -> list[dict]:
    findings: list[dict] = []
    paths = list((root / ".github" / "workflows").glob("*.y*ml"))
    gitlab_ci = root / ".gitlab-ci.yml"
    if gitlab_ci.exists():
        paths.append(gitlab_ci)

    for path in sorted(paths):
        text = path.read_text(encoding="utf-8")
        findings.extend(
            finding(severity, kind, path, message)
            for active, severity, kind, message in workflow_checks(path, text)
            if active
        )
    return findings


def candidate_paths(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        if EXCLUDED_PARTS.intersection(path.parts):
            continue
        yield path


def scan_secret_path(path: Path) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return []

    results = []
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match is None:
            continue
        results.append(
            finding(
                "critical",
                "possible_secret",
                path,
                f"possible credential pattern at offset {match.start()}",
            )
        )
    return results


def secret_findings(root: Path) -> list[dict]:
    findings: list[dict] = []
    for path in candidate_paths(root):
        findings.extend(scan_secret_path(path))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.root)
    findings = automation_findings(root) + secret_findings(root)
    counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    for item in findings:
        counts[item["severity"]] = counts.get(item["severity"], 0) + 1

    now = datetime.now(UTC).replace(microsecond=0)
    report = {
        "observed_at": now.isoformat(),
        "counts": counts,
        "finding_count": len(findings),
        "findings": findings,
    }
    output = Path(args.output or f"reports/security/{now.date().isoformat()}.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    print(
        "SECURITY=PASS "
        f"critical={counts['critical']} high={counts['high']} "
        f"medium={counts['medium']}"
    )
    return 2 if counts["critical"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
