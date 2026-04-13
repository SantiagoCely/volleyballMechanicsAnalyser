import cv2
import argparse
import os
from camera_calib import CameraCalibrator
from tracker import PlayerTracker
from analyzer import JumpAnalyzer

def get_court_corners_logic(frame):
    corners = []
    window_name = "Calibration: Click 4 corners. 'u': Undo, 'r': Reset, 'Enter': Finish, 'q': Quit."
    cv2.imshow(window_name, frame)
    
    def click_logic(event, x, y, flags, c):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(c) < 4:
                c.append((x, y))
                print(f"Point {len(c)} set at ({x}, {y})")

    cv2.setMouseCallback(window_name, lambda e, x, y, f, p: click_logic(e, x, y, f, corners))

    while True:
        temp_frame = frame.copy()
        
        # Draw lines between points
        for i in range(len(corners)):
            cv2.circle(temp_frame, corners[i], 7, (0, 255, 0), -1)
            cv2.putText(temp_frame, str(i+1), (corners[i][0]+10, corners[i][1]-10), 
                        cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 255, 0), 3)
            if i > 0:
                cv2.line(temp_frame, corners[i-1], corners[i], (0, 255, 0), 2)
        
        if len(corners) == 4:
            cv2.line(temp_frame, corners[3], corners[0], (0, 255, 0), 2)
            cv2.putText(temp_frame, "Area Defined! Press 'Enter' to confirm or 'u' to adjust.", (50, 50), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

        cv2.imshow(window_name, temp_frame)
        key = cv2.waitKey(20) & 0xFF
        
        if key == ord('q'): return None
        if key == ord('u') and len(corners) > 0:
            corners.pop()
            print("Last point removed.")
        if key == ord('r'):
            corners.clear()
            print("Reset all points.")
        if key == 13 or key == 10: # Enter key
            if len(corners) == 4:
                break
            else:
                print("Please select exactly 4 points first.")

    cv2.destroyWindow(window_name)
    return corners

def select_target_player(video_path, tracker):
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    if not ret: return None

    selected_id = [None]
    window_name = "Select Player: Click on the athlete, then press 'q'"
    
    # Run tracking once to get available players
    results = tracker.model.track(frame, persist=True, tracker="bytetrack.yaml")
    if not results or results[0].boxes.id is None:
        print("No players detected.")
        return None

    boxes = results[0].boxes.xyxy.cpu().numpy()
    ids = results[0].boxes.id.int().cpu().numpy()

    def click_event(event, x, y, flags, params):
        if event == cv2.EVENT_LBUTTONDOWN:
            min_dist = float('inf')
            best_id = None
            for box, track_id in zip(boxes, ids):
                cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
                dist = ((cx - x)**2 + (cy - y)**2)**0.5
                if dist < min_dist:
                    min_dist, best_id = dist, track_id
            
            selected_id[0] = int(best_id)
            temp_frame = frame.copy()
            for b, tid in zip(boxes, ids):
                color = (0, 255, 0) if tid == selected_id[0] else (255, 255, 255)
                cv2.rectangle(temp_frame, (int(b[0]), int(b[1])), (int(b[2]), int(b[3])), color, 2)
                cv2.putText(temp_frame, f"ID: {tid}", (int(b[0]), int(b[1]-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
            cv2.imshow(window_name, temp_frame)
            print(f"Selected Player ID: {selected_id[0]}")

    cv2.imshow(window_name, frame)
    cv2.setMouseCallback(window_name, click_event)
    cv2.waitKey(0)
    cv2.destroyWindow(window_name)
    return selected_id[0]

def main():
    parser = argparse.ArgumentParser(description="Volleyball Mechanics Analyzer")
    parser.add_argument("--video", type=str, required=True, help="Path to the video file")
    parser.add_argument("--calibrate", action="store_true",
        help="Enable court calibration for position-based metrics (drift, approach velocity, etc.)")
    parser.add_argument("--player_id", type=int, default=None, help="Specific Player ID to track")
    parser.add_argument("--output", type=str, default=None,
        help="Save results JSON to a custom path. Default: output/<video_stem>_analysis.json")
    parser.add_argument("--show", action="store_true", help="Display the video with overlays")

    args = parser.parse_args()

    if args.output is None:
        video_stem = os.path.splitext(os.path.basename(args.video))[0]
        args.output = os.path.join("output", f"{video_stem}_analysis.json")

    # 1. Tracker Initialization
    tracker = PlayerTracker(target_player_id=args.player_id)

    # 2. Calibration
    calibrator = None
    if args.calibrate:
        print("Court Calibration: click the 4 court corners (top-left, top-right, bottom-right, bottom-left).")
        cap = cv2.VideoCapture(args.video)
        ret, frame = cap.read()
        cap.release()
        if ret:
            corners = get_court_corners_logic(frame)
            if corners:
                calibrator = CameraCalibrator(corners)

    # 3. Player Selection
    if args.player_id is None:
        print("Player selection: click on the athlete to track.")
        target_id = select_target_player(args.video, tracker)
        if target_id is not None:
            tracker.target_player_id = target_id
    
    analyzer = JumpAnalyzer()
    cap = cv2.VideoCapture(args.video)
    fps = cap.get(cv2.CAP_PROP_FPS)

    print(f"Processing video: {args.video}")
    
    while cap.isOpened():
        frame_idx = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        frame_time = frame_idx / fps if fps > 0 else 0
        
        ret, frame = cap.read()
        if not ret: break
            
        player_id, knee_angles, hip_y, ground_pos, foot_pixels, upper_body = tracker.process_frame(frame)
        if player_id is not None:
            # Map position if calibrator is available, else use pixel pos
            pos = calibrator.transform_point(ground_pos) if calibrator else ground_pos
            foot_court_pos = None
            if foot_pixels is not None:
                l_foot, r_foot = foot_pixels
                if calibrator:
                    foot_court_pos = (
                        calibrator.transform_point(l_foot),
                        calibrator.transform_point(r_foot),
                    )
                else:
                    foot_court_pos = (l_foot, r_foot)
            analyzer.analyze_frame(player_id, knee_angles, hip_y, pos, frame_time, foot_court_pos, upper_body)
            
            if args.show:
                l_angle, r_angle = knee_angles
                cv2.putText(frame, f"Tracking ID: {player_id}", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                # Display current jump status if jumping
                if analyzer.is_jumping:
                    cv2.putText(frame, "JUMPING!", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                cv2.circle(frame, (int(ground_pos[0]), int(ground_pos[1])), 5, (255, 0, 0), -1)

        if args.show:
            cv2.imshow("Volleyball Mechanics Analysis", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'): break

    cap.release()
    cv2.destroyAllWindows()
    print(f"Analysis complete. Total Jumps: {analyzer.jump_count}")
    output_dir = os.path.dirname(args.output)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)
    video_name = os.path.basename(args.video)
    analyzer.save_logs(args.output, video_name=video_name)

if __name__ == "__main__":
    main()
