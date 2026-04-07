import cv2
import argparse
import os
import json
from camera_calib import CameraCalibrator
from tracker import PlayerTracker
from analyzer import JumpAnalyzer

def get_court_corners(video_path):
    """Opens the first frame of the video to allow the user to select 4 court corners."""
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Error: Could not read video.")
        return None

    corners = []
    window_name = "Select 4 Court Corners (TL, TR, BR, BL) - Press 'q' to finish"
    
    def click_event(event, x, y, flags, params):
        if event == cv2.EVENT_LBUTTONDOWN:
            corners.append((x, y))
            cv2.circle(frame, (x, y), 5, (0, 255, 0), -1)
            cv2.imshow(window_name, frame)
            if len(corners) == 4:
                print("4 points selected. Press 'q' to continue.")

    cv2.imshow(window_name, frame)
    cv2.setMouseCallback(window_name, click_event)
    
    while True:
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q') or len(corners) == 4:
            break
            
    cv2.destroyAllWindows()
    return corners if len(corners) == 4 else None

def main():
    parser = argparse.ArgumentParser(description="Volleyball Mechanics Analyzer")
    parser.add_argument("--video", type=str, required=True, help="Path to the video file")
    parser.add_argument("--player_id", type=int, default=None, help="Specific Player ID to track")
    parser.add_argument("--output", type=str, default="output/analysis_results.json", help="Path to save results")
    parser.add_argument("--show", action="store_true", help="Display the video with overlays")
    
    args = parser.parse_args()

    # 1. Calibration
    print("Step 1: Calibration. Please select 4 court corners (TL, TR, BR, BL).")
    corners = get_court_corners(args.video)
    if not corners:
        print("Calibration failed. Exiting.")
        return
    
    calibrator = CameraCalibrator(corners)
    
    # 2. Initialization
    tracker = PlayerTracker(target_player_id=args.player_id)
    analyzer = JumpAnalyzer()
    
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"Step 2: Processing video {args.video}...")
    
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break
            
        # Run tracking and pose estimation
        player_id, knee_angles, hip_y, ground_pos = tracker.process_frame(frame)
        
        if player_id is not None:
            # Map ground position to top-down court coordinates
            court_pos = calibrator.transform_point(ground_pos)
            
            # Run Jump/Landing Analysis
            analyzer.analyze_frame(player_id, knee_angles, hip_y, court_pos)
            
            # Optional Visualization
            if args.show:
                l_angle, r_angle = knee_angles
                cv2.putText(frame, f"ID: {player_id} L: {int(l_angle)} R: {int(r_angle)}", 
                            (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                
                # Draw court position indicator (mockup)
                cv2.circle(frame, (int(ground_pos[0]), int(ground_pos[1])), 5, (255, 0, 0), -1)
                cv2.putText(frame, f"Court: {int(court_pos[0])}, {int(court_pos[1])}", 
                            (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)

        if args.show:
            cv2.imshow("Volleyball Mechanics Analysis", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    cap.release()
    cv2.destroyAllWindows()
    
    # 3. Finalize
    print(f"Analysis complete. Total Jumps: {analyzer.jump_count}")
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    analyzer.save_logs(args.output)

if __name__ == "__main__":
    main()
