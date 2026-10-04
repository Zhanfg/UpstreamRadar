# Polyglot architecture

UpstreamRadar is evolving from a Python-only automation project into a polyglot upstream-intelligence platform.

The rule is simple: a language is added only when it owns a concrete responsibility. Language count is not a goal by itself; each implementation must contribute a parser, analyzer, runtime primitive, policy engine, ecosystem adapter, statistical kernel, or user-facing component.

## Current language map

| Area | Language | Responsibility |
| --- | --- | --- |
| Orchestration | Python | HARMONY scheduling, collection, policy and reports |
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

All implementations converge conceptually on `schemas/radar-event.schema.json`.

## Layout

```text
apps/          user-facing surfaces
core/          low-level and performance-sensitive primitives
services/      streaming, aggregation and event-processing services
ecosystems/    package-manager and platform-specific analyzers
analytics/     statistical, graph and numerical analysis
rules/         policy and classification engines
schemas/       cross-language normalized contracts
```

## Validation

`Polyglot CI` currently performs direct build or runtime validation for the main implementation set, including Rust, Go, TypeScript, C, C++, x86-64 Assembly, Fortran, Java, Kotlin, R and Julia. Additional language jobs are added when their toolchain cost is justified by the module's maturity and frequency of change.

## Commit policy

Scheduled collection may poll frequently, but repository history must describe real state transitions rather than polling frequency.

- no commit for a no-op collection;
- one atomic radar commit per collection cycle;
- changed snapshots and scheduler evidence are committed together;
- feature work is split only at meaningful, independently reviewable boundaries;
- discovery and Activity Matrix writes remain evidence-backed;
- automation is explicitly identified as automation;
- no empty commits, timestamp churn, artificial rewrites, or fabricated activity.

The result should be a large repository because the system has many real responsibilities, not because history is padded.
