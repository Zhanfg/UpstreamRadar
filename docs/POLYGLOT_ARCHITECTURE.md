# Polyglot architecture

UpstreamRadar is evolving from a Python-only automation project into a polyglot upstream-intelligence platform.

The rule is simple: a language is added only when it owns a concrete responsibility. Language count is not a goal by itself; each implementation must contribute a parser, analyzer, runtime primitive, policy engine, ecosystem adapter, statistical kernel, infrastructure contract, or user-facing component.

## Current implementation map

### Programming languages

| Area | Language | Responsibility |
| --- | --- | --- |
| Orchestration | Python | SKOPRÆD scheduling, collection, policy and reports |
| Native core | Rust | stable event fingerprinting and native transforms |
| Native core | C | low-overhead host/runtime probes |
| Native core | C++ | source-change scoring primitives |
| Native core | Zig | allocation-free repository fingerprinting |
| Native core | Assembly | x86-64 FNV-1a hot-path primitive |
| Native core | V | repository slug normalization |
| Services | Go | streaming event aggregation |
| Services | Elixir | repository event-window reduction |
| Services | Erlang | deterministic retry/backoff policy |
| Services | Common Lisp | normalized event deduplication |
| Web | TypeScript | typed dashboard-facing data summaries |
| JVM ecosystem | Java | Maven dependency semantics |
| JVM ecosystem | Kotlin | Gradle/Kotlin dependency semantics |
| JVM ecosystem | Groovy | Gradle repository-policy analysis |
| JVM analytics | Scala | rolling activity trend estimation |
| JVM analytics | Clojure | dependency graph reachability |
| .NET ecosystem | C# | NuGet dependency semantics |
| .NET analytics | F# | change-point scoring |
| Apple ecosystem | Swift | SwiftPM/release-tag semantics |
| Apple ecosystem | Objective-C | Apple bundle-version comparison |
| Flutter ecosystem | Dart | pub constraint classification |
| Ruby ecosystem | Ruby | RubyGems requirement risk |
| PHP ecosystem | PHP | Composer constraint classification |
| Perl ecosystem | Perl | CPAN release classification |
| Crystal ecosystem | Crystal | Shards dependency requirements |
| D ecosystem | D | dependency-cycle detection |
| Nim ecosystem | Nim | release-tag normalization |
| Statistical analytics | R | robust trend statistics |
| Numerical analytics | Julia | reusable numerical trend primitives |
| Numerical analytics | Fortran | rolling trend statistics kernel |
| Numerical analytics | Pascal | EWMA trend kernel |
| Policy | OCaml | typed policy threshold classification |
| Policy | Lua | embeddable semantic policy rules |
| Policy | Ada | deterministic severity classification |
| Functional analytics | Haskell | typed semantic impact model |

### Engineering languages and DSLs

| Area | Language / DSL | Responsibility |
| --- | --- | --- |
| Portable automation | Shell | repository/bootstrap preflight |
| Windows automation | PowerShell | Windows collector diagnostics |
| Storage | SQL | normalized radar event persistence |
| Reproducibility | Nix | polyglot development shell |
| Infrastructure | Terraform / HCL | collector deployment contract |
| Policy | Rego | evidence-based escalation policy |
| Configuration | CUE | radar configuration validation contract |
| API | GraphQL | typed repository/event query surface |

This gives the branch **36 programming languages plus 8 engineering languages/DSLs**, for **44 distinct implementation-language surfaces**.

All implementations converge conceptually on `schemas/radar-event.schema.json`.

## Layout

```text
apps/          user-facing surfaces
api/           query contracts
core/          low-level and performance-sensitive primitives
services/      streaming, aggregation and event-processing services
ecosystems/    package-manager and platform-specific analyzers
analytics/     statistical, graph and numerical analysis
rules/         policy and classification engines
schemas/       cross-language normalized contracts
storage/       persistence schema
infra/         deployment contracts
scripts/       portable operational tooling
```

## SKOPRÆD legacy-v3 stage ownership

The repository is no longer organized as a collection of unrelated language demos. Major language families own stages of one normalized evidence pipeline:

1. **Observation and runtime state** — Python, Go, C, PowerShell and Shell collect or validate raw operational evidence.
2. **Native transforms** — Rust, C++, Zig and x86-64 Assembly provide fingerprinting, nonlinear scoring, distance and low-level hot-path primitives.
3. **Ecosystem semantics** — Java, Kotlin, Groovy, C#, Swift, Objective-C, Dart, Ruby, PHP, Perl, Crystal and Nim classify package/release stability and compatibility risk.
4. **Graph structure** — Python, Clojure and D implement dependency diffusion, reachability, cycle and structural-novelty reasoning.
5. **Statistical dynamics** — Python, R, Julia, Scala, F#, Fortran and Pascal implement EWMA, change ensembles, Bayesian surprise and CVaR-style tail risk.
6. **Typed policy** — Haskell, OCaml, Lua, Rego, Ada and Common Lisp implement impact fusion, risk adjustment, policy thresholds and Pareto selection.
7. **Persistence and contracts** — JSON Schema, SQL, GraphQL, CUE and Terraform keep the v3 evidence model consistent across storage, API and deployment.
8. **Release hardening** — TypeScript/esbuild and native strip tooling harden generated release artifacts while leaving source code auditable.

Cross-language semantics are anchored by `tests/fixtures/harmony_v3_vectors.json`, `schemas/archive/legacy-score-v3.schema.json`, and the Python reference scheduler.

## Validation

`Polyglot CI` validates the main implementation set and now runs semantic tests for Rust/Go/Python plus numerical consistency checks in R and Julia. Native release artifacts are stripped and the web v3 bundle is minified in CI.

Additional language jobs are added when their toolchain cost is justified by module maturity and change frequency. A language being present does not automatically justify a heavyweight CI runtime.

## Commit policy

Scheduled collection may poll frequently, but repository history must describe real state transitions rather than polling frequency.

- no commit for a no-op collection;
- one atomic radar commit per collection cycle;
- changed snapshots and scheduler evidence are committed together;
- feature work is split only at meaningful, independently reviewable boundaries;
- discovery and Activity Matrix writes remain evidence-backed;
- automation is explicitly identified as automation;
- no empty commits, timestamp churn, artificial rewrites, or fabricated activity.

The repository should become large because the system has many real responsibilities, not because history is padded.
