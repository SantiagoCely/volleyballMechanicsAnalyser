"""
Utility functions for the Volleyball Mechanics Analyzer
"""

import numpy as np
import cv2
from typing import Tuple, List, Optional
import math


def calculate_angle(p1: Tuple[float, float], p2: Tuple[float, float], p3: Tuple[float, float]) -> float:
    """Calculate the angle between three points in 2D space.

    Args:
        p1: First point (x, y)
        p2: Second point (vertex) (x, y)
        p3: Third point (x, y)

    Returns:
        Angle in degrees
    """
    # Vectors from p2 to p1 and p2 to p3
    v1 = np.array([p1[0] - p2[0], p1[1] - p2[1]])
    v2 = np.array([p3[0] - p2[0], p3[1] - p2[1]])

    # Cosine of angle
    cos_angle = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2))

    # Clamp to avoid numerical errors
    cos_angle = np.clip(cos_angle, -1, 1)

    # Convert to degrees
    angle = math.degrees(math.acos(cos_angle))
    return angle


def calculate_distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Calculate Euclidean distance between two points.

    Args:
        p1: First point (x, y)
        p2: Second point (x, y)

    Returns:
        Distance between points
    """
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)


def smooth_trajectory(trajectory: np.ndarray, window_size: int = 5) -> np.ndarray:
    """Apply moving average smoothing to a trajectory.

    Args:
        trajectory: Array of positions over time (frames x dimensions)
        window_size: Size of the moving average window

    Returns:
        Smoothed trajectory
    """
    if len(trajectory) < window_size:
        return trajectory

    # Apply convolution for moving average
    smoothed = np.convolve(trajectory.flatten(), np.ones(window_size)/window_size, mode='valid')

    # Reshape back to original dimensions
    smoothed = smoothed.reshape(-1, trajectory.shape[1])

    # Pad to maintain original length
    pad_size = len(trajectory) - len(smoothed)
    if pad_size > 0:
        smoothed = np.pad(smoothed, ((pad_size, 0), (0, 0)), mode='edge')

    return smoothed


def detect_peaks(data: np.ndarray, threshold: float = 0.5, min_distance: int = 10) -> List[int]:
    """Detect peaks in a 1D signal.

    Args:
        data: 1D array of values
        threshold: Minimum peak height (relative to data range)
        min_distance: Minimum distance between peaks

    Returns:
        List of peak indices
    """
    if len(data) == 0:
        return []

    # Calculate threshold
    data_range = np.ptp(data)
    abs_threshold = np.min(data) + threshold * data_range

    peaks = []
    for i in range(1, len(data) - 1):
        if data[i] > data[i-1] and data[i] > data[i+1] and data[i] > abs_threshold:
            # Check minimum distance from previous peak
            if not peaks or i - peaks[-1] >= min_distance:
                peaks.append(i)

    return peaks


def extract_frames(video_path: str, frame_indices: List[int]) -> List[np.ndarray]:
    """Extract specific frames from a video.

    Args:
        video_path: Path to video file
        frame_indices: List of frame indices to extract

    Returns:
        List of extracted frames as numpy arrays
    """
    cap = cv2.VideoCapture(video_path)
    frames = []

    for idx in sorted(set(frame_indices)):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append(frame)

    cap.release()
    return frames


def draw_pose_landmarks(image: np.ndarray, landmarks: List[dict],
                       connections: Optional[List[Tuple[int, int]]] = None) -> np.ndarray:
    """Draw pose landmarks on an image.

    Args:
        image: Input image
        landmarks: List of landmark dictionaries with 'x', 'y' keys
        connections: Optional list of landmark connections to draw

    Returns:
        Image with landmarks drawn
    """
    img = image.copy()

    # Draw landmarks
    for landmark in landmarks:
        if 'x' in landmark and 'y' in landmark:
            x = int(landmark['x'] * img.shape[1])
            y = int(landmark['y'] * img.shape[0])
            cv2.circle(img, (x, y), 5, (0, 255, 0), -1)

    # Draw connections if provided
    if connections:
        for connection in connections:
            if connection[0] < len(landmarks) and connection[1] < len(landmarks):
                l1 = landmarks[connection[0]]
                l2 = landmarks[connection[1]]

                if 'x' in l1 and 'y' in l1 and 'x' in l2 and 'y' in l2:
                    x1 = int(l1['x'] * img.shape[1])
                    y1 = int(l1['y'] * img.shape[0])
                    x2 = int(l2['x'] * img.shape[1])
                    y2 = int(l2['y'] * img.shape[0])

                    cv2.line(img, (x1, y1), (x2, y2), (255, 0, 0), 2)

    return img


def normalize_coordinates(coords: np.ndarray, width: int, height: int) -> np.ndarray:
    """Normalize coordinates to [0, 1] range.

    Args:
        coords: Array of coordinates (x, y)
        width: Image width
        height: Image height

    Returns:
        Normalized coordinates
    """
    normalized = coords.copy().astype(float)
    normalized[:, 0] /= width
    normalized[:, 1] /= height
    return normalized


def denormalize_coordinates(coords: np.ndarray, width: int, height: int) -> np.ndarray:
    """Denormalize coordinates from [0, 1] range to pixel coordinates.

    Args:
        coords: Array of normalized coordinates
        width: Image width
        height: Image height

    Returns:
        Pixel coordinates
    """
    denormalized = coords.copy()
    denormalized[:, 0] *= width
    denormalized[:, 1] *= height
    return denormalized.astype(int)