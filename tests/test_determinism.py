"""In-process determinism checks (mirrors CLAUDE.md JSON `diff` intent without real video)."""

import json
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer
from jump_scoring import compute_jump_score

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEQUENCE_PATH = os.path.join(FIXTURES_DIR, "single_jump_sequence.json")


def _load_frames():
    with open(SEQUENCE_PATH) as f:
        return json.load(f)


def _run_sequence(analyzer, frames):
    for row in frames:
        foot = (
            (tuple(row["foot_court_pos"][0]), tuple(row["foot_court_pos"][1]))
            if row["foot_court_pos"]
            else None
        )
        analyzer.analyze_frame(
            player_id=1,
            knee_angles=tuple(row["knee_angles"]),
            current_hip_y=row["hip_y"],
            court_pos=tuple(row["court_pos"]),
            frame_time=row["frame_time"],
            foot_court_pos=foot,
        )


@pytest.mark.timeout(60)
class TestSaveLogsDeterminism:
    """Two isolated pipelines over the same synthetic sequence produce identical JSON."""

    def test_fixture_sequence_round_trip_twice(self, tmp_path):
        frames = _load_frames()

        def run_once(path):
            a = JumpAnalyzer()
            _run_sequence(a, frames)
            a.save_logs(str(path), video_name="fixture.mp4")
            with open(path) as f:
                return json.load(f)

        p1 = tmp_path / "once.json"
        p2 = tmp_path / "twice.json"
        assert run_once(p1) == run_once(p2)


@pytest.mark.timeout(30)
class TestJumpScoreDeterminism:
    """Pure scoring from fixed metric dicts is stable across repeated calls."""

    def test_compute_jump_score_identical_inputs(self):
        metrics = {
            "air_time_sec": 0.5,
            "jump_height_est_cm": 40.0,
            "jump_height_est_inch": 15.7,
            "takeoff_angle_deg": 45.0,
            "knee_angles": {"left": 150.0, "right": 152.0},
            "knee_symmetry_deg": 2.0,
            "min_landing_knee_angle_deg": 140.0,
            "landing_absorption_duration_sec": 0.2,
            "landing_knee_flexion_rate_degs": 10.0,
            "peak_wrist_height_ratio": 1.1,
            "arm_swing_symmetry_px": 5.0,
        }
        takeoff = {
            "pos": [0.0, 0.0],
            "approach_velocity_cms": 100.0,
            "stance_width_cm": 30.0,
            "crouch_depth_deg": 140.0,
            "crouch_duration_sec": 0.1,
            "trunk_lean_deg": None,
        }
        a = compute_jump_score(metrics, takeoff)
        b = compute_jump_score(metrics, takeoff)
        assert a == b
        assert 0 <= a["score"] <= 100
