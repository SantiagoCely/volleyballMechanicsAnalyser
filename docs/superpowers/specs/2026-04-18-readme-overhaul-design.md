# README Overhaul — Design Spec

**Date:** 2026-04-18  
**Goal:** Make `README.md` the single source of truth for all human-readable and AI-readable project documentation. `CLAUDE.md` becomes a thin dev-workflow overlay that references README instead of duplicating it.

---

## Problem

The current `README.md` has several inaccuracies relative to the current codebase:

1. **Wrong CLI flags** — documents `--debug` (old interactive bypass) and `--no_calibrate` (removed); misses the current `--debug` (diagnostic prints).
2. **Wrong output schema** — shows `JUMP_START` + `LANDING` as separate events; code emits a unified `JUMP` object plus a `SESSION_SUMMARY` header.
3. **Missing metrics** — ~8 metrics added in recent PRs are undocumented: `takeoff_crouch_depth_deg`, `takeoff_crouch_duration_sec`, `trunk_lean_at_takeoff_deg`, `knee_symmetry_deg`, `peak_wrist_height_ratio`, `arm_swing_symmetry_px`, `min_landing_knee_angle_deg`, `landing_absorption_duration_sec`, `landing_knee_flexion_rate_degs`.
4. **Missing test file** — `test_tracker.py` absent from project structure.
5. **No architecture explanation** — no data-flow description, no internals for AI context.
6. **Duplication with CLAUDE.md** — run commands and test commands are copy-pasted across both files.

---

## Approach

Single `README.md` with a Table of Contents and a layered architecture section (overview first, deep-dive last). `CLAUDE.md` retains only dev-specific hooks and adds references to README sections.

---

## README Structure

### Sections (in order)

1. **Header** — one-liner description, no badges needed.
2. **Table of Contents** — anchored links to all sections.
3. **Installation** — `pip install -r requirements.txt`, macOS SSL fix.
4. **Quick Start** — two canonical commands (default mode, calibration mode).
5. **CLI Flags** — complete, accurate flag table.
6. **Output Format**
   - `SESSION_SUMMARY` event schema
   - `JUMP` event schema
     - Top-level fields (`event`, `jump_num`, `player_id`, `start_video_time_sec`, `end_video_time_sec`, `status`, `landing_pos`)
     - `takeoff` sub-object fields
     - `metrics` sub-object fields — all fields grouped into: Injury Prevention, Jump Performance, Court Position & Drift, Pro Performance, Post-Landing Absorption
7. **Project Structure** — file tree including `test_tracker.py`.
8. **Architecture Overview** — module responsibilities (one paragraph per module), ASCII data-flow diagram.
9. **Architecture Deep-Dive**
   - `JumpAnalyzer` state machine (grounded → airborne → post-landing absorption)
   - `PlayerTracker` pipeline (YOLO detection → ByteTrack → MediaPipe pose → re-ID)
   - `CameraCalibrator` homography (pixel → cm via `getPerspectiveTransform`)
   - Key metric formulas (OLS approach velocity, jump height from hip pixel travel, takeoff angle)
10. **Testing** — fast/slow split, three test layers, fixture files, how to add tests for new metrics.
11. **CI Pipeline** — three jobs (tests, lint/typecheck), what blocks merges vs. informational.
12. **Development Guidelines** — adding a metric (checklist), consistency verification procedure.
13. **Dependencies** — table of packages and purpose.

---

## CLAUDE.md Changes

CLAUDE.md is trimmed to a **dev-workflow overlay**. Changes:

- **Remove:** Full run-command examples (→ README §Quick Start and §CLI Flags).
- **Remove:** Full test-command examples (→ README §Testing).
- **Remove:** Test structure table (→ README §Testing).
- **Keep:** Metric-addition checklist (with specific file paths — this is actionable dev guidance, not documentation).
- **Keep:** Consistency verification commands (these are the exact commands to run, not prose).
- **Add:** Opening line: *"For full project documentation see `README.md`. This file contains dev-workflow shortcuts and checklist reminders only."*
- **Add:** Per-section references: *"See README.md §CLI Flags"*, *"See README.md §Testing"* etc.

