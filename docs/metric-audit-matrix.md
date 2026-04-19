# Metric audit matrix (GitHub #15)

**Purpose:** Single reference for **metric → README → implementation → null/omit rules → notes**. Aligns with **README.md** (Output Format, Key metric formulas, Jump scoring) as of the audit closure.

**Maintenance:** When you add or change a metric, update this file in the same PR as **README** and code — see **CLAUDE.md** (*Adding a new metric — checklist*) and **README.md** → *Development Guidelines* → *Adding a new metric*.

**Legend — status:** **Pass** = implementation matches documented contract for normal pipeline output. **Pass (limited)** = contract explicitly documents stub, omission, or tracker-dependent behaviour.

---

## Pass / fail by metric family

| Family | Status | Notes |
|--------|--------|--------|
| **SESSION_SUMMARY** | **Pass** | Variability uses sample `stdev`; score rollups from `metrics.score`; `video` may be `null` if `save_logs` omits `video_name`. |
| **JUMP envelope** (timing, `status`, `landing_pos`) | **Pass** | Takeoff/landing frames per 93% / 97% thresholds; `STIFF` if either knee **>** threshold; `landing_pos` only with calibration. |
| **`takeoff`** | **Pass** | `pos` key always present (`null` without calibration); approach/stance keys omitted without cm data; crouch + trunk doc precision. |
| **`knee_angles` / `knee_symmetry_deg`** | **Pass** | Landing frame; hip–knee–ankle from tracker; symmetry = \|L−R\|. |
| **Air time / jump height / inch** | **Pass** | Detector interval; height from `peak_hip_y`; inch = cm × 0.393701. |
| **`takeoff_angle_deg`** | **Pass** | `null` without valid approach velocity or non-positive height. |
| **Upper body** (`peak_wrist_height_ratio`, `arm_swing_symmetry_px`) | **Pass (limited)** | Depends on MediaPipe / buffer; `null` when missing. |
| **Drift / `com_flight_drift_cm`** | **Pass** | Axis mapping Δx/Δy → JSON keys; omission without calibration path. |
| **Post-landing absorption** | **Pass (limited)** | Filled after 300 ms of grounded frames or next jump; stays `null` if processing stops early. |
| **Composite `score` / `score_breakdown`** | **Pass** | Weights renormalize; degenerate path `score` 0 + `_error` (see **#31**). |
| **Negative tests** | **Pass** | **Negative tests:** scenario matrix and harness layers in **`docs/negative-test-scenarios-plan-issue-31.md`** (GitHub **#31**). Implementation: `tests/test_jump_scoring_negative.py`, `tests/test_analyzer_negative.py`, `tests/test_json_contract_metrics.py`, plus Layer 3 pipeline cases in `tests/test_e2e.py`. |

---

## Detailed matrix

### SESSION_SUMMARY

| Field | README | Code | Units / null |
|-------|--------|------|----------------|
| `event` | Output Format | `analyzer.save_logs` | Always `"SESSION_SUMMARY"`. |
| `video` | Output Format | `save_logs(..., video_name=)` | `string` or `null` (tests). |
| `jump_count` | Output Format | `JumpAnalyzer.jump_count` | Integer; completed jumps only. |
| `jump_height_variability_cm` | Output Format | `statistics.stdev` on heights | `null` if &lt; 2 jumps. |
| `air_time_variability_sec` | Output Format | `statistics.stdev` on air times | `null` if &lt; 2 jumps. |
| `avg_jump_score` … `worst_jump_score` | Output Format | `session_jump_score_stats` | `null` if no `metrics.score` in history; ties: first in iteration order. |

### JUMP — top-level

| Field | README | Code | Notes |
|-------|--------|------|--------|
| `event` | Top-level JUMP | `jump_entry` | `"JUMP"`. |
| `jump_num`, `player_id` | Output Format | `jump_count`, `player_id` | |
| `start_video_time_sec`, `end_video_time_sec` | Output Format | `jump_start_time`, landing `frame_time` | Rounded 3 dp. |
| `status` | Output Format | `STIFF` if either knee &gt; `stiff_landing_threshold` (default 160°) | |
| `landing_pos` | Output Format | Set only if `court_pos` at landing | Omitted without `--calibrate`. |

### `takeoff`

| Field | README | Code | Null / omit |
|-------|--------|------|-------------|
| `pos` | `takeoff` table | `takeoff_section["pos"]` | `null` without calibration. |
| `approach_velocity_cms` | Key formulas + table | `_compute_approach_velocity` | Key omitted if `None`. |
| `stance_width_cm` | table | `_compute_stance_width` | Key omitted if `None`. |
| `crouch_depth_deg`, `crouch_duration_sec` | table | `_compute_takeoff_crouch` | Keys omitted if no approach knee window. |
| `trunk_lean_deg` | table | Hardcoded `None`; `_compute_trunk_lean` unused | Always `null`. |

### `metrics` — injury / core kinematics

| Field | README | Code | Notes |
|-------|--------|------|--------|
| `knee_angles.*` | Injury Prevention | Landing frame knees | Rounded 1 dp. |
| `knee_symmetry_deg` | Injury Prevention | `_compute_knee_symmetry` | |
| `air_time_sec` | Jump Performance | `frame_time - jump_start_time` | 3 dp. |
| `jump_height_est_cm`, `jump_height_est_inch` | Jump Performance + formulas | baseline/peak ratio; × 0.393701 | 1 dp. |
| `takeoff_angle_deg` | Jump Performance + formulas | `_compute_takeoff_angle` | `null` per rules. |
| `peak_wrist_height_ratio` | Jump Performance + formulas | `_compute_peak_wrist_height_ratio` | `null` if no pose / bad segment. |
| `arm_swing_symmetry_px` | Jump Performance | `_compute_arm_swing_symmetry` on last `approach_upper_body` | `null` if buffer empty. |

### `metrics` — calibration-only

| Field | README | Code | Notes |
|-------|--------|------|--------|
| `drift_cm.*` | Court Position + formulas | `drift_x/y`, magnitude | Omitted without both positions. |
| `com_flight_drift_cm` | Court Position + formulas | `_compute_com_flight_drift` | Omitted if &lt; 2 hip samples or missing positions. |

### `metrics` — absorption

| Field | README | Code | Notes |
|-------|--------|------|--------|
| `min_landing_knee_angle_deg` | Post-Landing | `_finalize_landing_absorption` | Min of avg(L,R) over window. |
| `landing_absorption_duration_sec` | Post-Landing | Time to first min sample | |
| `landing_knee_flexion_rate_degs` | Post-Landing | `(initial − min) / duration` | 0 if duration 0. |

### `metrics` — scoring

| Field | README | Code | Notes |
|-------|--------|------|--------|
| `score` | Jump scoring | `compute_jump_score` | `int` 0–100. |
| `score_breakdown` | Jump scoring | Per-channel sub-scores | `_error` only if no channel scored. |

---

## Follow-up tracking

- **Negative / edge tests:** Closed against **`docs/negative-test-scenarios-plan-issue-31.md`** (**#31**); includes `jump_scoring` degenerate path, `JumpAnalyzer` synthetic sequences, mocked pipeline, and JSON contract checks (`pytest tests/ -m "not slow and not fuzz and not stress"`).
- **Local-only media:** `*.mov` / `*.mp4` are **gitignored**; place **`single_jump.mov`** at repo root for the **CLAUDE.md** determinism check (not available on a fresh clone).

---

## Determinism (closure)

Run twice on the same clip (from repo root, with local `single_jump.mov` and player ID as used in development):

```bash
python main.py --video single_jump.mov --player_id 1 --output output/run1.json
python main.py --video single_jump.mov --player_id 1 --output output/run2.json
diff output/run1.json output/run2.json
```

**Expected:** no `diff` output. Verified **Pass** on maintainer machine at audit closure (`diff_exit=0`).
