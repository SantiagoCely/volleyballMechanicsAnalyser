import unittest
import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analyzer import JumpAnalyzer


class TestJumpAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_jump_detection(self):
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.assertEqual(self.analyzer.jump_count, 0)
        self.assertFalse(self.analyzer.is_jumping)

        self.analyzer.analyze_frame(1, (175, 178), 300)
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertTrue(self.analyzer.is_jumping)

        self.analyzer.analyze_frame(1, (165, 162), 400)
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertFalse(self.analyzer.is_jumping)

    def test_landing_status_stiff(self):
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (175, 178), 300)
        self.analyzer.analyze_frame(1, (170, 170), 400)

        last_event = self.analyzer.history[-1]
        self.assertEqual(last_event['event'], 'JUMP')
        self.assertEqual(last_event['status'], 'STIFF')

    def test_landing_status_safe(self):
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (175, 178), 300)
        self.analyzer.analyze_frame(1, (140, 145), 400)

        last_event = self.analyzer.history[-1]
        self.assertEqual(last_event['event'], 'JUMP')
        self.assertEqual(last_event['status'], 'SAFE')


class TestApproachVelocity(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_approach_velocity_captured_at_jump_start(self):
        """After jump starts, approach_velocity_cms should be in the JUMP entry's takeoff dict."""
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        # Jump start — hip drops to 300 (< 400 * 0.93 = 372)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)
        # Confirm jump has started (no JUMP event yet — landing not detected)
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertTrue(self.analyzer.is_jumping)
        # approach velocity captured internally
        self.assertIsNotNone(self.analyzer.takeoff_approach_velocity)
        self.assertAlmostEqual(self.analyzer.takeoff_approach_velocity, 100.0, delta=1.0)

    def test_approach_velocity_in_jump_takeoff(self):
        """approach_velocity_cms is stored in entry['takeoff'] of the JUMP event."""
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(105, 0), frame_time=1.5)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('approach_velocity_cms', jump['takeoff'])

    def test_no_approach_velocity_without_history(self):
        """Without position history, approach_velocity_cms should be absent from takeoff."""
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (170, 175), 300)
        # Jump started but no landing yet — check internal state
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertTrue(self.analyzer.is_jumping)
        self.assertIsNone(self.analyzer.takeoff_approach_velocity)

        # Trigger landing to get JUMP event
        self.analyzer.analyze_frame(1, (140, 140), 400)
        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertNotIn('approach_velocity_cms', jump['takeoff'])


class TestTakeoffStanceWidth(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_stance_width_at_jump_start(self):
        """stance_width_cm should be captured in the JUMP entry's takeoff dict."""
        foot_pos = ((0.0, 0.0), (30.0, 0.0))  # 30 cm apart
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, foot_court_pos=foot_pos)
        # Jump started — confirm state
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertTrue(self.analyzer.is_jumping)
        self.assertIsNotNone(self.analyzer.takeoff_stance_width)
        self.assertAlmostEqual(self.analyzer.takeoff_stance_width, 30.0, delta=0.1)

    def test_stance_width_in_jump_takeoff(self):
        """stance_width_cm is present in entry['takeoff'] of the JUMP event."""
        foot_pos = ((0.0, 0.0), (40.0, 0.0))
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, foot_court_pos=foot_pos)
        self.analyzer.analyze_frame(1, (140, 145), 400, frame_time=0.6)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('stance_width_cm', jump['takeoff'])
        self.assertAlmostEqual(jump['takeoff']['stance_width_cm'], 40.0, delta=0.1)


