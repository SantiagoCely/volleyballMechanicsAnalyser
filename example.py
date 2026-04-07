#!/usr/bin/env python3
"""
Example usage of the Volleyball Mechanics Analyzer

This script demonstrates how to use the analyzer with sample data.
"""

import os
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, os.path.dirname(__file__))

from analyzer import VolleyballAnalyzer


def main():
    """Example analysis workflow."""
    # Initialize analyzer
    analyzer = VolleyballAnalyzer()

    # For demonstration, we'll show the expected workflow
    # In a real scenario, you would provide a video file path

    print("Volleyball Mechanics Analyzer - Example Usage")
    print("=" * 50)
    print()
    print("To analyze a volleyball video, run:")
    print("python main.py path/to/your/video.mp4 --pose --metrics --visualize")
    print()
    print("Options:")
    print("  --pose      : Enable pose estimation")
    print("  --metrics   : Calculate performance metrics")
    print("  --visualize : Generate plots and visualizations")
    print("  --output DIR: Specify output directory (default: output)")
    print()
    print("Example with all features:")
    print("python main.py video.mp4 --pose --metrics --visualize --output results")
    print()
    print("The analysis will:")
    print("- Process each frame for pose landmarks")
    print("- Calculate joint ranges of motion")
    print("- Generate trajectory plots")
    print("- Save results as JSON and CSV files")
    print()
    print("Output files:")
    print("- pose_data.json    : Raw pose estimation data")
    print("- metrics.json      : Calculated performance metrics")
    print("- joint_ranges.csv  : Joint range data for analysis")
    print("- joint_trajectories.png : Visualization of joint movement")
    print("- metrics_summary.png   : Summary of performance metrics")


if __name__ == '__main__':
    main()