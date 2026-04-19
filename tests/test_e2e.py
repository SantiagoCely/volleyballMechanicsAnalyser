"""
End-to-end tests for the Volleyball Mechanics Analyser.

Four layers of coverage:
  Layer 1 — Analyzer fixture tests: feed a known frame sequence through
             JumpAnalyzer and assert on event structure + exact metric values.
             Fast (~0.04 s), no GPU needed.

  Layer 2 — Tracker smoke tests: verify PlayerTracker can be imported,
             initialised, and process a blank synthetic frame without crashing.
             Slow (~5–15 s) due to YOLO model load; tagged @pytest.mark.slow.

  Layer 3 — Pipeline integration tests: mock PlayerTracker.process_frame to
             return the fixture sequence, then run main.py's processing loop
             end-to-end and assert the saved JSON is correct.
             Medium speed (~1 s), no GPU needed.

  Layer 4 — Video regression tests: run the FULL pipeline (YOLO + MediaPipe +
             analyser) on real video files and compare the output JSON against
             golden fixture files using per-field tolerances.
             Slow (~15–30 s per video); tagged @pytest.mark.slow.
             Golden files live in tests/fixtures/*_video_golden.json.
             When a metric is added or removed, update the golden files by
             running:
               python main.py --video <video> --player_id 1 --output tests/fixtures/<name>_video_golden.json

Running all layers:
    python -m pytest tests/test_e2e.py -v

Skipping slow, fuzz, and stress tests:
    python -m pytest tests/test_e2e.py -v -m "not slow and not fuzz and not stress"
"""

import json
import math
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import cv2
import numpy as np
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from analyzer import JumpAnalyzer

# ── Fixture paths ─────────────────────────────────────────────────────────────

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")
SEQUENCE_PATH = os.path.join(FIXTURES_DIR, "single_jump_sequence.json")
EXPECTED_PATH = os.path.join(FIXTURES_DIR, "expected_output.json")


# ── Shared helper ─────────────────────────────────────────────────────────────

def _load_fixture():
    with open(SEQUENCE_PATH) as f:
        return json.load(f)


def _load_expected():
    with open(EXPECTED_PATH) as f:
        return json.load(f)


def _run_fixture(frames=None):
    """Feed the fixture frame sequence through a fresh JumpAnalyzer."""
    if frames is None:
        frames = _load_fixture()
    analyzer = JumpAnalyzer()
    for row in frames:
        foot = (tuple(row["foot_court_pos"][0]), tuple(row["foot_court_pos"][1])) \
            if row["foot_court_pos"] else None
        analyzer.analyze_frame(
            player_id=1,
            knee_angles=tuple(row["knee_angles"]),
            current_hip_y=row["hip_y"],
            court_pos=tuple(row["court_pos"]),
            frame_time=row["frame_time"],
            foot_court_pos=foot,
        )
    return analyzer


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1 — Analyzer fixture tests
# ══════════════════════════════════════════════════════════════════════════════

class TestE2EPipelineStructure(unittest.TestCase):
    """Assert the fixture produces the expected event structure."""

    def setUp(self):
        self.analyzer = _run_fixture()
        self.expected = _load_expected()
        self.events = self.analyzer.history

    def test_event_count(self):
        self.assertEqual(len(self.events), self.expected["event_count"])

    def test_only_event_is_jump(self):
        self.assertEqual(self.events[0]["event"], "JUMP")

    def test_jump_has_required_top_level_keys(self):
        jump = self.events[0]
        for key in ("event", "jump_num", "player_id",
                    "start_video_time_sec", "end_video_time_sec",
                    "status", "takeoff", "metrics"):
            self.assertIn(key, jump, msg=f"JUMP missing key: {key}")

    def test_jump_takeoff_has_required_keys(self):
        takeoff = self.events[0]["takeoff"]
        for key in ("pos", "approach_velocity_cms", "stance_width_cm",
                    "crouch_depth_deg", "crouch_duration_sec", "trunk_lean_deg"):
            self.assertIn(key, takeoff, msg=f"takeoff missing key: {key}")

    def test_jump_metrics_has_required_keys(self):
        metrics = self.events[0]["metrics"]
        for key in ("air_time_sec", "jump_height_est_cm", "jump_height_est_inch",
                    "knee_angles", "knee_symmetry_deg", "drift_cm", "takeoff_angle_deg",
                    "com_flight_drift_cm", "score", "score_breakdown"):
            self.assertIn(key, metrics, msg=f"metrics missing key: {key}")

    def test_drift_cm_has_all_components(self):
        drift = self.events[0]["metrics"]["drift_cm"]
        for key in ("forward_back", "side_to_side", "magnitude"):
            self.assertIn(key, drift, msg=f"drift_cm missing key: {key}")

    def test_jump_has_landing_pos(self):
        self.assertIn("landing_pos", self.events[0])

    def test_jump_count(self):
        self.assertEqual(self.analyzer.jump_count, 1)

    def test_not_still_jumping_at_end(self):
        self.assertFalse(self.analyzer.is_jumping)


