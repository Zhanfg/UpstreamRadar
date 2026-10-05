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
    _e("theil-sen", "Theil–Sen estimator", "robust-statistics", 1950, "O(n²)",
       "outlier-resistant trend slope"),
    _e("hampel", "Hampel identifier", "robust-statistics", 1974, "O(n)",
       "median/MAD outlier evidence"),
    _e("cusum", "CUSUM", "change-detection", 1954, "O(n)",
       "persistent mean-shift evidence"),
    _e("page-hinkley", "Page–Hinkley", "change-detection", 1954, "O(n)",
       "online positive regime-shift evidence"),
    _e("bocpd-beta", "Beta-Bernoulli BOCPD", "bayesian-change-detection", 2007, "O(n²)",
       "posterior run-length reset probability"),
    _e("adwin", "ADWIN", "change-detection", 2007, "O(n²)",
       "adaptive-window distribution shift evidence"),
    _e("jsd", "Jensen–Shannon divergence", "information-theory", 1991, "O(k)",
       "distributional information gain"),
    _e("wasserstein-1", "1-Wasserstein distance", "information-theory", 1942, "O(n log n)",
       "earth-mover distribution shift"),
    _e("mmd-rbf", "Maximum Mean Discrepancy", "information-theory", 2006, "O(n²)",
       "kernel two-sample distribution shift"),
    _e("pagerank", "PageRank", "graph-centrality", 1998, "O(kE)",
       "stationary dependency influence"),
    _e("hits", "HITS", "graph-centrality", 1999, "O(kE)",
       "hub/authority structure"),
    _e("katz", "Katz centrality", "graph-centrality", 1953, "O(kE)",
       "attenuated walk influence"),
    _e("tarjan-scc", "Tarjan SCC", "graph-structure", 1972, "O(V+E)",
       "cycle condensation and structural complexity"),
    _e("brandes", "Brandes betweenness", "graph-centrality", 2001, "O(VE)",
       "bridge and shortest-path mediation"),
    _e("k-core", "k-core decomposition", "graph-structure", 1983, "O((V+E) log V)",
       "structural core membership"),
    _e("ucb-v", "UCB-V", "online-learning", 2009, "O(1)",
       "variance-aware exploration"),
    _e("kl-ucb", "KL-UCB", "online-learning", 2011, "O(log(1/ε))",
       "Bernoulli information-bound exploration"),
    _e("bayes-ucb", "Bayes-UCB", "online-learning", 2012, "O(log(1/ε)·Iβ)",
       "posterior-quantile exploration"),
    _e("bloom", "Bloom filter", "streaming-sketch", 1970, "O(k)",
       "probabilistic membership prefilter", production=False),
    _e("minhash", "MinHash", "streaming-sketch", 1997, "O(k·n)",
       "scalable dependency-set similarity"),
    _e("count-min", "Count-Min Sketch", "streaming-sketch", 2003, "O(d)",
       "approximate frequency estimation", production=False),
    _e("space-saving", "Space-Saving", "streaming-sketch", 2005, "O(k)",
       "bounded-memory heavy hitters", production=False),
    _e("hyperloglog", "HyperLogLog", "streaming-sketch", 2007, "O(1)",
       "approximate unique-cardinality estimation", production=False),
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
