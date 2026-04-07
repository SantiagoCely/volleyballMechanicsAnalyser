import cv2
import numpy as np

class CameraCalibrator:
    def __init__(self, court_points, target_width=900, target_height=1800):
        """
        court_points: List of 4 (x, y) tuples representing court corners in image:
                      [top-left, top-right, bottom-right, bottom-left]
        target_width: Width of the top-down view (default 9m scaled x100)
        target_height: Height of the top-down view (default 18m scaled x100)
        """
        self.src_pts = np.float32(court_points)
        self.dst_pts = np.float32([
            [0, 0],
            [target_width, 0],
            [target_width, target_height],
            [0, target_height]
        ])
        self.matrix = cv2.getPerspectiveTransform(self.src_pts, self.dst_pts)

    def transform_point(self, point):
        """Transforms a single (x, y) point to top-down coordinates."""
        px, py = point
        point_transformed = np.array([[[px, py]]], dtype=np.float32)
        transformed = cv2.perspectiveTransform(point_transformed, self.matrix)
        return transformed[0][0]

    def warp_frame(self, frame):
        """Warps the entire frame to top-down view."""
        width = int(self.dst_pts[2][0])
        height = int(self.dst_pts[2][1])
        return cv2.warpPerspective(frame, self.matrix, (width, height))

if __name__ == "__main__":
    # Example usage
    # Replace with actual corner coordinates from your video
    corners = [(100, 100), (400, 100), (450, 500), (50, 500)]
    calibrator = CameraCalibrator(corners)
    print("Calibration matrix initialized.")
