from __future__ import annotations

from math import sqrt
from typing import Mapping, Sequence

_EPS = 1e-12


def _nodes(graph: Mapping[str, Sequence[str]]) -> tuple[str, ...]:
    found = set(graph)
    for targets in graph.values():
        found.update(targets)
    return tuple(sorted(found))


def pagerank(
    graph: Mapping[str, Sequence[str]],
    *,
    damping: float = 0.85,
    steps: int = 48,
    seeds: Mapping[str, float] | None = None,
) -> dict[str, float]:
    nodes = _nodes(graph)
    if not nodes:
        return {}
    known = set(nodes)
    raw = {
        node: max(float((seeds or {}).get(node, 1.0)), _EPS)
        for node in nodes
    }
    total = sum(raw.values())
    teleport = {node: raw[node] / total for node in nodes}
    rank = dict(teleport)

    for _ in range(max(1, steps)):
        nxt = {node: (1.0 - damping) * teleport[node] for node in nodes}
        dangling = 0.0
        for source in nodes:
            targets = tuple(
                target for target in graph.get(source, ())
                if target in known and target != source
            )
            if not targets:
                dangling += rank[source]
                continue
            share = damping * rank[source] / len(targets)
            for target in targets:
                nxt[target] += share
        if dangling:
            for node in nodes:
                nxt[node] += damping * dangling * teleport[node]
        rank = nxt

    scale = sum(rank.values()) or 1.0
    return {node: rank[node] / scale for node in nodes}


def hits(
    graph: Mapping[str, Sequence[str]],
    *,
    steps: int = 32,
) -> tuple[dict[str, float], dict[str, float]]:
    nodes = _nodes(graph)
    if not nodes:
        return {}, {}
    known = set(nodes)
    hubs = {node: 1.0 for node in nodes}
    authorities = {node: 1.0 for node in nodes}

    incoming: dict[str, list[str]] = {node: [] for node in nodes}
    outgoing: dict[str, tuple[str, ...]] = {}
    for source in nodes:
        targets = tuple(
            target for target in graph.get(source, ())
            if target in known and target != source
        )
        outgoing[source] = targets
        for target in targets:
            incoming[target].append(source)

    for _ in range(max(1, steps)):
        new_authorities = {
            node: sum(hubs[source] for source in incoming[node])
            for node in nodes
        }
        norm = sqrt(sum(value * value for value in new_authorities.values())) or 1.0
        new_authorities = {
            node: value / norm for node, value in new_authorities.items()
        }

        new_hubs = {
            node: sum(new_authorities[target] for target in outgoing[node])
            for node in nodes
        }
        norm = sqrt(sum(value * value for value in new_hubs.values())) or 1.0
        hubs = {node: value / norm for node, value in new_hubs.items()}
        authorities = new_authorities

    return hubs, authorities


def katz(
    graph: Mapping[str, Sequence[str]],
    *,
    alpha: float | None = None,
    beta: float = 1.0,
    steps: int = 40,
) -> dict[str, float]:
    nodes = _nodes(graph)
    if not nodes:
        return {}
    known = set(nodes)
    incoming: dict[str, list[str]] = {node: [] for node in nodes}
    maximum_degree = 1
    for source in nodes:
        targets = tuple(
            target for target in graph.get(source, ())
            if target in known and target != source
        )
        maximum_degree = max(maximum_degree, len(targets))
        for target in targets:
            incoming[target].append(source)

    attenuation = alpha if alpha is not None else 0.85 / maximum_degree
    scores = {node: 1.0 for node in nodes}
    for _ in range(max(1, steps)):
        nxt = {
            node: beta + attenuation * sum(scores[source] for source in incoming[node])
            for node in nodes
        }
        scale = max(nxt.values(), default=1.0) or 1.0
        scores = {node: value / scale for node, value in nxt.items()}
    return scores


def tarjan_scc(graph: Mapping[str, Sequence[str]]) -> tuple[tuple[str, ...], ...]:
    nodes = _nodes(graph)
    known = set(nodes)
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    components: list[tuple[str, ...]] = []

    def visit(node: str) -> None:
        nonlocal index
        indices[node] = index
        lowlink[node] = index
        index += 1
        stack.append(node)
        on_stack.add(node)

        for target in graph.get(node, ()):
            if target not in known or target == node:
                continue
            if target not in indices:
                visit(target)
                lowlink[node] = min(lowlink[node], lowlink[target])
            elif target in on_stack:
                lowlink[node] = min(lowlink[node], indices[target])

        if lowlink[node] == indices[node]:
            component: list[str] = []
            while stack:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == node:
                    break
            components.append(tuple(sorted(component)))

    for node in nodes:
        if node not in indices:
            visit(node)
    return tuple(sorted(components, key=lambda group: (group[0], len(group))))


def centrality_consensus(
    graph: Mapping[str, Sequence[str]],
    *,
    seeds: Mapping[str, float] | None = None,
) -> tuple[dict[str, float], dict[str, tuple[tuple[str, float], ...]]]:
    pr = pagerank(graph, seeds=seeds)
    hubs, authorities = hits(graph)
    kz = katz(graph)
    sccs = tarjan_scc(graph)

    max_pr = max(pr.values(), default=1.0) or 1.0
    max_hub = max(hubs.values(), default=1.0) or 1.0
    max_auth = max(authorities.values(), default=1.0) or 1.0
    cyclic = {
        node
        for component in sccs
        if len(component) > 1
        for node in component
    }

    result: dict[str, float] = {}
    trace: dict[str, tuple[tuple[str, float], ...]] = {}
    for node in _nodes(graph):
        prn = pr.get(node, 0.0) / max_pr
        hub = hubs.get(node, 0.0) / max_hub
        auth = authorities.get(node, 0.0) / max_auth
        katz_score = kz.get(node, 0.0)
        cycle = 1.0 if node in cyclic else 0.0
        votes = (
            ("pagerank", prn),
            ("hits-hub", hub),
            ("hits-authority", auth),
            ("katz", katz_score),
            ("tarjan-cycle", cycle),
        )
        mean = sum(value for _, value in votes) / len(votes)
        spread = max(value for _, value in votes) - min(value for _, value in votes)
        result[node] = max(0.0, min(1.0, mean * (1.0 - 0.16 * spread)))
        trace[node] = votes
    return result, trace
