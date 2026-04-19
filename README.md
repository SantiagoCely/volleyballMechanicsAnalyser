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

## Output Format

Results are saved as a JSON array. The first element is always a `SESSION_SUMMARY`; each subsequent element is one `JUMP` per detected jump.

### `SESSION_SUMMARY` event

```json
{
  "event": "SESSION_SUMMARY",
  "video": "single_jump.mov",
  "jump_count": 2,
  "jump_height_variability_cm": 1.4,
  "air_time_variability_sec": 0.012,
  "avg_jump_score": 76.5,
  "best_jump_num": 2,
  "best_jump_score": 82.0,
  "worst_jump_num": 1,
  "worst_jump_score": 71.0
}
```

| Field | Type | Description |
|---|---|---|
| `event` | string | Always `"SESSION_SUMMARY"` |
| `video` | string \| null | Basename of the analyzed file from `--video`. `null` if results were saved without a name (e.g. some tests call `save_logs` with no `video_name`) |
| `jump_count` | int | Total jumps detected in the video |
| `jump_height_variability_cm` | float \| null | Sample standard deviation (`statistics.stdev`) of `jump_height_est_cm` across all jumps. `null` if fewer than 2 jumps |
| `air_time_variability_sec` | float \| null | Sample standard deviation of `air_time_sec` across all jumps. `null` if fewer than 2 jumps |
| `avg_jump_score` | float \| null | Mean of each jump’s `metrics.score` (see [Jump scoring](#jump-scoring)). `null` if no `JUMP` entry has `metrics.score` (should not occur in normal runs). Jumps without `metrics.score` are skipped |
| `best_jump_num` | int \| null | `jump_num` of the highest-scoring jump. `null` if there are no scored jumps. If two jumps tie for highest, the earlier `jump_num` in file order wins |
| `best_jump_score` | float \| null | Highest composite score in the session |
| `worst_jump_num` | int \| null | `jump_num` of the lowest-scoring jump. If two jumps tie for lowest, the earlier `jump_num` wins |
| `worst_jump_score` | float \| null | Lowest composite score in the session |

---

### Jump scoring

Each completed `JUMP` includes a composite **score** (`int`, **0–100**) and a **`score_breakdown`** of per-channel sub-scores (each **0–100** **before** weighting). **`compute_jump_score`** (`jump_scoring.py`):

1. Computes one sub-score per channel that has inputs (missing optional inputs → entire channel omitted).
2. **Renormalizes** the five **base weights** over **only** those active channels so they sum to **1**.
3. **`score = int(round(sum(weight_i × sub_score_i)))`**, clamped to **\[0, 100\]**.
4. **`score_breakdown`** lists **`round(sub_score_i, 1)`** only for active channels — except the degenerate case below.

**Degenerate inputs:** If **no** channel produced a sub-score (should not occur for a normal completed jump), **`score`** is **`0`** and **`score_breakdown`** is **`{"_error": "no scoring inputs available"}`**.

**Channels and default weights** (weights are **renormalized** over channels that have data — without **`--calibrate`**, **`drift_stability`**, **`approach_control`**, and parts of **`takeoff_form`** usually drop because **`metrics.drift_cm`**, **`takeoff.approach_velocity_cms`**, **`takeoff.stance_width_cm`**, or **`metrics.takeoff_angle_deg`** are missing):

| Channel | Inputs | Interpretation |
|--------|--------|------------------|
| `landing_quality` | `knee_angles.left`, `knee_angles.right` at contact | Each knee scored then **averaged**. **100** in **[130°, 155°]**; below **130°**, lose **4** points per degree shallow of **130°**; above **155°**, lose **5** points per degree stiff above **155°** |
| `jump_quality` | `jump_height_est_cm` | Linear map: **8 cm → 0**, **45 cm → 100**, linear between (below **8 → 0**, above **45 → 100** via clamp). Named **`jump_quality`** to avoid confusion with **`jump_height_est_cm`** |
| `drift_stability` | `drift_cm.magnitude` | **`100 − (magnitude / 40) × 100`**, floored at **0** (**40 cm → 0**). Requires **`drift_cm`** |
| `approach_control` | `takeoff.approach_velocity_cms` | **100** in **[350, 620]** cm/s; linear **0–100** between **150–350** and **620–800**; **≤150** or **≥800 → 0** |
| `takeoff_form` | `takeoff.stance_width_cm`, `metrics.takeoff_angle_deg` | **Mean** of whichever sub-scores exist: **stance** **100** when **\[18, 38\]** cm (else linear penalty outside band), **angle** **100** when **\[12°, 40°\]** (else linear penalty). If **only one** of stance/angle exists, **`takeoff_form`** equals that single sub-score |

**Base weights before renormalization:** landing **0.25**, jump-quality **0.25**, drift **0.20**, approach **0.15**, takeoff form **0.15**.

#### `metrics` fields — Jump scoring

| Field | Type | Description |
|--------|------|-------------|
| `score` | int | Composite quality **0–100** (`jump_scoring.compute_jump_score`) |
| `score_breakdown` | object | Active channels only: each value is **0–100**, **one decimal**. Includes **`_error`** only in the degenerate case above |

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
    "com_flight_drift_cm": 15.1,
    "score": 78,
    "score_breakdown": {
      "landing_quality": 95.0,
      "jump_quality": 62.0,
      "drift_stability": 88.0,
      "approach_control": 100.0,
      "takeoff_form": 92.0
    }
  },
  "landing_pos": [275.2, 1201.5]
}
```

> **Calibration note:** Without `--calibrate`, **`takeoff.pos`** is JSON **`null`** (the key is still present); **`takeoff.approach_velocity_cms`** and **`takeoff.stance_width_cm`** keys are **omitted** (no cm geometry); **`metrics.drift_cm`**, **`metrics.com_flight_drift_cm`**, and **`landing_pos`** are omitted. Pose-based fields (including **`takeoff.crouch_*`** and most **`metrics`**) still populate when tracking succeeds.

> **`trunk_lean_deg` note:** Always **`null`** in output — `JumpAnalyzer` assigns `None` at jump completion; a `_compute_trunk_lean` helper exists but shoulder/hip wiring is not hooked up yet.

#### Top-level JUMP fields

| Field | Type | Description |
|---|---|---|
| `event` | string | Always `"JUMP"` |
| `jump_num` | int | Sequential jump counter for this player in the video |
| `player_id` | int | ByteTrack ID of the tracked player |
| `start_video_time_sec` | float | Video clock time (seconds) at the **jump-start** frame: first frame where the hip crosses the takeoff detector (`hip_y` below 93% of the standing baseline). Rounded to 3 decimal places |
| `end_video_time_sec` | float | Video clock time (seconds) at the **landing** frame: first frame after takeoff where the hip returns within the landing band (`hip_y` at or above 97% of the standing baseline). Rounded to 3 decimal places |
| `status` | string | `"SAFE"`: both knees ≤ **160°** at the landing frame (default threshold; configurable via `JumpAnalyzer(..., stiff_landing_threshold=...)`). `"STIFF"`: either knee **strictly greater than** that threshold — straighter legs increase ACL and patellar tendon injury risk |
| `landing_pos` | [x, y] | Player ground position in court coordinates (cm) at the landing frame (`court_pos` from the tracker’s feet/ground point after `CameraCalibrator.transform_point`). Only with `--calibrate` |

#### `takeoff` fields

| Field | Type | Description |
|---|---|---|
| `pos` | [x, y] \| null | Ground position transformed to court coordinates (cm) at **jump-start** (`jump_start_pos`). **`null`** without calibration |
| `approach_velocity_cms` | float | 2D court-plane speed (cm/s) via OLS over the **`approach_window_sec`** interval (default **0.5 s**) ending at jump-start — see **Key metric formulas**. Key **omitted** without calibration-derived position history |
| `stance_width_cm` | float | Euclidean distance between left and right ankles in cm at jump-start (**`foot_court_pos`**). Key **omitted** without ankle positions in cm |
| `crouch_depth_deg` | float | Minimum, over grounded samples with `t ≤` jump-start time, of the **average** `(left_knee_angle + right_knee_angle) / 2`. Samples come from the rolling **1 s** approach buffer (`approach_knee_angles`). Lower = deeper squat. Present only together with **`crouch_duration_sec`** — both keys **omitted** if no approach knee samples buffered through takeoff |
| `crouch_duration_sec` | float | Among the same buffered samples with `t ≤` jump-start: **elapsed time between the first and last timestamp** whose average knee angle is **strictly less than** **150°** (`JumpAnalyzer._CROUCH_THRESHOLD_DEG`). **0** if average never drops below **150°** **or** only **one** such sample exists |
| `trunk_lean_deg` | float \| null | Planned: angle of hip→shoulder line from vertical at takeoff (0° = upright). Stubbed **`null`** until torso position is plumbed through (see calibration note above) |

#### `metrics` fields — Injury Prevention

| Field | Type | Description |
|---|---|---|
| `knee_angles.left` | float | Left knee **hip–knee–ankle** angle (degrees) from pose (`tracker.py`, world landmarks). Straighter legs approach **180°**; smaller values mean deeper flexion. Taken from the **landing-detection frame** — the first airborne frame where `hip_y` reaches the landing band (`≥ 97%` of standing baseline), same instant as **`end_video_time_sec`**. Rounded to **1** decimal |
| `knee_angles.right` | float | Same as left, for the right leg |
| `knee_symmetry_deg` | float | Absolute difference **between left and right** knee angles at that same landing frame (degrees). **0** = symmetric; larger values indicate asymmetric loading. Rounded to **1** decimal. Always present with numeric angles for a completed `JUMP` (no JSON `null`) |

#### `metrics` fields — Jump Performance

| Field | Type | Description |
|---|---|---|
| `air_time_sec` | float | **`end_video_time_sec` − `start_video_time_sec`** for this jump — wall-clock span from jump-start detection to landing detection (same video clock used for timestamps). Rounded to **3** decimals |
| `jump_height_est_cm` | float | **Model:** `(baseline_hip_y − peak_hip_y) / baseline_hip_y × 100`, where **`peak_hip_y`** is the **minimum** hip pixel Y reached while airborne (lowest row in the image = highest point in space). Treats that fraction as vertical hip displacement in **cm** under an implicit ~**100 cm** hip-height scale — see **Key metric formulas**. Rounded to **1** decimal |
| `jump_height_est_inch` | float | **`jump_height_est_cm × 0.393701`**, rounded to **1** decimal |
| `takeoff_angle_deg` | float \| null | Degrees above horizontal from **`atan2(v₀_vertical, approach_velocity_cms)`** with **`v₀_vertical = √(2 × 981 × jump_height_est_cm)`** — see **Key metric formulas**. Rounded to **1** decimal. **`null`** if approach velocity is missing or **`≤ 0`**, or **`jump_height_est_cm` ≤ 0** (usual without **`--calibrate`**) |
| `peak_wrist_height_ratio` | float \| null | At **peak hip** (minimum `hip_y` while airborne): **`(hip_y_peak − avg_wrist_y) / (hip_y_peak − avg_shoulder_y)`** using **`upper_body_at_peak`** from the tracker (`shoulders_px` / `wrists_px` in **full-frame pixels**; image Y increases downward). **> 1** when wrists are **above** shoulders in the frame. Rounded to **3** decimals. **`null`** if pose did not supply upper body at peak, or shoulder–hip segment length **`≤ 0`** |
| `arm_swing_symmetry_px` | float \| null | **`|left_wrist_y − right_wrist_y|`** from **`wrists_px`** on the **last** sample in the **1 s** grounded **`approach_upper_body`** buffer — i.e. the **takeoff** frame’s arms when tracking is continuous (pixels). Rounded to **1** decimal. **`null`** if no **`upper_body`** was recorded in that buffer during the approach window |

#### `metrics` fields — Court Position & Drift (requires `--calibrate`)

Court positions are **`CameraCalibrator.transform_point`** outputs in cm on the canonical top-down court (**`x`** ≈ 9 m span **0–900**, **`y`** ≈ 18 m span **0–1800** — see **`camera_calib.py`**). **`takeoff`** uses **`jump_start_pos`**; landing uses **`court_pos`** on the landing frame (`ground_pos` transformed).

| Field | Type | Description |
|---|---|---|
| `drift_cm.forward_back` | float | **`landing_y − takeoff_y`** (cm). **Positive** when the landing **`y`** is greater than at takeoff in this coordinate frame (interpret as “forward” along the court **`y`** axis after your corner calibration). Rounded to **1** decimal |
| `drift_cm.side_to_side` | float | **`landing_x − takeoff_x`** (cm). Lateral shift along **`x`**. Rounded to **1** decimal |
| `drift_cm.magnitude` | float | **`√(side_to_side² + forward_back²)`** — planar distance from takeoff to landing (cm). Rounded to **1** decimal |
| `com_flight_drift_cm` | float | Maximum **perpendicular** distance (cm) from any **hip path sample** during flight to the **infinite line** through takeoff and landing court positions — same geometry as **Key metric formulas** (`cross` / chord length). Hip positions are appended each airborne frame when **`court_pos`** exists (**≥ 2** samples required, including straight-line degeneracy handling). Rounded to **1** decimal |

The entire **`drift_cm`** object is **omitted** if **`court_pos`** or **`jump_start_pos`** is missing at landing. **`com_flight_drift_cm`** is **omitted** if fewer than **two** hip samples were collected in flight **or** takeoff/landing court positions are missing.

#### `metrics` fields — Post-Landing Absorption

While grounded **after** landing (and **not** airborne on a later jump), the analyzer collects knee samples into **`post_landing_knee`** until **`post_landing_window`** (**300 ms**) elapses (`JumpAnalyzer.post_landing_window`). The buffer is **seeded with the landing frame**. Finalization runs when that timer fires **or** early when **takeoff for the next jump** begins (same `_finalize_landing_absorption` path).

They are **`null` on the `JUMP` row until finalized**. If processing **stops** before **300 ms** of post-landing frames arrives **and** no further jump occurs, metrics **stay `null`** — **`save_logs` does not synthesize frames**.

| Field | Type | Description |
|---|---|---|
| `min_landing_knee_angle_deg` | float \| null | Minimum over the window of **`(left_knee_angle + right_knee_angle) / 2`** (same knee convention as landing). Lower = deeper flexion during absorption. **`null`** until finalized |
| `landing_absorption_duration_sec` | float \| null | **`t_min − t_landing`** where **`t_min`** is the timestamp of the **first** sample (chronological order) achieving **`min_landing_knee_angle_deg`**. **`0`** if the deepest flex is on the landing frame itself. **`null`** until finalized |
| `landing_knee_flexion_rate_degs` | float \| null | **`(avg_at_landing − min_avg) / landing_absorption_duration_sec`** when duration **`> 0`** — average rate (°/s) from landing-frame average knee angle to deepest flex in the window; **`0`** when duration is **`0`**. **`null`** until finalized |

**Rounding:** **`min`** and **`flexion_rate`** to **1** decimal; **`duration`** to **3** decimals (`analyzer.py`).

---

## Project Structure

```
volleyballMechanicsAnalyser/
├── main.py                        # Entry point: CLI, calibration UI, player selection, video loop
├── analyzer.py                    # JumpAnalyzer — jump detection state machine and metric computation
├── jump_scoring.py                # Composite jump score (0–100), breakdown, session rollups
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

