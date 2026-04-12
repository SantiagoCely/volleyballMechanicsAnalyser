# Volleyball Mechanics Analyser

A Python tool that analyses volleyball player jump mechanics from video, using YOLOv10 for player detection and MediaPipe for pose estimation. Produces a JSON file with injury-prevention and pro-performance metrics for every jump detected.

## Installation

```bash
git clone <repository-url>
cd volleyballMechanicsAnalyser
pip install mediapipe==0.10.14 ultralytics opencv-python numpy matplotlib pandas scipy scikit-learn lap
```

**macOS SSL fix** — if you see `[SSL: CERTIFICATE_VERIFY_FAILED]` during model download:
```bash
/Applications/Python\ 3.10/Install\ Certificates.command
```
*(replace `3.10` with your Python version)*

---

## Running the analyser

### Normal mode
Prompts you to click 4 court corners for calibration, then click the player to track:
```bash
python main.py --video path/to/video.mov
```

### Debug mode (no UI interaction)
Uses hardcoded court corners and tracks player ID 1 — use this for quick testing:
```bash
python main.py --video single_jump.mov --debug --player_id 1
python main.py --video multiple_jumps.mov --debug --player_id 1
```

### All flags

| Flag | Description |
|---|---|
| `--video <path>` | Path to video file (required) |
| `--debug` | Skip UI — use hardcoded court corners and bypass player selection |
| `--player_id <id>` | Track a specific player by ID |
| `--no_calibrate` | Skip court calibration (drift/position metrics will be in pixels, not cm) |
| `--output <path>` | Where to save results JSON (default: `output/analysis_results.json`) |
| `--show` | Display the video with tracking overlays while processing |

---

## Output format

Results are saved as a JSON array of events. Each jump produces two events: `JUMP_START` and `LANDING`.

```json
[
  {
    "timestamp": "2026-04-09T18:37:57.608977",
    "event": "JUMP_START",
    "details": { ... }
  },
  {
    "timestamp": "2026-04-09T18:37:58.994045",
    "event": "LANDING",
    "details": { ... }
  }
]
```

### JUMP_START event

```json
{
  "player_id": 1,
  "jump_num": 1,
  "takeoff_pos": [270.8, 986.1],
  "approach_velocity_cms": 547.7,
  "takeoff_stance_width_cm": 26.2
}
```

| Field | Type | Description |
|---|---|---|
| `player_id` | int | ByteTrack ID of the tracked player |
| `jump_num` | int | Sequential jump counter for this player in the video |
| `takeoff_pos` | [x, y] | Court position (cm) at the moment of takeoff. Requires calibration; in pixels otherwise |
| `approach_velocity_cms` | float | 2D court-plane speed (cm/s) estimated via OLS regression over the 0.5 s window before takeoff. Elite attackers typically reach 400–600 cm/s |
| `takeoff_stance_width_cm` | float | Distance between left and right ankles at the moment of takeoff (cm). Reflects jump preparation stance width |

### LANDING event

```json
{
  "player_id": 1,
  "status": "STIFF",
  "metrics": {
    "air_time_sec": 0.418,
    "jump_height_est_cm": 18.6,
    "jump_height_est_inch": 7.3,
    "knee_angles": { "left": 164.2, "right": 166.7 },
    "drift_cm": {
      "forward_back": 215.4,
      "side_to_side": 4.4,
      "magnitude": 215.4
    },
    "approach_velocity_cms": 547.7,
    "takeoff_stance_width_cm": 26.2,
    "takeoff_angle_deg": 19.2,
    "com_flight_drift_cm": 15.1
  },
  "landing_pos": [275.2, 1201.5]
}
```

#### Top-level landing fields

| Field | Type | Description |
|---|---|---|
| `player_id` | int | ByteTrack ID of the tracked player |
| `status` | string | `"SAFE"` or `"STIFF"` — see injury prevention section below |
| `landing_pos` | [x, y] | Court position (cm) at the moment of landing. Requires calibration |