---

## Accuracy Fixes (detailed)

### CLI Flags

| Current README | Reality | Fix |
|---|---|---|
| `--debug` (skip UI, hardcoded corners) | Removed | Delete |
| `--no_calibrate` | Removed | Delete |
| `--calibrate` not mentioned as opt-in clearly | Opt-in flag | Clarify |
| Default output path `output/analysis_results.json` | `output/<video_stem>_analysis.json` | Fix |
| `--debug` (diagnostic prints) | Present in code | Add |

### Output Schema

**Remove** the `JUMP_START` + `LANDING` two-event structure entirely.

**Add** `SESSION_SUMMARY` (first element in JSON array):
```json
{
  "event": "SESSION_SUMMARY",
  "video": "single_jump.mov",
  "jump_count": 2,
  "jump_height_variability_cm": 1.4,
  "air_time_variability_sec": 0.012
}
```

**Replace** with unified `JUMP` event:
```json
{
  "event": "JUMP",
  "jump_num": 1,
  "player_id": 1,
  "start_video_time_sec": 2.133,
  "end_video_time_sec": 2.567,
  "status": "SAFE",
  "takeoff": {
    "pos": [270.8, 986.1],
    "approach_velocity_cms": 547.7,
    "stance_width_cm": 26.2,
    "crouch_depth_deg": 132.4,
    "crouch_duration_sec": 0.183,
    "trunk_lean_deg": null
  },
  "metrics": {
    "air_time_sec": 0.434,
    "jump_height_est_cm": 22.1,
    "jump_height_est_inch": 8.7,
    "takeoff_angle_deg": 19.2,
    "knee_angles": { "left": 154.2, "right": 156.7 },
    "knee_symmetry_deg": 2.5,
    "min_landing_knee_angle_deg": 121.3,
    "landing_absorption_duration_sec": 0.217,
    "landing_knee_flexion_rate_degs": 183.7,
    "peak_wrist_height_ratio": 1.12,
    "arm_swing_symmetry_px": 14.3,
    "drift_cm": {
      "forward_back": 215.4,
      "side_to_side": 4.4,
      "magnitude": 215.4
    },
    "com_flight_drift_cm": 15.1
  },
  "landing_pos": [275.2, 1201.5]
}
```

**Note on calibration:** `takeoff.pos`, `takeoff.approach_velocity_cms`, `takeoff.stance_width_cm`, `metrics.drift_cm`, `metrics.com_flight_drift_cm`, and `landing_pos` are only present when `--calibrate` is used. All other metrics are available without calibration.

**Note on `trunk_lean_deg`:** Currently always `null` — `hip_x` is not yet threaded through the data pipeline from tracker to analyzer.

### Metrics table — new fields to document

| Field | Group | Description |
|---|---|---|
| `takeoff.crouch_depth_deg` | Pro Performance | Minimum average knee angle in 1 s before takeoff. Lower = deeper pre-jump squat |
| `takeoff.crouch_duration_sec` | Pro Performance | Time both knees spent below 150° during approach crouch |
| `takeoff.trunk_lean_deg` | Pro Performance | Angle of hip→shoulder line from vertical at takeoff. 0° = upright |
| `metrics.arm_swing_symmetry_px` | Pro Performance | Absolute wrist Y difference at takeoff. 0 = symmetric arm swing |
| `metrics.knee_symmetry_deg` | Injury Prevention | Absolute difference between left and right knee angles at landing |
| `metrics.peak_wrist_height_ratio` | Pro Performance | Wrist height relative to shoulder-to-hip segment at peak. >1.0 = arms above shoulders |
| `metrics.min_landing_knee_angle_deg` | Post-Landing Absorption | Minimum average knee angle in 300 ms after landing |
| `metrics.landing_absorption_duration_sec` | Post-Landing Absorption | Time from landing to deepest knee flexion |
| `metrics.landing_knee_flexion_rate_degs` | Post-Landing Absorption | Rate of knee bend after landing (°/s). Higher = faster shock absorption |