## Architecture Deep-Dive

### `JumpAnalyzer` state machine

The analyzer operates in three states per jump cycle:

**1. Grounded (waiting for takeoff)**
- Jump detected when `hip_y < baseline_hip_height × 0.93` (hip rises more than 7% above its standing baseline).
- At the moment of takeoff, the analyzer captures: jump start time and court position (when calibrated), approach velocity (OLS regression over a 0.5 s sliding window — see formula below), stance width (when ankle positions are available in cm), crouch depth/duration from a 1 s approach buffer, arm swing symmetry from the last upper-body sample in that buffer, and **`trunk_lean_deg` is filled as `null`** (stub until wired).
- While grounded, a slow EMA adapts the baseline: `baseline = 0.98 × baseline + 0.02 × hip_y`. The guard `|hip_y − baseline| / baseline < 0.15` ensures crouches and jumps don't corrupt the baseline estimate.

**2. Airborne (tracking peak)**
- Tracks the minimum `hip_y` seen so far (lower pixel Y = higher in frame = peak height).
- Accumulates all CoM (hip) positions for the flight-drift computation.

**3. Landing**
- Landing detected when `hip_y ≥ baseline_hip_height × 0.97`.
- Computes: air time, jump height, knee angles at landing, all drift metrics, takeoff angle, CoM flight drift, and peak wrist height ratio.
- Appends a `JUMP` entry to the history log.
- Starts a **300 ms** **post-landing absorption window** (grounded samples only); when the window ends **or** the athlete’s **next takeoff** begins early, **`_finalize_landing_absorption`** patches the latest `JUMP.metrics` with the absorption trio. Frames must actually be processed — **writing JSON without ~300 ms of subsequent frames leaves these fields `null`**.

