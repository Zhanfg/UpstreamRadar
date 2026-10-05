# Automation architecture

UpstreamRadar is designed to operate without manual daily intervention.

## Schedule

GitHub Actions wakes the collector every 15 minutes.

The wake-up cadence is intentionally different from the commit cadence. A deterministic time-of-day gate decides whether the slot should perform a scan:

| Local time (Asia/Shanghai) | Run probability |
| --- | ---: |
| 00:00–05:59 | 40% |
| 06:00–08:59 | 70% |
| 09:00–17:59 | 95% |
| 18:00–22:59 | 85% |
| 23:00–23:59 | 60% |

This produces about 72 scheduled collection cycles per day on average before upstream-change commits are added.

Because the gate is derived from the 15-minute time slot hash, re-running the same scheduled slot makes the same decision. Manual workflow dispatch bypasses the gate.

## One collection cycle

1. Load historical Bayesian/change state.
2. Convert repository history into SKOPRÆD signals.
3. Apply dependency-aware scoring and budgeted scheduling.
4. Select at most 16 repositories within the configured scan budget.
5. Query live GitHub repository metadata and latest release metadata.
6. Compare the observation with the last committed snapshot.
7. Create one atomic commit per repository whose real upstream snapshot changed.
8. Update the SKOPRÆD learning state.
9. Store one immutable run journal.
10. Regenerate the daily report.
11. Commit those operational records as one checkpoint.
12. Open an Issue only after a target fails collection at least three consecutive checks.

## Why checkpoint commits are real data

A checkpoint is not an empty activity commit. It records new negative or positive evidence for the Bayesian scheduler.

If a repository was scanned and did not change, that observation increases the scheduler's recent miss evidence. If it changed, the hit evidence and EWMA activity are updated.

The committed model therefore represents the exact information state used to decide future scans.

## Atomic snapshot commits

When multiple repositories change in the same cycle, they are committed separately:

```text
[data] refresh torvalds/linux
[data] refresh openai/openai-python
[data] refresh MetaCubeX/mihomo
[radar] checkpoint 2026-09-29T02:15:00Z
```

This gives each data commit one clear semantic meaning and makes historical diffs useful.

## CI isolation

Code CI only runs when algorithm, tests, examples, configuration, packaging, or the CI workflow itself changes.

Generated paths such as:

- `data/`
- `state/`
- `reports/`

do not trigger the Python version matrix. This prevents the automated data stream from wasting runner time.

## Authentication

The scheduled workflow expects one repository secret:

```text
UPSTREAMRADAR_PAT
```

The token is never written to repository files or logs. It is used for authenticated GitHub API reads, pushing generated data, and creating persistent-failure Issues.