class TestTakeoffAngle(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_takeoff_angle_present_with_approach_velocity(self):
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(105, 0), frame_time=1.5)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('takeoff_angle_deg', jump['metrics'])
        angle = jump['metrics']['takeoff_angle_deg']
        # Angle must be between 0° and 90° when approach velocity is available
        self.assertIsNotNone(angle)
        self.assertGreater(angle, 0)
        self.assertLess(angle, 90)

    def test_takeoff_angle_null_without_approach_velocity(self):
        """Without approach velocity, takeoff_angle_deg is present in metrics but None."""
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (170, 175), 300)
        self.analyzer.analyze_frame(1, (140, 140), 400)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('takeoff_angle_deg', jump['metrics'])
        self.assertIsNone(jump['metrics']['takeoff_angle_deg'])

    def test_takeoff_angle_absent_when_jump_height_zero_or_negative(self):
        """Angle must be None (not crash) when jump_height_cm <= 0."""
        analyzer = JumpAnalyzer()
        self.assertIsNone(analyzer._compute_takeoff_angle(0.0, 200.0))
        self.assertIsNone(analyzer._compute_takeoff_angle(-5.0, 200.0))

    def test_takeoff_angle_physics(self):
        """Verify angle is computed correctly from known velocity + height."""
        analyzer = JumpAnalyzer()
        # Manually set approach velocity
        analyzer.takeoff_approach_velocity = 200.0  # cm/s
        # jump height 50 cm → v0 = sqrt(2 * 981 * 50) ≈ 313.2 cm/s
        angle = analyzer._compute_takeoff_angle(50.0, 200.0)
        expected = math.degrees(math.atan2(math.sqrt(2 * 981 * 50), 200.0))
        self.assertAlmostEqual(angle, expected, places=3)


class TestCoMFlightDrift(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_com_drift_straight_path(self):
        """Player moves perfectly straight — drift should be near zero."""
        drift = self.analyzer._compute_com_flight_drift(
            (0, 0), (100, 0),
            [(0, 0), (25, 0), (50, 0), (75, 0), (100, 0)]
        )
        self.assertAlmostEqual(drift, 0.0, places=5)

    def test_com_drift_curved_path(self):
        """Player deviates laterally — drift should be positive."""
        # Straight line from (0,0) to (100,0); mid-point swings to (50, 20)
        drift = self.analyzer._compute_com_flight_drift(
            (0, 0), (100, 0),
            [(0, 0), (50, 20), (100, 0)]
        )
        self.assertAlmostEqual(drift, 20.0, places=5)

    def test_com_drift_in_jump_metrics(self):
        court_positions = [(0, 0), (0, 0), (0, 5), (5, 10), (10, 10)]
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=court_positions[0], frame_time=0.0)
        for i, pos in enumerate(court_positions[1:], 1):
            hip_y = 300 if i == 1 else 400
            knee = (170, 175) if i < len(court_positions) - 1 else (140, 140)
            self.analyzer.analyze_frame(1, knee, hip_y, court_pos=pos, frame_time=i * 0.1)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('com_flight_drift_cm', jump['metrics'])

    def test_drift_magnitude_in_jump(self):
        """drift_cm.magnitude equals sqrt of forward_back² + side_to_side²."""
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(0, 0), frame_time=0.1)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(30, 40), frame_time=0.6)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        drift = jump['metrics']['drift_cm']
        expected_mag = math.sqrt(drift['forward_back'] ** 2 + drift['side_to_side'] ** 2)
        self.assertAlmostEqual(drift['magnitude'], expected_mag, places=1)


class TestKneeSymmetry(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_symmetric_angles(self):
        """Identical knee angles → symmetry = 0."""
        result = self.analyzer._compute_knee_symmetry((145, 145))
        self.assertAlmostEqual(result, 0.0, places=5)

    def test_asymmetric_angles(self):
        """Different knee angles → symmetry = absolute difference."""
        result = self.analyzer._compute_knee_symmetry((145, 160))
        self.assertAlmostEqual(result, 15.0, places=5)

    def test_symmetry_in_jump_metrics(self):
        """knee_symmetry_deg is present in JUMP metrics after landing."""
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        self.analyzer.analyze_frame(1, (145, 160), 400, frame_time=0.6)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('knee_symmetry_deg', jump['metrics'])
        self.assertAlmostEqual(jump['metrics']['knee_symmetry_deg'], 15.0, delta=0.1)


class TestTakeoffCrouch(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_crouch_depth_captured(self):
        """Knee angles below threshold should produce a crouch_depth_deg in takeoff."""
        # Baseline
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        # Approach with crouch (avg angle = 140 < 150 threshold)
        self.analyzer.analyze_frame(1, (140, 140), 390, frame_time=0.1)
        # Jump
        self.analyzer.analyze_frame(1, (160, 160), 300, frame_time=0.2)
        # Landing
        self.analyzer.analyze_frame(1, (155, 155), 400, frame_time=0.7)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        self.assertIn('crouch_depth_deg', jump['takeoff'])
        self.assertLessEqual(jump['takeoff']['crouch_depth_deg'], 150.0)

    def test_no_crouch_above_threshold(self):
        """If approach angles stay above threshold, crouch_duration is 0."""
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 390, frame_time=0.1)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.2)
        self.analyzer.analyze_frame(1, (155, 155), 400, frame_time=0.7)

        jump = self.analyzer.history[-1]
        self.assertIn('crouch_depth_deg', jump['takeoff'])
        # Crouch duration should be 0 when never below threshold
        self.assertEqual(jump['takeoff']['crouch_duration_sec'], 0.0)


