from __future__ import annotations

from .model import AlgorithmExhibit


def _e(
    slug: str,
    name: str,
    family: str,
    introduced: int,
    complexity: str,
    role: str,
    production: bool = True,
    notes: str = "",
) -> AlgorithmExhibit:
    return AlgorithmExhibit(
        slug=slug,
        name=name,
        family=family,
        introduced=introduced,
        complexity=complexity,
        role=role,
        production=production,
        notes=notes,
    )


EXHIBITS = (
    _e("huber", "Huber M-estimator", "robust-statistics", 1964, "O(n·k)",
       "robust activity location under outliers"),
    _e("cusum", "CUSUM", "change-detection", 1954, "O(n)",
       "persistent mean-shift evidence"),
    _e("page-hinkley", "Page–Hinkley", "change-detection", 1954, "O(n)",
       "online positive regime-shift evidence"),
    _e("bocpd-beta", "Beta-Bernoulli BOCPD", "bayesian-change-detection", 2007, "O(n²)",
       "posterior run-length reset probability"),
    _e("jsd", "Jensen–Shannon divergence", "information-theory", 1991, "O(k)",
       "distributional information gain"),
    _e("pagerank", "PageRank", "graph-centrality", 1998, "O(kE)",
       "stationary dependency influence"),
    _e("hits", "HITS", "graph-centrality", 1999, "O(kE)",
       "hub/authority structure"),
    _e("katz", "Katz centrality", "graph-centrality", 1953, "O(kE)",
       "attenuated walk influence"),
    _e("tarjan-scc", "Tarjan SCC", "graph-structure", 1972, "O(V+E)",
       "cycle condensation and structural complexity"),
    _e("ucb-v", "UCB-V", "online-learning", 2009, "O(1)",
       "variance-aware exploration"),
    _e("kl-ucb", "KL-UCB", "online-learning", 2011, "O(log(1/ε))",
       "Bernoulli information-bound exploration"),
    _e("minhash", "MinHash", "streaming-sketch", 1997, "O(k·n)",
       "scalable dependency-set similarity"),
    _e("celf", "CELF lazy greedy", "submodular-optimization", 2007, "O(n log n + q)",
       "coverage-aware portfolio construction", production=False,
       notes="benchmark/alternative selector; beam search remains default"),
    _e("knapsack-dp", "0/1 Knapsack dynamic programming", "combinatorial-optimization", 1957, "O(nB)",
       "exact small-instance optimality oracle", production=False),
    _e("epsilon-pareto", "ε-Pareto archive", "multiobjective-optimization", 1985, "O(n²)",
       "non-dominated diagnostic frontier", production=False),
)


_BY_SLUG = {item.slug: item for item in EXHIBITS}


def exhibit(slug: str) -> AlgorithmExhibit:
    try:
        return _BY_SLUG[slug]
    except KeyError as exc:
        raise KeyError(f"unknown algorithm exhibit: {slug}") from exc