---

### `PlayerTracker` pipeline

Each call to `process_frame(frame)`:

1. **YOLO detection** — YOLOv10n runs on the full frame (GPU via MPS on Apple Silicon, CUDA on NVIDIA, CPU fallback). Returns bounding boxes and ByteTrack IDs for all detected persons.
2. **Target selection** — the box whose ByteTrack ID matches `target_player_id` is selected. If no match (occlusion, ID switch), re-ID runs.
3. **Re-ID** — a candidate is accepted as the re-acquired target only if all three conditions hold:
   - Bounding-box height within ±30% of last known height
   - Hue-histogram correlation between the candidate's torso crop and the saved target histogram ≥ 0.5
   - Centre-to-centre distance from last known position ≤ 200 px (the closest passing candidate is selected)
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

**Air time (s)**
```
air_time_sec = landing_frame_time − jump_start_frame_time
```
Uses the same frame timestamps as **`start_video_time_sec`** / **`end_video_time_sec`** — i.e. **not** physics-derived from hang time, but the detector’s takeoff-to-landing interval.

**Upper body (pixels, from `tracker.py` landmarks mapped to full frame)**

```
avg_shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
avg_wrist_y    = (left_wrist.y + right_wrist.y) / 2
segment        = hip_y_peak − avg_shoulder_y        # must be > 0
peak_wrist_height_ratio = (hip_y_peak − avg_wrist_y) / segment
```
`hip_y_peak` is the minimum hip row during the jump (same as **`peak_hip_y`** in `JumpAnalyzer`). **`arm_swing_symmetry_px`** uses the same landmark **Y** coordinates: **`|left_wrist_y − right_wrist_y|`** from the last grounded **`approach_upper_body`** sample (takeoff frame when pose is present).

