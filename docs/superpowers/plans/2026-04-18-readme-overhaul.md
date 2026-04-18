# README Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `README.md` to be accurate, architecturally comprehensive, and the single source of truth for both human readers and AI assistants; trim `CLAUDE.md` to a thin dev-workflow overlay that references README.

**Architecture:** Complete replacement of `README.md` (no content is preserved verbatim — all sections have inaccuracies or are missing). `CLAUDE.md` keeps only actionable dev-workflow shortcuts and adds explicit references to README sections. No source code is touched.

**Tech Stack:** Markdown, Python (read-only to verify field names / flags against source)

**Spec:** `docs/superpowers/specs/2026-04-18-readme-overhaul-design.md`

---

### Task 1: Write README — header through CLI Flags

**Files:**
- Modify: `README.md` (full replacement — start fresh)

- [ ] **Step 1: Verify CLI flags against `main.py`**

Run:
```bash
grep "add_argument" main.py
```
Expected output (confirm these are the only flags):
```
--video, --calibrate, --player_id, --output, --show, --debug
```

- [ ] **Step 2: Replace `README.md` with header, ToC, Installation, Quick Start, and CLI Flags**

Write the following as the complete new `README.md` (overwrite the file entirely — subsequent tasks will append):

```markdown
# Volleyball Mechanics Analyser

A Python tool that analyses volleyball player jump mechanics from video using YOLOv10 for player detection and MediaPipe for pose estimation. Produces a structured JSON file with injury-prevention and performance metrics for every jump detected.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [CLI Flags](#cli-flags)
- [Output Format](#output-format)
- [Project Structure](#project-structure)
- [Architecture Overview](#architecture-overview)
- [Architecture Deep-Dive](#architecture-deep-dive)
- [Testing](#testing)
- [CI Pipeline](#ci-pipeline)
- [Development Guidelines](#development-guidelines)
- [Dependencies](#dependencies)

---

## Installation

```bash
git clone <repository-url>
cd volleyballMechanicsAnalyser
pip install -r requirements.txt
```

**macOS SSL fix** — if you see `[SSL: CERTIFICATE_VERIFY_FAILED]` during model download:
```bash
/Applications/Python\ 3.10/Install\ Certificates.command
```
*(replace `3.10` with your Python version)*

---

## Quick Start

**Default mode** — track a player (click to select) and compute all non-position metrics automatically:
```bash
python main.py --video path/to/video.mov
python main.py --video single_jump.mov --player_id 1
```

**Calibration mode** — click 4 court corners first to unlock position-based metrics (drift, approach velocity, stance width):
```bash
python main.py --video path/to/video.mov --calibrate
python main.py --video training.mov --player_id 1 --calibrate
```

---

## CLI Flags

| Flag | Description |
|---|---|
| `--video <path>` | Path to the video file (required) |
| `--calibrate` | Enable court calibration for position-based metrics. Prompts you to click 4 court corners on the first frame |
| `--player_id <id>` | Track a specific player ID without clicking to select |
| `--output <path>` | Save results JSON to a custom path. Default: `output/<video_stem>_analysis.json` |
| `--show` | Display the video with tracking overlays while processing |
| `--debug` | Print per-frame tracking and jump-detection diagnostics to stdout |

---
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Docs: rewrite README header, ToC, installation, quick start, CLI flags"
```

---

### Task 2: Write README — Output Format

**Files:**
- Modify: `README.md` (append Output Format section)

- [ ] **Step 1: Verify SESSION_SUMMARY fields against `analyzer.py`**

Run:
```bash
grep -A 8 "session_summary = {" analyzer.py
```
Expected: keys `event`, `video`, `jump_count`, `jump_height_variability_cm`, `air_time_variability_sec`

- [ ] **Step 2: Verify JUMP event top-level and takeoff fields against `analyzer.py`**

