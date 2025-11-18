'''import cv2
import os
import argparse
import mediapipe as mp
from utils import *
from body_part_angle import BodyPartAngle
from types_of_exercise import TypeOfExercise

# --------------------------------------------------------
# INTERACTIVE MENU
# --------------------------------------------------------

print("\n====================================")
print("         FITNESS TRACKER MENU        ")
print("====================================\n")

print("Select Exercise:")
print("1. Squat")
print("2. Push-up")
print("3. Pull-up")
print("4. Sit-up")

choice = input("\nEnter option (1-4): ").strip()

exercise_map = {
    "1": "squat",
    "2": "push-up",
    "3": "pull-up",
    "4": "sit-up"
}

if choice not in exercise_map:
    print("\n❌ Invalid exercise option!")
    exit()

exercise_type = exercise_map[choice]
print(f"\n✔ Exercise selected: {exercise_type.upper()}")


print("\nSelect Video Source:")
print("1. Live Webcam")
print("2. Pre-recorded Video")

source_choice = input("\nEnter option (1-2): ").strip()

if source_choice == "1":
    video_source = 0
    print("\n✔ Using Live Webcam")

elif source_choice == "2":
    video_path = input("\nEnter full path of the video file: ").strip()
    if not os.path.exists(video_path):
        print("\n❌ ERROR: File not found at this path!")
        exit()
    video_source = video_path
    print(f"✔ Using Video File: {video_path}")

else:
    print("\n❌ Invalid video source option!")
    exit()


# --------------------------------------------------------
# Mediapipe Setup
# --------------------------------------------------------

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose

cap = cv2.VideoCapture(video_source)
cap.set(3, 800)
cap.set(4, 480)

with mp_pose.Pose(min_detection_confidence=0.5,
                  min_tracking_confidence=0.5) as pose:

    counter = 0
    status = True     # GOOD posture = True, BAD posture = False

    while cap.isOpened():

        ret, frame = cap.read()
        if not ret:
            print("\n❌ ERROR: Could not read video stream.")
            break

        frame = cv2.resize(frame, (800, 480))
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False

        results = pose.process(rgb_frame)

        rgb_frame.flags.writeable = True
        frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

        try:
            landmarks = results.pose_landmarks.landmark

            counter, status = TypeOfExercise(landmarks).calculate_exercise(
                exercise_type, counter, status
            )

        except:
            pass

        # ----------------------------------------------
        # COLOR LOGIC: RED = BAD, GREEN = GOOD
        # ----------------------------------------------
        if status:
            line_color = (0, 255, 0)      # GREEN
            dot_color = (0, 255, 0)
        else:
            line_color = (0, 0, 255)      # RED
            dot_color = (0, 0, 255)

        # Updated score table UI
        frame = score_table(exercise_type, frame, counter, status)

        # Draw pose skeleton
        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=dot_color, thickness=3, circle_radius=3),
                mp_drawing.DrawingSpec(color=line_color, thickness=3, circle_radius=3),
            )

        cv2.imshow("Fitness Tracker", frame)

        if cv2.waitKey(10) & 0xFF == ord("q"):
            break

cap.release()
cv2.destroyAllWindows()'''
import cv2
import argparse
from utils import *
import mediapipe as mp
from body_part_angle import BodyPartAngle
from types_of_exercise import TypeOfExercise

mp_drawing = mp.solutions.drawing_utils
mp_pose = mp.solutions.pose


# ------------------------------------------------
# Formatting helper for angles
# ------------------------------------------------
def fmt_ang(a):
    return f"{int(a)}°" if a is not None else "N/A"


# ------------------------------------------------
# INTERACTIVE MENU
# ------------------------------------------------
print("\n====================================")
print("         FITNESS TRACKER MENU        ")
print("====================================\n")

print("Select Exercise:")
print("1. Squat")
print("2. Push-up")
print("3. Pull-up")
print("4. Sit-up")

choice = input("\nEnter option (1-4): ").strip()

exercise_map = {
    "1": "squat",
    "2": "push-up",
    "3": "pull-up",
    "4": "sit-up"
}

if choice not in exercise_map:
    print("\n❌ Invalid option.")
    exit()

exercise_type = exercise_map[choice]
print(f"\n✔ Selected: {exercise_type.upper()}")

print("\nSelect Video Source:")
print("1. Live Webcam")
print("2. Pre-recorded Video")

source_choice = input("\nChoose (1-2): ").strip()

