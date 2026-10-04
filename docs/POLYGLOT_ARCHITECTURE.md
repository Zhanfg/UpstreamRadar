# Polyglot architecture

UpstreamRadar is evolving from a Python-only automation project into a polyglot upstream-intelligence platform.

The rule is simple: a language is added only when it owns a concrete responsibility.

| Area | Language | Responsibility |
| --- | --- | --- |
| HARMONY orchestration | Python | scheduling, collection, policy and reports |
| Event fingerprinting | Rust | stable event identity and CPU-efficient native transforms |
| Event aggregation | Go | streaming aggregation and network-service building blocks |
| Web data model | TypeScript | dashboard-facing typed summaries |
| Native change scoring | C++ | low-overhead source-change scoring primitives |
| Maven analysis | Java | JVM/Maven dependency semantics |
| Gradle analysis | Kotlin | Gradle/Kotlin dependency semantics |
| Statistical reports | R | robust trend analysis |
| Numerical analytics | Julia | reusable numerical trend primitives |

All implementations converge on `schemas/radar-event.schema.json`.

## Commit policy

Scheduled collection is allowed to poll frequently, but repository history should describe real state transitions rather than polling frequency.

- no commit for a no-op collection;
- one atomic radar commit per collection cycle;
- changed snapshots and scheduler evidence are committed together;
- discovery and Activity Matrix writes remain evidence-backed;
- automation is explicitly identified as automation.

This keeps the history useful for archaeology and avoids manufacturing activity.
