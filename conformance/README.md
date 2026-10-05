# SKOPRÆD conformance

This directory is the language-neutral source of behavioural truth.

A runtime is not considered production-compatible merely because it implements
similarly named algorithms. It must consume the shared fixtures and satisfy the
same invariants.

## Layout

- `fixtures/`: deterministic RepositorySignal inputs.
- `contract/`: tolerances and required invariants.
- `golden/`: generated, reviewed reference summaries.

## Philosophy

Exact floating-point equality across Python, Rust, Go, C++ and JavaScript is not
a useful requirement. Structural agreement is.

Production runtimes must agree on:

- input validity;
- score bounds;
- budget feasibility;
- selected repository identities;
- top-candidate ordering;
- deterministic replay;
- audit/frontier existence.

Numeric evidence is compared under explicit tolerances from the contract.

The conformance layer is intentionally separate from any one implementation so
no language silently becomes the specification.