---

## Architecture Deep-Dive Content

### JumpAnalyzer state machine

Three states: **grounded**, **airborne**, **post-landing**.

- **grounded → airborne:** `hip_y < baseline * 0.93` (hip rises 7% above baseline). Captures: jump start time, takeoff court position, approach velocity (OLS over 0.5 s window), stance width, crouch depth/duration (from 1 s approach buffer), trunk lean, arm swing symmetry.
- **airborne:** Tracks peak `hip_y` (minimum pixel Y = highest point). Accumulates CoM positions for flight drift.
- **airborne → grounded (landing):** `hip_y >= baseline * 0.97`. Computes: air time, jump height, knee angles, drift, takeoff angle, CoM flight drift, peak wrist height ratio. Appends `JUMP` entry to history. Starts 300 ms post-landing absorption window.
- **post-landing absorption (300 ms):** Collects knee angles after landing. On expiry, amends the most recent `JUMP` entry with `min_landing_knee_angle_deg`, `landing_absorption_duration_sec`, `landing_knee_flexion_rate_degs`.
- **Baseline adaptation:** While grounded and within ±15% of current baseline, `baseline = 0.98 * baseline + 0.02 * hip_y` — slow EMA that handles camera drift without being fooled by crouches or jumps.

### PlayerTracker pipeline

Per frame:
1. **YOLO detection** (YOLOv10n, class=person) — bounding boxes + ByteTrack IDs.
2. **Target selection** — match by `target_player_id`, or by proximity + colour histogram correlation if ID was lost (re-ID).
3. **Re-ID logic** — if target missing for >0 frames: candidate must be within 200 px of last known centre, bbox height within ±30%, and hue histogram correlation ≥ 0.5.
4. **MediaPipe Pose** — run on the cropped player bounding box. Extracts: left/right knee angles (3D world landmarks), hip Y pixel position, ground position (midpoint of ankles), foot pixel positions, shoulder/wrist positions (upper body dict).
5. **Returns 6-tuple:** `(player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body)`. Any field is `None` if detection fails.

### CameraCalibrator

User clicks 4 court corners (top-left, top-right, bottom-right, bottom-left) on the first frame. `cv2.getPerspectiveTransform` computes a 3×3 homography matrix mapping those corners to a canonical 900×1800 target (9 m × 18 m court at 1 cm/pixel). `transform_point(px, py)` applies `cv2.perspectiveTransform` to convert any pixel coordinate to court centimetres.

### Key formulas

- **Approach velocity (cm/s):** OLS linear regression on court positions over the 0.5 s window before takeoff. `vx = Σ(t−t̄)(x−x̄) / Σ(t−t̄)²`, same for `vy`. Speed = `sqrt(vx²+vy²)`. More robust than start-to-end displacement against single noisy frames.
- **Jump height (cm):** `(baseline_hip_y − peak_hip_y) / baseline_hip_y * player_height_est`. Specifically: ratio of hip pixel travel to baseline hip height, scaled — most accurate with calibration.
- **Takeoff angle (°):** `atan2(v0_vertical, approach_velocity)` where `v0_vertical = sqrt(2 * 981 * jump_height_cm)`. Only present when approach velocity is available.
- **CoM flight drift (cm):** Maximum perpendicular deviation of hip positions from the straight line between takeoff and landing positions.

---

## Out of Scope

- No new metrics added in this task.
- No changes to `analyzer.py`, `tracker.py`, `main.py`, or tests.
- No new `docs/` files beyond this spec.
