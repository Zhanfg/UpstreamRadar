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


def workflow_findings(root: Path) -> list[dict]:
    findings = []
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return findings

    for path in sorted(workflow_dir.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        if "pull_request_target:" in text:
            findings.append(
                {
                    "severity": "high",
                    "kind": "pull_request_target",
                    "path": str(path),
                    "message": "pull_request_target is enabled and requires manual trust-boundary review",
                }
            )
        if re.search(r"(?m)^\s*permissions:\s*write-all\s*$", text):
            findings.append(
                {
                    "severity": "high",
                    "kind": "write_all",
                    "path": str(path),
                    "message": "workflow grants write-all permissions",
                }
            )
        if "permissions:" not in text:
            findings.append(
                {
                    "severity": "medium",
                    "kind": "implicit_permissions",
                    "path": str(path),
                    "message": "workflow does not declare an explicit permissions block",
                }
            )
        if re.search(r"\bcurl\b[^\n|]*\|\s*(?:bash|sh)\b", text):
            findings.append(
                {
                    "severity": "high",
                    "kind": "pipe_to_shell",
                    "path": str(path),
                    "message": "workflow pipes downloaded content directly into a shell",
                }
            )
    return findings


def secret_findings(root: Path) -> list[dict]:
    findings = []
    allowed_suffixes = {".py", ".yml", ".yaml", ".toml", ".json", ".sh"}
    excluded = {"tests", "docs", ".git", "data", "reports"}
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in allowed_suffixes:
            continue
        if excluded.intersection(path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for pattern in SECRET_PATTERNS:
            match = pattern.search(text)
            if match:
                findings.append(
                    {
                        "severity": "critical",
                        "kind": "possible_secret",
                        "path": str(path),
                        "message": f"possible credential pattern at offset {match.start()}",
                    }
                )
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--output")
    args = parser.parse_args()

    root = Path(args.root)
    findings = workflow_findings(root) + secret_findings(root)
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
    output = Path(
        args.output
        or f"reports/security/{now.date().isoformat()}.json"
    )
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