**Takeoff angle (degrees)**
```
v0_vertical = sqrt(2 × 981 cm/s² × jump_height_cm)
takeoff_angle_deg = atan2(v0_vertical, approach_velocity_cms)   # converted to degrees in code
```
Uses **`jump_height_est_cm`** from the pixel-height model above and **`takeoff.approach_velocity_cms`** from OLS — same inputs as emitted in JSON. **`null`** if **`approach_velocity_cms`** is absent or **`≤ 0`** or **`jump_height_cm ≤ 0`**. Missing approach velocity is the usual case **without `--calibrate`**.

**Planar drift (`drift_cm`, cm)**

Computed at landing from takeoff vs landing **`court_pos`**:
```
side_to_side   = landing_x − takeoff_x    # JSON key drift_cm.side_to_side
forward_back   = landing_y − takeoff_y    # JSON key drift_cm.forward_back
magnitude      = sqrt(side_to_side² + forward_back²)
```

**CoM flight drift (cm)**

Maximum perpendicular distance from any hip **`court_pos`** sample during flight to the **line** through takeoff and landing (infinite line, same as classic point-to-line distance):
```
distance = |(ey − sy)·px − (ex − sx)·py + ex·sy − ey·sx| / √((ex − sx)² + (ey − sy)²)
```
If takeoff and landing coincide (**0** chord length), the implementation falls back to the **maximum distance** from takeoff to any hip sample (see `_compute_com_flight_drift`).

