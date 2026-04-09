import json
from datetime import datetime

class JumpAnalyzer:
    def __init__(self, stiff_landing_threshold=160):
        self.stiff_landing_threshold = stiff_landing_threshold
        self.jump_count = 0
        self.is_jumping = False
        self.baseline_hip_height = None
        self.history = []
        
        # State tracking for metrics
        self.jump_start_time = None
        self.jump_start_pos = None
        self.peak_hip_y = float('inf') # Min Y is highest in image

    def log_event(self, event_type, details):
        timestamp = datetime.now().isoformat()
        
        # Ensure details are JSON serializable (convert numpy types to native)
        def make_serializable(obj):
            if hasattr(obj, 'tolist'): # numpy array
                return obj.tolist()
            if hasattr(obj, 'item'): # numpy scalar
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

    def analyze_frame(self, player_id, knee_angles, current_hip_y, court_pos=None, frame_time=0):
        """
        player_id: ID of the tracked player
        knee_angles: Tuple of (left_knee_angle, right_knee_angle)
        current_hip_y: Vertical position of the hip
        court_pos: (x, y) coordinates
        frame_time: Elapsed time in seconds
        """
        if self.baseline_hip_height is None:
            self.baseline_hip_height = current_hip_y
            return

        # 1. JUMP START DETECTION
        if not self.is_jumping and current_hip_y < self.baseline_hip_height * 0.93:
            self.is_jumping = True
            self.jump_count += 1
            self.jump_start_time = frame_time
            self.jump_start_pos = court_pos
            self.peak_hip_y = current_hip_y
            
            details = {"player_id": player_id, "jump_num": self.jump_count}
            if court_pos is not None:
                details["takeoff_pos"] = court_pos
            self.log_event("JUMP_START", details)

        # 2. DURING JUMP (TRACK PEAK)
        elif self.is_jumping:
            if current_hip_y < self.peak_hip_y:
                self.peak_hip_y = current_hip_y

            # 3. LANDING DETECTION
            if current_hip_y >= self.baseline_hip_height * 0.97:
                self.is_jumping = False
                l_angle, r_angle = knee_angles
                
                # Performance Calculations
                air_time = frame_time - self.jump_start_time
                
                # Jump Height Estimation (Pixels to CM conversion)
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
                        "knee_angles": {"left": round(l_angle, 1), "right": round(r_angle, 1)}
                    }
                }
                
                if court_pos is not None and self.jump_start_pos is not None:
                    drift_x = court_pos[0] - self.jump_start_pos[0]
                    drift_y = court_pos[1] - self.jump_start_pos[1]
                    details["metrics"]["drift_cm"] = {
                        "forward_back": round(drift_y, 1),
                        "side_to_side": round(drift_x, 1)
                    }
                    details["landing_pos"] = court_pos
                    
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
