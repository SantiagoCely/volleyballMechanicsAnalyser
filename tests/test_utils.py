import unittest
import numpy as np
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils import calculate_angle, calculate_distance, smooth_trajectory, detect_peaks

class TestUtils(unittest.TestCase):
    def test_calculate_angle(self):
        # 90 degree angle
        p1 = (1, 0)
        p2 = (0, 0)
        p3 = (0, 1)
        self.assertAlmostEqual(calculate_angle(p1, p2, p3), 90.0)

        # 180 degree angle
        p1 = (1, 0)
        p2 = (0, 0)
        p3 = (-1, 0)
        self.assertAlmostEqual(calculate_angle(p1, p2, p3), 180.0)

    def test_calculate_distance(self):
        p1 = (0, 0)
        p2 = (3, 4)
        self.assertEqual(calculate_distance(p1, p2), 5.0)

    def test_smooth_trajectory(self):
        # Test smoothing of a simple constant signal with a window size of 3
        trajectory = np.ones((5, 2))
        smoothed = smooth_trajectory(trajectory, window_size=3)
        self.assertEqual(smoothed.shape, (5, 2))
        # Constant signal should remain constant after smoothing
        np.testing.assert_array_almost_equal(smoothed, trajectory)

    def test_detect_peaks(self):
        # Data with a clear peak at index 2
        data = np.array([0, 0, 10, 0, 0])
        peaks = detect_peaks(data, threshold=0.5, min_distance=1)
        self.assertEqual(len(peaks), 1)
        self.assertEqual(peaks[0], 2)

if __name__ == '__main__':
    unittest.main()
