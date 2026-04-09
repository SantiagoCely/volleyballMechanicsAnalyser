import unittest
import numpy as np
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from camera_calib import CameraCalibrator

class TestCameraCalibrator(unittest.TestCase):
    def test_transform_point(self):
        # Define a square as input and target a corresponding square view
        # court_points = [top-left, top-right, bottom-right, bottom-left]
        court_points = [(0, 0), (100, 0), (100, 100), (0, 100)]
        target_width = 100
        target_height = 100
        
        calibrator = CameraCalibrator(court_points, target_width, target_height)
        
        # Test transform for a middle point
        p_in = (50, 50)
        p_out = calibrator.transform_point(p_in)
        
        # In a perfect square mapping, middle should map to middle
        self.assertAlmostEqual(p_out[0], 50.0)
        self.assertAlmostEqual(p_out[1], 50.0)

        # Test transform for a corner point
        p_in = (0, 100)
        p_out = calibrator.transform_point(p_in)
        self.assertAlmostEqual(p_out[0], 0.0)
        self.assertAlmostEqual(p_out[1], 100.0)

if __name__ == '__main__':
    unittest.main()
