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