Run:
```bash
grep -A 12 "jump_entry = {" analyzer.py
grep -A 12 "takeoff_section = {" analyzer.py
grep "takeoff_section\[" analyzer.py
```
Expected takeoff keys: `pos`, `approach_velocity_cms`, `stance_width_cm`, `crouch_depth_deg`, `crouch_duration_sec`, `trunk_lean_deg`

- [ ] **Step 3: Verify metrics fields against `analyzer.py`**

Run:
```bash
grep -A 20 "metrics_section = {" analyzer.py
grep "metrics_section\[" analyzer.py
```
Expected metrics keys: `air_time_sec`, `jump_height_est_cm`, `jump_height_est_inch`, `takeoff_angle_deg`, `knee_angles`, `knee_symmetry_deg`, `min_landing_knee_angle_deg`, `landing_absorption_duration_sec`, `landing_knee_flexion_rate_degs`, `peak_wrist_height_ratio`, `arm_swing_symmetry_px`, `drift_cm` (calibration only), `com_flight_drift_cm` (calibration only)

- [ ] **Step 4: Append Output Format section to `README.md`**

Append the following to `README.md`:

```markdown
## Output Format

Results are saved as a JSON array. The first element is always a `SESSION_SUMMARY`; each subsequent element is one `JUMP` per detected jump.

### `SESSION_SUMMARY` event

```json
{
  "event": "SESSION_SUMMARY",
  "video": "single_jump.mov",
  "jump_count": 2,
  "jump_height_variability_cm": 1.4,
  "air_time_variability_sec": 0.012
}
```

| Field | Type | Description |
|---|---|---|
| `jump_count` | int | Total jumps detected in the video |
| `jump_height_variability_cm` | float \| null | Standard deviation of estimated jump heights across all jumps. `null` if fewer than 2 jumps |
| `air_time_variability_sec` | float \| null | Standard deviation of air times. `null` if fewer than 2 jumps |

---

### `JUMP` event

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

> **Calibration note:** `takeoff.pos`, `takeoff.approach_velocity_cms`, `takeoff.stance_width_cm`, `metrics.drift_cm`, `metrics.com_flight_drift_cm`, and `landing_pos` are only present when `--calibrate` is used. All other fields are always computed.

> **`trunk_lean_deg` note:** Currently always `null` — `hip_x` is not yet threaded through the tracker→analyzer data flow.

#### Top-level JUMP fields

| Field | Type | Description |
|---|---|---|
| `jump_num` | int | Sequential jump counter for this player in the video |
| `player_id` | int | ByteTrack ID of the tracked player |
| `start_video_time_sec` | float | Video timestamp at takeoff (seconds) |
| `end_video_time_sec` | float | Video timestamp at landing (seconds) |
| `status` | string | `"SAFE"`: both knees ≤ 160° at landing. `"STIFF"`: either knee > 160° — straighter legs increase ACL and patellar tendon injury risk |
| `landing_pos` | [x, y] | Court position (cm) at landing. Only with `--calibrate` |

#### `takeoff` fields

| Field | Type | Description |
|---|---|---|
| `pos` | [x, y] | Court position (cm) at takeoff. Only with `--calibrate` |
| `approach_velocity_cms` | float | 2D court-plane speed (cm/s) via OLS regression over the 0.5 s window before takeoff. Elite attackers typically reach 400–600 cm/s. Only with `--calibrate` |
| `stance_width_cm` | float | Distance between left and right ankles at takeoff (cm). Only with `--calibrate` |
| `crouch_depth_deg` | float | Minimum average knee angle in the 1 s before takeoff. Lower = deeper pre-jump squat |
| `crouch_duration_sec` | float | Time (seconds) both knees spent below 150° during the approach crouch |
| `trunk_lean_deg` | float \| null | Angle of hip→shoulder line from vertical at takeoff. 0° = perfectly upright. Currently always `null` |

#### `metrics` fields — Injury Prevention

| Field | Type | Description |
|---|---|---|
| `knee_angles.left` | float | Left knee angle at landing (degrees). 180° = fully straight |
| `knee_angles.right` | float | Right knee angle at landing (degrees). 180° = fully straight |
| `knee_symmetry_deg` | float | Absolute difference between left and right knee angles at landing. Larger values indicate asymmetric loading |

#### `metrics` fields — Jump Performance

| Field | Type | Description |
|---|---|---|
| `air_time_sec` | float | Time from takeoff to landing (seconds) |
| `jump_height_est_cm` | float | Estimated vertical hip displacement (cm), derived from the ratio of hip pixel travel to baseline hip height |
| `jump_height_est_inch` | float | Same as above, in inches |
| `takeoff_angle_deg` | float \| null | Jump trajectory angle from horizontal (degrees). Computed as `atan2(v₀_vertical, approach_velocity)`. Only present when approach velocity is available |
| `peak_wrist_height_ratio` | float \| null | Wrist height relative to the shoulder-to-hip body segment at peak jump. > 1.0 means wrists are above the shoulders (full arm extension) |
| `arm_swing_symmetry_px` | float \| null | Absolute difference between left and right wrist Y positions at takeoff (pixels). 0 = perfectly symmetric arm swing |

#### `metrics` fields — Court Position & Drift (requires `--calibrate`)

| Field | Type | Description |
|---|---|---|
| `drift_cm.forward_back` | float | How far the player landed in front of (positive) or behind (negative) their takeoff point (cm) |
| `drift_cm.side_to_side` | float | Lateral displacement from takeoff to landing (cm). Large values may indicate balance issues |
| `drift_cm.magnitude` | float | Straight-line distance from takeoff to landing: `sqrt(forward_back² + side_to_side²)` (cm) |
| `com_flight_drift_cm` | float | Maximum perpendicular deviation of the hip (CoM proxy) from the straight takeoff-to-landing line (cm). Lower = more controlled flight |

#### `metrics` fields — Post-Landing Absorption

These fields are computed from a 300 ms window after landing and are initially `null`, then filled in by the time the next jump starts.

| Field | Type | Description |
|---|---|---|
| `min_landing_knee_angle_deg` | float \| null | Minimum average knee angle in the 300 ms after landing. Lower = deeper absorption squat |
| `landing_absorption_duration_sec` | float \| null | Time from landing frame to the frame of deepest knee flexion (seconds) |
| `landing_knee_flexion_rate_degs` | float \| null | Rate of knee bend after landing (°/s). Higher = faster shock absorption |

---
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Docs: add accurate output format section — SESSION_SUMMARY + unified JUMP schema"
```

