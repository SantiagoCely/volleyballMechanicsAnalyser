# Issue #33 — Optional / follow-up test work (beyond core phases)

This supplements **`docs/issue-33-test-strategy-plan.md`**. Core phase 1–2 items (CLI, state machine, determinism, fuzz) are implemented in-tree; this document tracks **optional** taxonomy rows and **where** they live.

---

## Implemented (optional bucket)

| Plan reference | What | Where |
|----------------|------|--------|
| §6 Subprocess `main` + synthetic video + mocked tracker | Subprocess invokes a tiny script that patches **`tracker.PlayerTracker`** before importing **`main`**, runs **`main.main()`**, asserts exit 0 + JSON shape | **`tests/run_main_mocked_subprocess.py`**, **`tests/test_optional_integration.py`** |
| §5 Optional slow — full pipeline `diff` on real clip | **`@pytest.mark.slow`** — runs **`main.py`** twice on **`single_jump.mov`** at repo root; **skips** if file missing | **`tests/test_slow_video_determinism.py`** |
| §8 Stress — long synthetic loop without tracker | **`@pytest.mark.stress`** — many grounded `analyze_frame` calls, monotonicity / consistency | **`tests/test_stress_analyzer.py`** |
| Invariance — renormalization / inactive keys | **Fast** — same `compute_jump_score` when non-scoring keys differ | **`tests/test_jump_scoring_negative.py`** — `TestRenormalizationStability` |
| §8 Performance / throughput gates | **Not implemented** — needs product budgets and a policy (scheduled job vs PR). |

---

## CI / pytest selection

Blocking gate (matches **`.github/workflows/ci.yml`**):

```bash
python -m pytest tests/ -v -m "not slow and not fuzz and not stress"
```

Run optional suites locally:

```bash
pytest tests/ -v -m stress
pytest tests/test_slow_video_determinism.py -v -m slow
pytest tests/test_optional_integration.py -v
```

---

## Future work (if needed)

1. **Perf gate** — e.g. optional workflow on `workflow_dispatch` timing `analyze_frame` N frames (no YOLO).
2. **Subprocess script** — extend with `--fixture path.json` if multiple sequences are needed (currently fixed to **`single_jump_sequence.json`**).
3. **CI job** for `stress` or slow determinism — non-blocking or nightly only; keep PR gate lean.

---

## Related

- **`docs/issue-33-test-strategy-plan.md`** — original taxonomy and phases  
- **`README.md` → Testing** — marker table and commands  