class TestE2EMetricRegression(unittest.TestCase):
    """Pin exact metric values. Any silent regression in formulas will fail here.
    Update expected_output.json when making intentional metric changes."""

    def setUp(self):
        self.analyzer = _run_fixture()
        self.expected = _load_expected()
        self.jump = self.analyzer.history[0]
        self.takeoff = self.jump["takeoff"]
        self.metrics = self.jump["metrics"]

    def test_approach_velocity_in_takeoff(self):
        self.assertAlmostEqual(
            self.takeoff["approach_velocity_cms"],
            self.expected["jump"]["takeoff"]["approach_velocity_cms"],
            delta=1.0,
        )

    def test_takeoff_stance_width(self):
        self.assertAlmostEqual(
            self.takeoff["stance_width_cm"],
            self.expected["jump"]["takeoff"]["stance_width_cm"],
            delta=0.1,
        )

    def test_status(self):
        self.assertEqual(self.jump["status"], self.expected["jump"]["status"])

    def test_air_time(self):
        self.assertAlmostEqual(
            self.metrics["air_time_sec"],
            self.expected["jump"]["metrics"]["air_time_sec"],
            places=3,
        )

    def test_jump_height_cm(self):
        self.assertAlmostEqual(
            self.metrics["jump_height_est_cm"],
            self.expected["jump"]["metrics"]["jump_height_est_cm"],
            delta=0.1,
        )

    def test_jump_height_inch(self):
        self.assertAlmostEqual(
            self.metrics["jump_height_est_inch"],
            self.expected["jump"]["metrics"]["jump_height_est_inch"],
            delta=0.1,
        )

    def test_knee_angles(self):
        exp = self.expected["jump"]["metrics"]["knee_angles"]
        self.assertAlmostEqual(self.metrics["knee_angles"]["left"],  exp["left"],  delta=0.1)
        self.assertAlmostEqual(self.metrics["knee_angles"]["right"], exp["right"], delta=0.1)

    def test_knee_symmetry(self):
        self.assertAlmostEqual(
            self.metrics["knee_symmetry_deg"],
            self.expected["jump"]["metrics"]["knee_symmetry_deg"],
            delta=0.1,
        )

    def test_drift_forward_back(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["forward_back"],
            self.expected["jump"]["metrics"]["drift_cm"]["forward_back"],
            delta=0.1,
        )

    def test_drift_side_to_side(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["side_to_side"],
            self.expected["jump"]["metrics"]["drift_cm"]["side_to_side"],
            delta=0.1,
        )

    def test_drift_magnitude(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["magnitude"],
            self.expected["jump"]["metrics"]["drift_cm"]["magnitude"],
            delta=0.1,
        )

    def test_takeoff_angle(self):
        self.assertAlmostEqual(
            self.metrics["takeoff_angle_deg"],
            self.expected["jump"]["metrics"]["takeoff_angle_deg"],
            delta=0.2,
        )

    def test_com_flight_drift(self):
        self.assertAlmostEqual(
            self.metrics["com_flight_drift_cm"],
            self.expected["jump"]["metrics"]["com_flight_drift_cm"],
            delta=0.1,
        )

    def test_jump_score(self):
        self.assertEqual(
            self.metrics["score"],
            self.expected["jump"]["metrics"]["score"],
        )

    def test_score_breakdown(self):
        exp = self.expected["jump"]["metrics"]["score_breakdown"]
        for key, val in exp.items():
            self.assertAlmostEqual(
                self.metrics["score_breakdown"][key],
                val,
                delta=0.05,
            )

    def test_video_timestamps(self):
        self.assertAlmostEqual(
            self.jump["start_video_time_sec"],
            self.expected["jump"]["start_video_time_sec"],
            delta=0.01,
        )
        self.assertAlmostEqual(
            self.jump["end_video_time_sec"],
            self.expected["jump"]["end_video_time_sec"],
            delta=0.01,
        )


