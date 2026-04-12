import json
import math
from datetime import datetime

import numpy as np

# Gravitational acceleration in cm/s²
_GRAVITY_CM_S2 = 981.0

class JumpAnalyzer:
    def __init__(self, stiff_landing_threshold=160, approach_window_sec=0.5):
        self.stiff_landing_threshold = stiff_landing_threshold
        self.approach_window_sec = approach_window_sec
        self.jump_count = 0
        self.is_jumping = False
        self.baseline_hip_height = None
        self.history = []

        # State tracking for metrics
        self.jump_start_time = None
        self.jump_start_pos = None
        self.peak_hip_y = float('inf')  # Min Y is highest in image

        # Position history for approach velocity (court coords + timestamps)
        self.pos_history = []  # list of (court_pos, frame_time)

        # CoM (hip) positions recorded during the jump for CoM drift
        self.com_positions_during_jump = []

        # Approach velocity captured at jump start (cm/s)
        self.takeoff_approach_velocity = None

        # Stance width captured at jump start (cm)
        self.takeoff_stance_width = None

    def log_event(self, event_type, details):
        timestamp = datetime.now().isoformat()

        def make_serializable(obj):
            if hasattr(obj, 'tolist'):
                return obj.tolist()
            if hasattr(obj, 'item'):
                return obj.item()
            if isinstance(obj, dict):
                return {k: make_serializable(v) for k, v in obj.items()}
            if isinstance(obj, (list, tuple)):
                return [make_serializable(v) for v in obj]
            return obj

        serializable_details = make_serializable(details)
        log_entry = {
            "timestamp": timestamp,
            "event": event_type,
            "details": serializable_details
        }
        self.history.append(log_entry)
        print(f"[{timestamp}] {event_type}: {serializable_details}")

    def _compute_approach_velocity(self, current_time):
        """Speed (cm/s) estimated via linear regression over the approach window.

        Linear regression across all positions in the window is much more robust
        than a simple start-to-end displacement: a single noisy frame at either
        end of the window cannot blow up the result.
        """
        if len(self.pos_history) < 2:
            return None
        cutoff = current_time - self.approach_window_sec
        window = [(p, t) for p, t in self.pos_history if t >= cutoff]
        if len(window) < 2:
            window = self.pos_history[-2:]
        if len(window) < 2:
            return None

        times = np.array([t for _, t in window])
        xs = np.array([p[0] for p, _ in window])
        ys = np.array([p[1] for p, _ in window])

        # Ordinary least-squares slope: β = Σ(t - t̄)(x - x̄) / Σ(t - t̄)²
        t_mean = times.mean()
        denom = np.sum((times - t_mean) ** 2)
        if denom < 1e-9:
            return None
        vx = float(np.sum((times - t_mean) * xs) / denom)
        vy = float(np.sum((times - t_mean) * ys) / denom)
        return math.sqrt(vx ** 2 + vy ** 2)

    def _compute_stance_width(self, foot_court_pos):
        """Distance between left and right ankles at takeoff (cm)."""
        if foot_court_pos is None:
            return None
        (lx, ly), (rx, ry) = foot_court_pos
        return math.sqrt((rx - lx) ** 2 + (ry - ly) ** 2)

    def _compute_takeoff_angle(self, jump_height_cm, approach_velocity_cms):
        """
        Estimate takeoff angle (degrees from horizontal) using:
          - initial vertical velocity: v0 = sqrt(2 * g * h)
          - horizontal velocity: approach_velocity_cms
        """
        if approach_velocity_cms is None or approach_velocity_cms <= 0:
            return None
        v0_vertical = math.sqrt(2 * _GRAVITY_CM_S2 * jump_height_cm)
        angle = math.degrees(math.atan2(v0_vertical, approach_velocity_cms))
        return angle

    def analyze_frame(self, player_id, knee_angles, current_hip_y, court_pos=None, frame_time=0, foot_court_pos=None):
        """
        player_id:      ID of the tracked player
        knee_angles:    Tuple of (left_knee_angle, right_knee_angle)
        current_hip_y:  Vertical pixel position of the hip (lower value = higher in image)
        court_pos:      (x, y) court coordinates
        frame_time:     Elapsed time in seconds
        foot_court_pos: ((left_x, left_y), (right_x, right_y)) ankle court coords
        """
        if self.baseline_hip_height is None:
            self.baseline_hip_height = current_hip_y
            return

        # Buffer position history for approach velocity
        if court_pos is not None:
            self.pos_history.append((court_pos, frame_time))
            # Keep only the last 2 seconds of history to bound memory
            cutoff = frame_time - 2.0
            self.pos_history = [(p, t) for p, t in self.pos_history if t >= cutoff]

        # 1. JUMP START DETECTION
        if not self.is_jumping and current_hip_y < self.baseline_hip_height * 0.93:
            self.is_jumping = True
            self.jump_count += 1
            self.jump_start_time = frame_time
            self.jump_start_pos = court_pos
            self.peak_hip_y = current_hip_y
            self.com_positions_during_jump = [court_pos] if court_pos is not None else []

            self.takeoff_approach_velocity = self._compute_approach_velocity(frame_time)
            self.takeoff_stance_width = self._compute_stance_width(foot_court_pos)

            details = {"player_id": player_id, "jump_num": self.jump_count}
            if court_pos is not None:
                details["takeoff_pos"] = court_pos
            if self.takeoff_approach_velocity is not None:
                details["approach_velocity_cms"] = round(self.takeoff_approach_velocity, 1)
            if self.takeoff_stance_width is not None:
                details["takeoff_stance_width_cm"] = round(self.takeoff_stance_width, 1)
            self.log_event("JUMP_START", details)

        # 2. DURING JUMP (TRACK PEAK & CoM PATH)
        elif self.is_jumping:
            if current_hip_y < self.peak_hip_y:
                self.peak_hip_y = current_hip_y
            if court_pos is not None:
                self.com_positions_during_jump.append(court_pos)

            # 3. LANDING DETECTION
            if current_hip_y >= self.baseline_hip_height * 0.97:
                self.is_jumping = False
                l_angle, r_angle = knee_angles

                # Performance Calculations
                air_time = frame_time - self.jump_start_time

                # Jump Height Estimation
                pixel_jump = self.baseline_hip_height - self.peak_hip_y
                jump_height_cm = (pixel_jump / self.baseline_hip_height) * 100
                jump_height_inch = jump_height_cm * 0.393701

                is_stiff = l_angle > self.stiff_landing_threshold or r_angle > self.stiff_landing_threshold

                details = {
                    "player_id": player_id,
                    "status": "STIFF" if is_stiff else "SAFE",
                    "metrics": {
                        "air_time_sec": round(air_time, 3),
                        "jump_height_est_cm": round(jump_height_cm, 1),
                        "jump_height_est_inch": round(jump_height_inch, 1),
                        "knee_angles": {"left": round(l_angle, 1), "right": round(r_angle, 1)},
                    }
                }

                if court_pos is not None and self.jump_start_pos is not None:
                    drift_x = court_pos[0] - self.jump_start_pos[0]
                    drift_y = court_pos[1] - self.jump_start_pos[1]
                    drift_magnitude = math.sqrt(drift_x ** 2 + drift_y ** 2)
                    details["metrics"]["drift_cm"] = {
                        "forward_back": round(drift_y, 1),
                        "side_to_side": round(drift_x, 1),
                        "magnitude": round(drift_magnitude, 1),
                    }
                    details["landing_pos"] = court_pos

                # Pro metrics
                if self.takeoff_approach_velocity is not None:
                    details["metrics"]["approach_velocity_cms"] = round(self.takeoff_approach_velocity, 1)

                if self.takeoff_stance_width is not None:
                    details["metrics"]["takeoff_stance_width_cm"] = round(self.takeoff_stance_width, 1)

                takeoff_angle = self._compute_takeoff_angle(jump_height_cm, self.takeoff_approach_velocity)
                if takeoff_angle is not None:
                    details["metrics"]["takeoff_angle_deg"] = round(takeoff_angle, 1)

                # CoM drift magnitude during flight (max lateral deviation from straight path)
                if len(self.com_positions_during_jump) >= 2 and self.jump_start_pos is not None and court_pos is not None:
                    com_drift_mag = self._compute_com_flight_drift(self.jump_start_pos, court_pos, self.com_positions_during_jump)
                    details["metrics"]["com_flight_drift_cm"] = round(com_drift_mag, 1)

                self.log_event("LANDING", details)

    def _compute_com_flight_drift(self, start_pos, end_pos, com_positions):
        """
        Maximum perpendicular deviation of CoM from the straight line
        between takeoff and landing positions.
        """
        sx, sy = start_pos
        ex, ey = end_pos
        line_len = math.sqrt((ex - sx) ** 2 + (ey - sy) ** 2)
        if line_len == 0:
            # No horizontal movement — just return max distance from start
            return max(math.sqrt((p[0] - sx) ** 2 + (p[1] - sy) ** 2) for p in com_positions)
        max_dev = 0.0
        for px, py in com_positions:
            # Perpendicular distance from point to line segment
            cross = abs((ey - sy) * px - (ex - sx) * py + ex * sy - ey * sx)
            dev = cross / line_len
            if dev > max_dev:
                max_dev = dev
        return max_dev

    def save_logs(self, filename="jump_analysis.json"):
        with open(filename, 'w') as f:
            json.dump(self.history, f, indent=4)
        print(f"Logs saved to {filename}")


if __name__ == "__main__":
    analyzer = JumpAnalyzer()
    analyzer.analyze_frame(1, (170, 175), 400)  # Baseline
    analyzer.analyze_frame(1, (175, 178), 300)  # Jump start
    analyzer.analyze_frame(1, (165, 162), 400)  # Stiff landing
    print(f"Total jumps: {analyzer.jump_count}")
