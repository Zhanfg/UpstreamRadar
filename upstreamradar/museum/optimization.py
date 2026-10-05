from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence


@dataclass(frozen=True)
class Item:
    name: str
    cost: int
    utility: float


def exact_knapsack(items: Sequence[Item], budget: int) -> tuple[str, ...]:
    """Exact 0/1 knapsack oracle for small budgeted benchmark instances."""
    if budget <= 0 or not items:
        return ()
    dp: list[tuple[float, tuple[str, ...]]] = [
        (0.0, ()) for _ in range(budget + 1)
    ]
    for item in items:
        if item.cost <= 0:
            raise ValueError("item cost must be positive")
        for capacity in range(budget, item.cost - 1, -1):
            previous_utility, previous_names = dp[capacity - item.cost]
            candidate = (
                previous_utility + item.utility,
                previous_names + (item.name,),
            )
            if candidate[0] > dp[capacity][0]:
                dp[capacity] = candidate
    return max(dp, key=lambda state: (state[0], tuple(sorted(state[1]))))[1]


def celf_select(
    items: Sequence[Item],
    budget: int,
    marginal_gain: Callable[[str, frozenset[str]], float],
) -> tuple[str, ...]:
    """CELF-style lazy greedy for monotone-ish coverage objectives."""
    selected: frozenset[str] = frozenset()
    cost_by_name = {item.name: item.cost for item in items}
    remaining = {
        item.name: [marginal_gain(item.name, selected), 0]
        for item in items
    }
    spent = 0

    while remaining:
        name = max(
            remaining,
            key=lambda candidate: (
                remaining[candidate][0] / cost_by_name[candidate],
                remaining[candidate][0],
                candidate,
            ),
        )
        gain, stamp = remaining[name]
        if stamp != len(selected):
            remaining[name] = [marginal_gain(name, selected), len(selected)]
            continue
        cost = cost_by_name[name]
        del remaining[name]
        if spent + cost > budget:
            continue
        if gain <= 0.0:
            break
        selected = selected | {name}
        spent += cost
    return tuple(sorted(selected))


def epsilon_pareto(
    points: Iterable[Mapping[str, float | str]],
    *,
    maximize: Sequence[str],
    minimize: Sequence[str] = (),
    epsilon: float = 1e-6,
) -> tuple[Mapping[str, float | str], ...]:
    items = tuple(points)

    def dominates(left: Mapping[str, float | str], right: Mapping[str, float | str]) -> bool:
        weak = True
        strict = False
        for key in maximize:
            a, b = float(left[key]), float(right[key])
            weak &= a + epsilon >= b
            strict |= a > b + epsilon
        for key in minimize:
            a, b = float(left[key]), float(right[key])
            weak &= a <= b + epsilon
            strict |= a + epsilon < b
        return bool(weak and strict)

    frontier = [
        item
        for index, item in enumerate(items)
        if not any(
            other_index != index and dominates(other, item)
            for other_index, other in enumerate(items)
        )
    ]
    return tuple(frontier)
