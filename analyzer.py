import json
import math
import statistics

import numpy as np

# Gravitational acceleration in cm/s²
_GRAVITY_CM_S2 = 981.0

class JumpAnalyzer:
    _CROUCH_THRESHOLD_DEG = 150.0

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

        # Upper body at peak frame
        self.upper_body_at_peak = None  # upper_body dict captured at the frame of peak hip height

        # Approach phase tracking (grounded phase buffers, 1-second sliding window)
        self.approach_knee_angles = []  # list of (frame_time, l_angle, r_angle)
        self.approach_upper_body  = []  # list of (frame_time, upper_body_dict)

        # Post-landing absorption window
        self.post_landing_active  = False
        self.post_landing_start   = None
        self.post_landing_knee    = []   # list of (frame_time, l_angle, r_angle)
        self.post_landing_window  = 0.3  # seconds

        # Takeoff crouch metrics (set at jump start, read at landing)
        self._takeoff_crouch_depth = None
        self._takeoff_crouch_duration = None

        # Session-level accumulators (populated from each JUMP event)
        self.all_jump_heights = []
        self.all_air_times    = []

    @staticmethod
    def _make_serializable(obj):
        if hasattr(obj, 'tolist'):
            return obj.tolist()
        if hasattr(obj, 'item'):
            return obj.item()
        if isinstance(obj, dict):
            return {k: JumpAnalyzer._make_serializable(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [JumpAnalyzer._make_serializable(v) for v in obj]
        return obj

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

    def _compute_takeoff_angle(self, jump_height_cm, approach_velocity_cms):
        """
        Estimate takeoff angle (degrees from horizontal) using:
          - initial vertical velocity: v0 = sqrt(2 * g * h)
          - horizontal velocity: approach_velocity_cms
        """
        if approach_velocity_cms is None or approach_velocity_cms <= 0 or jump_height_cm <= 0:
            return None
        v0_vertical = math.sqrt(2 * _GRAVITY_CM_S2 * jump_height_cm)
        angle = math.degrees(math.atan2(v0_vertical, approach_velocity_cms))
        return angle

    def _compute_knee_symmetry(self, knee_angles):
        """Absolute difference between left and right knee angles at landing (degrees)."""
        return abs(knee_angles[0] - knee_angles[1])

    def _compute_takeoff_crouch(self, jump_start_time):
        """
        From approach_knee_angles in the last 1s before jump:
        - takeoff_crouch_depth_deg: minimum average knee angle (deepest squat)
        - takeoff_crouch_duration_sec: time spent below CROUCH_THRESHOLD degrees
        Returns (crouch_depth, crouch_duration) or (None, None) if no data.
        """
        window = [(t, l, r) for t, l, r in self.approach_knee_angles if t <= jump_start_time]
        if not window:
            return None, None
        avg_angles = [(l + r) / 2 for _, l, r in window]
        crouch_depth = min(avg_angles)
        crouch_frames = [(t, l, r) for t, l, r in window if (l + r) / 2 < JumpAnalyzer._CROUCH_THRESHOLD_DEG]
        if len(crouch_frames) >= 2:
            crouch_duration = crouch_frames[-1][0] - crouch_frames[0][0]
        elif len(crouch_frames) == 1:
            crouch_duration = 0.0
        else:
            crouch_duration = 0.0
        return crouch_depth, crouch_duration

    def _compute_trunk_lean(self, upper_body, hip_y, hip_x):
        """
        Angle of the hip→shoulder line from vertical (degrees).
        0° = perfectly upright, larger = more forward/sideward lean.
        Returns None if upper_body is None.
        """
        if upper_body is None:
            return None
        l_shoulder, r_shoulder = upper_body["shoulders_px"]
        avg_shoulder_x = (l_shoulder[0] + r_shoulder[0]) / 2
        avg_shoulder_y = (l_shoulder[1] + r_shoulder[1]) / 2
        dx = avg_shoulder_x - hip_x
        dy = hip_y - avg_shoulder_y  # positive = shoulder above hip (normal)
        if dy <= 0:
            return None  # degenerate: shoulder below hip in image (bad detection)
        return abs(math.degrees(math.atan2(abs(dx), dy)))

    def _compute_peak_wrist_height_ratio(self, upper_body_at_peak, hip_y_at_peak):
        """
        How high the wrists are relative to the shoulder-to-hip body segment at peak jump.
        ratio > 1.0 means wrists are above the shoulders (full arm extension).
        Returns None if data is unavailable.
        """
        if upper_body_at_peak is None:
            return None
        l_shoulder, r_shoulder = upper_body_at_peak["shoulders_px"]
        l_wrist, r_wrist = upper_body_at_peak["wrists_px"]
        avg_shoulder_y = (l_shoulder[1] + r_shoulder[1]) / 2
        avg_wrist_y    = (l_wrist[1]    + r_wrist[1])    / 2
        segment_len = hip_y_at_peak - avg_shoulder_y  # pixels, positive when shoulder is above hip
        if segment_len <= 0:
            return None
        # How far above the hip are the wrists, normalized by shoulder-to-hip distance
        return (hip_y_at_peak - avg_wrist_y) / segment_len

    def _compute_arm_swing_symmetry(self, upper_body):
        """
        Absolute difference in wrist Y positions at takeoff (pixels).
        0 = perfectly symmetric arm swing. Larger = one arm higher than the other.
        Returns None if upper_body is None.
        """
        if upper_body is None:
            return None
        l_wrist, r_wrist = upper_body["wrists_px"]
        return abs(l_wrist[1] - r_wrist[1])

    def _finalize_landing_absorption(self):
        """
        Called after the post-landing window expires. Computes absorption metrics
        from post_landing_knee buffer and amends the most recent JUMP entry in history.
        """
        if not self.post_landing_knee:
            return
        avg_angles = [(l + r) / 2 for _, l, r in self.post_landing_knee]
        min_angle = min(avg_angles)
        min_idx   = avg_angles.index(min_angle)
        absorption_duration = self.post_landing_knee[min_idx][0] - self.post_landing_start
        initial_angle = avg_angles[0]
        if absorption_duration > 0:
            flexion_rate = (initial_angle - min_angle) / absorption_duration
        else:
            flexion_rate = 0.0

        # Amend the most recent JUMP event
        for entry in reversed(self.history):
            if entry.get("event") == "JUMP":
                entry["metrics"]["min_landing_knee_angle_deg"] = round(min_angle, 1)
                entry["metrics"]["landing_absorption_duration_sec"] = round(absorption_duration, 3)
                entry["metrics"]["landing_knee_flexion_rate_degs"] = round(flexion_rate, 1)
                break

    def analyze_frame(self, player_id, knee_angles, current_hip_y, court_pos=None, frame_time=0, foot_court_pos=None, upper_body=None):
        """
        player_id:      ID of the tracked player
        knee_angles:    Tuple of (left_knee_angle, right_knee_angle)
        current_hip_y:  Vertical pixel position of the hip (lower value = higher in image)
        court_pos:      (x, y) court coordinates
        frame_time:     Elapsed time in seconds
        foot_court_pos: ((left_x, left_y), (right_x, right_y)) ankle court coords
        upper_body:     dict with shoulders_px and wrists_px, or None
        """
        if self.baseline_hip_height is None:
            self.baseline_hip_height = current_hip_y
            return

        # Slowly adapt baseline to camera/position drift while the player is grounded and near standing height.
        # Only update when hip_y is within ±15% of the current baseline (excludes deep crouches and jumps).
        if not self.is_jumping and abs(current_hip_y - self.baseline_hip_height) / self.baseline_hip_height < 0.15:
            self.baseline_hip_height = 0.98 * self.baseline_hip_height + 0.02 * current_hip_y

        # Collect post-landing absorption frames (only while grounded — not during flight of next jump)
        if self.post_landing_active and not self.is_jumping:
            self.post_landing_knee.append((frame_time, knee_angles[0], knee_angles[1]))
            if frame_time - self.post_landing_start >= self.post_landing_window:
                self._finalize_landing_absorption()
                self.post_landing_active = False

        # Buffer position history for approach velocity (only while grounded)
        if court_pos is not None and not self.is_jumping:
            self.pos_history.append((court_pos, frame_time))
            # Keep only the last 2 seconds of history to bound memory
            cutoff = frame_time - 2.0
            self.pos_history = [(p, t) for p, t in self.pos_history if t >= cutoff]

        # Buffer approach knee angles and upper body (grounded phase, 1-second sliding window)
        if not self.is_jumping:
            self.approach_knee_angles.append((frame_time, knee_angles[0], knee_angles[1]))
            self.approach_knee_angles = [(t, l, r) for t, l, r in self.approach_knee_angles if frame_time - t <= 1.0]
            if upper_body is not None:
                self.approach_upper_body.append((frame_time, upper_body))
                self.approach_upper_body = [(t, u) for t, u in self.approach_upper_body if frame_time - t <= 1.0]

        # 1. JUMP START DETECTION
        if not self.is_jumping and current_hip_y < self.baseline_hip_height * 0.93:
            # If jump 1's absorption window hasn't expired, finalize it now before starting jump 2
            if self.post_landing_active:
                self._finalize_landing_absorption()
                self.post_landing_active = False
                self.post_landing_knee = []

            self.is_jumping = True
            self.jump_count += 1
            self.jump_start_time = frame_time
            self.jump_start_pos = court_pos
            self.peak_hip_y = current_hip_y
            self.upper_body_at_peak = upper_body
            self.com_positions_during_jump = [court_pos] if court_pos is not None else []

            self.takeoff_approach_velocity = self._compute_approach_velocity(frame_time)
            self.takeoff_stance_width = self._compute_stance_width(foot_court_pos)

            # Capture crouch metrics now so they are available at landing
            self._takeoff_crouch_depth, self._takeoff_crouch_duration = self._compute_takeoff_crouch(frame_time)

        # 2. DURING JUMP (TRACK PEAK & CoM PATH)
        elif self.is_jumping:
            if current_hip_y < self.peak_hip_y:
                self.peak_hip_y = current_hip_y
                self.upper_body_at_peak = upper_body  # capture upper body at peak
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

                # Build takeoff section
                crouch_depth = self._takeoff_crouch_depth
                crouch_duration = self._takeoff_crouch_duration

                takeoff_section = {
                    "pos": list(self.jump_start_pos) if self.jump_start_pos is not None else None,
                }
                if self.takeoff_approach_velocity is not None:
                    takeoff_section["approach_velocity_cms"] = round(self.takeoff_approach_velocity, 1)
                if self.takeoff_stance_width is not None:
                    takeoff_section["stance_width_cm"] = round(self.takeoff_stance_width, 1)
                if crouch_depth is not None:
                    takeoff_section["crouch_depth_deg"] = round(crouch_depth, 1)
                    takeoff_section["crouch_duration_sec"] = round(crouch_duration, 3)
                takeoff_section["trunk_lean_deg"] = None  # hip_x not in current data flow

                # Compute optional upper-body metrics
                takeoff_angle = self._compute_takeoff_angle(jump_height_cm, self.takeoff_approach_velocity)
                peak_wrist_ratio = self._compute_peak_wrist_height_ratio(self.upper_body_at_peak, self.peak_hip_y)
                arm_sym = None
                if self.approach_upper_body:
                    _, ub = self.approach_upper_body[-1]
                    arm_sym = self._compute_arm_swing_symmetry(ub)

                # Build metrics section (all fields always present, null when unavailable)
                metrics_section = {
                    "air_time_sec": round(air_time, 3),
                    "jump_height_est_cm": round(jump_height_cm, 1),
                    "jump_height_est_inch": round(jump_height_inch, 1),
                    "takeoff_angle_deg": round(takeoff_angle, 1) if takeoff_angle is not None else None,
                    "knee_angles": {"left": round(l_angle, 1), "right": round(r_angle, 1)},
                    "knee_symmetry_deg": round(self._compute_knee_symmetry(knee_angles), 1),
                    "min_landing_knee_angle_deg": None,      # filled by _finalize_landing_absorption
                    "landing_absorption_duration_sec": None, # filled by _finalize_landing_absorption
                    "landing_knee_flexion_rate_degs": None,  # filled by _finalize_landing_absorption
                    "peak_wrist_height_ratio": round(peak_wrist_ratio, 3) if peak_wrist_ratio is not None else None,
                    "arm_swing_symmetry_px": round(arm_sym, 1) if arm_sym is not None else None,
                }

                # Add calibration-dependent metrics only when available
                if court_pos is not None and self.jump_start_pos is not None:
                    drift_x = court_pos[0] - self.jump_start_pos[0]
                    drift_y = court_pos[1] - self.jump_start_pos[1]
                    drift_magnitude = math.sqrt(drift_x ** 2 + drift_y ** 2)
                    metrics_section["drift_cm"] = {
                        "forward_back": round(drift_y, 1),
                        "side_to_side": round(drift_x, 1),
                        "magnitude": round(drift_magnitude, 1),
                    }

                if len(self.com_positions_during_jump) >= 2 and self.jump_start_pos is not None and court_pos is not None:
                    com_drift = self._compute_com_flight_drift(self.jump_start_pos, court_pos, self.com_positions_during_jump)
                    metrics_section["com_flight_drift_cm"] = round(com_drift, 1)

                # Build unified JUMP entry
                jump_entry = {
                    "event": "JUMP",
                    "jump_num": self.jump_count,
                    "player_id": self._make_serializable(player_id),
                    "start_video_time_sec": round(self.jump_start_time, 3),
                    "end_video_time_sec": round(frame_time, 3),
                    "status": "STIFF" if is_stiff else "SAFE",
                    "takeoff": self._make_serializable(takeoff_section),
                    "metrics": self._make_serializable(metrics_section),
                }
                if court_pos is not None:
                    jump_entry["landing_pos"] = list(court_pos)

                self.history.append(jump_entry)
                print(f"[t={round(frame_time, 3)}s] JUMP #{self.jump_count}: {jump_entry['status']}, air_time={round(air_time, 3)}s, height={round(jump_height_cm, 1)}cm")

                # Session accumulators
                self.all_jump_heights.append(jump_height_cm)
                self.all_air_times.append(air_time)

                # Reset upper body at peak for next jump
                self.upper_body_at_peak = None

                # Clear approach buffers so post-landing deep-flex frames don't corrupt next jump's crouch metrics
                self.approach_knee_angles = []
                self.approach_upper_body = []

                # Start post-landing absorption window, seeded with the landing frame itself
                self.post_landing_active = True
                self.post_landing_start  = frame_time
                self.post_landing_knee   = [(frame_time, l_angle, r_angle)]  # seed with landing frame

    def save_logs(self, filename="jump_analysis.json", video_name=None):
        # Compute session summary
        height_consistency = None
        if len(self.all_jump_heights) >= 2:
            height_consistency = round(statistics.stdev(self.all_jump_heights), 1)
        air_time_consistency = None
        if len(self.all_air_times) >= 2:
            air_time_consistency = round(statistics.stdev(self.all_air_times), 3)

        session_summary = {
            "event": "SESSION_SUMMARY",
            "video": video_name,
            "jump_count": self.jump_count,
            "jump_height_variability_cm": height_consistency,
            "air_time_variability_sec": air_time_consistency,
        }
        output = [session_summary] + self.history

        with open(filename, 'w') as f:
            json.dump(output, f, indent=4)
        print(f"Logs saved to {filename}")


if __name__ == "__main__":
    analyzer = JumpAnalyzer()
    analyzer.analyze_frame(1, (170, 175), 400)  # Baseline
    analyzer.analyze_frame(1, (175, 178), 300)  # Jump start
    analyzer.analyze_frame(1, (165, 162), 400)  # Stiff landing
    print(f"Total jumps: {analyzer.jump_count}")
