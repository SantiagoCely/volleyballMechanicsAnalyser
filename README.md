
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
pip install -r requirements.txt
```

## Quick Start

Run the example to see usage instructions:
```bash
python example.py
```

## Usage

### Basic Analysis

Analyze a volleyball video with pose estimation:
```bash
python main.py path/to/video.mp4 --pose
```

### Full Analysis

Run complete analysis with all features:
```bash
python main.py video.mp4 --pose --metrics --visualize --output results
```

### Command Line Options

- `video_path`: Path to the volleyball video file (required)
- `--output`, `-o`: Output directory for results (default: `output`)
- `--pose`: Enable pose estimation analysis
- `--metrics`: Calculate performance metrics
- `--visualize`: Generate visualization plots

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