---

### Task 3: Write README — Project Structure and Architecture Overview

**Files:**
- Modify: `README.md` (append two sections)

- [ ] **Step 1: Verify project file list**

Run:
```bash
ls tests/
```
Confirm `test_tracker.py` is present alongside `test_analyzer.py`, `test_utils.py`, `test_camera_calib.py`, `test_e2e.py`.

- [ ] **Step 2: Append Project Structure and Architecture Overview to `README.md`**

```markdown
## Project Structure

```
volleyballMechanicsAnalyser/
├── main.py                        # Entry point: CLI, calibration UI, player selection, video loop
├── analyzer.py                    # JumpAnalyzer — jump detection state machine and metric computation
├── tracker.py                     # PlayerTracker — YOLO detection, ByteTrack, MediaPipe pose
├── camera_calib.py                # CameraCalibrator — perspective transform (pixel → cm)
├── utils.py                       # Geometry and signal-processing helpers
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Test configuration (slow marker definition)
├── tests/
│   ├── test_analyzer.py           # Unit tests for JumpAnalyzer
│   ├── test_tracker.py            # Smoke tests for PlayerTracker
│   ├── test_utils.py              # Unit tests for geometry helpers
│   ├── test_camera_calib.py       # Unit tests for perspective transform accuracy
│   ├── test_e2e.py                # End-to-end tests (3 layers, see Testing section)
│   └── fixtures/
│       ├── single_jump_sequence.json   # Deterministic 11-frame input fixture
│       └── expected_output.json        # Pinned expected metric values
├── output/                        # Default location for analysis_results JSON files
└── docs/
    └── superpowers/
        ├── specs/                 # Design specs
        └── plans/                 # Implementation plans
