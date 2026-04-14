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

        # Last known bounding-box center and height of the target player (for re-ID after occlusion)
        self._last_known_center = None
        self._last_known_bbox_height = None
        # Hue histogram of the target player's torso — colour signature for re-ID
        self._target_hue_hist = None
        # How many consecutive frames the target has been missing
        self._frames_missing = 0
        # Re-ID thresholds
        self._reacquire_threshold_px  = 200   # max centre-to-centre distance (px)
        self._reacquire_height_tol    = 0.30  # bbox height must be within ±30% of last known
        self._reacquire_colour_thresh = 0.5   # minimum hue-histogram correlation (0–1)
        
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

    @staticmethod
    def _torso_hue_hist(frame, box):
        """Return a normalised H-channel histogram for the torso region of a bounding box.

        We slice the vertical middle 25–65% of the box to capture the jersey while
        avoiding the head (top) and legs (bottom), which are noisier for colour ID.
        36 bins gives 10° resolution in hue — enough to separate distinct jersey colours
        without overfitting to exact lighting conditions.
        Returns None if the crop is empty.
        """
        x1, y1, x2, y2 = map(int, box[:4])
        h = y2 - y1
        torso_y1 = y1 + int(h * 0.25)
        torso_y2 = y1 + int(h * 0.65)
        crop = frame[max(0, torso_y1):min(frame.shape[0], torso_y2),
                     max(0, x1):min(frame.shape[1], x2)]
        if crop.size == 0:
            return None
        hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0], None, [36], [0, 180])  # hue channel only
        cv2.normalize(hist, hist)
        return hist

    def process_frame(self, frame):
        """Processes a frame to track player and calculate knee flexion."""
        # Run YOLOv10 tracking on the selected device
        results = self.model.track(frame, persist=True, tracker="bytetrack.yaml", device=self.device, verbose=False)
        
        if not results or results[0].boxes.id is None:
            return None, None, None, None, None, None

        boxes = results[0].boxes.xyxy.cpu().numpy()
        ids = results[0].boxes.id.int().cpu().numpy()

        # --- Re-ID logic: if target was lost for enough frames, find nearest re-appearing track ---
        # We only attempt re-ID after _MIN_MISSING_FRAMES consecutive absences to avoid reacting to
        # normal 1-frame ByteTrack jitter. Real occlusion events last many more frames.
        _MIN_MISSING_FRAMES = 5
        if self.target_player_id is not None:
            target_found = any(tid == self.target_player_id for tid in ids)
            if not target_found:
                self._frames_missing += 1
                if self._frames_missing >= _MIN_MISSING_FRAMES and self._last_known_center is not None:
                    # Find the best candidate: must pass bbox-height, distance, and colour gates
                    best_dist = float('inf')
                    best_id = None
                    for box, tid in zip(boxes, ids):
                        # Gate 1: bbox height similarity (rejects people at very different scales)
                        h = box[3] - box[1]
                        if self._last_known_bbox_height is not None:
                            height_ratio = h / self._last_known_bbox_height
                            if not (1 - self._reacquire_height_tol <= height_ratio <= 1 + self._reacquire_height_tol):
                                continue
                        # Gate 2: colour similarity (rejects people with different jersey colours)
                        if self._target_hue_hist is not None:
                            candidate_hist = self._torso_hue_hist(frame, box)
                            if candidate_hist is not None:
                                corr = cv2.compareHist(self._target_hue_hist, candidate_hist, cv2.HISTCMP_CORREL)
                                if corr < self._reacquire_colour_thresh:
                                    continue
                        # Gate 3: proximity
                        cx = (box[0] + box[2]) / 2
                        cy = (box[1] + box[3]) / 2
                        dist = ((cx - self._last_known_center[0]) ** 2 + (cy - self._last_known_center[1]) ** 2) ** 0.5
                        if dist < best_dist:
                            best_dist = dist
                            best_id = tid
                    if best_id is not None and best_dist <= self._reacquire_threshold_px:
                        print(f"[Tracker] Re-acquired target: old ID={self.target_player_id} → new ID={int(best_id)} (dist={best_dist:.0f}px, missing={self._frames_missing}f)")
                        self.target_player_id = int(best_id)
                        self._frames_missing = 0
            else:
                self._frames_missing = 0

        for box, track_id in zip(boxes, ids):
            if self.target_player_id is not None and track_id != self.target_player_id:
                continue

            # Update last known center and bbox height for re-ID continuity
            cx = (box[0] + box[2]) / 2
            cy = (box[1] + box[3]) / 2
            self._last_known_center = (cx, cy)
            self._last_known_bbox_height = box[3] - box[1]

            # Capture colour signature on the first confirmed detection of the target
            if self._target_hue_hist is None:
                self._target_hue_hist = self._torso_hue_hist(frame, box)

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
                        (x1 + l_shoulder.x * roi_width, y1 + l_shoulder.y * roi_height),
                        (x1 + r_shoulder.x * roi_width, y1 + r_shoulder.y * roi_height),
                    ),
                    "wrists_px": (
                        (x1 + l_wrist.x * roi_width, y1 + l_wrist.y * roi_height),
                        (x1 + r_wrist.x * roi_width, y1 + r_wrist.y * roi_height),
                    ),
                }

                return track_id, (l_angle, r_angle), avg_hip_y_frame, (ground_x, ground_y), (l_ankle_pixel, r_ankle_pixel), upper_body

        return None, None, None, None, None, None

if __name__ == "__main__":
    tracker = PlayerTracker()
    print("Tracker initialized.")
