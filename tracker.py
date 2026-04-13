import cv2
import numpy as np
import mediapipe as mp
import ssl
from ultralytics import YOLO

# Bypass SSL certificate verification for model downloads
ssl._create_default_https_context = ssl._create_unverified_context

import torch

class PlayerTracker:
    def __init__(self, model_path='yolov10n.pt', target_player_id=None):
        # Detect device: use 'mps' for Mac GPU, else 'cpu'
        if torch.backends.mps.is_available():
            self.device = 'mps'
            print("Using Apple Silicon (MPS) Acceleration")
        elif torch.cuda.is_available():
            self.device = 'cuda'
        else:
            self.device = 'cpu'
            
        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.target_player_id = target_player_id
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5
        )

    def calculate_knee_angle(self, hip, knee, ankle):
        """Calculates the angle at the knee in 3D space using MediaPipe World Landmarks."""
        a = np.array([hip.x, hip.y, hip.z])
        b = np.array([knee.x, knee.y, knee.z])
        c = np.array([ankle.x, ankle.y, ankle.z])

        ba = a - b
        bc = c - b

        cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
        angle = np.degrees(np.arccos(np.clip(cosine_angle, -1.0, 1.0)))
        return angle

    def process_frame(self, frame):
        """Processes a frame to track player and calculate knee flexion."""
        # Run YOLOv10 tracking on the selected device
        results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", device=self.device, verbose=False)
        
        if not results or results[0].boxes.id is None:
            return None, None, None, None, None, None

        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.int().cpu().numpy()

        for box, track_id in zip(boxes, ids):
            if self.target_player_id is not None and track_id != self.target_player_id:
                continue

            # Extract bounding box
            x1, y1, x2, y2 = map(int, box)
            roi = frame[max(0, y1):min(frame.shape[0], y2), max(0, x1):min(frame.shape[1], x2)]
            
            if roi.size == 0:
                continue

            # Pose detection on the cropped player ROI
            roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
            pose_results = self.pose.process(roi_rgb)

            if pose_results.pose_landmarks:
                landmarks = pose_results.pose_landmarks.landmark
                world_landmarks = pose_results.pose_world_landmarks.landmark
                
                # Right knee angle
                r_hip_w = world_landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP]
                r_knee_w = world_landmarks[self.mp_pose.PoseLandmark.RIGHT_KNEE]
                r_ankle_w = world_landmarks[self.mp_pose.PoseLandmark.RIGHT_ANKLE]
                
                # Left knee angle
                l_hip_w = world_landmarks[self.mp_pose.PoseLandmark.LEFT_HIP]
                l_knee_w = world_landmarks[self.mp_pose.PoseLandmark.LEFT_KNEE]
                l_ankle_w = world_landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE]
                
                r_angle = self.calculate_knee_angle(r_hip_w, r_knee_w, r_ankle_w)
                l_angle = self.calculate_knee_angle(l_hip_w, l_knee_w, l_ankle_w)
                
                # Calculate Absolute Hip Y relative to the full frame
                # landmarks[].y is 0-1 relative to the ROI. We need to map it back to frame.
                roi_height = y2 - y1
                l_hip_y_abs = y1 + (landmarks[self.mp_pose.PoseLandmark.LEFT_HIP].y * roi_height)
                r_hip_y_abs = y1 + (landmarks[self.mp_pose.PoseLandmark.RIGHT_HIP].y * roi_height)
                avg_hip_y_frame = (l_hip_y_abs + r_hip_y_abs) / 2
                
                # Also get ground position for mapping
                l_ankle = landmarks[self.mp_pose.PoseLandmark.LEFT_ANKLE]
                r_ankle = landmarks[self.mp_pose.PoseLandmark.RIGHT_ANKLE]
                ground_x = x1 + ((l_ankle.x + r_ankle.x) / 2 * (x2 - x1))
                ground_y = y1 + ((l_ankle.y + r_ankle.y) / 2 * roi_height)

                roi_width = x2 - x1
                l_ankle_pixel = (x1 + l_ankle.x * roi_width, y1 + l_ankle.y * roi_height)
                r_ankle_pixel = (x1 + r_ankle.x * roi_width, y1 + r_ankle.y * roi_height)

                # Upper body landmarks (pixel coords mapped to full frame)
                l_shoulder = landmarks[self.mp_pose.PoseLandmark.LEFT_SHOULDER]
                r_shoulder = landmarks[self.mp_pose.PoseLandmark.RIGHT_SHOULDER]
                l_wrist = landmarks[self.mp_pose.PoseLandmark.LEFT_WRIST]
                r_wrist = landmarks[self.mp_pose.PoseLandmark.RIGHT_WRIST]

                upper_body = {
                    "shoulders_px": (
                        (int(x1 + l_shoulder.x * roi_width), int(y1 + l_shoulder.y * roi_height)),
                        (int(x1 + r_shoulder.x * roi_width), int(y1 + r_shoulder.y * roi_height)),
                    ),
                    "wrists_px": (
                        (int(x1 + l_wrist.x * roi_width), int(y1 + l_wrist.y * roi_height)),
                        (int(x1 + r_wrist.x * roi_width), int(y1 + r_wrist.y * roi_height)),
                    ),
                }

                return track_id, (l_angle, r_angle), avg_hip_y_frame, (ground_x, ground_y), (l_ankle_pixel, r_ankle_pixel), upper_body

        return None, None, None, None, None, None

if __name__ == "__main__":
    tracker = PlayerTracker()
    print("Tracker initialized.")