**Post-landing absorption (after the 300 ms window is finalized)**

Over grounded samples `(t, left, right)` collected starting at **`t_landing`**:

```
avg(t)           = (left + right) / 2
min_avg          = minimum of avg(t) over the buffer
duration         = t_* − t_landing   where t_* is timestamp of first sample attaining min_avg
flexion_rate     = (avg(t_landing) − min_avg) / duration    if duration > 0 else 0
```

---

## Testing

### Running tests

```bash
# Fast tests (no GPU, ~2–4 s) — run after every change — excludes slow + fuzz markers
python -m pytest tests/ -v -m "not slow and not fuzz"

# Full suite including tracker smoke tests (~15 s, requires YOLO model load); still excludes fuzz
python -m pytest tests/ -v -m "not fuzz"

# Property/fuzz tests (Hypothesis — optional, slower / randomized)
python -m pytest tests/ -v -m fuzz

# Single file (fast layers only)
python -m pytest tests/test_e2e.py -v -m "not slow and not fuzz"
python -m pytest tests/test_analyzer.py -v
```

### Test files

| File | What it tests |
|---|---|
| `tests/test_analyzer.py` | Unit tests for `JumpAnalyzer` — jump detection logic and landing classification |
| `tests/test_analyzer_state_machine.py` | Synthetic frame sequences asserting jump / post-landing state transitions (`is_jumping`, `post_landing_active`, history) |
| `tests/test_determinism.py` | Same inputs produce identical saved JSON (`save_logs`) and identical `compute_jump_score` outputs |
| `tests/test_fuzz_properties.py` | **`@pytest.mark.fuzz`** — Hypothesis properties for `compute_jump_score` and `analyze_frame` short sequences |
| `tests/test_main_cli.py` | `parse_main_args` / default `--output` path / nested output dir creation / `main.py --help` (no model load) |
| `tests/test_tracker.py` | Smoke tests for `PlayerTracker` — initialisation and `process_frame` return shape |
| `tests/test_utils.py` | Unit tests for geometry helpers (`calculate_angle`, `calculate_distance`, etc.) |
| `tests/test_camera_calib.py` | Unit tests for perspective transform accuracy |
| `tests/test_e2e.py` | End-to-end tests (three layers — see below) |

