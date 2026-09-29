from __future__ import annotations

import json
import os
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from upstreamradar.forking import select_fork_batch


API = "https://api.github.com"
TOKEN = os.environ.get("UPSTREAMRADAR_FORK_PAT", "")
CONFIG_PATH = Path("config/discovery.json")
QUEUE_PATH = Path("discovery/github_fork_queue.json")
HISTORY_PATH = Path("state/forks_github.json")


def request(path: str, method: str = "GET", payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "UpstreamRadar-Fork-Governor",
        "X-GitHub-Api-Version": "2026-03-10",
    }
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = Request(f"{API}{path}", method=method, headers=headers, data=data)
    with urlopen(req, timeout=30) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else None


def load(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def current_login() -> str | None:
    if not TOKEN:
        return None
    try:
        return request("/user").get("login")
    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
        return None


def main() -> int:
    if not TOKEN:
        print("FORK=SKIP dedicated UPSTREAMRADAR_FORK_PAT is not configured")
        return 0

    config = load(CONFIG_PATH, {})
    queue = load(QUEUE_PATH, [])
    history = load(HISTORY_PATH, [])
    login = current_login()
    plans = select_fork_batch(
        queue,
        history,
        config,
        platform="github",
        personal_namespace=login,
    )
    if not plans:
        print("FORK=SKIP no configured namespace, capacity, or eligible candidate")
        return 0

    for plan in plans:
        owner, repo = plan.full_name.split("/", 1)
        payload = {"default_branch_only": True}
        if plan.destination != login:
            payload["organization"] = plan.destination
        try:
            created = request(
                f"/repos/{quote(owner)}/{quote(repo)}/forks",
                method="POST",
                payload=payload,
            )
            history.append(
                {
                    **asdict(plan),
                    "status": "forked",
                    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "fork_full_name": created.get("full_name"),
                    "fork_url": created.get("html_url"),
                }
            )
            print(f"FORK=PASS source={plan.full_name} destination={plan.destination}")
        except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            history.append(
                {
                    **asdict(plan),
                    "status": "error",
                    "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                    "error": f"{type(exc).__name__}: {exc}"[:500],
                }
            )
            print(f"FORK=ERROR source={plan.full_name} error={type(exc).__name__}")

    save(HISTORY_PATH, history[-200:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