```

---

## Architecture Overview

The pipeline has four modules with clear single responsibilities:

**`main.py`** owns the CLI and orchestration. It handles the two optional UI interactions (court calibration clicks, player selection click), then runs the frame-by-frame video loop — passing each frame to the tracker, transforming coordinates if a calibrator is present, and forwarding results to the analyzer.

**`tracker.py` (`PlayerTracker`)** handles all computer vision. Each call to `process_frame(frame)` runs YOLOv10 detection, selects the target player via ByteTrack ID (with colour-histogram re-ID fallback), crops the bounding box, runs MediaPipe Pose on the crop, and returns a 6-tuple: `(player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body)`. Any element is `None` if detection fails.

**`analyzer.py` (`JumpAnalyzer`)** owns all biomechanics logic. It is a pure state machine with no video or image dependencies — it only consumes the 6-tuple values plus optional court coordinates. It detects jumps, computes all metrics, and accumulates a history list that becomes the output JSON.

**`camera_calib.py` (`CameraCalibrator`)** is an optional coordinate transformer. When `--calibrate` is used, it holds a perspective-transform matrix and converts any pixel `(x, y)` to court centimetres via `transform_point()`.

**`utils.py`** contains standalone geometry helpers (`calculate_angle`, `calculate_distance`, `smooth_trajectory`, etc.). These are not imported by the main pipeline — they are available as utilities for exploratory use.

### Data flow

```
Video file
    │
    ▼
PlayerTracker.process_frame(frame)
    │  returns: (player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body)
    │
    ├─► [if --calibrate] CameraCalibrator.transform_point(ground_pos)
    │       returns: court_pos (cm)
    │
    ▼
JumpAnalyzer.analyze_frame(player_id, knee_angles, hip_y, court_pos, frame_time,
                            foot_court_pos, upper_body)
    │  updates internal state; emits JUMP entries to history on landing
    │
    ▼
JumpAnalyzer.save_logs(output_path)
    │
    ▼
output/<video_stem>_analysis.json
    [SESSION_SUMMARY, JUMP, JUMP, ...]
```

---
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Docs: add project structure and architecture overview"
```

---

### Task 4: Write README — Architecture Deep-Dive

**Files:**
- Modify: `README.md` (append Architecture Deep-Dive section)

- [ ] **Step 1: Verify jump detection thresholds against `analyzer.py`**

Run:
```bash
grep "0\.93\|0\.97\|0\.15\|0\.98\|0\.02\|CROUCH_THRESHOLD\|post_landing_window\|approach_window" analyzer.py | head -20
```
Confirm: jump-start threshold `0.93`, landing threshold `0.97`, baseline EMA `0.98`/`0.02`, baseline drift guard `0.15`, crouch threshold `150`, post-landing window `0.3`, approach window `0.5`.

- [ ] **Step 2: Verify re-ID thresholds against `tracker.py`**

Run:
```bash
grep "_reacquire\|_frames_missing\|_target_hue" tracker.py | head -10
```
Confirm: distance threshold `200` px, height tolerance `0.30`, colour threshold `0.5`.

- [ ] **Step 3: Append Architecture Deep-Dive section to `README.md`**

