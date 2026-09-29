from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import exp, log1p
import re
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class DiscoveryCandidate:
    platform: str
    source_id: str
    full_name: str
    url: str
    category: str
    score: float
    stars: int
    forks: int
    pushed_at: str | None
    license_id: str | None
    reasons: tuple[str, ...]
    description: str = ""


def _tokenize(repo: Mapping[str, Any]) -> str:
    topics = repo.get("topics") or []
    return " ".join(
        [
            str(repo.get("name") or ""),
            str(repo.get("full_name") or repo.get("path_with_namespace") or ""),
            str(repo.get("description") or ""),
            " ".join(str(item) for item in topics),
        ]
    ).lower()


def classify(repo: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[str, float, tuple[str, ...]]:
    haystack = _tokenize(repo)
    best_category = "other"
    best = 0.0
    matched: list[str] = []

    for category in config.get("categories", []):
        local = []
        for keyword in category.get("keywords", []):
            token = str(keyword).lower()
            pattern = re.compile(
                r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])"
            )
            if pattern.search(haystack):
                local.append(token)
        if not local:
            continue
        density = min(1.0, 0.35 + 0.18 * len(local))
        score = density * float(category.get("weight", 1.0))
        if score > best:
            best = score
            best_category = str(category["id"])
            matched = local

    return best_category, best, tuple(matched[:6])


def excluded(repo: Mapping[str, Any], config: Mapping[str, Any]) -> bool:
    if repo.get("archived"):
        return True
    haystack = _tokenize(repo)
    name = str(repo.get("name") or "").lower()
    exclusions = config.get("exclusions", {})
    if any(name.startswith(str(prefix).lower()) for prefix in exclusions.get("name_prefixes", [])):
        return True
    return any(str(keyword).lower() in haystack for keyword in exclusions.get("keywords", []))


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def score_repository(
    repo: Mapping[str, Any],
    config: Mapping[str, Any],
    *,
    platform: str,
    now: datetime | None = None,
) -> DiscoveryCandidate | None:
    now = now or datetime.now(timezone.utc)
    if excluded(repo, config):
        return None
    if repo.get("fork") or repo.get("forked_from_project"):
        return None

    category, relevance, matches = classify(repo, config)
    if relevance <= 0.0:
        return None

    stars = int(repo.get("stargazers_count") or repo.get("star_count") or 0)
    forks = int(repo.get("forks_count") or 0)
    pushed_at = repo.get("pushed_at") or repo.get("last_activity_at")
    pushed = _parse_time(pushed_at)
    age_days = 3650.0 if pushed is None else max(0.0, (now - pushed).total_seconds() / 86400.0)

    recency = exp(-age_days / 120.0)
    popularity = min(1.0, log1p(stars) / log1p(5000))
    ecosystem_signal = min(1.0, log1p(forks) / log1p(1000))

    license_obj = repo.get("license")
    if isinstance(license_obj, Mapping):
        license_id = (
            license_obj.get("spdx_id")
            or license_obj.get("key")
            or license_obj.get("name")
        )
    else:
        license_id = repo.get("license_id") or repo.get("license_name")
    licensed = bool(license_id and str(license_id).upper() not in {"NOASSERTION", "OTHER"})

    description = str(repo.get("description") or "")
    description_quality = min(1.0, len(description.strip()) / 120.0)
    quality = 0.46 * popularity + 0.22 * ecosystem_signal + 0.20 * description_quality + 0.12 * float(licensed)

    novelty = 1.0 if stars < 250 else 0.65
    score = (
        0.42 * relevance
        + 0.24 * recency
        + 0.18 * quality
        + 0.10 * novelty
        + 0.06 * float(licensed)
    )

    reasons = [f"category:{category}"] + [f"keyword:{token}" for token in matches]
    if recency >= 0.75:
        reasons.append("recently-active")
    if licensed:
        reasons.append(f"license:{license_id}")
    if stars >= 100:
        reasons.append("community-signal")
    elif stars < 50:
        reasons.append("emerging")

    full_name = str(repo.get("full_name") or repo.get("path_with_namespace") or repo.get("name") or "")
    url = str(repo.get("html_url") or repo.get("web_url") or "")
    source_id = str(repo.get("id") or full_name)

    return DiscoveryCandidate(
        platform=platform,
        source_id=source_id,
        full_name=full_name,
        url=url,
        category=category,
        score=round(score, 8),
        stars=stars,
        forks=forks,
        pushed_at=pushed_at,
        license_id=str(license_id) if license_id else None,
        reasons=tuple(reasons[:8]),
        description=description,
    )


def candidate_from_mapping(item: Mapping[str, Any]) -> DiscoveryCandidate:
    return DiscoveryCandidate(
        platform=str(item.get("platform") or ""),
        source_id=str(item.get("source_id") or ""),
        full_name=str(item.get("full_name") or ""),
        url=str(item.get("url") or ""),
        category=str(item.get("category") or "other"),
        score=float(item.get("score") or 0.0),
        stars=int(item.get("stars") or 0),
        forks=int(item.get("forks") or 0),
        pushed_at=item.get("pushed_at"),
        license_id=item.get("license_id"),
        reasons=tuple(str(value) for value in item.get("reasons", [])),
        description=str(item.get("description") or ""),
    )


def should_auto_fork(candidate: DiscoveryCandidate, config: Mapping[str, Any], *, now: datetime | None = None) -> bool:
    policy = config.get("fork_policy", {})
    if candidate.score < float(policy.get("auto_fork_threshold", 0.86)):
        return False
    if candidate.stars < int(policy.get("min_stars", 8)):
        return False
    if policy.get("prefer_known_license", True) and not candidate.license_id:
        return False

    now = now or datetime.now(timezone.utc)
    pushed = _parse_time(candidate.pushed_at)
    if pushed is None:
        return False
    max_age = float(policy.get("max_age_days_since_push", 180))
    return (now - pushed).total_seconds() / 86400.0 <= max_age


def merge_candidates(candidates: Sequence[DiscoveryCandidate], limit: int = 80) -> tuple[DiscoveryCandidate, ...]:
    best: dict[tuple[str, str], DiscoveryCandidate] = {}
    for candidate in candidates:
        key = (candidate.platform, candidate.full_name.lower())
        previous = best.get(key)
        if previous is None or candidate.score > previous.score:
            best[key] = candidate
    ordered = sorted(best.values(), key=lambda item: (-item.score, -item.stars, item.full_name.lower()))
    return tuple(ordered[: max(0, limit)])
