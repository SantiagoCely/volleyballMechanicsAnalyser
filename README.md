
# Volleyball Mechanics Analyzer

A Python-based tool for analyzing volleyball player mechanics through video analysis and pose estimation.

## Features

- Video analysis of volleyball techniques
- Pose estimation using MediaPipe
- Data visualization and reporting
- Performance metrics calculation
- Joint trajectory analysis
- Range of motion calculations

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd volleyballMechanicsAnalyser
```

2. Install dependencies:
```bash
pip install mediapipe==0.10.14 ultralytics opencv-python numpy matplotlib pandas scipy scikit-learn lap
```

### macOS Troubleshooting

If you encounter `[SSL: CERTIFICATE_VERIFY_FAILED]` when MediaPipe tries to download models, run the following command to install the required certificates:

```bash
/Applications/Python\ 3.10/Install\ Certificates.command
```
*(Replace `3.10` with your actual Python version, e.g., `3.11`, `3.12`)*

Note: The code now includes a built-in bypass for this specific download.

## Testing

To ensure the integrity of the core logic, you can run the test suite:

```bash
./run_tests.sh
```
Or manually using pytest:
```bash
python -m pytest tests/
```

The test suite covers:
- **utils.py**: Geometry calculations and signal processing (smoothing, peak detection).
- **analyzer.py**: Jump detection logic and event logging.
- **camera_calib.py**: Perspective transformation accuracy.

## Quick Start

Run the analyzer with your video file:
```bash
python main.py --video IMG_9478.mov --show
```

## Usage

### Basic Analysis

Analyze a volleyball video:
```bash
python main.py --video path/to/video.mov --show
```

### Full Analysis Options

- `--video`: Path to the video file (required)
- `--show`: Display the video with real-time tracking overlays
- `--no_calibrate`: Skip court calibration (use this if you only care about knee angles)
- `--player_id ID`: Track a specific player ID (found during a previous run)
- `--output PATH`: Path to save the JSON results (default: `output/analysis_results.json`)

## Understanding the Metrics

The analysis results in `analysis_results.json` provide both injury prevention and performance data:

### Injury Prevention (Landing Quality)
- **Status (SAFE vs STIFF)**: 
    - **SAFE**: The player landed with sufficient knee flexion.
    - **STIFF**: The player landed with a knee angle > 160° (straighter legs). Stiff landings increase the risk of ACL and patellar tendon injuries as the joints absorb more impact.
- **Knee Angles**: The specific degrees of flexion for the left and right knees at the moment of ground contact. 180° is a fully straight leg.

### Performance Metrics
- **Jump Height (est_cm / est_inch)**: An estimation of the vertical displacement of the player's hips. 
    - *Note: This is most accurate when the court is calibrated.*
- **Air Time (sec)**: The total time the player spent in the air from takeoff to landing. 
- **Drift (cm)**:
    - **Forward/Back**: Positive values indicate the player landed in front of their takeoff point (common in aggressive approaches).
    - **Side-to-Side**: Indicates if the player is drifting laterally during flight, which can affect landing stability.

## Output Files

The analysis generates several output files in the specified output directory:

- `pose_data.json`: Raw pose estimation data for each frame
- `metrics.json`: Calculated performance metrics
- `joint_ranges.csv`: Joint range of motion data
- `joint_trajectories.png`: Visualization of joint movement over time
- `metrics_summary.png`: Summary bar chart of joint ranges

## Project Structure

```
volleyballMechanicsAnalyser/
├── main.py              # Main entry point
├── analyzer.py          # Core analysis logic
├── utils.py             # Utility functions
├── example.py           # Usage examples
├── requirements.txt     # Python dependencies
├── README.md           # This file
├── .gitignore          # Git ignore rules
├── data/               # Directory for input videos
└── output/             # Directory for analysis results
```

## Dependencies

- **OpenCV**: Computer vision library for video processing
- **NumPy**: Numerical computing
- **Matplotlib**: Data visualization
- **MediaPipe**: Pose estimation and landmark detection
- **Pandas**: Data manipulation and CSV export
- **SciPy**: Scientific computing
- **Scikit-learn**: Machine learning utilities

## Analysis Features

### Pose Estimation
- Real-time pose landmark detection using MediaPipe
- 33 body landmarks tracked per frame
- Confidence scores for landmark visibility

### Performance Metrics
- Joint range of motion calculations
- Velocity analysis of key joints
- Trajectory smoothing and peak detection

### Visualizations
- Joint trajectory plots over time
- Range of motion summary charts
- Customizable output formats

## Development

To extend the analyzer:

1. Add new metrics in `analyzer.py`
2. Implement utility functions in `utils.py`
3. Update visualizations in the `generate_visualizations` method

## License

[Add your license information here]