```markdown
## Architecture Deep-Dive

### `JumpAnalyzer` state machine

The analyzer operates in three states per jump cycle:

**1. Grounded (waiting for takeoff)**
- Jump detected when `hip_y < baseline_hip_height × 0.93` (hip rises more than 7% above its standing baseline).
- At the moment of takeoff, the analyzer captures: jump start time and court position, approach velocity (OLS regression over a 0.5 s sliding window — see formula below), stance width, crouch depth/duration from a 1 s approach buffer, trunk lean, and arm swing symmetry.
- While grounded, a slow EMA adapts the baseline: `baseline = 0.98 × baseline + 0.02 × hip_y`. The guard `|hip_y − baseline| / baseline < 0.15` ensures crouches and jumps don't corrupt the baseline estimate.

**2. Airborne (tracking peak)**
- Tracks the minimum `hip_y` seen so far (lower pixel Y = higher in frame = peak height).
- Accumulates all CoM (hip) positions for the flight-drift computation.

**3. Landing**
- Landing detected when `hip_y ≥ baseline_hip_height × 0.97`.
- Computes: air time, jump height, knee angles at landing, all drift metrics, takeoff angle, CoM flight drift, and peak wrist height ratio.
- Appends a `JUMP` entry to the history log.
- Starts a 300 ms **post-landing absorption window**: collects knee angles until it expires, then amends the most recent `JUMP` entry with `min_landing_knee_angle_deg`, `landing_absorption_duration_sec`, and `landing_knee_flexion_rate_degs`.

---

### `PlayerTracker` pipeline

Each call to `process_frame(frame)`:

1. **YOLO detection** — YOLOv10n runs on the full frame (GPU via MPS on Apple Silicon, CUDA on NVIDIA, CPU fallback). Returns bounding boxes and ByteTrack IDs for all detected persons.
2. **Target selection** — the box whose ByteTrack ID matches `target_player_id` is selected. If no match (occlusion, ID switch), re-ID runs.
3. **Re-ID** — a candidate is accepted as the re-acquired target only if all three conditions hold:
   - Centre-to-centre distance from last known position ≤ 200 px
   - Bounding-box height within ±30% of last known height
   - Hue-histogram correlation between the candidate's torso crop and the saved target histogram ≥ 0.5
4. **MediaPipe Pose** — run on the player's bounding-box crop. Uses `model_complexity=1` and 3D world landmarks for knee angles (more robust than 2D pixel angles under perspective distortion).
5. **Extracted values:**
   - `knee_angles` — `(left_deg, right_deg)` computed via the hip→knee→ankle angle in 3D world space
   - `hip_y` — pixel Y of the mid-hip landmark (lower = higher in frame)
   - `ground_pos` — midpoint of left and right ankle pixels
   - `foot_pixels` — `((left_ankle_x, left_ankle_y), (right_ankle_x, right_ankle_y))`
   - `upper_body` — `{"shoulders_px": [(lx,ly),(rx,ry)], "wrists_px": [(lx,ly),(rx,ry)]}`

---

### `CameraCalibrator` — pixel → cm transform

The user clicks 4 court corners (top-left, top-right, bottom-right, bottom-left) on the first frame. `cv2.getPerspectiveTransform` computes a 3×3 homography matrix mapping those 4 points to a canonical 900×1800 rectangle (representing a standard 9 m × 18 m volleyball court at 1 px/cm). `transform_point(px, py)` applies `cv2.perspectiveTransform` to any pixel coordinate, returning `(x_cm, y_cm)` in court space.

---

### Key metric formulas

**Approach velocity (cm/s)**
OLS linear regression on court positions over the 0.5 s window before takeoff:
```
vx = Σ(t − t̄)(x − x̄) / Σ(t − t̄)²
vy = Σ(t − t̄)(y − ȳ) / Σ(t − t̄)²
speed = sqrt(vx² + vy²)
```
OLS is used rather than start-to-end displacement because a single noisy frame at either edge of the window cannot inflate the result.

**Jump height (cm)**
```
pixel_jump = baseline_hip_y − peak_hip_y
jump_height_cm = (pixel_jump / baseline_hip_y) × 100
```
Interprets the hip's fractional rise relative to its standing position as a percentage of an assumed ~100 cm hip height. Most accurate when court calibration is active (pixel scale is known).

**Takeoff angle (degrees)**
```
v0_vertical = sqrt(2 × 981 cm/s² × jump_height_cm)
takeoff_angle = atan2(v0_vertical, approach_velocity_cms)
```
Estimates how much of the athlete's total takeoff velocity was directed vertically vs. horizontally. Only computed when approach velocity is available.

**CoM flight drift (cm)**
Maximum perpendicular distance from any hip position during flight to the straight line between takeoff and landing positions. Computed via the point-to-line formula:
```
distance = |cross_product(landing − takeoff, takeoff − point)| / |landing − takeoff|
```

---
```

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Docs: add architecture deep-dive — state machine, tracker pipeline, formulas"
```

---

### Task 5: Write README — Testing, CI, Development Guidelines, Dependencies

**Files:**
- Modify: `README.md` (append final sections)

- [ ] **Step 1: Verify test file contents**

Run:
```bash
grep "class Test\|def test_\|@pytest.mark" tests/test_e2e.py | head -20
```
Confirm the three test layers (fixture regression, tracker smoke, pipeline integration).

- [ ] **Step 2: Append Testing section to `README.md`**

```markdown
## Testing

