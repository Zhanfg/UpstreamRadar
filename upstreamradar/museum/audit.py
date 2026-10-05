from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .optimization import Item, celf_select, epsilon_pareto, exact_knapsack


@dataclass(frozen=True)
class AuditPoint:
    name: str
    cost: int
    utility: float
    novelty: float
    risk: float
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class MuseumAuditReport:
    production_selected: tuple[str, ...]
    base_knapsack_selected: tuple[str, ...]
    celf_selected: tuple[str, ...]
    pareto_frontier: tuple[str, ...]
    production_base_utility: float
    exact_base_utility: float
    base_utility_ratio: float


def audit_portfolio(
    points: Iterable[AuditPoint],
    *,
    budget: int,
    production_selected: Iterable[str],
) -> MuseumAuditReport:
    items = tuple(points)
    by_name = {item.name: item for item in items}
    production = tuple(sorted(set(production_selected)))

    exact = tuple(sorted(exact_knapsack(
        [Item(item.name, item.cost, item.utility) for item in items],
        budget,
    )))

    tags = {item.name: item.tags for item in items}

    def marginal(name: str, selected: frozenset[str]) -> float:
        covered = set()
        for selected_name in selected:
            covered.update(tags.get(selected_name, ()))
        new_tags = tags.get(name, frozenset()) - covered
        point = by_name[name]
        return (
            float(len(new_tags))
            + 0.50 * point.utility
            + 0.25 * point.novelty
            - 0.15 * point.risk
        )

    celf = celf_select(
        [Item(item.name, item.cost, item.utility) for item in items],
        budget,
        marginal,
    )

    frontier_points = epsilon_pareto(
        [
            {
                "name": item.name,
                "utility": item.utility,
                "novelty": item.novelty,
                "risk": item.risk,
            }
            for item in items
        ],
        maximize=("utility", "novelty"),
        minimize=("risk",),
    )
    frontier = tuple(sorted(str(item["name"]) for item in frontier_points))

    production_utility = sum(
        by_name[name].utility
        for name in production
        if name in by_name
    )
    exact_utility = sum(
        by_name[name].utility
        for name in exact
        if name in by_name
    )
    ratio = (
        min(1.0, production_utility / exact_utility)
        if exact_utility > 0.0
        else 1.0
    )

    return MuseumAuditReport(
        production_selected=production,
        base_knapsack_selected=exact,
        celf_selected=tuple(sorted(celf)),
        pareto_frontier=frontier,
        production_base_utility=production_utility,
        exact_base_utility=exact_utility,
        base_utility_ratio=ratio,
    )
