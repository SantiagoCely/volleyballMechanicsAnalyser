# Implementation plan — Issue #33 (test strategy gaps)

Reference: [Issue #33 — Test strategy: fuzz, stress/load, invariance, formal state coverage](https://github.com/SantiagoCely/volleyballMechanicsAnalyser/issues/33)

This document maps the issue’s taxonomy and acceptance criteria to concrete tasks. Scope decisions below are **proposed defaults**; adjust before coding if CI budget or product priorities differ.

---

## Goals (from issue)

1. Close selected gaps versus the taxonomy table: **fuzz**, **invariance/determinism**, **`main.py` / CLI sanity**, **formal analyzer state transitions**, optional **performance/stress**.
2. For each in-scope item: tests use **pytest markers**, **timeouts** where loops could hang, and fit the existing fast suite (`-m "not slow"`) unless explicitly tagged otherwise.
3. **`README.md` → Testing** (and **CI docs**): short pointer if new test categories/markers are introduced.
4. **Continuous integration**: any change to marker semantics must update **`.github/workflows/ci.yml`** so the blocking job still runs the intended subset.

Related context (from issue): negative/edge coverage is documented under **`docs/negative-test-scenarios-plan-issue-31.md`** (add or restore this file when #31 documentation exists in-repo). Optional boundary tweaks from #31 remain boundary-shaped and are **not** prerequisites for #33 unless a regression proves a hole.

---

## Taxonomy checklist (issue #33) → this plan

Legend from issue: **Strong** / **Partial** / **Gap**. The table below ties each category to **repo reality** and **planned work**.

| Category | Representative coverage today | Gap vs issue | Planned response |
|----------|------------------------------|--------------|------------------|
| **Boundary / edge case** | Strong — `tests/test_jump_scoring_negative.py`, `tests/test_analyzer_negative.py`, `tests/test_analyzer.py` | Optional deeper §4.10 rows | **Out of scope** unless product reopens #31-style rows or a hole appears. |
| **Regression** | Strong — `tests/test_e2e.py`, `tests/fixtures/expected_output.json`, slow goldens | Maintenance only | **No new suite** — keep updating fixtures when metrics change (existing process). |
| **Integration** | Strong — `tests/test_e2e.py` (`TestPipelineIntegration`, mocked tracker path), `tests/test_json_contract_metrics.py` | Optional subprocess `main.py` | **Optional phase 1b or 2:** subprocess invoking `python main.py` with **synthetic video + mocked tracker** (heavier setup); see §Integration (subprocess). |
| **Smoke** | Partial — `TestTrackerSmoke` (`@slow`), pipeline output checks | Expand CI smoke | **Explicitly unchanged** in phase 1 — only revisit if policy requires a **minimal always-on smoke job** (cost vs value). |
| **State transition** | Partial — jump start/land, mid-video end, tracker thresholds | Formal analyzer FSM | **In scope phase 1** — named suite + diagram-driven scenarios (`§` Analyzer state machine tests). |
| **Heuristic / sanity** | Partial — pipeline structure tests, nullable semantics, JSON round-trip | CLI / argparse / paths | **In scope phase 1** — lightweight **`main`/CLI** tests without loading YOLO (`§` CLI sanity). Optionally extend **`tests/test_json_contract_metrics.py`** only if new export paths appear. |
| **Invariance** | Partial — tie-breaking in `session_jump_score_stats` already tested (`tests/test_jump_scoring_negative.py` `TestSessionJumpScoreStatsRollups`) | CI determinism | **In scope phase 1** — double-run JSON equality for deterministic pipelines; optional **slow** subprocess `diff`-style check on real video (`§` Determinism / invariance). Optional: scoring **renormalization** stability when optional channels missing (may overlap existing jump scoring tests). |
| **Fuzz** | Gap | Property/random inputs | **Phase 2** — Hypothesis behind `@pytest.mark.fuzz`; exclude from default CI until stable. |
| **Performance / load** | Gap | Throughput/latency | **Defer** unless product sets budgets — optional non-blocking job. |
| **Stress** | Gap | Long sequences, concurrency | **Defer** — optional `@pytest.mark.stress` + local or scheduled run. |

---

## Recommended scope (phase 1 — merge-friendly)

| Gap | In scope for phase 1? | Rationale |
|-----|----------------------|-----------|
| **CLI / `main` sanity** | **Yes** | No YOLO load: factor or test `argparse` + default output path + `os.makedirs` behavior in isolation. |
| **Formal state transitions** | **Yes** | Drive `JumpAnalyzer.analyze_frame` with **synthetic sequences** (existing pattern in `tests/test_analyzer.py`) and assert flags (`is_jumping`, `post_landing_active`, `jump_count`, history shape) through named scenarios. |
| **Invariance / determinism** | **Yes (fast path)** | Run **deterministic** pipelines twice in-process (`JumpAnalyzer` + fixture JSON / synthetic frames, or `save_logs` round-trip) and assert **deep equality** of parsed JSON — mirrors `CLAUDE.md` `diff` check without subprocess + real video unless later expanded. |
| **Session rollups** | **Mostly covered** | Tie-breaking and empty history already tested in `test_jump_scoring_negative.py`; add new tests only if **SESSION_SUMMARY** assembly or `save_logs` ordering changes. |
| **Fuzz / property tests** | **Optional phase 2** | Adds **`hypothesis`** (dev dependency) and `@pytest.mark.fuzz`; keep **off default CI** until stable. |
| **Performance / load / stress** | **Defer** unless product sets budgets | Long sequences and perf gates belong in a **separate optional job** with explicit time/memory limits. |
| **Smoke (`TestTrackerSmoke`)** | **No change by default** | Keeps CI fast; expand only if team mandates minimal smoke in CI. |

---

## Acceptance criteria checklist (complete)

- [x] **Decide scope** — Confirm phase 1 vs 2 vs deferred rows; record in PR description (“Scope decisions”).
- [x] **Per in-scope gap** — Tests use **markers** and **timeouts** where loops or Hypothesis could run long.
- [x] **`pytest.ini`** — Register every marker you use (`slow` exists; add `fuzz`, `stress` only when needed).
- [x] **`.github/workflows/ci.yml`** — Blocking step `Run fast test suite` must stay aligned with markers (today: `python -m pytest tests/ -v -m "not slow" --tb=short`). If fuzz/stress land, update to e.g. `-m "not slow and not fuzz and not stress"` or equivalent **and** mirror the same expression in **`README.md` → CI Pipeline** so docs do not drift.
- [x] **`README.md` → Testing** — Bullet or table row for new markers/categories / optional jobs.
- [x] **`CLAUDE.md`** — Optional one-line pointer if automated determinism replaces **only-manual** consistency check for some workflows.

---

## Technical design notes

### 1. Markers (`pytest.ini`)

Today only `slow` is registered. Add **only markers you actually use**:

| Marker | Meaning | Default CI (`-m "not slow"`) |
|--------|---------|-------------------------------|
| `slow` | YOLO / real video | Excluded |
| `fuzz` | Hypothesis / randomised inputs | Excluded |
| `stress` | Long runs, concurrency, resource experiments | Excluded |

**Convention:** Keep the **blocking** job selecting the fast suite; when `fuzz` or `stress` exist, the workflow string must exclude them explicitly (markers are not auto-excluded).

### 2. Timeouts (`pytest-timeout`)

Issue calls for timeouts on risky tests. Either:

- Add **`pytest-timeout`** to `requirements.txt` (or `requirements-dev.txt` if split), **or**
- Use **bounded** Hypothesis settings (`max_examples`, `deadline`) and finite loops only.

Prefer one consistent approach document-wide.

### 3. CLI sanity without loading YOLO

`main.py` couples `argparse`, default `--output`, and directory creation with tracker construction. Options (pick one):

- **A (preferred):** Extract a pure function `build_main_args(argv: list[str] | None) -> argparse.Namespace` (or parse + post-process defaults), then unit-test it.
- **B:** `subprocess.run([sys.executable, "main.py", "--help"], …)` — validates entrypoint and help; **does not** alone validate default `--output` path logic.
- **C:** Expose `ArgumentParser` from `main` for `parse_args([...])` after small refactor.

Also test that **nested `--output` paths** trigger directory creation (`os.makedirs` behavior around `main()`).

### 4. Analyzer state machine tests

Conceptual states (from `analyzer.py`): **grounded** → **airborne** (`is_jumping`) → **landing** → **post_landing** (`post_landing_active`) → **absorption finalized** / grounded.

- Add **`tests/test_analyzer_state_machine.py`** (or `TestAnalyzerStateMachine` in `tests/test_analyzer.py`) with **diagram-driven** scenarios:
  - Single jump: `is_jumping` transitions; `post_landing_active` after landing; cleared after window or next takeoff.
  - Back-to-back jumps: post-landing interrupted by new jump.
  - Video ends mid-flight: align with `tests/test_analyzer_negative.py` (`TestMidJumpVideoEnd`); name states in docstrings.

Prefer assertions on **public outputs** (`jump_count`, `history`, absorption metrics) over private helpers unless necessary.

### 5. Determinism / invariance

Layers (increasing cost):

1. **`JumpAnalyzer.save_logs`** — Two passes over identical synthetic `analyze_frame` sequences → identical JSON (`json.loads` comparison).
2. **`compute_jump_score`** — Same metric dict → same `score` / `score_breakdown`; phase 2 may add Hypothesis.
3. **`session_jump_score_stats`** — Tie-breaking **already covered** (`test_tie_best_and_worst_use_earlier_jump_num`). For pipeline determinism, ensure **SESSION_SUMMARY** embedded in saved logs matches **fixed-input** expectations when testing end-to-end snapshots.
4. **Optional slow:** Subprocess `python main.py` twice on **`single_jump.mov`** — `@pytest.mark.slow`; requires assets + model load; often **non-blocking** in CI unless the repo commits to it.

### 6. Integration (subprocess — optional)

Issue suggests: **subprocess** `python main.py` with **synthetic video** and **fully mocked tracker** to exercise the real CLI loop without GPU.

Implementation sketch:

- Generate minimal video (e.g. blank or few frames) on disk or in `tmp_path`.
- Patch or inject **`PlayerTracker`** / **`main`** dependencies via `unittest.mock` **or** a **`if __name__`**-safe entrypoint that accepts injected dependencies (larger refactor — only if worth it).
- Assert: process exit code 0, output JSON path exists, minimal schema checks.

Treat as **phase 1b or 2** if argparse tests + existing `TestPipelineIntegration` already satisfy integration confidence.

### 7. Fuzz / property tests (phase 2)

If Hypothesis is adopted:

- **`compute_jump_score`** — Constrained domains; no exceptions; scores in **[0, 100]**.
- **`JumpAnalyzer.analyze_frame`** — Short sequences; invariants (`jump_count` monotonicity, history consistency).

Use **`@pytest.mark.fuzz`**, cap **`max_examples`**, **`deadline`** or **`pytest-timeout`**.

### 8. Stress / performance (defer)

- **Stress:** Many-frame synthetic loop **without** tracker; optional ceiling assertion or local-only.
- **Perf gate:** Scheduled / optional workflow; not PR-blocking unless agreed.

---

## Files and surfaces to touch (when implementing)

| Surface | Purpose |
|---------|---------|
| `pytest.ini` | New markers |
| `.github/workflows/ci.yml` | Fast-suite `-m` expression |
| `README.md` | Testing + CI Pipeline tables |
| `tests/test_*` | New suites (CLI, state machine, determinism, fuzz later) |
| `main.py` | Optional small refactor for testable argparse/defaults |
| `CLAUDE.md` | Optional if determinism automation documented |
| `docs/negative-test-scenarios-plan-issue-31.md` | Link from this plan when file exists |

---

## Task breakdown (ordered)

1. **Markers, timeouts, CI** — Register markers; add timeout strategy; **update `ci.yml` and README CI section** in the same PR as new markers.
2. **CLI / path sanity** — Parse defaults + nested output dir creation.
3. **State machine suite** — Named scenarios + docstrings.
4. **Determinism** — Double-run JSON / `save_logs` equality (fast).
5. **README (+ optional CLAUDE)** — Document markers and optional suites.
6. ~~**Phase 2**~~ — Hypothesis **`@pytest.mark.fuzz`** suite (`tests/test_fuzz_properties.py`); CI/readme `-m "not slow and not fuzz"`. *(Optional subprocess integration / slow video `diff` — still deferred.)*

---

## Verification before closing the issue

- `python -m pytest tests/ -v -m "not slow and not fuzz"` passes (or the **exact** expression documented in **README + ci.yml** after marker changes).
- New tests are **deterministic** and **bounded** (timeouts or finite examples).
- **`README.md`** Testing (and **CI Pipeline**) updated when markers or jobs change.
- Optional: manual **`diff`** consistency check from **`CLAUDE.md`** when changing pipeline determinism.

---

## Non-goals (issue-aligned)

- Duplicating #31 boundary cases unless a new hole appears.
- GPU-required CI without `@pytest.mark.slow` and documented justification.