class TestLandingAbsorption(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def _do_full_jump(self, post_landing_frames):
        """Helper: baseline → jump → landing → post-landing frames."""
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        # Landing at t=0.6
        self.analyzer.analyze_frame(1, (165, 165), 400, frame_time=0.6)
        for angles, t in post_landing_frames:
            self.analyzer.analyze_frame(1, angles, 400, frame_time=t)

    def test_absorption_metrics_present_after_window(self):
        """After 0.3s post-landing window, absorption metrics should be filled."""
        post_frames = [
            ((155, 155), 0.65),
            ((140, 140), 0.70),
            ((130, 130), 0.75),
            ((125, 125), 0.80),
            ((130, 130), 0.85),
            ((140, 140), 0.90),
            ((155, 155), 0.95),  # past the 0.3s window (0.6 + 0.3 = 0.9)
        ]
        self._do_full_jump(post_frames)

        jump = self.analyzer.history[-1]
        self.assertEqual(jump['event'], 'JUMP')
        # min_landing_knee_angle_deg should be around 125
        self.assertIsNotNone(jump['metrics']['min_landing_knee_angle_deg'])
        self.assertAlmostEqual(jump['metrics']['min_landing_knee_angle_deg'], 125.0, delta=2.0)
        self.assertIsNotNone(jump['metrics']['landing_absorption_duration_sec'])
        self.assertGreater(jump['metrics']['landing_absorption_duration_sec'], 0)
        self.assertIsNotNone(jump['metrics']['landing_knee_flexion_rate_degs'])

    def test_absorption_absent_before_window_expires(self):
        """Right at landing, before 0.3s elapses, absorption fields are None."""
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        self.analyzer.analyze_frame(1, (155, 155), 400, frame_time=0.6)
        # No post-landing frames — window hasn't expired

        jump = self.analyzer.history[-1]
        self.assertIsNone(jump['metrics']['min_landing_knee_angle_deg'])
        self.assertIsNone(jump['metrics']['landing_absorption_duration_sec'])


class TestUpperBodyMetrics(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def _make_upper_body(self, l_wrist_y, r_wrist_y, shoulder_y=200, hip_y=300):
        """Create a synthetic upper_body dict with controllable wrist heights."""
        return {
            "shoulders_px": ((320, shoulder_y), (360, shoulder_y)),
            "wrists_px": ((310, l_wrist_y), (370, r_wrist_y)),
        }

    def test_arm_swing_symmetry_computed_when_upper_body_present(self):
        """arm_swing_symmetry_px should be non-null when upper_body is provided."""
        # symmetric arms
        ub = self._make_upper_body(l_wrist_y=150, r_wrist_y=150)
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0, upper_body=ub)
        # jump
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, upper_body=ub)
        # landing
        self.analyzer.analyze_frame(1, (145, 148), 400, frame_time=0.6, upper_body=ub)

        jump = self.analyzer.history[-1]
        self.assertIsNotNone(jump["metrics"]["arm_swing_symmetry_px"])
        self.assertAlmostEqual(jump["metrics"]["arm_swing_symmetry_px"], 0.0, delta=0.1)

    def test_arm_swing_asymmetry_detected(self):
        """Unequal wrist heights should produce non-zero arm_swing_symmetry_px."""
        ub_asymmetric = self._make_upper_body(l_wrist_y=100, r_wrist_y=180)
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0, upper_body=ub_asymmetric)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, upper_body=ub_asymmetric)
        self.analyzer.analyze_frame(1, (145, 148), 400, frame_time=0.6, upper_body=ub_asymmetric)

        jump = self.analyzer.history[-1]
        self.assertIsNotNone(jump["metrics"]["arm_swing_symmetry_px"])
        self.assertAlmostEqual(jump["metrics"]["arm_swing_symmetry_px"], 80.0, delta=0.1)

    def test_peak_wrist_height_ratio_computed_at_peak(self):
        """peak_wrist_height_ratio should be non-null when upper_body is tracked through the jump."""
        ub = self._make_upper_body(l_wrist_y=100, r_wrist_y=100, shoulder_y=200)
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0, upper_body=ub)
        # jump start
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, upper_body=ub)
        # peak
        self.analyzer.analyze_frame(1, (170, 175), 260, frame_time=0.2, upper_body=ub)
        # landing
        self.analyzer.analyze_frame(1, (145, 148), 400, frame_time=0.7, upper_body=ub)

        jump = self.analyzer.history[-1]
        self.assertIsNotNone(jump["metrics"]["peak_wrist_height_ratio"])
        # ratio = (hip_y_peak - avg_wrist_y) / (hip_y_peak - avg_shoulder_y)
        # = (260 - 100) / (260 - 200) = 160 / 60 ≈ 2.67
        self.assertAlmostEqual(jump["metrics"]["peak_wrist_height_ratio"], 2.667, delta=0.1)

    def test_metrics_null_without_upper_body(self):
        """Without upper_body, arm/wrist metrics should be null."""
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        self.analyzer.analyze_frame(1, (145, 148), 400, frame_time=0.6)

        jump = self.analyzer.history[-1]
        self.assertIsNone(jump["metrics"]["arm_swing_symmetry_px"])
        self.assertIsNone(jump["metrics"]["peak_wrist_height_ratio"])


