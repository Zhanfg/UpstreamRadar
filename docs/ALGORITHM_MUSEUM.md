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
│   Huber M-estimator                                        │
├──────────────────────────────────────────────────────────────┤
│ Gallery II  Sequential / Bayesian change detection          │
│   CUSUM · Page–Hinkley · Beta-Bernoulli BOCPD              │
├──────────────────────────────────────────────────────────────┤
│ Gallery III Information theory                              │
│   entropy · Jensen–Shannon divergence                      │
├──────────────────────────────────────────────────────────────┤
│ Gallery IV  Graph structure                                 │
│   Katz · Tarjan SCC · PageRank · HITS                      │
├──────────────────────────────────────────────────────────────┤
│ Gallery V   Online learning                                 │
│   UCB-V · KL-UCB                                           │
├──────────────────────────────────────────────────────────────┤
│ Gallery VI  Streaming / approximation                       │
│   MinHash dependency similarity                            │
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
| 1953 | Katz centrality | Graph | attenuated dependency-walk influence |
| 1954 | CUSUM | Change detection | persistent shift evidence |
| 1954 | Page–Hinkley | Change detection | online regime-shift evidence |
| 1957 | 0/1 knapsack DP | Optimization | small-instance audit oracle |
| 1964 | Huber M-estimator | Robust statistics | outlier-resistant activity location |
| 1972 | Tarjan SCC | Graph | cyclic dependency structure |
| 1985 | ε-Pareto archive | Multi-objective | diagnostic non-dominated frontier |
| 1991 | Jensen–Shannon divergence | Information theory | history distribution shift |
| 1997 | MinHash | Sketches | dependency-set novelty at scale |
| 1998 | PageRank | Graph | stationary dependency influence |
| 1999 | HITS | Graph | hub/authority decomposition |
| 2007 | CELF | Submodular optimization | challenger/reference selector |
| 2007 | Bayesian online changepoint detection | Bayesian inference | run-length reset evidence |
| 2009 | UCB-V | Online learning | variance-aware exploration |
| 2011 | KL-UCB | Online learning | information-bound exploration |

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
- **Tarjan SCC**: exposes cyclic components that centrality alone cannot describe.

The scheduler consumes their consensus rather than declaring one centrality metric universally correct.

## Change gallery

The detectors cover different failure modes:

- **CUSUM** reacts to persistent shifts.
- **Page–Hinkley** is lightweight and streaming-friendly.
- **Beta-Bernoulli BOCPD** maintains run-length posterior evidence and can react to model resets.

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
