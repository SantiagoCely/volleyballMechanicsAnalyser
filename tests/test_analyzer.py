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
        self.assertEqual(last_event['event'], 'LANDING')
        self.assertEqual(last_event['details']['status'], 'STIFF')

    def test_landing_status_safe(self):
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (175, 178), 300)
        self.analyzer.analyze_frame(1, (140, 145), 400)

        last_event = self.analyzer.history[-1]
        self.assertEqual(last_event['event'], 'LANDING')
        self.assertEqual(last_event['details']['status'], 'SAFE')


class TestApproachVelocity(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_approach_velocity_computed_at_jump_start(self):
        # Baseline, then approach frames, then jump
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        # Jump start
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)

        jump_start = self.analyzer.history[-1]
        self.assertEqual(jump_start['event'], 'JUMP_START')
        self.assertIn('approach_velocity_cms', jump_start['details'])
        # 100 cm in 1.0 s = 100 cm/s (within approach window)
        self.assertAlmostEqual(jump_start['details']['approach_velocity_cms'], 100.0, delta=5.0)

    def test_approach_velocity_in_landing_metrics(self):
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(105, 0), frame_time=1.5)

        landing = self.analyzer.history[-1]
        self.assertEqual(landing['event'], 'LANDING')
        self.assertIn('approach_velocity_cms', landing['details']['metrics'])

    def test_no_approach_velocity_without_history(self):
        # No position history — velocity should be absent from JUMP_START
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (170, 175), 300)

        jump_start = self.analyzer.history[-1]
        self.assertEqual(jump_start['event'], 'JUMP_START')
        self.assertNotIn('approach_velocity_cms', jump_start['details'])


class TestTakeoffStanceWidth(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_stance_width_at_jump_start(self):
        foot_pos = ((0.0, 0.0), (30.0, 0.0))  # 30 cm apart
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, foot_court_pos=foot_pos)

        jump_start = self.analyzer.history[-1]
        self.assertEqual(jump_start['event'], 'JUMP_START')
        self.assertIn('takeoff_stance_width_cm', jump_start['details'])
        self.assertAlmostEqual(jump_start['details']['takeoff_stance_width_cm'], 30.0, delta=0.1)

    def test_stance_width_in_landing_metrics(self):
        foot_pos = ((0.0, 0.0), (40.0, 0.0))
        self.analyzer.analyze_frame(1, (170, 175), 400, frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, frame_time=0.1, foot_court_pos=foot_pos)
        self.analyzer.analyze_frame(1, (140, 145), 400, frame_time=0.6)

        landing = self.analyzer.history[-1]
        self.assertEqual(landing['event'], 'LANDING')
        self.assertIn('takeoff_stance_width_cm', landing['details']['metrics'])
        self.assertAlmostEqual(landing['details']['metrics']['takeoff_stance_width_cm'], 40.0, delta=0.1)


class TestTakeoffAngle(unittest.TestCase):
    def setUp(self):
        self.analyzer = JumpAnalyzer()

    def test_takeoff_angle_present_with_approach_velocity(self):
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(50, 0), frame_time=0.5)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(100, 0), frame_time=1.0)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(105, 0), frame_time=1.5)

        landing = self.analyzer.history[-1]
        self.assertEqual(landing['event'], 'LANDING')
        self.assertIn('takeoff_angle_deg', landing['details']['metrics'])
        angle = landing['details']['metrics']['takeoff_angle_deg']
        # Angle must be between 0° and 90°
        self.assertGreater(angle, 0)
        self.assertLess(angle, 90)

    def test_takeoff_angle_absent_without_approach_velocity(self):
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.analyzer.analyze_frame(1, (170, 175), 300)
        self.analyzer.analyze_frame(1, (140, 140), 400)

        landing = self.analyzer.history[-1]
        self.assertEqual(landing['event'], 'LANDING')
        self.assertNotIn('takeoff_angle_deg', landing['details']['metrics'])

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

    def test_com_drift_in_landing_metrics(self):
        court_positions = [(0, 0), (0, 0), (0, 5), (5, 10), (10, 10)]
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=court_positions[0], frame_time=0.0)
        for i, pos in enumerate(court_positions[1:], 1):
            hip_y = 300 if i == 1 else 400
            knee = (170, 175) if i < len(court_positions) - 1 else (140, 140)
            self.analyzer.analyze_frame(1, knee, hip_y, court_pos=pos, frame_time=i * 0.1)

        landing = self.analyzer.history[-1]
        self.assertEqual(landing['event'], 'LANDING')
        self.assertIn('com_flight_drift_cm', landing['details']['metrics'])

    def test_drift_magnitude_in_landing(self):
        """drift_cm.magnitude equals sqrt of forward_back² + side_to_side²."""
        self.analyzer.analyze_frame(1, (170, 175), 400, court_pos=(0, 0), frame_time=0.0)
        self.analyzer.analyze_frame(1, (170, 175), 300, court_pos=(0, 0), frame_time=0.1)
        self.analyzer.analyze_frame(1, (140, 140), 400, court_pos=(30, 40), frame_time=0.6)

        landing = self.analyzer.history[-1]
        drift = landing['details']['metrics']['drift_cm']
        expected_mag = math.sqrt(drift['forward_back'] ** 2 + drift['side_to_side'] ** 2)
        self.assertAlmostEqual(drift['magnitude'], expected_mag, places=1)


if __name__ == '__main__':
    unittest.main()
