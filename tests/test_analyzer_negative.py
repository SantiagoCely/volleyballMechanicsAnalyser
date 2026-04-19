"""
Phase 2 — JumpAnalyzer negative & edge-case tests (GitHub #31, Layer B).

Synthetic frame sequences only — no tracker, no video.
Expectations follow README SESSION_SUMMARY, JUMP envelope, metrics, takeoff, absorption.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer


def _make_ub(l_wrist_y: float, r_wrist_y: float, shoulder_y: float = 200.0) -> dict:
    return {
        "shoulders_px": ((320.0, shoulder_y), (360.0, shoulder_y)),
        "wrists_px": ((310.0, l_wrist_y), (370.0, r_wrist_y)),
    }


class TestSessionSummaryNegative(unittest.TestCase):
    """§4.1 SESSION_SUMMARY — video null, tie-breaking."""

    def test_video_is_null_when_save_logs_has_no_video_name(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            a = JumpAnalyzer()
            a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
            a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
            a.analyze_frame(1, (140, 145), 400, frame_time=0.6)
            a.save_logs(path, video_name=None)
            with open(path) as f:
                data = json.load(f)
            self.assertEqual(data[0]["event"], "SESSION_SUMMARY")
            self.assertIsNone(data[0]["video"])
        finally:
            os.unlink(path)

    def test_tied_scores_use_earlier_jump_num_for_best_and_worst(self):
        """README: tie → earlier jump_num wins for both best and worst."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            a = JumpAnalyzer()

            def identical_jump_pair(t0: float):
                a.analyze_frame(1, (170, 175), 400, frame_time=t0 + 0.0)
                a.analyze_frame(1, (170, 175), 300, frame_time=t0 + 0.1)
                a.analyze_frame(1, (140, 145), 400, frame_time=t0 + 0.6)

            identical_jump_pair(0.0)
            identical_jump_pair(2.0)

            a.save_logs(path, video_name="tie.mov")
            with open(path) as f:
                data = json.load(f)
            summary = data[0]
            self.assertEqual(summary["jump_count"], 2)
            self.assertEqual(summary["best_jump_score"], summary["worst_jump_score"])
            self.assertEqual(summary["best_jump_num"], 1)
            self.assertEqual(summary["worst_jump_num"], 1)
        finally:
            os.unlink(path)


class TestJumpStatusBoundaries(unittest.TestCase):
    """§4.2 — SAFE iff both knees ≤ threshold; STIFF if either > threshold."""

    def test_safe_when_both_knees_equal_to_default_threshold(self):
        a = JumpAnalyzer(stiff_landing_threshold=160)
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (160, 160), 400, frame_time=0.6)
        self.assertEqual(a.history[-1]["status"], "SAFE")

    def test_stiff_when_either_knee_above_threshold(self):
        a = JumpAnalyzer(stiff_landing_threshold=160)
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (161, 140), 400, frame_time=0.6)
        self.assertEqual(a.history[-1]["status"], "STIFF")

    def test_custom_stiff_threshold_boundary(self):
        """§4.11 — non-default threshold redefines SAFE/STIFF."""
        a = JumpAnalyzer(stiff_landing_threshold=165)
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (165, 165), 400, frame_time=0.6)
        self.assertEqual(a.history[-1]["status"], "SAFE")

        b = JumpAnalyzer(stiff_landing_threshold=165)
        b.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        b.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        b.analyze_frame(1, (166, 140), 400, frame_time=0.6)
        self.assertEqual(b.history[-1]["status"], "STIFF")


class TestApproachWindowConfig(unittest.TestCase):
    """§4.11 — approach velocity uses OLS over configurable window ending at jump-start."""

    def test_narrow_window_changes_velocity_vs_long_window(self):
        def takeoff_velocity(window_sec: float) -> float:
            a = JumpAnalyzer(approach_window_sec=window_sec)
            a.analyze_frame(1, (170, 175), 400, court_pos=(0.0, 0.0), frame_time=0.0)
            a.analyze_frame(1, (170, 175), 400, court_pos=(200.0, 0.0), frame_time=0.50)
            a.analyze_frame(1, (170, 175), 400, court_pos=(205.0, 0.0), frame_time=0.90)
            a.analyze_frame(1, (170, 175), 300, court_pos=(210.0, 0.0), frame_time=1.0)
            a.analyze_frame(1, (140, 140), 400, court_pos=(215.0, 0.0), frame_time=1.5)
            return a.history[-1]["takeoff"]["approach_velocity_cms"]

        v_long = takeoff_velocity(2.0)
        v_short = takeoff_velocity(0.12)
        self.assertIsNotNone(v_long)
        self.assertIsNotNone(v_short)
        self.assertNotAlmostEqual(v_long, v_short, delta=0.01)


