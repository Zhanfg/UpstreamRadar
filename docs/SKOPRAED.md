# SKOPRÆD

**Display name:** SKOPRÆD  
**ASCII namespace:** `Skopraed` / `skopraed`  
**Contract generation:** v1

## Name

SKOPRÆD is an intentionally coined system name.

- Greek **skopos / skopein** contributes the sense of watching, inspecting, and examining.
- Old English **ræd** contributes judgment, counsel, plan, and considered advice.

The intended reading is therefore:

> observe first, then make a bounded judgment.

That matches UpstreamRadar's role: collect upstream evidence, measure uncertainty
and structural impact, then select a constrained observation portfolio.

The ASCII spelling is normative for source paths, package names, schemas,
environment keys, CLI binaries, and network protocols. The ligature spelling is
for human-facing documentation only.

## Collision screening

On 2026-10-05 the exact ASCII name `Skopraed` was checked against:

- public GitHub repository search;
- exact-match general web search;
- common public package-index search terms.

No exact software-system or repository collision was found at that time.
This is a dated namespace check, not a guarantee that nobody can adopt the name
later.

## Architecture

SKOPRÆD is not one language implementation.

```text
providers / telemetry
        │
        ▼
normalised RepositorySignal
        │
        ├──────────────┬───────────────┬────────────────┐
        ▼              ▼               ▼                ▼
  Rust core        Go data plane   C++ native      TypeScript
  inference        collectors      scanning        product layer
        │              │               │                │
        └──────────────┴───────┬───────┴────────────────┘
                               ▼
                    SKOPRÆD v1 contract
                               │
                               ▼
                   portfolio + audit evidence
```

Python remains the orchestration/reference implementation during migration, but
the long-term invariant is that production semantics are specified by the
contract and conformance fixtures rather than by one language's implementation.

## Naming rules

New production identifiers must use one of these forms:

- `SkopraedScheduler`
- `SkopraedConfig`
- `skopraed-v1`
- `skopraed_v1`
- `skopraed-*`

Do not create new identifiers under the retired scheduler codename.

Historical documents are stored under `docs/archive/` using neutral
`LEGACY_SCHEDULER_*` names.

## Contract invariants

All production implementations must preserve:

1. deterministic output for deterministic input;
2. bounded evidence metrics;
3. no fabricated observations or history;
4. explicit algorithm disagreement;
5. budget and ecosystem constraints;
6. stable reason tags;
7. auditability of reference selectors;
8. equivalent ordering under the published tolerance rules.

See `conformance/README.md`.
