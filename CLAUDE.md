# Volleyball Mechanics Analyser

## Running the analyser

### Normal mode
Prompts you to click 4 court corners for calibration, then click the player to track:
```bash
python main.py --video <path_to_video>
```

### Debug mode (no UI interaction required)
Uses hardcoded court corners and tracks player ID 1 directly — use this for quick testing and development:
```bash
python main.py --video single_jump.mov --debug --player_id 1
python main.py --video multiple_jumps.mov --debug --player_id 1
```

### Other flags
| Flag | Description |
|---|---|
| `--no_calibrate` | Skip court calibration (drift metrics will be in pixels, not cm) |
| `--player_id <id>` | Track a specific player ID without clicking |
| `--output <path>` | Save results JSON to a custom path (default: `output/analysis_results.json`) |
| `--show` | Display the video with overlays while processing |

## Running tests

### Fast tests (no GPU, ~2s) — run after every change
```bash
python -m pytest tests/ -v -m "not slow"
```

### Full suite including tracker smoke test (requires YOLO model load, ~15s)
```bash
python -m pytest tests/ -v
```

### Single test file
```bash
python -m pytest tests/test_e2e.py -v -m "not slow"
python -m pytest tests/test_analyzer.py -v
```

## Test structure

| File | What it tests |
|---|---|
| `tests/test_analyzer.py` | Unit tests for `JumpAnalyzer` jump detection and landing classification |
| `tests/test_utils.py` | Unit tests for geometry helpers (`calculate_angle`, `calculate_distance`, etc.) |
| `tests/test_camera_calib.py` | Unit tests for perspective transform accuracy |
| `tests/test_e2e.py` | End-to-end tests (see below) |

### End-to-end test layers (`test_e2e.py`)
- **Layer 1 — Analyzer fixture tests**: feed a known 11-frame sequence through `JumpAnalyzer` and pin every metric value. Catches silent regressions in metric formulas.
- **Layer 2 — Tracker smoke tests** (`@pytest.mark.slow`): verify `PlayerTracker` initialises and `process_frame` returns a 5-tuple without crashing.
- **Layer 3 — Pipeline integration tests**: mock the tracker, create a synthetic video, run the full `main.py` processing loop, and assert on the saved JSON.

### Adding tests for new features
1. Add frames to `tests/fixtures/single_jump_sequence.json` if the new metric needs different input data.
2. Add expected values to `tests/fixtures/expected_output.json`.
3. Add a test to `TestE2EMetricRegression` in `tests/test_e2e.py`.

---

## Development guidelines

### Adding a new metric
- Add a regression test to `TestE2EMetricRegression` in `tests/test_e2e.py` and update `tests/fixtures/expected_output.json` with the pre-computed expected value
- Document the new field in `README.md` under the correct table (JUMP_START or LANDING metrics), including units and what the value range means

### Verify consistency after any change
Run the tool at least twice on the same video and confirm the output is stable before calling it done:
```bash
python main.py --video single_jump.mov --debug --player_id 1 --output output/run1.json
python main.py --video single_jump.mov --debug --player_id 1 --output output/run2.json
diff output/run1.json output/run2.json
```

### Debug mode is for code flow, not metric accuracy
The `--debug` flag uses hardcoded court corners that don't match any real video. Coordinate-based metrics (`drift_cm`, `approach_velocity_cms`, `takeoff_pos`, etc.) will have wrong absolute values. Use debug mode to verify the tool runs without crashing and that jump detection triggers — not to validate the numbers. For accurate metrics, run with proper court calibration.