### Running tests

```bash
# Fast tests (no GPU, ~2 s) — run after every change
python -m pytest tests/ -v -m "not slow"

# Full suite including tracker smoke tests (~15 s, requires YOLO model load)
python -m pytest tests/ -v

# Single file
python -m pytest tests/test_e2e.py -v -m "not slow"
python -m pytest tests/test_analyzer.py -v
```

### Test files

| File | What it tests |
|---|---|
| `tests/test_analyzer.py` | Unit tests for `JumpAnalyzer` — jump detection logic and landing classification |
| `tests/test_tracker.py` | Smoke tests for `PlayerTracker` — initialisation and `process_frame` return shape |
| `tests/test_utils.py` | Unit tests for geometry helpers (`calculate_angle`, `calculate_distance`, etc.) |
| `tests/test_camera_calib.py` | Unit tests for perspective transform accuracy |
| `tests/test_e2e.py` | End-to-end tests (three layers — see below) |

### End-to-end test layers (`test_e2e.py`)

- **Layer 1 — Metric regression tests (`TestE2EMetricRegression`):** Feed the deterministic 11-frame fixture (`tests/fixtures/single_jump_sequence.json`) through `JumpAnalyzer` and assert every metric value against `tests/fixtures/expected_output.json`. Catches silent regressions in metric formulas without running a real video.
- **Layer 2 — Tracker smoke tests (`@pytest.mark.slow`):** Verify `PlayerTracker` initialises and `process_frame` returns a 6-tuple without crashing. Requires the YOLO model to load — excluded from fast CI.
- **Layer 3 — Pipeline integration tests:** Mock the tracker, generate a synthetic video in memory, run the full `main.py` processing loop, and assert on the saved JSON structure and values.

### Adding tests for new metrics

1. Add frames to `tests/fixtures/single_jump_sequence.json` if the new metric requires different input.
2. Compute the expected value by hand or from a trusted run, then add it to `tests/fixtures/expected_output.json`.
3. Add an assertion to `TestE2EMetricRegression` in `tests/test_e2e.py`.

---
```

- [ ] **Step 3: Append CI Pipeline section**

```markdown
## CI Pipeline

Three jobs run on every pull request, push to `main`, and merge-queue event.

| Job | Blocks merge? | What it checks |
|---|---|---|
| **Tests (fast suite)** | Yes | `pytest tests/ -m "not slow"` — all non-GPU tests must pass |
| **Lint (syntax errors)** | Yes | `flake8 --select=E9,F63,F7,F82` — runtime errors and undefined names only |
| **Lint (style)** | No | Full `flake8` style check — informational, never blocks |
| **Type-check** | No | `mypy` with `--exit-code 0` — informational while annotations are sparse |

