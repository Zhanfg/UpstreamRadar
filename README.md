# UpstreamRadar

Automatically maintained upstream development radar for Android, Linux, networking, AI agents, security, and developer tooling.

The repository is designed around a real optimization problem: when upstream sources outnumber available API calls, CI minutes, or analyst attention, **which repositories should be checked first?**

## HARMONY

The core algorithm is **HARMONY** — **Hierarchical Adaptive Radar Multi-objective Optimizer with Network-aware Yield**.

**HARMONY v2** upgrades the original single-round ranker into a stateful, content-aware information-selection system. It combines:

- ecosystem-local robust statistics with global shrinkage for small groups;
- Bayesian change-probability estimation with freshness decay;
- fast / medium / slow EWMA dynamics;
- online regime-shift detection over semantic-impact history;
- change entropy and impact volatility;
- evidence-based content-yield estimation;
- reliability-aware source weighting;
- deterministic exploration pressure inspired by upper-confidence bounds;
- signal-seeded dependency and ecosystem graph diffusion;
- submodular-style portfolio coverage;
- diversity, redundancy, and dependency-overlap shaping;
- state-specific fractional-knapsack bounds inside constrained beam search.

The implementation remains dependency-free Python so the mathematical structure stays visible rather than being hidden behind ML libraries.

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

The original derivation is in docs/HARMONY.md, and the v2 architecture is specified in docs/HARMONY_V2.md.

The document explains why each layer exists and derives:

1. robust local normalization;
2. latent activity and risk subspaces;
3. the Bayesian posterior and freshness decay;
4. dependency influence diffusion;
5. grouped anomaly energy;
6. multi-objective utility fusion;
7. diversity-aware marginal utility;
8. constrained beam-search scheduling.

HARMONY v2 adds multi-timescale dynamics, semantic impact, regime-shift detection, content yield, reliability, graph seeding, portfolio coverage, and a budget-aware upper bound.

## Evidence-first content planning

The scheduler now produces report-ready content opportunities in addition to scan priority.

build_content_plan() converts selected candidates into:

- a content priority;
- a suggested investigation angle;
- compact reason tags such as regime-shift or dependency-hub;
- the strongest numeric evidence behind the recommendation.

It deliberately does not invent article prose. Reports remain grounded in real upstream telemetry and can explain why an item is worth attention.

## Repository structure

```text
UpstreamRadar/
├── upstreamradar/
│   ├── __init__.py
│   ├── engine.py
│   ├── collector.py
│   └── reviewer.py
├── tests/
│   ├── test_engine.py
│   ├── test_collector.py
│   └── test_reviewer.py
├── examples/
│   └── harmony_demo.py
├── docs/
│   ├── HARMONY.md
│   ├── AUTOMATION.md
│   └── CODE_REVIEW.md
├── .github/workflows/
│   ├── python-ci.yml
│   ├── radar.yml
│   ├── code-review.yml
│   └── verify-upstreamradar-pat.yml
└── pyproject.toml
```

## Automation

The live radar runs automatically from GitHub Actions. Scheduled wake-ups use
off-boundary minutes (`:07/:22/:37/:52`) to reduce scheduler contention.

If GitHub delays scheduled execution, the next successful collection increases
its **current** scan breadth according to elapsed time, up to 2.5×. It never
backdates commits or fabricates historical observations.

See [docs/AUTOMATION.md](docs/AUTOMATION.md).

## Automated Code Review

Pull requests targeting `main` receive a repository-local automated COMMENT
review. The reviewer analyzes the unified diff for security and maintainability
risks, including possible secrets, dangerous dynamic execution, shell injection
risk, broad exception handling, deep nesting, and source changes without tests.

The review is explicitly marked as automated and never auto-approves a PR.

See [docs/CODE_REVIEW.md](docs/CODE_REVIEW.md).

## Validation

CI currently validates the algorithm on Python 3.10, 3.11, 3.12, and 3.13.

The test suite covers HARMONY scoring and constraints, resilient scheduling,
collector semantics, and automated code-review rules.

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