### pytest markers, timeouts, CI

| Marker | Meaning |
|--------|---------|
| *(default)* | Fast blocking suite: `-m "not slow and not fuzz"` |
| `slow` | YOLO load and/or committed golden video regressions — excluded from PR CI |
| `fuzz` | Hypothesis property tests (`tests/test_fuzz_properties.py`) — excluded from PR CI |

Some tests use **`pytest-timeout`** (`@pytest.mark.timeout`) so bounded loops stay bounded. Install with `pip install pytest pytest-timeout` (included when installing from `requirements.txt`). **`hypothesis`** powers `@pytest.mark.fuzz` tests (also listed in `requirements.txt`).

If you add optional markers such as **`stress`** (long-run suites), register them in `pytest.ini` and extend the blocking CI expression — for example `-m "not slow and not fuzz and not stress"` — because pytest does not auto-exclude unknown markers.

### End-to-end test layers (`test_e2e.py`)

- **Layer 1 — Metric regression tests (`TestE2EMetricRegression`):** Feed the deterministic 11-frame fixture (`tests/fixtures/single_jump_sequence.json`) through `JumpAnalyzer` and assert every metric value against `tests/fixtures/expected_output.json`. Catches silent regressions in metric formulas without running a real video.
- **Layer 2 — Tracker smoke tests (`@pytest.mark.slow`):** Verify `PlayerTracker` initialises and `process_frame` returns a 6-tuple without crashing. Requires the YOLO model to load — excluded from fast CI.
- **Layer 3 — Pipeline integration tests:** Mock the tracker, generate a synthetic video in memory, run the full `main.py` processing loop, and assert on the saved JSON structure and values.