class TestE2EOutputJSON(unittest.TestCase):
    """Verify the output JSON can be saved, reloaded, and matches history exactly."""

    def test_save_and_reload_round_trip(self):
        analyzer = _run_fixture()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            analyzer.save_logs(tmp_path)
            with open(tmp_path) as f:
                reloaded = json.load(f)
            # Output is SESSION_SUMMARY + history entries
            self.assertEqual(len(reloaded), len(analyzer.history) + 1)
            # First entry must be the session summary
            self.assertEqual(reloaded[0]["event"], "SESSION_SUMMARY")
            # Remaining entries must match history exactly
            for saved, original in zip(reloaded[1:], analyzer.history):
                self.assertEqual(saved["event"], original["event"])
                self.assertEqual(saved["metrics"], original["metrics"])
        finally:
            os.unlink(tmp_path)

    def test_output_is_valid_json_array(self):
        analyzer = _run_fixture()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w") as f:
            tmp_path = f.name
        try:
            analyzer.save_logs(tmp_path)
            with open(tmp_path) as f:
                data = json.load(f)
            self.assertIsInstance(data, list)
        finally:
            os.unlink(tmp_path)

    def test_all_values_are_json_serializable(self):
        """Confirm no numpy types leak into the output."""
        analyzer = _run_fixture()
        try:
            serialized = json.dumps(analyzer.history)
            self.assertIsInstance(serialized, str)
        except (TypeError, ValueError) as e:
            self.fail(f"history contains non-serializable values: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2 — Tracker smoke tests  (marked slow — requires YOLO model download)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.slow
class TestTrackerSmoke(unittest.TestCase):
    """Verify the tracker imports, initialises, and handles a blank frame
    without crashing. Does NOT assert player detection (blank frames have
    no players), only that the interface contract is upheld."""

    @classmethod
    def setUpClass(cls):
        from tracker import PlayerTracker
        cls.tracker = PlayerTracker()

    def test_process_frame_returns_six_tuple(self):
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.tracker.process_frame(blank)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 6,
                         "process_frame must return a 6-tuple: "
                         "(track_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body)")

    def test_process_frame_none_on_blank_frame(self):
        """A blank frame has no detectable player — all values should be None."""
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        track_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = self.tracker.process_frame(blank)
        self.assertIsNone(track_id)
        self.assertIsNone(knee_angles)
        self.assertIsNone(hip_y)
        self.assertIsNone(ground_pos)
        self.assertIsNone(foot_pixels)
        self.assertIsNone(upper_body)

    def test_process_frame_type_contract_when_detected(self):
        """If a player IS detected, verify types are correct (skipped on blank frame)."""
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        track_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = self.tracker.process_frame(blank)
        if track_id is None:
            self.skipTest("No player detected in blank frame — type contract skipped")
        self.assertIsInstance(knee_angles, tuple)
        self.assertEqual(len(knee_angles), 2)
        self.assertIsInstance(hip_y, float)
        self.assertIsInstance(ground_pos, tuple)
        self.assertEqual(len(ground_pos), 2)
        self.assertIsInstance(foot_pixels, tuple)
        self.assertEqual(len(foot_pixels), 2)
        # upper_body is None on blank frame, but verify structure if present
        if upper_body is not None:
            self.assertIsInstance(upper_body, dict)
            self.assertIn("shoulders_px", upper_body)
            self.assertIn("wrists_px", upper_body)


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3 — Pipeline integration tests
# ══════════════════════════════════════════════════════════════════════════════

def _make_synthetic_video(path, n_frames=11, fps=10):
    """Write a minimal synthetic .avi video to disk."""
    fourcc = cv2.VideoWriter_fourcc(*"XVID")
    writer = cv2.VideoWriter(path, fourcc, fps, (640, 480))
    for _ in range(n_frames):
        writer.write(np.zeros((480, 640, 3), dtype=np.uint8))
    writer.release()