class TestTakeoffNegative(unittest.TestCase):
    """§4.3 — trunk_lean always null; stance omitted without feet."""

    def test_trunk_lean_deg_null_on_completed_jump(self):
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (140, 145), 400, frame_time=0.6)
        self.assertIn("trunk_lean_deg", a.history[-1]["takeoff"])
        self.assertIsNone(a.history[-1]["takeoff"]["trunk_lean_deg"])

    def test_stance_width_omitted_when_foot_court_pos_absent_but_drift_present(self):
        """§4.12 — court_pos without foot_court_pos: stance omitted; drift may exist."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, court_pos=(0.0, 0.0), frame_time=0.0)
        a.analyze_frame(1, (170, 175), 400, court_pos=(50.0, 0.0), frame_time=0.5)
        a.analyze_frame(1, (170, 175), 300, court_pos=(100.0, 0.0), frame_time=1.0)
        a.analyze_frame(1, (140, 140), 400, court_pos=(105.0, 0.0), frame_time=1.5)
        jump = a.history[-1]
        self.assertIn("drift_cm", jump["metrics"])
        self.assertNotIn("stance_width_cm", jump["takeoff"])


class TestMetricsCoreRegression(unittest.TestCase):
    """§4.4 — completed jump: core kinematics numeric; takeoff_angle null rules."""

    def test_core_numeric_fields_present_on_uncalibrated_jump(self):
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (148, 152), 400, frame_time=0.6)
        m = a.history[-1]["metrics"]
        for key in ("left", "right"):
            self.assertIsInstance(m["knee_angles"][key], (int, float))
        for key in ("knee_symmetry_deg", "air_time_sec", "jump_height_est_cm", "jump_height_est_inch"):
            self.assertIsInstance(m[key], (int, float))

    def test_arm_swing_null_when_no_upper_body_in_approach_buffer(self):
        """§4.4 — empty approach upper-body buffer → arm_swing_symmetry_px null."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (145, 148), 400, frame_time=0.6)
        self.assertIsNone(a.history[-1]["metrics"]["arm_swing_symmetry_px"])


class TestCalibrationPartialNegative(unittest.TestCase):
    """§4.5 / §4.12 — com_flight_drift_cm omitted with insufficient in-flight samples."""

    def test_com_flight_drift_omitted_when_only_one_court_pos_during_jump(self):
        """Takeoff without court_pos; landing with court_pos → one CoM sample in flight phase."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (140, 140), 400, court_pos=(10.0, 0.0), frame_time=0.6)
        m = a.history[-1]["metrics"]
        self.assertNotIn("drift_cm", m)
        self.assertNotIn("com_flight_drift_cm", m)


class TestUpperBodyPeakSplit(unittest.TestCase):
    """§4.13 — upper_body in approach but None at peak: symmetry numeric, peak ratio null."""

    def test_peak_wrist_null_when_upper_body_absent_at_peak_only(self):
        ub = _make_ub(150.0, 150.0)
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0, upper_body=ub)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1, upper_body=ub)
        a.analyze_frame(1, (170, 175), 260, frame_time=0.2, upper_body=None)
        a.analyze_frame(1, (145, 148), 400, frame_time=0.7, upper_body=ub)
        jump = a.history[-1]
        self.assertIsNotNone(jump["metrics"]["arm_swing_symmetry_px"])
        self.assertIsNone(jump["metrics"]["peak_wrist_height_ratio"])


class TestLandingAbsorptionNegative(unittest.TestCase):
    """§4.6 / §4.14 — absorption contract under window and early finalize."""

    def test_absorption_finalized_when_next_jump_starts_before_window(self):
        """§4.14 — next takeoff finalizes absorption so metrics become non-null."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (165, 165), 400, frame_time=0.60)
        a.analyze_frame(1, (170, 175), 400, frame_time=0.68)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.75)
        a.analyze_frame(1, (140, 145), 400, frame_time=1.30)

        first = a.history[0]
        self.assertEqual(first["event"], "JUMP")
        self.assertIsNotNone(first["metrics"]["min_landing_knee_angle_deg"])
        self.assertIsNotNone(first["metrics"]["landing_absorption_duration_sec"])

    def test_absorption_duration_and_rate_zero_when_min_at_contact(self):
        """§4.6 — deepest flex at landing instant → duration 0, flexion rate 0."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (130, 130), 400, frame_time=0.60)
        a.analyze_frame(1, (170, 175), 400, frame_time=0.62)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.63)
        a.analyze_frame(1, (140, 145), 400, frame_time=1.20)

        first = a.history[0]
        self.assertAlmostEqual(first["metrics"]["landing_absorption_duration_sec"], 0.0, places=3)
        self.assertAlmostEqual(first["metrics"]["landing_knee_flexion_rate_degs"], 0.0, places=3)


class TestSessionSummaryPhase3(unittest.TestCase):
    """Phase 3 — SESSION_SUMMARY / §4.15 unscored jumps skipped in rollups."""

    def test_save_logs_skips_jumps_without_metrics_score(self):
        """README: rows lacking metrics.score do not affect avg/best/worst."""
        a = JumpAnalyzer()
        a.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        a.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        a.analyze_frame(1, (140, 145), 400, frame_time=0.6)
        scored = float(a.history[-1]["metrics"]["score"])

        a.history.append(
            {
                "event": "JUMP",
                "jump_num": 999,
                "metrics": {},
            }
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
        try:
            a.save_logs(path, video_name="phase3.mov")
            with open(path) as fp:
                data = json.load(fp)
            summary = data[0]
            self.assertEqual(summary["avg_jump_score"], scored)
            self.assertEqual(summary["best_jump_score"], scored)
            self.assertEqual(summary["worst_jump_score"], scored)
            self.assertEqual(summary["best_jump_num"], 1)
            self.assertEqual(summary["worst_jump_num"], 1)
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