if source_choice == "1":
    video_source = 0
    print("\n✔ Using Live Webcam")
elif source_choice == "2":
    video_path = input("\nEnter full video path: ").strip()
    if video_path == "":
        print("❌ No path entered.")
        exit()
    video_source = video_path
    print(f"✔ Using Video: {video_path}")
else:
    print("❌ Invalid choice.")
    exit()


# ------------------------------------------------
# CAPTURE
# ------------------------------------------------
cap = cv2.VideoCapture(video_source)
cap.set(3, 800)
cap.set(4, 480)

# create persistent tracker object
tracker = TypeOfExercise(None)

counter = 0
stage = None
posture = False
progress = 0.0


# ------------------------------------------------
# MEDIAPIPE + MAIN LOOP
# ------------------------------------------------
with mp_pose.Pose(min_detection_confidence=0.5,
                  min_tracking_confidence=0.5) as pose:

    while cap.isOpened():

        ret, frame = cap.read()
        if not ret:
            print("❌ Unable to read video.")
            break

        frame = cv2.resize(frame, (800, 480))
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False

        results = pose.process(rgb)

        rgb.flags.writeable = True
        frame = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        landmarks = None
        if results.pose_landmarks:
            landmarks = results.pose_landmarks.landmark

        # update tracker
        tracker.update_landmarks(landmarks)

        # calculate exercise
        counter, stage, posture, progress = tracker.calculate_exercise(
            exercise_type, counter, stage
        )

        # get angles for debug display
        smoothed = tracker.get_smoothed_angles()
        debug = []
        et = exercise_type.lower()

        if et == "squat":
            debug.append(f"Knee L: {fmt_ang(smoothed.get('left_knee'))}")
            debug.append(f"Knee R: {fmt_ang(smoothed.get('right_knee'))}")
        elif et in ("push-up", "pull-up"):
            debug.append(f"Elbow L: {fmt_ang(smoothed.get('left_elbow'))}")
            debug.append(f"Elbow R: {fmt_ang(smoothed.get('right_elbow'))}")
        elif et == "sit-up":
            debug.append(f"Torso: {fmt_ang(smoothed.get('abdomen'))}")

        # -------------------------------------
        # Score Table (exercise, counter, posture)
        # -------------------------------------
        posture_text = "Good" if posture else "Bad"
        frame = score_table(exercise_type, frame, counter, posture_text)

        # -------------------------------------
        # Skeleton color: green=good posture, red=bad posture
        # -------------------------------------
        color = (0, 255, 0) if posture else (0, 0, 255)

        if results.pose_landmarks:
            mp_drawing.draw_landmarks(
                frame,
                results.pose_landmarks,
                mp_pose.POSE_CONNECTIONS,
                mp_drawing.DrawingSpec(color=(255, 255, 255), thickness=2, circle_radius=2),
                mp_drawing.DrawingSpec(color=color, thickness=3, circle_radius=3),
            )

        # -------------------------------------
        # Angle Text (top-left)
        # -------------------------------------
        y0 = 30
        for i, txt in enumerate(debug):
            cv2.putText(frame, txt, (10, y0 + i * 25),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # -------------------------------------
        # SHOW STAGE AND REPS
        # -------------------------------------
        cv2.putText(frame, f"Stage: {stage}", (10, 440),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(frame, f"Reps: {counter}", (10, 470),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # -------------------------------------
        # VERTICAL PROGRESS BAR (LEFT SIDE)
        # -------------------------------------
        bar_w = 24
        bar_h = 220
        margin = 12
        x0 = margin
        y0_bar = int((frame.shape[0] - bar_h) / 2)
        x1 = x0 + bar_w
        y1 = y0_bar + bar_h

        cv2.rectangle(frame, (x0, y0_bar), (x1, y1), (200, 200, 200), 2)

        fill_h = int(bar_h * progress)
        fill_y0 = y1 - fill_h

        fill_color = (0, 255, 0) if posture else (0, 0, 255)

        if fill_h > 0:
            cv2.rectangle(frame, (x0 + 2, fill_y0),
                          (x1 - 2, y1 - 2),
                          fill_color, -1)

        cv2.putText(frame, f"{int(progress * 100)}%",
                    (x1 + 8, y1 - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    (255, 255, 255), 1)

        # -------------------------------------
        cv2.imshow('Fitness Tracker', frame)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break


cap.release()
cv2.destroyAllWindows()