### Adding tests for new metrics

1. Add frames to `tests/fixtures/single_jump_sequence.json` if the new metric requires different input.
2. Compute the expected value by hand or from a trusted run, then add it to `tests/fixtures/expected_output.json`.
3. Add an assertion to `TestE2EMetricRegression` in `tests/test_e2e.py`.
4. For nullable metrics, include a fixture or unit test that asserts JSON `null` (or omitted key) when the “no data” branch is exercised — see `CLAUDE.md` (**Nullable metric verification**). Extend `tests/test_analyzer.py` **`TestNullableMetricSemantics`** when the contract changes.

---

## CI Pipeline

Three jobs run on every pull request, push to `main`, and merge-queue event.

| Job | Blocks merge? | What it checks |
|---|---|---|
| **Tests (fast suite)** | Yes | `pytest tests/ -m "not slow and not fuzz"` — deterministic unit/e2e tests; excludes GPU video **and** Hypothesis fuzz (`pytest-timeout` used in some modules; add `and not stress` when that marker exists) |
| **Property / fuzz tests** | No | Same CI job runs `pytest tests/test_fuzz_properties.py -m fuzz` **after** the fast suite with **`continue-on-error: true`** — failures are visible in logs but do **not** block merge until promoted — [issue #35](https://github.com/SantiagoCely/volleyballMechanicsAnalyser/issues/35) |
| **Lint (syntax errors)** | Yes | `flake8 --select=E9,F63,F7,F82` — runtime errors and undefined names only |
| **Lint (style)** | No | Full `flake8` style check — informational, never blocks |
| **Type-check** | No | `mypy` run with `|| true` — always passes, findings visible in CI logs only |

Slow tests (`@pytest.mark.slow`) require a real video file and GPU — run them locally before opening a PR.

---

## Development Guidelines

### Adding a new metric

1. Add a regression test to `TestE2EMetricRegression` in `tests/test_e2e.py` and update `tests/fixtures/expected_output.json` with the pre-computed expected value.
2. Implement the metric in `analyzer.py`.
3. Document the new field in `README.md` under the relevant `metrics` table, including units and value range.
4. **Nullable fields:** document every `null when …` rule and verify the saved JSON uses real JSON `null` (or omits the key, if that is the contract — see `CLAUDE.md` → **Nullable metric verification**). Add a test or fixture branch that exercises the absent-data case when feasible.
5. Update **`docs/metric-audit-matrix.md`** so the audit matrix stays aligned with **README + code** (same metric contract you just documented above).
6. Verify consistency: run the tool twice on the same video and confirm the output is identical:
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
