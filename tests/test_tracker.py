"""Unit tests for PlayerTracker re-ID logic.

These tests cover the three-gate re-acquisition logic added to process_frame()
to handle player occlusion:

  Gate 1 — minimum missing frames  (avoids reacting to 1-frame ByteTrack jitter)
  Gate 2 — bbox height similarity  (rejects people at very different distances)
  Gate 3 — HSV colour correlation  (rejects people wearing different colours)

The tracker is instantiated via __new__ (bypasses __init__, so no YOLO or
MediaPipe model is loaded). model.track is set to a MagicMock on each tracker
instance. Pose detection is mocked to return no landmarks — we only care
whether target_player_id is updated by the re-ID block.

All tests are fast (~0.01 s each, no GPU needed).
"""

import os
import sys
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tracker import PlayerTracker


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_yolo_result(boxes, ids):
    """Build a minimal YOLO tracking-result mock.

    boxes : list of [x1, y1, x2, y2] — one row per detected person
    ids   : list of int track IDs, or None to simulate zero detections
    """
    result = MagicMock()
    if ids is None:
        result.boxes.id = None
    else:
        result.boxes.xyxy.cpu.return_value.numpy.return_value = (
            np.array(boxes, dtype=float)
        )
        result.boxes.id.int.return_value.cpu.return_value.numpy.return_value = (
            np.array(ids, dtype=int)
        )
    return [result]


def _make_tracker(target_id=1, last_center=(300.0, 400.0), last_height=200.0):
    """Create a PlayerTracker with only re-ID state pre-populated.

    Bypasses __init__ so no YOLO or MediaPipe model is loaded.
    Pose always returns no landmarks — the tests only care about
    target_player_id changes caused by the re-ID block.
    """
    t = PlayerTracker.__new__(PlayerTracker)
    t.target_player_id = target_id
    t._last_known_center = last_center
    t._last_known_bbox_height = last_height
    t._target_hue_hist = None   # colour gate disabled when None
    t._frames_missing = 0
    t._reacquire_threshold_px  = 200
    t._reacquire_height_tol    = 0.30
    t._reacquire_colour_thresh = 0.5
    t.device = "cpu"
    t.model = MagicMock()
    # Pose mock: no landmarks → process_frame returns None after the re-ID block
    pose_result = MagicMock()
    pose_result.pose_landmarks = None
    t.pose = MagicMock()
    t.pose.process.return_value = pose_result
    t.mp_pose = MagicMock()
    return t


# A box whose centre (300, 400) and height (200) exactly match the default
# tracker state — all three gates should pass for this candidate.
_GOOD_BOX = [[200.0, 300.0, 400.0, 500.0]]   # x1,y1,x2,y2 → cx=300,cy=400,h=200
_GOOD_ID  = [2]

_BLANK_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestReIDMinimumFrames(unittest.TestCase):
    """Gate 1: re-ID must not trigger until the player has been missing for
    exactly _MIN_MISSING_FRAMES (5) consecutive frames."""

    def test_no_reid_before_threshold(self):
        """target_player_id unchanged after 4 missing frames (below threshold)."""
        tracker = _make_tracker()
        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, _GOOD_ID)

        for _ in range(4):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 1)
        self.assertEqual(tracker._frames_missing, 4)

    def test_reid_fires_at_threshold(self):
        """target_player_id updates to 2 on the 5th consecutive missing frame."""
        tracker = _make_tracker()
        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, _GOOD_ID)

        for _ in range(5):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 2)
        self.assertEqual(tracker._frames_missing, 0,
                         "_frames_missing should reset after successful re-ID")

    def test_frames_missing_resets_when_target_reappears(self):
        """If the target reappears with its original ID, _frames_missing resets."""
        tracker = _make_tracker()
        # First: 3 frames without target
        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, _GOOD_ID)
        for _ in range(3):
            tracker.process_frame(_BLANK_FRAME)
        self.assertEqual(tracker._frames_missing, 3)

        # Then: target reappears with ID=1
        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, [1])
        tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker._frames_missing, 0)
        self.assertEqual(tracker.target_player_id, 1)