#### `metrics` fields

**Injury prevention**

| Field | Type | Description |
|---|---|---|
| `knee_angles.left` | float | Left knee flexion angle at landing (degrees). 180° = fully straight leg |
| `knee_angles.right` | float | Right knee flexion angle at landing (degrees). 180° = fully straight leg |
| `status` | string | `"SAFE"`: both knees ≤ 160° — good shock absorption. `"STIFF"`: either knee > 160° — straighter legs increase ACL and patellar tendon injury risk |

**Jump performance**

| Field | Type | Description |
|---|---|---|
| `air_time_sec` | float | Time from takeoff to landing (seconds) |
| `jump_height_est_cm` | float | Estimated vertical displacement of the hips (cm). Derived from the ratio of hip pixel travel to baseline hip height — most accurate with court calibration |
| `jump_height_est_inch` | float | Same as above, in inches |

**Court position and drift**

| Field | Type | Description |
|---|---|---|
| `drift_cm.forward_back` | float | How far the player landed in front of (positive) or behind (negative) their takeoff point (cm). Common in aggressive attacking approaches |
| `drift_cm.side_to_side` | float | Lateral displacement from takeoff to landing (cm). Large values may indicate balance issues during flight |
| `drift_cm.magnitude` | float | Straight-line distance from takeoff to landing position: `sqrt(forward_back² + side_to_side²)` (cm) |

**Pro performance metrics**

| Field | Type | Description |
|---|---|---|
| `approach_velocity_cms` | float | Same value as in `JUMP_START` — repeated here for convenience when analysing landing-only data (cm/s) |
| `takeoff_stance_width_cm` | float | Same value as in `JUMP_START` — repeated here for convenience (cm) |
| `takeoff_angle_deg` | float | Estimated angle of the jump trajectory from horizontal (degrees). Computed as `atan2(v₀_vertical, approach_velocity)` where `v₀ = sqrt(2·g·jump_height)`. Higher angles (closer to 90°) mean more vertical jump; lower angles mean more of the approach speed is going forward rather than up. Only present when approach velocity is available |
| `com_flight_drift_cm` | float | Maximum perpendicular deviation of the hip (centre of mass proxy) from the straight line between takeoff and landing positions (cm). Measures how much the player's body swerves during flight — lower is more controlled |

---

## Project structure

```
volleyballMechanicsAnalyser/
├── main.py                        # Entry point and processing loop
├── analyzer.py                    # JumpAnalyzer — event detection and metrics
├── tracker.py                     # PlayerTracker — YOLO detection + MediaPipe pose
├── camera_calib.py                # Court calibration (pixel → cm conversion)
├── utils.py                       # Geometry and signal processing helpers
├── pytest.ini                     # Test configuration
├── tests/
│   ├── test_analyzer.py           # Unit tests for JumpAnalyzer
│   ├── test_utils.py              # Unit tests for geometry helpers
│   ├── test_camera_calib.py       # Unit tests for perspective transform
│   ├── test_e2e.py                # End-to-end tests (3 layers)
│   └── fixtures/
│       ├── single_jump_sequence.json   # Deterministic input fixture
│       └── expected_output.json        # Pinned expected metric values
└── output/
    └── analysis_results.json      # Results from the last run
```

## Running tests

```bash
# Fast (no GPU, ~2s) — run after every change
python -m pytest tests/ -v -m "not slow"

# Full suite including tracker smoke test (~15s)
python -m pytest tests/ -v
```

See `CLAUDE.md` for development workflows.

---

## Dependencies

| Package | Purpose |
|---|---|
| `opencv-python` | Video decoding and frame processing |
| `mediapipe` | Pose estimation (33 body landmarks per frame) |
| `ultralytics` | YOLOv10 player detection + ByteTrack multi-object tracking |
| `numpy` | Numerical operations |
| `scipy` | Signal processing |
| `matplotlib` | Visualisation |
| `pandas` | Data handling |
| `lap` | Linear assignment for ByteTrack |
