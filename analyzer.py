import json
from datetime import datetime

class JumpAnalyzer:
    def __init__(self, stiff_landing_threshold=160, jump_threshold_multiplier=1.1):
        self.stiff_landing_threshold = stiff_landing_threshold
        self.jump_count = 0
        self.is_jumping = False
        self.baseline_hip_height = None
        self.history = []

    def log_event(self, event_type, details):
        timestamp = datetime.now().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "event": event_type,
            "details": details
        }
        self.history.append(log_entry)
        print(f"[{timestamp}] {event_type}: {details}")

    def analyze_frame(self, player_id, knee_angles, current_hip_y, court_pos=None):
        """
        player_id: ID of the tracked player
        knee_angles: Tuple of (left_knee_angle, right_knee_angle)
        current_hip_y: Vertical position of the hip (to detect jumps)
        court_pos: Optional (x, y) coordinates on the top-down map
        """
        if self.baseline_hip_height is None:
            self.baseline_hip_height = current_hip_y
            return

        # Simple jump detection logic based on vertical movement
        # (Lower Y value in image coordinates means higher in the air)
        if not self.is_jumping and current_hip_y < self.baseline_hip_height * 0.93:
            self.is_jumping = True
            self.jump_count += 1
            details = {"player_id": player_id, "jump_num": self.jump_count}
            if court_pos is not None:
                details["court_pos"] = (round(float(court_pos[0])), round(float(court_pos[1])))
            self.log_event("JUMP_START", details)

        elif self.is_jumping and current_hip_y >= self.baseline_hip_height * 0.97:
            self.is_jumping = False
            l_angle, r_angle = knee_angles
            
            is_stiff = l_angle > self.stiff_landing_threshold or r_angle > self.stiff_landing_threshold
            
            status = "STIFF" if is_stiff else "SAFE"
            details = {
                "player_id": player_id,
                "status": status,
                "angles": {"left": round(l_angle, 2), "right": round(r_angle, 2)}
            }
            if court_pos is not None:
                details["court_pos"] = (round(float(court_pos[0])), round(float(court_pos[1])))
                
            self.log_event("LANDING", details)

    def save_logs(self, filename="jump_analysis.json"):
        with open(filename, 'w') as f:
            json.dump(self.history, f, indent=4)
        print(f"Logs saved to {filename}")

if __name__ == "__main__":
    analyzer = JumpAnalyzer()
    # Mock analysis
    analyzer.analyze_frame(1, (170, 175), 400) # Baseline
    analyzer.analyze_frame(1, (175, 178), 300) # Jump start
    analyzer.analyze_frame(1, (165, 162), 400) # Stiff landing
    print(f"Total jumps: {analyzer.jump_count}")