Slow tests (`@pytest.mark.slow`) require a real video file and GPU — run them locally before opening a PR.

---
```

- [ ] **Step 4: Append Development Guidelines and Dependencies**

```markdown
## Development Guidelines

### Adding a new metric

1. Add a regression test to `TestE2EMetricRegression` in `tests/test_e2e.py` and update `tests/fixtures/expected_output.json` with the pre-computed expected value.
2. Implement the metric in `analyzer.py`.
3. Document the new field in `README.md` under the relevant `metrics` table, including units and value range.
4. Verify consistency: run the tool twice on the same video and confirm the output is identical:
   ```bash
   python main.py --video single_jump.mov --player_id 1 --output output/run1.json
   python main.py --video single_jump.mov --player_id 1 --output output/run2.json
   diff output/run1.json output/run2.json
   ```

### Consistency check

The tool must be deterministic. Before calling any feature done, run the consistency check above (`diff` should produce no output).

---

## Dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Video decoding, frame processing, perspective transform |
| `mediapipe` | Pose estimation — 33 body landmarks per frame |
| `ultralytics` | YOLOv10 player detection + ByteTrack multi-object tracking |
| `numpy` | Numerical operations |
| `scipy` | Signal processing |
| `matplotlib` | Visualisation utilities |
| `pandas` | Data handling |
| `scikit-learn` | ML utilities |
```

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "Docs: add testing, CI, development guidelines, and dependencies sections"
```

---

### Task 6: Trim `CLAUDE.md` to thin dev-workflow overlay

**Files:**
- Modify: `CLAUDE.md` (full replacement)

- [ ] **Step 1: Read current `CLAUDE.md`**

Read `CLAUDE.md` and confirm which sections duplicate README content vs. which are dev-workflow-only.

- [ ] **Step 2: Replace `CLAUDE.md`**

Write the following as the complete new `CLAUDE.md` (overwrite entirely):

```markdown
# Volleyball Mechanics Analyser — Dev Workflow

> For full project documentation (architecture, output schema, metrics reference, CLI flags) see `README.md`.

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
2. Implement in `analyzer.py`
3. Document in `README.md` under the relevant metrics table
4. Run the consistency check (below) before calling it done

## Consistency check (always run before done)

```bash
python main.py --video single_jump.mov --player_id 1 --output output/run1.json
python main.py --video single_jump.mov --player_id 1 --output output/run2.json
diff output/run1.json output/run2.json
```

`diff` must produce no output.
```

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "Docs: trim CLAUDE.md to dev-workflow overlay, reference README for all other content"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Covered by |
|---|---|
| Fix `--debug` / `--no_calibrate` flags | Task 1 |
| Fix default output path | Task 1 |
| SESSION_SUMMARY schema | Task 2 |
| Unified JUMP schema with correct field names | Task 2 |
| All ~8 new metrics documented | Task 2 |
| `trunk_lean_deg` always-null note | Task 2 |
| Calibration-gated fields called out | Task 2 |
| `test_tracker.py` in project structure | Task 3 |
| Architecture overview + data-flow diagram | Task 3 |
| JumpAnalyzer state machine with thresholds | Task 4 |
| PlayerTracker re-ID logic | Task 4 |
| CameraCalibrator homography | Task 4 |
| Key formulas (OLS, jump height, takeoff angle, CoM drift) | Task 4 |
| Test layers, fixture files, adding-tests instructions | Task 5 |
| CI pipeline (3 jobs, what blocks) | Task 5 |
| Dev guidelines (metric checklist, consistency check) | Task 5 |
| CLAUDE.md → thin overlay with README references | Task 6 |

### Placeholder scan

No TBDs, TODOs, or "implement later" phrases. All code blocks contain actual content. Field names verified against source in Step 1 of each relevant task.

### Type consistency

No method signatures or property names span tasks — this is a documentation plan. Field names are verified against source in each task before being written.
