# UpstreamRadar Algorithm Museum

HARMONY v4 treats algorithms as a curated collection rather than a pile of scoring tricks.

Every exhibit must answer four questions:

1. **What historical problem was it designed to solve?**
2. **What invariant does our implementation preserve?**
3. **Where does it sit in the HARMONY pipeline?**
4. **Is it production evidence or an audit/reference exhibit?**

The executable source of truth is `upstreamradar/museum/registry.py`; `museum/catalog.json` is generated from that registry and checked in CI.

## Floor plan

```text
┌──────────────────────────────────────────────────────────────┐
│ Gallery I   Robust statistics                              │
│   Theil–Sen · Huber M-estimator · Hampel                   │
├──────────────────────────────────────────────────────────────┤
│ Gallery II  Sequential / Bayesian change detection          │
│   CUSUM · Page–Hinkley · ADWIN · Beta-Bernoulli BOCPD      │
├──────────────────────────────────────────────────────────────┤
│ Gallery III Information theory                              │
│   entropy · Jensen–Shannon · Wasserstein-1 · RBF MMD       │
├──────────────────────────────────────────────────────────────┤
│ Gallery IV  Graph structure                                 │
│   Katz · Tarjan SCC · k-core · PageRank · HITS · Brandes   │
├──────────────────────────────────────────────────────────────┤
│ Gallery V   Online learning                                 │
│   UCB-V · KL-UCB · Bayes-UCB                               │
├──────────────────────────────────────────────────────────────┤
│ Gallery VI  Streaming / approximation                       │
│   Bloom · MinHash · Count-Min · Space-Saving · HyperLogLog │
├──────────────────────────────────────────────────────────────┤
│ Gallery VII Combinatorial & submodular optimization         │
│   0/1 knapsack · CELF lazy greedy                          │
├──────────────────────────────────────────────────────────────┤
│ Gallery VIII Multi-objective decision                       │
│   ε-Pareto archive                                         │
└──────────────────────────────────────────────────────────────┘
```

## Timeline

| Year | Exhibit | Gallery | Production role |
| ---: | --- | --- | --- |
| 1942 | 1-Wasserstein distance | Information theory | empirical distribution transport distance |
| 1950 | Theil–Sen estimator | Robust statistics | robust trend slope |
| 1953 | Katz centrality | Graph | attenuated dependency-walk influence |
| 1954 | CUSUM | Change detection | persistent shift evidence |
| 1954 | Page–Hinkley | Change detection | online regime-shift evidence |
| 1957 | 0/1 knapsack DP | Optimization | small-instance audit oracle |
| 1964 | Huber M-estimator | Robust statistics | outlier-resistant activity location |
| 1972 | Tarjan SCC | Graph | cyclic dependency structure |
| 1974 | Hampel identifier | Robust statistics | median/MAD outlier evidence |
| 1983 | k-core decomposition | Graph | structural core membership |
| 1985 | ε-Pareto archive | Multi-objective | diagnostic non-dominated frontier |
| 1991 | Jensen–Shannon divergence | Information theory | history distribution shift |
| 2006 | Maximum Mean Discrepancy | Information theory | kernel two-sample distribution shift |
| 1970 | Bloom filter | Sketches | probabilistic membership |
| 1997 | MinHash | Sketches | dependency-set novelty at scale |
| 2003 | Count-Min Sketch | Sketches | approximate frequencies |
| 2005 | Space-Saving | Sketches | bounded-memory heavy hitters |
| 2007 | HyperLogLog | Sketches | approximate cardinality |
| 1998 | PageRank | Graph | stationary dependency influence |
| 1999 | HITS | Graph | hub/authority decomposition |
| 2001 | Brandes betweenness | Graph | shortest-path mediation |
| 2007 | CELF | Submodular optimization | challenger/reference selector |
| 2007 | Bayesian online changepoint detection | Bayesian inference | run-length reset evidence |
| 2007 | ADWIN | Change detection | adaptive-window distribution shift |
| 2009 | UCB-V | Online learning | variance-aware exploration |
| 2011 | KL-UCB | Online learning | information-bound exploration |
| 2012 | Bayes-UCB | Online learning | posterior-quantile exploration |

