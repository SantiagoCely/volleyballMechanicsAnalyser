# Volleyball Mechanics Analyser — Dev Workflow

> For full project documentation (architecture, output schema, metrics reference, CLI flags) see `README.md`. Jump composite scoring and session rollups are under **Output Format → Jump scoring** and **SESSION_SUMMARY** in `README.md`.

## Planning docs (agents)

Implementation plans and issue/task breakdown files exist only to steer work — **do not commit them** to this repository (no new plan `.md` files under `docs/` or elsewhere from agent work unless the maintainer explicitly asks that a specific document be persisted). Prefer keeping plans in chat or local-only notes.

## Running the analyser

See `README.md` — [Quick Start](#quick-start) and [CLI Flags](#cli-flags).

## Running tests

```bash
# Fast tests (no GPU, ~2–4 s) — run after every change
python -m pytest tests/ -v -m "not slow and not fuzz and not stress"

# Full suite including tracker smoke test (~15 s); still excludes fuzz + stress
python -m pytest tests/ -v -m "not fuzz and not stress"

# Single file
python -m pytest tests/test_e2e.py -v -m "not slow and not fuzz and not stress"
python -m pytest tests/test_analyzer.py -v
```

See `README.md` — [Testing](#testing) for test structure and layer descriptions.

## Adding a new metric — checklist

1. Add a regression test to `tests/test_e2e.py` (`TestE2EMetricRegression`) and update `tests/fixtures/expected_output.json`
2. Implement in `analyzer.py` (or `jump_scoring.py` if the value feeds `metrics.score` / `score_breakdown`)
3. Document in `README.md` under the relevant metrics table (and under **Jump scoring** if it affects the composite score)
4. If the metric appears in Layer 4 golden files, update `tests/fixtures/*_video_golden.json` and widen `_VIDEO_FLOAT_TOLERANCES` in `tests/test_e2e.py` only when inference noise requires it
5. If the metric is nullable, follow **Nullable metric verification** (below) — including a test or manual run that proves real `null` / correct omission
6. Update **`docs/metric-audit-matrix.md`** — add/adjust the row(s) for the metric family so README, code pointers, and null rules stay corroborated
7. Run the consistency check (below) before calling it done

## Nullable metric verification (audit & implementation)

For **every** field documented as nullable, optional, or calibration-gated, confirm the output matches the coaching contract — not only the numeric case, but the “no value” case.

Do this for full JSON-audit passes (e.g. GitHub “verify all metrics”) and whenever you add or change a nullable field.

**1. Exercise each “null when …” / “omit when …” branch**

- No `--calibrate` vs with `--calibrate`
- Missing pose / upper body / partial tracker output, as relevant
- Session edge cases (e.g. fewer than two jumps for variability fields)

**2. True `null` vs sentinel vs wrong type**

After `json.loads` on saved output:

- Values documented as **JSON `null`** must parse to Python `None`. They must **not** be disguised sentinels (`0`, `-1`, `""`) or the string `"null"` unless `README.md` explicitly defines that convention.
- **Floating point:** do not use `NaN` in JSON output for “missing”; use `null`.

**3. Key present vs key omitted**

`README.md` distinguishes two patterns; both are valid but they must not be confused:

- **Key always present, value `null`** — e.g. many `metrics` fields that are filled when data exists.
- **Key absent** — e.g. `landing_pos` or `metrics.drift_cm` without calibration.

Verify the implementation matches **exactly** what the docs say (present+`null` vs omitted).

**4. Regression / tests**

Automated baseline: `tests/test_analyzer.py` → **`TestNullableMetricSemantics`** (uncalibrated vs calibrated omission rules, JSON round-trip keeps real `null`, empty session score rollups). Extend this class when you add nullable fields.

Elsewhere: `TestTakeoffAngle::test_takeoff_angle_null_without_approach_velocity`, upper-body null tests, absorption-window tests, session variability tests — together they pin many branches.

Also assert manually where practical: `assert x is None`, `assert "key" not in obj`. Manual audit on real footage remains useful for tracker-noise edge cases.

## Jump score and session rollups

- Per-jump **`score`** and **`score_breakdown`** are computed in `jump_scoring.py` and attached to each `JUMP.metrics` when the jump completes.
- **`SESSION_SUMMARY`** includes **`avg_jump_score`**, **`best_jump_num`**, **`best_jump_score`**, **`worst_jump_num`**, **`worst_jump_score`** (all `null` when there are no scored jumps). See `README.md` for definitions.

## Consistency check (always run before done)

```bash
python main.py --video single_jump.mov --player_id 1 --output output/run1.json
python main.py --video single_jump.mov --player_id 1 --output output/run2.json
diff output/run1.json output/run2.json
```

`diff` must produce no output.

Fast in-process coverage of the same idea (fixture sequence, no video): `tests/test_determinism.py` (`TestSaveLogsDeterminism`).

**Example clip:** `single_jump.mov` is intentionally **not in git** (see `.gitignore` — `*.mov`). Keep a short test clip at the **repo root** locally; fresh clones skip this step until a file is added.

## Metric audit (GitHub #15)

Stable checklist: **`docs/metric-audit-matrix.md`** — pass/fail by metric family, detailed mapping (README ↔ code ↔ null rules), determinism note, link to **#31** for negative scenarios.