def _build_mock_side_effect(frames):
    """Return a side_effect list for mock process_frame from the fixture sequence.
    Frames where tracker would return None (before player is visible) are skipped here —
    we return data for every frame to mirror a real tracking session."""
    side_effects = []
    for row in frames:
        foot = (tuple(row["foot_court_pos"][0]), tuple(row["foot_court_pos"][1])) \
            if row["foot_court_pos"] else None
        side_effects.append((
            1,                            # track_id
            tuple(row["knee_angles"]),    # knee_angles
            float(row["hip_y"]),          # hip_y (absolute pixel)
            tuple(row["court_pos"]),      # ground_pos (used as court_pos when no calibrator)
            foot,                         # foot_pixels (used as foot_court_pos when no calibrator)
            None,                         # upper_body (not used in pipeline integration test)
        ))
    return side_effects


class TestPipelineIntegration(unittest.TestCase):
    """Run the main.py processing loop end-to-end with a mocked tracker.
    Exercises: VideoCapture loop, tracker↔analyzer interface, save_logs."""

    def _run_pipeline_loop(self, video_path, output_path):
        """Replicate the main.py processing loop directly so we can mock the tracker."""
        from tracker import PlayerTracker
        frames = _load_fixture()
        side_effects = _build_mock_side_effect(frames)

        with patch.object(PlayerTracker, "process_frame", side_effect=side_effects):
            tracker = PlayerTracker.__new__(PlayerTracker)  # skip __init__ (no model needed)
            tracker.target_player_id = None
            analyzer = JumpAnalyzer()

            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS) or 10.0

            while cap.isOpened():
                frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                frame_time = frame_idx / fps
                ret, frame = cap.read()
                if not ret:
                    break
                result = tracker.process_frame(frame)
                if result is None or len(result) != 6:
                    continue
                player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = result
                if player_id is None:
                    continue
                foot_court_pos = foot_pixels  # no calibrator in this test
                analyzer.analyze_frame(player_id, knee_angles, hip_y,
                                       ground_pos, frame_time, foot_court_pos, upper_body)

            cap.release()
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            analyzer.save_logs(output_path)
            return analyzer

    def test_output_file_is_created(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)
            self._run_pipeline_loop(video_path, output_path)
            self.assertTrue(os.path.exists(output_path))

    def test_output_contains_jump_and_session_summary(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)
            self._run_pipeline_loop(video_path, output_path)

            with open(output_path) as f:
                data = json.load(f)

            event_types = [e["event"] for e in data]
            self.assertIn("JUMP", event_types)
            self.assertIn("SESSION_SUMMARY", event_types)

    def test_tracker_return_tuple_length_is_consumed_correctly(self):
        """Changing process_frame's return length breaks the pipeline — catch it."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path, n_frames=3)

            from tracker import PlayerTracker
            # Return a 4-tuple (old interface) — pipeline should handle it gracefully
            with patch.object(PlayerTracker, "process_frame",
                               return_value=(None, None, None, None)):
                tracker = PlayerTracker.__new__(PlayerTracker)
                tracker.target_player_id = None
                analyzer = JumpAnalyzer()
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
                errors = []
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    result = tracker.process_frame(frame)
                    try:
                        if result is None or len(result) != 6:
                            continue  # pipeline skips mismatched tuples
                        player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = result
                    except Exception as e:
                        errors.append(str(e))
                cap.release()
                self.assertEqual(errors, [], "Pipeline raised errors on wrong tuple length")

    def test_pipeline_wrong_tuple_length_writes_valid_summary_without_jumps(self):
        """Phase 4 — non-6-tuples skipped end-to-end; JSON still valid, no partial writes."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path, n_frames=11)

            from tracker import PlayerTracker

            with patch.object(
                PlayerTracker, "process_frame", return_value=(None, None, None, None)
            ):
                tracker = PlayerTracker.__new__(PlayerTracker)
                analyzer = JumpAnalyzer()
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    result = tracker.process_frame(frame)
                    if result is None or len(result) != 6:
                        continue
                    pid, knees, hip_y, gpos, feet, ub = result
                    if pid is None:
                        continue
                    analyzer.analyze_frame(pid, knees, hip_y, gpos, frame_time=0.0, foot_court_pos=feet, upper_body=ub)
                cap.release()
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                analyzer.save_logs(output_path, video_name="bad_tuple.avi")

            with open(output_path) as f:
                data = json.load(f)
            self.assertEqual(data[0]["event"], "SESSION_SUMMARY")
            self.assertEqual(data[0]["jump_count"], 0)
            self.assertIsNone(data[0]["avg_jump_score"])
            self.assertEqual([e["event"] for e in data].count("JUMP"), 0)

    def test_pipeline_track_id_none_never_analyzes_zero_jumps(self):
        """§4.9 — track_id None: no analyze_frame path, SESSION_SUMMARY has jump_count 0."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path, n_frames=11)

            from tracker import PlayerTracker

            none_track = (None, None, None, None, None, None)
            with patch.object(
                PlayerTracker, "process_frame", side_effect=[none_track] * 15
            ):
                tracker = PlayerTracker.__new__(PlayerTracker)
                analyzer = JumpAnalyzer()
                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
                while cap.isOpened():
                    ret, frame = cap.read()
                    if not ret:
                        break
                    frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                    frame_time = frame_idx / fps if fps > 0 else 0
                    result = tracker.process_frame(frame)
                    if result is None or len(result) != 6:
                        continue
                    player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = result
                    if player_id is None:
                        continue
                    analyzer.analyze_frame(
                        player_id,
                        knee_angles,
                        hip_y,
                        ground_pos,
                        frame_time,
                        foot_court_pos=foot_pixels,
                        upper_body=upper_body,
                    )
                cap.release()
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                analyzer.save_logs(output_path, video_name="no_id.avi")

                self.assertEqual(analyzer.jump_count, 0)
            with open(output_path) as f:
                data = json.load(f)
            self.assertEqual(data[0]["jump_count"], 0)
            self.assertEqual(len(data), 1)

    def test_pipeline_upper_body_none_throughout_nulls_pose_metrics(self):
        """§4.9 — Layer C with upper_body always None (_build_mock_side_effect); pose metrics null."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)
            self._run_pipeline_loop(video_path, output_path)

            with open(output_path) as f:
                data = json.load(f)
            jump = next(e for e in data if e["event"] == "JUMP")
            self.assertIsNone(jump["metrics"]["peak_wrist_height_ratio"])
            self.assertIsNone(jump["metrics"]["arm_swing_symmetry_px"])

    def test_no_calibrator_does_not_raise(self):
        """Running without a calibrator should not raise any exceptions."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)
            try:
                self._run_pipeline_loop(video_path, output_path)
            except Exception as e:
                self.fail(f"Pipeline raised an exception without calibrator: {e}")

    def test_with_calibrator_populates_position_metrics(self):
        """When a CameraCalibrator is active, position-based metrics
        (drift_cm, approach_velocity_cms, stance_width_cm) must be present
        and non-null in the JUMP output.  Without --calibrate they are absent
        because pixel coords are meaningless as cm distances."""
        from camera_calib import CameraCalibrator
        from tracker import PlayerTracker

        frames = _load_fixture()
        side_effects = _build_mock_side_effect(frames)

        # A passthrough mock calibrator: court_coord == pixel_coord.
        # The actual values don't matter — we only assert presence / non-null.
        mock_calibrator = MagicMock(spec=CameraCalibrator)
        mock_calibrator.transform_point.side_effect = lambda p: (float(p[0]), float(p[1]))

        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)

            with patch.object(PlayerTracker, "process_frame", side_effect=side_effects):
                tracker = PlayerTracker.__new__(PlayerTracker)
                tracker.target_player_id = None
                analyzer = JumpAnalyzer()

                cap = cv2.VideoCapture(video_path)
                fps = cap.get(cv2.CAP_PROP_FPS) or 10.0

                while cap.isOpened():
                    frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
                    frame_time = frame_idx / fps
                    ret, frame = cap.read()
                    if not ret:
                        break
                    result = tracker.process_frame(frame)
                    if result is None or len(result) != 6:
                        continue
                    player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = result
                    if player_id is None:
                        continue

                    # Apply calibrator — mirrors main.py's --calibrate path
                    court_pos = mock_calibrator.transform_point(ground_pos)
                    foot_court_pos = None
                    if foot_pixels is not None:
                        l_foot, r_foot = foot_pixels
                        foot_court_pos = (
                            mock_calibrator.transform_point(l_foot),
                            mock_calibrator.transform_point(r_foot),
                        )
                    analyzer.analyze_frame(player_id, knee_angles, hip_y,
                                           court_pos, frame_time, foot_court_pos, upper_body)

                cap.release()
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                analyzer.save_logs(output_path)

            with open(output_path) as f:
                data = json.load(f)

        jump = next(e for e in data if e["event"] == "JUMP")

        # All three position-based metrics must be present and populated
        self.assertIn("drift_cm", jump["metrics"],
                      "drift_cm must appear in metrics when calibrator is active")
        self.assertIsNotNone(jump["metrics"]["drift_cm"],
                             "drift_cm must be non-null when calibrator is active")

        self.assertIn("approach_velocity_cms", jump["takeoff"],
                      "approach_velocity_cms must appear in takeoff when calibrator is active")
        self.assertIsNotNone(jump["takeoff"]["approach_velocity_cms"],
                             "approach_velocity_cms must be non-null when calibrator is active")

        self.assertIn("stance_width_cm", jump["takeoff"],
                      "stance_width_cm must appear in takeoff when calibrator is active")
        self.assertIsNotNone(jump["takeoff"]["stance_width_cm"],
                             "stance_width_cm must be non-null when calibrator is active")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4 — Video regression tests  (marked slow — runs full YOLO + MediaPipe)
# ══════════════════════════════════════════════════════════════════════════════

# Per-field float tolerances for the golden-file comparison.
# Keyed by the JSON field name (last segment of the dotted path).
# Inference variability (GPU fp ordering, ByteTrack jitter) drives these values:
# they are wide enough to survive across runs, tight enough to catch real bugs.
#
# To add a tolerance for a new metric, add it here.
_VIDEO_FLOAT_TOLERANCES = {
    # ── Composite score (int in JSON; compared via int branch using this delta)
    "score":                           10.0,
    # ── Session score rollups ───────────────────────────────────────────────
    "avg_jump_score":                  3.0,
    "best_jump_score":                 5.0,
    "worst_jump_score":                5.0,
    # ── score_breakdown channel sub-scores (0–100) ───────────────────────────
    "landing_quality":                 12.0,
    "jump_quality":                    8.0,
    "drift_stability":                 12.0,
    "approach_control":                12.0,
    "takeoff_form":                    12.0,
    # ── Time fields ────────────────────────────────────────────────────────
    "air_time_sec":                    0.15,
    "start_video_time_sec":            0.20,
    "end_video_time_sec":              0.20,
    "crouch_duration_sec":             0.20,
    "landing_absorption_duration_sec": 0.15,
    "air_time_variability_sec":        0.05,
    # ── Height / distance fields ───────────────────────────────────────────
    "jump_height_est_cm":              3.0,
    "jump_height_est_inch":            1.5,
    "jump_height_variability_cm":      2.0,
    # ── Angle fields ──────────────────────────────────────────────────────
    "crouch_depth_deg":                15.0,
    "left":                            10.0,   # knee_angles.left
    "right":                           10.0,   # knee_angles.right
    "knee_symmetry_deg":               10.0,
    "min_landing_knee_angle_deg":      15.0,
    "landing_knee_flexion_rate_degs":  60.0,
    "takeoff_angle_deg":               10.0,
    "trunk_lean_deg":                  10.0,
    # ── Pixel / ratio fields ───────────────────────────────────────────────
    "peak_wrist_height_ratio":         0.30,
    "arm_swing_symmetry_px":           25.0,
}
_VIDEO_FLOAT_TOLERANCE_DEFAULT = 5.0


_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _run_pipeline_on_video(video_filename, player_id, output_path):
    """Invoke main.py as a subprocess so the full stack is exercised."""
    video_path = os.path.join(_PROJECT_ROOT, video_filename)
    result = subprocess.run(
        [sys.executable, "main.py",
         "--video", video_path,
         "--player_id", str(player_id),
         "--output", output_path],
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"main.py exited with code {result.returncode}:\n{result.stderr}"
        )


class _VideoRegressionBase:
    """Shared comparison logic for Layer 4 video regression tests.

    Subclasses set GOLDEN_PATH, VIDEO_FILENAME, and PLAYER_ID.
    The golden JSON file is the source of truth for both schema and values.

    When a metric is added:
      1. Re-run main.py on the video to produce updated output.
      2. Copy the output to the golden fixture path.
      3. Add the new field's tolerance to _VIDEO_FLOAT_TOLERANCES above.

    When a metric is removed:
      1. Remove it from the golden fixture file.
      2. Remove its entry from _VIDEO_FLOAT_TOLERANCES.
    """

    GOLDEN_PATH: str = ""
    VIDEO_FILENAME: str = ""
    PLAYER_ID: int = 1

    @classmethod
    def setUpClass(cls):
        with open(cls.GOLDEN_PATH) as f:
            cls._golden = json.load(f)
        with tempfile.TemporaryDirectory() as tmp:
            output_path = os.path.join(tmp, "actual.json")
            _run_pipeline_on_video(cls.VIDEO_FILENAME, cls.PLAYER_ID, output_path)
            with open(output_path) as f:
                cls._actual = json.load(f)

    def _assert_matches_golden(self, actual, golden, path="root"):
        """Recursively compare actual vs golden with per-field float tolerances.

        Fails with a clear message when:
          - A key is present in actual but missing from golden (new metric, update golden)
          - A key is present in golden but missing from actual (metric removed)
          - A float value is outside the allowed tolerance band
          - A non-float value doesn't match exactly
        """
        if isinstance(golden, dict):
            self.assertEqual(
                set(actual.keys()), set(golden.keys()),
                msg=(
                    f"Schema mismatch at '{path}'.\n"
                    f"  Keys in actual but not golden (new metric — update golden): "
                    f"{set(actual.keys()) - set(golden.keys())}\n"
                    f"  Keys in golden but not actual (metric removed): "
                    f"{set(golden.keys()) - set(actual.keys())}"
                ),
            )
            for key in golden:
                if key == "player_id":
                    # ByteTrack IDs are non-deterministic; only verify type.
                    self.assertIsInstance(
                        actual[key], int,
                        msg=f"player_id at '{path}.{key}' must be int, got {type(actual[key])}"
                    )
                    continue
                self._assert_matches_golden(actual[key], golden[key], f"{path}.{key}")

        elif isinstance(golden, list):
            self.assertEqual(
                len(actual), len(golden),
                msg=f"List length mismatch at '{path}': expected {len(golden)}, got {len(actual)}",
            )
            for i, (a, g) in enumerate(zip(actual, golden)):
                self._assert_matches_golden(a, g, f"{path}[{i}]")

        elif golden is None:
            self.assertIsNone(
                actual,
                msg=f"Expected None at '{path}', got {actual!r}",
            )

        elif isinstance(golden, float):
            field = path.rsplit(".", 1)[-1]
            tol = _VIDEO_FLOAT_TOLERANCES.get(field, _VIDEO_FLOAT_TOLERANCE_DEFAULT)
            self.assertAlmostEqual(
                actual, golden, delta=tol,
                msg=f"At '{path}': expected {golden} ± {tol}, got {actual}",
            )

        elif isinstance(golden, int) and path.rsplit(".", 1)[-1] in _VIDEO_FLOAT_TOLERANCES:
            # Integer JSON fields (e.g. score) that tolerate inference-driven drift
            field = path.rsplit(".", 1)[-1]
            tol = _VIDEO_FLOAT_TOLERANCES[field]
            self.assertAlmostEqual(
                float(actual), float(golden), delta=tol,
                msg=f"At '{path}': expected {golden} ± {tol}, got {actual}",
            )

        else:
            # int, str, bool — exact match
            self.assertEqual(
                actual, golden,
                msg=f"At '{path}': expected {golden!r}, got {actual!r}",
            )

    def test_full_output_matches_golden(self):
        self._assert_matches_golden(self._actual, self._golden)


@pytest.mark.slow
class TestVideoRegressionSingleJump(_VideoRegressionBase, unittest.TestCase):
    """Layer 4: full pipeline on single_jump.mov vs golden fixture."""

    GOLDEN_PATH    = os.path.join(FIXTURES_DIR, "single_jump_video_golden.json")
    VIDEO_FILENAME = "single_jump.mov"
    PLAYER_ID      = 1


@pytest.mark.slow
class TestVideoRegressionMultipleJumps(_VideoRegressionBase, unittest.TestCase):
    """Layer 4: full pipeline on multiple_jumps.mov vs golden fixture."""

    GOLDEN_PATH    = os.path.join(FIXTURES_DIR, "multiple_jumps_video_golden.json")
    VIDEO_FILENAME = "multiple_jumps.mov"
    PLAYER_ID      = 1


if __name__ == "__main__":
    unittest.main()
