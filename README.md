# UpstreamRadar

Automatically maintained upstream development radar for Android, Linux, networking, AI agents, security, and developer tooling.

The repository is designed around a real optimization problem: when upstream sources outnumber available API calls, CI minutes, or analyst attention, **which repositories should be checked first?**

## HARMONY

The first core algorithm is **HARMONY** — **Hierarchical Adaptive Radar Multi-objective Optimizer with Network-aware Yield**.

It combines:

- ecosystem-local robust statistics using median/MAD;
- a hierarchical activity/risk interaction model;
- Bayesian change-probability estimation;
- exponential time decay;
- dependency-graph PageRank-style diffusion;
- grouped anomaly-energy detection;
- uncertainty-aware exploration;
- diversity and redundancy shaping;
- dependency-overlap penalties;
- constrained beam search under API/CI budgets.

The implementation is intentionally dependency-free Python so the mathematical structure is visible rather than hidden behind ML libraries.

### Minimal example

```python
from upstreamradar import HarmonyScheduler, RepositorySignal

records = [
    RepositorySignal(
        name="linux",
        ecosystem="kernel",
        cost=5,
        freshness_hours=1,
        commit_velocity=18,
        security_signal=8,
        dependency_importance=10,
        recent_change_hits=9,
        recent_change_misses=1,
    ),
    RepositorySignal(
        name="android-kernel",
        ecosystem="android",
        cost=4,
        freshness_hours=2,
        commit_velocity=14,
        security_signal=9,
        dependency_importance=10,
        recent_change_hits=8,
        recent_change_misses=2,
    ),
]

result = HarmonyScheduler().schedule(
    records,
    budget=6,
    dependencies={"android-kernel": ["linux"]},
)

for candidate in result.selected:
    print(candidate.name, candidate.base_utility)
```

A fuller executable example is available in [`examples/harmony_demo.py`](examples/harmony_demo.py).

## Learn the algorithm

The complete mathematical derivation is in [`docs/HARMONY.md`](docs/HARMONY.md).

The document explains why each layer exists and derives:

1. robust local normalization;
2. latent activity and risk subspaces;
3. the Bayesian posterior and freshness decay;
4. dependency influence diffusion;
5. grouped anomaly energy;
6. multi-objective utility fusion;
7. diversity-aware marginal utility;
8. constrained beam-search scheduling.

## Repository structure

```text
UpstreamRadar/
├── upstreamradar/
│   ├── __init__.py
│   └── engine.py
├── tests/
│   └── test_engine.py
├── examples/
│   └── harmony_demo.py
├── docs/
│   └── HARMONY.md
├── .github/workflows/
│   ├── python-ci.yml
│   └── verify-upstreamradar-pat.yml
└── pyproject.toml
```

## Validation

CI currently validates the algorithm on Python 3.10, 3.11, 3.12, and 3.13.

The test suite checks deterministic scoring, dependency-hub influence, budget constraints, ecosystem quotas, impossible schedules, duplicate-input rejection, and zero-budget behavior.

## Direction

HARMONY is only the scheduling core. The next layers will connect it to real upstream telemetry:

- GitHub repository activity;
- releases and tags;
- security advisories;
- dependency relationships;
- historical change-hit/miss feedback;
- adaptive scan costs;
- daily and weekly radar reports.

The long-term goal is a reproducible dataset and decision engine rather than a passive list of repository links.
