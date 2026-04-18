# Volleyball Mechanics Analyser — Dev Workflow

> For full project documentation (architecture, output schema, metrics reference, CLI flags) see `README.md`. Jump composite scoring and session rollups are under **Output Format → Jump scoring** and **SESSION_SUMMARY** in `README.md`.

## Running the analyser

See `README.md` — [Quick Start](#quick-start) and [CLI Flags](#cli-flags).

## Running tests

```bash
# Fast tests (no GPU, ~2 s) — run after every change
python -m pytest tests/ -v -m "not slow"

# Full suite including tracker smoke test (~15 s)
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_e2e.py -v -m "not slow"
python -m pytest tests/test_analyzer.py -v
```

See `README.md` — [Testing](#testing) for test structure and layer descriptions.

## Adding a new metric — checklist

1. Add a regression test to `tests/test_e2e.py` (`TestE2EMetricRegression`) and update `tests/fixtures/expected_output.json`
2. Implement in `analyzer.py` (or `jump_scoring.py` if the value feeds `metrics.score` / `score_breakdown`)
3. Document in `README.md` under the relevant metrics table (and under **Jump scoring** if it affects the composite score)
4. If the metric appears in Layer 4 golden files, update `tests/fixtures/*_video_golden.json` and widen `_VIDEO_FLOAT_TOLERANCES` in `tests/test_e2e.py` only when inference noise requires it
5. Run the consistency check (below) before calling it done

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