class TestSessionSummary(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_single_jump_consistency_is_null(self):
        """With only one jump, consistency fields should be None (need >= 2 for stdev)."""
        import tempfile, json, os
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        self.analyzer.analyze_frame(1, (140, 145), 400, frame_time=0.6)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            self.analyzer.save_logs(path, video_name="test_video.mov")
            with open(path) as f:
                data = json.load(f)
            summary = data[0]
            self.assertEqual(summary['event'], 'SESSION_SUMMARY')
            self.assertEqual(summary['jump_count'], 1)
            self.assertIsNone(summary['jump_height_variability_cm'])
            self.assertIsNone(summary['air_time_variability_sec'])
            self.assertEqual(summary['video'], 'test_video.mov')
        finally:
            os.unlink(path)

    def test_two_jumps_variability_computed(self):
        """With two jumps of different heights, variability should be stdev > 0."""
        import tempfile, json, os

        # Jump 1: baseline=400, peak=300 → height = (100/400)*100 = 25 cm
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1)
        self.analyzer.analyze_frame(1, (140, 145), 400, frame_time=0.6)

        # Jump 2: same baseline, different peak=250 → height = (150/400)*100 = 37.5 cm
        self.analyzer.analyze_frame(1, (170, 175), 380, frame_time=1.0)
        self.analyzer.analyze_frame(1, (170, 175), 250, frame_time=1.1)
        self.analyzer.analyze_frame(1, (140, 145), 400, frame_time=1.6)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            path = f.name
        try:
            self.analyzer.save_logs(path, video_name="test_video.mov")
            with open(path) as f:
                data = json.load(f)
            summary = data[0]
            self.assertEqual(summary['event'], 'SESSION_SUMMARY')
            self.assertEqual(summary['jump_count'], 2)
            self.assertIsNotNone(summary['jump_height_variability_cm'])
            self.assertGreater(summary['jump_height_variability_cm'], 0)
            self.assertIsNotNone(summary['air_time_variability_sec'])
            self.assertEqual(summary['video'], 'test_video.mov')
        finally:
            os.unlink(path)


if __name__ == '__main__':
    unittest.main()
