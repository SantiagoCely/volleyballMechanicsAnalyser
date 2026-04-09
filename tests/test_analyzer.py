import unittest
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from analyzer import JumpAnalyzer

class TestJumpAnalyzer(unittest.TestCase):
    def setUp(self):
        # Initialize JumpAnalyzer with default parameters
        self.analyzer = JumpAnalyzer()

    def test_jump_detection(self):
        # Initial baseline frame (hip height at 400)
        self.analyzer.analyze_frame(1, (170, 175), 400)
        self.assertEqual(self.analyzer.jump_count, 0)
        self.assertFalse(self.analyzer.is_jumping)

        # Frame indicating the start of a jump (hip height decreases to 300)
        self.analyzer.analyze_frame(1, (175, 178), 300)
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertTrue(self.analyzer.is_jumping)

        # Frame indicating the landing (hip height returns to baseline 400)
        self.analyzer.analyze_frame(1, (165, 162), 400)
        self.assertEqual(self.analyzer.jump_count, 1)
        self.assertFalse(self.analyzer.is_jumping)

    def test_landing_status_stiff(self):
        # Baseline
        self.analyzer.analyze_frame(1, (170, 175), 400)
        # Jump
        self.analyzer.analyze_frame(1, (175, 178), 300)
        # Landing with high knee angles (stiff landing threshold is 160)
        self.analyzer.analyze_frame(1, (170, 170), 400)
        
        last_event = self.analyzer.history[-1]
        self.assertEqual(last_event['event'], 'LANDING')
        self.assertEqual(last_event['details']['status'], 'STIFF')

    def test_landing_status_safe(self):
        # Baseline
        self.analyzer.analyze_frame(1, (170, 175), 400)
        # Jump
        self.analyzer.analyze_frame(1, (175, 178), 300)
        # Landing with lower knee angles
        self.analyzer.analyze_frame(1, (140, 145), 400)
        
        last_event = self.analyzer.history[-1]
        self.assertEqual(last_event['event'], 'LANDING')
        self.assertEqual(last_event['details']['status'], 'SAFE')

if __name__ == '__main__':
    unittest.main()