class TestReIDBboxHeightGate(unittest.TestCase):
    """Gate 2: reject candidates whose bbox height is outside ±30% of last known."""

    def test_candidate_too_tall_is_rejected(self):
        """A box with height 2× the last known (ratio 2.0 > 1.30) is rejected."""
        tracker = _make_tracker(last_height=200.0)
        tracker.model.track.return_value = _make_yolo_result(
            [[200.0, 200.0, 400.0, 600.0]],  # h=400, ratio=2.0
            [2],
        )

        for _ in range(6):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 1,
                         "Candidate 2× taller than last known must be rejected")

    def test_candidate_too_short_is_rejected(self):
        """A box with height 0.5× the last known (ratio 0.5 < 0.70) is rejected."""
        tracker = _make_tracker(last_height=200.0)
        tracker.model.track.return_value = _make_yolo_result(
            [[250.0, 350.0, 350.0, 450.0]],  # h=100, ratio=0.5
            [2],
        )

        for _ in range(6):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 1,
                         "Candidate 0.5× shorter than last known must be rejected")

    def test_candidate_within_height_tolerance_is_accepted(self):
        """A box with height within ±30% passes the height gate."""
        tracker = _make_tracker(last_height=200.0)
        # height=220 → ratio=1.10, within ±30%
        tracker.model.track.return_value = _make_yolo_result(
            [[190.0, 290.0, 410.0, 510.0]],  # h=220, cx=300,cy=400
            [2],
        )

        for _ in range(5):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 2,
                         "Candidate within height tolerance should be accepted")


class TestReIDDistanceGate(unittest.TestCase):
    """Gate 3: reject candidates whose centre is beyond the distance threshold."""

    def test_candidate_too_far_is_rejected(self):
        """Box centred 320 px away (> 200 px threshold) is rejected."""
        tracker = _make_tracker(last_center=(300.0, 400.0))
        # cx=620, cy=400 → distance = 320 px
        tracker.model.track.return_value = _make_yolo_result(
            [[520.0, 300.0, 720.0, 500.0]],
            [2],
        )

        for _ in range(6):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 1,
                         "Candidate beyond distance threshold must be rejected")

    def test_candidate_just_within_distance_is_accepted(self):
        """Box centred 190 px away (< 200 px threshold) is accepted."""
        tracker = _make_tracker(last_center=(300.0, 400.0), last_height=200.0)
        # cx=490, cy=400 → distance = 190 px
        tracker.model.track.return_value = _make_yolo_result(
            [[390.0, 300.0, 590.0, 500.0]],  # cx=490, h=200
            [2],
        )

        for _ in range(5):
            tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 2,
                         "Candidate within distance threshold should be accepted")


class TestReIDColourGate(unittest.TestCase):
    """Gate 4: reject candidates whose HSV hue histogram is too different from the
    stored target signature (correlation < 0.5)."""

    def _make_hist(self, peak_bin):
        """Return a unit-energy 36-bin hue histogram with all mass in one bin."""
        h = np.zeros((36, 1), dtype=np.float32)
        h[peak_bin] = 1.0
        return h

    def test_low_colour_correlation_rejected(self):
        """Candidate whose hue is in bin 35 (blue) does not match a bin-0 (red)
        reference — correlation is near -1, well below the 0.5 threshold."""
        tracker = _make_tracker()
        tracker._target_hue_hist = self._make_hist(peak_bin=0)   # reference: red

        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, _GOOD_ID)

        # Patch _torso_hue_hist to return a 'blue' histogram for the candidate
        blue_hist = self._make_hist(peak_bin=35)
        with patch.object(PlayerTracker, "_torso_hue_hist", return_value=blue_hist):
            for _ in range(6):
                tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 1,
                         "Candidate with very different colour must be rejected")

    def test_high_colour_correlation_accepted(self):
        """Candidate whose hue closely matches the reference is accepted."""
        tracker = _make_tracker()
        tracker._target_hue_hist = self._make_hist(peak_bin=5)   # reference

        tracker.model.track.return_value = _make_yolo_result(_GOOD_BOX, _GOOD_ID)

        # Candidate has nearly identical histogram (same bin)
        matching_hist = self._make_hist(peak_bin=5)
        with patch.object(PlayerTracker, "_torso_hue_hist", return_value=matching_hist):
            for _ in range(5):
                tracker.process_frame(_BLANK_FRAME)

        self.assertEqual(tracker.target_player_id, 2,
                         "Candidate with matching colour should be accepted")


if __name__ == "__main__":
    unittest.main()