Years identify the canonical publication/era represented by the exhibit; the repository implementation is clean-room and intentionally compact.

## Curatorial rule

A production candidate does **not** receive fifteen independent bonuses.

Algorithms first vote inside a gallery. The gallery outputs a bounded consensus and a disagreement measure. HARMONY then combines gallery-level evidence.

For example, the change-detection gallery is:

```text
Page–Hinkley ─┐
CUSUM ─────────┼─> change consensus ─┐
BOCPD ─────────┘                     │
                                      ├─> museum consensus
Huber ─────────────> robust activity ┤
JSD ───────────────> information gain│
Graph ensemble ─────> graph consensus│
UCB-V / KL-UCB ────> exploration ───┤
MinHash ────────────> novelty ───────┘
```

High disagreement is preserved as evidence and slightly penalizes automatic scheduling. It is **not hidden by averaging**.

## Graph gallery

Graph influence is deliberately plural:

- **PageRank**: stationary influence under directed propagation.
- **HITS**: separates hubs from authorities.
- **Katz**: counts attenuated walks, preserving multi-hop structure.
- **Brandes betweenness**: measures shortest-path mediation / bridge structure.
- **k-core**: distinguishes dense structural core from peripheral nodes.
- **Tarjan SCC**: exposes cyclic components that centrality alone cannot describe.

The scheduler consumes their consensus rather than declaring one centrality metric universally correct.

## Change gallery

The detectors cover different failure modes:

- **CUSUM** reacts to persistent shifts.
- **Page–Hinkley** is lightweight and streaming-friendly.
- **Beta-Bernoulli BOCPD** maintains run-length posterior evidence and can react to model resets.
- **ADWIN** scans adaptive window cuts with a Hoeffding-style confidence bound.
- **Theil–Sen** contributes a robust trend vote that is resistant to isolated spikes.

BOCPD's changepoint branch uses the prior predictive; the growth branch uses each run-length state's posterior predictive. A regression test protects this distinction.

## Optimization gallery

The production scheduler remains the constrained beam/submodular search because it supports ecosystem caps, coverage and evidence interactions.

Reference exhibits are still valuable:

- exact knapsack catches obvious budget/utility regressions on small instances;
- CELF provides a classic lazy-greedy challenger for submodular coverage;
- ε-Pareto exposes candidates that are non-dominated across utility, novelty and risk.

Reference algorithms do not get artificial production weight merely because they exist.

## Machine-readable catalog

Run:

```sh
python scripts/export_museum_catalog.py --check
```

The command fails if `museum/catalog.json` no longer matches the executable registry.

## Design boundary

The museum rejects three forms of fake complexity:

- duplicate algorithms with renamed variables;
- algorithms that have no stated role or invariant;
- source obfuscation presented as algorithmic sophistication.

Release minification/symbol stripping remains separate from the museum and does not affect source auditability.


## Streaming gallery

The streaming gallery is intentionally separated into **production** and **reference/infrastructure** exhibits.

- MinHash currently contributes dependency-set novelty to HARMONY.
- Bloom Filter, Count-Min Sketch, Space-Saving and HyperLogLog are executable infrastructure exhibits for future high-volume collectors and are tested for their core invariants.
- They do not receive scheduler weight merely because they exist.

## Information-distance gallery

Distribution shift is now triangulated by three geometrically different views:

- Jensen–Shannon divergence: probability-mass shape;
- Wasserstein-1: how far mass must move;
- RBF Maximum Mean Discrepancy: kernel-space two-sample discrepancy.

Their disagreement is preserved, so a binning artifact in JSD cannot silently dominate the result.
