# Automated Code Review

UpstreamRadar includes a repository-local pull-request reviewer implemented in
`upstreamradar/reviewer.py`.

The goal is to make reviews reproducible and inspectable instead of hiding them
behind an opaque external service.

## Trigger

The workflow runs for pull requests targeting `main` when they are:

- opened;
- updated with new commits;
- reopened;
- marked ready for review.

Each head SHA is reviewed at most once.

## Review semantics

The workflow submits a GitHub **COMMENT review**. It deliberately does **not**
auto-approve a pull request and it does not pretend to be human review.

Every review starts with:

> Automated Code Review

and explicitly states that the result is heuristic.

## Current rules

The analyzer inspects added lines and repository-level change structure.

### Critical

- likely credential/token/secret literals.

### High

- Python `eval(...)` / `exec(...)`;
- `subprocess.*(..., shell=True)`;
- dangerous `pull_request_target` + checkout combinations.

### Medium

- broad `except Exception:` / `except BaseException:`;
- newly added Python nesting depth >= 6;
- source-code changes without corresponding test changes.

### Low

- TODO / FIXME / HACK / XXX markers.

## Why COMMENT instead of APPROVE

An automated heuristic should provide evidence, not impersonate a maintainer's
approval decision. CI remains responsible for executable validation, while this
reviewer surfaces structural and security smells.

The two signals are intentionally separate:

```text
PR
├── Python CI                 executable correctness
└── Automated Code Review     heuristic engineering review
```

## Idempotency

The review body embeds:

```html
<!-- upstreamradar-review:<HEAD_SHA> -->
```

Before submitting, the workflow checks existing PR reviews for that marker.
Re-running the workflow therefore does not duplicate reviews for the same code.

## Extending the reviewer

New rules should be:

1. deterministic;
2. explainable;
3. covered by tests;
4. conservative enough to avoid excessive noise;
5. assigned an explicit severity.

The module intentionally returns structured `ReviewFinding` objects so future
versions can add inline annotations, SARIF export, or learned risk weighting
without replacing the core parser.
