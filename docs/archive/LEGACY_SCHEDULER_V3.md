# SKOPRÆD legacy-v3 — Risk-Aware Polyglot Information Scheduling

SKOPRÆD legacy-v3 turns the scheduler from a Python-centric ranking engine into a cross-language information-selection pipeline.

The design remains deterministic and evidence-first. Complexity is introduced only where it changes selection quality, robustness, or explainability.

## Pipeline

```text
raw upstream telemetry
    ↓
hierarchical robust normalization
    ↓
ecosystem empirical-Bayes hyperprior
    ↓
posterior change probability
    ↓
multi-timescale dynamics
    ↓
change-point ensemble
    ├─ Page-Hinkley style excursion
    ├─ robust last-point jump
    └─ least-squares trend slope
    ↓
Bayesian surprise
    ↓
dependency graph diffusion
    ↓
structural novelty
    ↓
tail-risk estimation
    ↓
risk-adjusted utility
    ↓
submodular coverage + diversity search
    ↓
budgeted beam selection
```

## Ecosystem empirical Bayes

SKOPRÆD legacy-v3 estimates an ecosystem-level Beta hyperprior from recent hit/miss evidence, then shrinks sparse ecosystems toward the global change-rate baseline. The prior strength and global shrinkage are configurable.

This prevents a repository with only one or two observations from looking artificially certain while still allowing mature ecosystems to retain their own behavior.

## Bayesian surprise

The scheduler compares the empirical recent change rate q against the current predictive probability p using Bernoulli KL divergence:

```
D_KL(q || p) =
q log(q/p) + (1-q) log((1-q)/(1-p))
```

The divergence is transformed into [0,1]. A source can therefore become important even when its raw activity is modest, if its behavior is unexpectedly different from the model.

## Change-point ensemble

v2 used a Page-Hinkley/CUSUM-like signal. v3 keeps it, but combines it with:

1. a robust jump score using median/MAD against the latest observation;
2. a least-squares slope signal over the active history window.

The three signals are fused instead of trusting any one detector.

## Structural novelty

Dependency structure is scored by:

- dependency rarity across the tracked universe;
- dependency breadth;
- intrinsic repository novelty.

This rewards sources whose dependency shape adds genuinely new information rather than duplicating already-covered topology.

## Tail risk

The impact history is converted to a bounded CVaR-style tail estimate. Security signal, breakage risk, and failure streak are then folded into the same risk surface.

Tail risk does not automatically suppress a source. It discounts raw utility while also surfacing a reason tag when risk itself is operationally important.

## Risk-adjusted utility

The original multi-objective score is extended with Bayesian surprise and structural novelty. The result is then adjusted by tail risk and source reliability before cost normalization and portfolio selection.

The scheduler exposes both `risk_adjusted_utility` and final `base_utility` so reports can distinguish information value from operational scheduling value.

## Polyglot decomposition

The v3 contract lives at `schemas/archive/legacy-score-v3.schema.json`.

Different languages may implement independent stages:

- Rust/C/C++/Zig/Assembly: fingerprints, native statistics and hot-path transforms;
- Go/Elixir/Erlang: stream aggregation, windows and retry semantics;
- TypeScript: typed dashboard projection and Pareto/frontier views;
- Java/Kotlin/Groovy/Scala/Clojure: JVM ecosystem parsing, dependency graphs and ranking;
- C#/F#: .NET dependency and change-point analysis;
- R/Julia/Fortran/Pascal: statistical and numerical kernels;
- Haskell/OCaml/Lua/Rego/Ada/Common Lisp: typed policy, risk and rule evaluation.

Cross-language implementations do not need to duplicate the full scheduler. They own one mathematically defined stage and emit normalized evidence.

## Release hardening

Obfuscation is restricted to generated release artifacts:

- minification for web bundles;
- native symbol stripping for release binaries;
- optional JVM/.NET release symbol reduction where supported.

Source code stays readable and reviewable. SKOPRÆD legacy-v1 does not use source obfuscation to manufacture apparent complexity.

## Invariants

- deterministic output for deterministic input;
- no fabricated observations;
- no synthetic history backfill;
- no random commit generation;
- bounded evidence metrics;
- backward-compatible RepositorySignal construction;
- explicit reasons for high-surprise, structural-novelty and tail-risk selections.
