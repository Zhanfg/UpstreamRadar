from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

from upstreamradar.discovery import (
    DiscoveryCandidate,
    merge_candidates,
    score_repository,
    should_auto_fork,
)


API = "https://api.github.com"
TOKEN = os.environ.get("UPSTREAMRADAR_PAT", "")
CONFIG_PATH = Path("config/discovery.json")
STATE_PATH = Path("state/discovery_github.json")
REGISTRY_PATH = Path("discovery/github_candidates.json")
QUEUE_PATH = Path("discovery/github_fork_queue.json")
REPORT_PATH = Path("reports/discovery/github.md")


def request(path: str):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "UpstreamRadar-Discovery",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    req = Request(f"{API}{path}", headers=headers)
    with urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def enrich(repo: dict) -> dict:
    full_name = repo.get("full_name")
    if not full_name:
        return repo
    try:
        return request(f"/repos/{full_name}")
    except Exception:
        return repo


def priority_queries(config: dict, state: dict) -> list[str]:
    categories = config.get("categories", [])
    if not categories:
        return []
    count = int(config.get("scan", {}).get("priority_queries_per_run", 2))
    index = int(state.get("priority_index", 0))
    queries = []
    for offset in range(count):
        category = categories[(index + offset) % len(categories)]
        keywords = category.get("keywords", [])[:3]
        if keywords:
            queries.append(" ".join(keywords))
    state["priority_index"] = (index + count) % len(categories)
    return queries


def scan() -> tuple[dict, list[dict], list[dict]]:
    config = load_json(CONFIG_PATH, {})
    state = load_json(
        STATE_PATH,
        {
            "version": 1,
            "since_id": 0,
            "priority_index": 0,
            "runs": 0,
            "scanned": 0,
        },
    )
    candidates: list[DiscoveryCandidate] = []

    cursor = int(state.get("since_id", 0))
    pages = int(config.get("scan", {}).get("census_pages_per_run", 40))
    per_page = int(config.get("scan", {}).get("per_page", 100))
    scanned = 0

    for _ in range(pages):
        repos = request(f"/repositories?since={cursor}&per_page={per_page}")
        if not repos:
            break
        for repo in repos:
            cursor = max(cursor, int(repo.get("id", cursor)))
            scanned += 1
            candidate = score_repository(repo, config, platform="github")
            if candidate is not None:
                candidates.append(candidate)

    for query in priority_queries(config, state):
        q = quote_plus(f"{query} in:name,description,topics fork:false archived:false")
        result = request(f"/search/repositories?q={q}&sort=updated&order=desc&per_page=30")
        for repo in result.get("items", []):
            candidate = score_repository(enrich(repo), config, platform="github")
            if candidate is not None:
                candidates.append(candidate)

    existing = load_json(REGISTRY_PATH, [])
    for item in existing:
        try:
            candidates.append(
                DiscoveryCandidate(
                    **{
                        **item,
                        "reasons": tuple(item.get("reasons", [])),
                    }
                )
            )
        except TypeError:
            continue

    limit = int(config.get("scan", {}).get("candidate_limit", 80))
    merged = merge_candidates(candidates, limit=limit)
    registry = []
    queue = []
    for candidate in merged:
        item = asdict(candidate)
        item["reasons"] = list(candidate.reasons)
        item["auto_fork_eligible"] = should_auto_fork(candidate, config)
        registry.append(item)
        if item["auto_fork_eligible"]:
            queue.append(item)

    state["since_id"] = cursor
    state["runs"] = int(state.get("runs", 0)) + 1
    state["scanned"] = int(state.get("scanned", 0)) + scanned
    state["last_run_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    state["last_scanned"] = scanned
    state["candidate_count"] = len(registry)
    state["fork_queue_count"] = len(queue)

    return state, registry, queue


def render_report(state: dict, registry: list[dict], queue: list[dict]) -> str:
    lines = [
        "# GitHub Discovery Garden",
        "",
        f"- total census repositories scanned: **{state.get('scanned', 0)}**",
        f"- latest census cursor: **{state.get('since_id', 0)}**",
        f"- retained candidates: **{len(registry)}**",
        f"- governed fork queue: **{len(queue)}**",
        "",
        "## Top directions",
        "",
    ]

    grouped: dict[str, list[dict]] = {}
    for item in registry:
        grouped.setdefault(item["category"], []).append(item)

    for category in sorted(grouped):
        lines.append(f"### {category}")
        lines.append("")
        for item in grouped[category][:8]:
            lines.append(
                f"- **{item['full_name']}** — score={item['score']:.3f}, "
                f"stars={item['stars']}; {', '.join(item['reasons'][:5])}"
            )
        lines.append("")

    lines += ["## Fork queue", ""]
    if queue:
        for item in queue[:20]:
            lines.append(
                f"- **{item['full_name']}** → {item['category']} "
                f"(score={item['score']:.3f}, license={item.get('license_id')})"
            )
    else:
        lines.append("- No candidate currently satisfies the governed fork policy.")

    lines += [
        "",
        "Fork execution is intentionally separated from discovery so namespace, "
        "permissions, deduplication, and daily/weekly caps can be enforced safely.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    state, registry, queue = scan()
    write_json(STATE_PATH, state)
    write_json(REGISTRY_PATH, registry)
    write_json(QUEUE_PATH, queue)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(state, registry, queue), encoding="utf-8")
    print(
        f"DISCOVERY=PASS scanned={state['last_scanned']} "
        f"candidates={len(registry)} fork_queue={len(queue)} cursor={state['since_id']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
