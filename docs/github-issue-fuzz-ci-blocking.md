> Filed on the repo as **issue #35** — this file is the canonical body for that issue.

## Summary

Fuzz / property tests (`tests/test_fuzz_properties.py`, `pytest -m fuzz`) currently run in CI **after** the fast suite with **`continue-on-error: true`** so merges are not blocked while we gain confidence.

This issue tracks promoting that step to **blocking** once we have evidence the suite is not flaky in production CI.

## Acceptance criteria (close when all are met)

1. **Merge history review:** The **last 10–15 merges to `main`** have completed CI with the fuzz step **without** the fuzz step failing for reasons attributed to **flakiness** (intermittent red with no code change / no reproducible Hypothesis counterexample).
   - Transient failures that are **reproduced locally** with the printed Hypothesis example count as **bugs or wrong properties**, not flakiness — fix those before flipping to blocking.
2. **Workflow change:** Remove `continue-on-error: true` from the **“Property / fuzz tests”** step in `.github/workflows/ci.yml` (or fold fuzz into the same `pytest` invocation if we standardize on one command).
3. **Docs:** Update **README → CI Pipeline** (and this comment in `ci.yml`) so the fuzz step is described as merge-blocking.

## Notes

- Optional: enable or check **Hypothesis example database / CI artifacts** if we want faster diagnosis when a failure appears.
- If fuzz becomes blocking and we see rare noise, consider **`--hypothesis-profile ci`** or pinned `derandomize` only for CI (document in README).

## Related

- GitHub [**#33** — Test strategy](https://github.com/SantiagoCely/volleyballMechanicsAnalyser/issues/33) (context)
- **`tests/test_fuzz_properties.py`**
