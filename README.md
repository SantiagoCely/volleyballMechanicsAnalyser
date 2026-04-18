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
