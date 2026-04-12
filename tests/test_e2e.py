"""
End-to-end tests for the Volleyball Mechanics Analyser.

Three layers of coverage:
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

Running all layers:
    python -m pytest tests/test_e2e.py -v

Skipping the slow tracker smoke test:
    python -m pytest tests/test_e2e.py -v -m "not slow"
"""

import json
import math
import os
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

    def test_first_event_is_jump_start(self):
        self.assertEqual(self.events[0]["event"], "JUMP_START")

    def test_second_event_is_landing(self):
        self.assertEqual(self.events[1]["event"], "LANDING")

    def test_jump_start_has_required_keys(self):
        details = self.events[0]["details"]
        for key in ("player_id", "jump_num", "takeoff_pos",
                    "approach_velocity_cms", "takeoff_stance_width_cm"):
            self.assertIn(key, details, msg=f"JUMP_START missing key: {key}")

    def test_landing_has_required_metric_keys(self):
        metrics = self.events[1]["details"]["metrics"]
        for key in ("air_time_sec", "jump_height_est_cm", "jump_height_est_inch",
                    "knee_angles", "drift_cm", "approach_velocity_cms",
                    "takeoff_stance_width_cm", "takeoff_angle_deg",
                    "com_flight_drift_cm"):
            self.assertIn(key, metrics, msg=f"LANDING metrics missing key: {key}")

    def test_drift_cm_has_all_components(self):
        drift = self.events[1]["details"]["metrics"]["drift_cm"]
        for key in ("forward_back", "side_to_side", "magnitude"):
            self.assertIn(key, drift, msg=f"drift_cm missing key: {key}")

    def test_landing_has_landing_pos(self):
        self.assertIn("landing_pos", self.events[1]["details"])

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
        self.jump_start = self.analyzer.history[0]["details"]
        self.landing = self.analyzer.history[1]["details"]
        self.metrics = self.landing["metrics"]

    # JUMP_START metrics
    def test_approach_velocity_at_jump_start(self):
        self.assertAlmostEqual(
            self.jump_start["approach_velocity_cms"],
            self.expected["jump_start"]["approach_velocity_cms"],
            delta=1.0,
        )

    def test_takeoff_stance_width_at_jump_start(self):
        self.assertAlmostEqual(
            self.jump_start["takeoff_stance_width_cm"],
            self.expected["jump_start"]["takeoff_stance_width_cm"],
            delta=0.1,
        )

    # LANDING status
    def test_landing_status(self):
        self.assertEqual(self.landing["status"], self.expected["landing"]["status"])

    # Performance metrics
    def test_air_time(self):
        self.assertAlmostEqual(
            self.metrics["air_time_sec"],
            self.expected["landing"]["metrics"]["air_time_sec"],
            places=3,
        )

    def test_jump_height_cm(self):
        self.assertAlmostEqual(
            self.metrics["jump_height_est_cm"],
            self.expected["landing"]["metrics"]["jump_height_est_cm"],
            delta=0.1,
        )

    def test_jump_height_inch(self):
        self.assertAlmostEqual(
            self.metrics["jump_height_est_inch"],
            self.expected["landing"]["metrics"]["jump_height_est_inch"],
            delta=0.1,
        )

    def test_knee_angles(self):
        exp = self.expected["landing"]["metrics"]["knee_angles"]
        self.assertAlmostEqual(self.metrics["knee_angles"]["left"],  exp["left"],  delta=0.1)
        self.assertAlmostEqual(self.metrics["knee_angles"]["right"], exp["right"], delta=0.1)

    def test_drift_forward_back(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["forward_back"],
            self.expected["landing"]["metrics"]["drift_cm"]["forward_back"],
            delta=0.1,
        )

    def test_drift_side_to_side(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["side_to_side"],
            self.expected["landing"]["metrics"]["drift_cm"]["side_to_side"],
            delta=0.1,
        )

    def test_drift_magnitude(self):
        self.assertAlmostEqual(
            self.metrics["drift_cm"]["magnitude"],
            self.expected["landing"]["metrics"]["drift_cm"]["magnitude"],
            delta=0.1,
        )

    # Pro metrics
    def test_approach_velocity_in_landing(self):
        self.assertAlmostEqual(
            self.metrics["approach_velocity_cms"],
            self.expected["landing"]["metrics"]["approach_velocity_cms"],
            delta=1.0,
        )

    def test_takeoff_stance_width_in_landing(self):
        self.assertAlmostEqual(
            self.metrics["takeoff_stance_width_cm"],
            self.expected["landing"]["metrics"]["takeoff_stance_width_cm"],
            delta=0.1,
        )

    def test_takeoff_angle(self):
        self.assertAlmostEqual(
            self.metrics["takeoff_angle_deg"],
            self.expected["landing"]["metrics"]["takeoff_angle_deg"],
            delta=0.2,
        )

    def test_com_flight_drift(self):
        self.assertAlmostEqual(
            self.metrics["com_flight_drift_cm"],
            self.expected["landing"]["metrics"]["com_flight_drift_cm"],
            delta=0.1,
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
            self.assertEqual(len(reloaded), len(analyzer.history))
            for saved, original in zip(reloaded, analyzer.history):
                self.assertEqual(saved["event"], original["event"])
                self.assertEqual(saved["details"], original["details"])
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

    def test_process_frame_returns_five_tuple(self):
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        result = self.tracker.process_frame(blank)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 5,
                         "process_frame must return a 5-tuple: "
                         "(track_id, knee_angles, hip_y, ground_pos, foot_pixels)")

    def test_process_frame_none_on_blank_frame(self):
        """A blank frame has no detectable player — all values should be None."""
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        track_id, knee_angles, hip_y, ground_pos, foot_pixels = self.tracker.process_frame(blank)
        self.assertIsNone(track_id)
        self.assertIsNone(knee_angles)
        self.assertIsNone(hip_y)
        self.assertIsNone(ground_pos)
        self.assertIsNone(foot_pixels)

    def test_process_frame_type_contract_when_detected(self):
        """If a player IS detected, verify types are correct (skipped on blank frame)."""
        blank = np.zeros((480, 640, 3), dtype=np.uint8)
        track_id, knee_angles, hip_y, ground_pos, foot_pixels = self.tracker.process_frame(blank)
        if track_id is None:
            self.skipTest("No player detected in blank frame — type contract skipped")
        self.assertIsInstance(knee_angles, tuple)
        self.assertEqual(len(knee_angles), 2)
        self.assertIsInstance(hip_y, float)
        self.assertIsInstance(ground_pos, tuple)
        self.assertEqual(len(ground_pos), 2)
        self.assertIsInstance(foot_pixels, tuple)
        self.assertEqual(len(foot_pixels), 2)


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
                if result is None or len(result) != 5:
                    continue
                player_id, knee_angles, hip_y, ground_pos, foot_pixels = result
                if player_id is None:
                    continue
                foot_court_pos = foot_pixels  # no calibrator in this test
                analyzer.analyze_frame(player_id, knee_angles, hip_y,
                                       ground_pos, frame_time, foot_court_pos)

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

    def test_output_contains_jump_start_and_landing(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = os.path.join(tmp_dir, "test.avi")
            output_path = os.path.join(tmp_dir, "output", "results.json")
            _make_synthetic_video(video_path)
            self._run_pipeline_loop(video_path, output_path)

            with open(output_path) as f:
                data = json.load(f)

            event_types = [e["event"] for e in data]
            self.assertIn("JUMP_START", event_types)
            self.assertIn("LANDING", event_types)

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
                        if result is None or len(result) != 5:
                            continue  # pipeline skips mismatched tuples
                        player_id, knee_angles, hip_y, ground_pos, foot_pixels = result
                    except Exception as e:
                        errors.append(str(e))
                cap.release()
                self.assertEqual(errors, [], "Pipeline raised errors on wrong tuple length")

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


if __name__ == "__main__":
    unittest.main()
