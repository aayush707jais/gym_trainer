import numpy as np
from body_part_angle import BodyPartAngle
from utils import *


class TypeOfExercise(BodyPartAngle):
    def __init__(self, landmarks):
        super().__init__(landmarks)

    def push_up(self, counter, status):
        left_arm_angle = self.angle_of_the_left_arm()
        right_arm_angle = self.angle_of_the_left_arm()
        avg_arm_angle = (left_arm_angle + right_arm_angle) // 2

        if status:
            if avg_arm_angle < 70:
                counter += 1
                status = False
        else:
            if avg_arm_angle > 160:
                status = True

        return [counter, status]


    def pull_up(self, counter, status):
        nose = detection_body_part(self.landmarks, "NOSE")
        left_elbow = detection_body_part(self.landmarks, "LEFT_ELBOW")
        right_elbow = detection_body_part(self.landmarks, "RIGHT_ELBOW")
        avg_shoulder_y = (left_elbow[1] + right_elbow[1]) / 2

        if status:
            if nose[1] > avg_shoulder_y:
                counter += 1
                status = False

        else:
            if nose[1] < avg_shoulder_y:
                status = True

        return [counter, status]

    def squat(self, counter, status):
        left_leg_angle = self.angle_of_the_right_leg()
        right_leg_angle = self.angle_of_the_left_leg()
        avg_leg_angle = (left_leg_angle + right_leg_angle) // 2

        if status:
            if avg_leg_angle < 70:
                counter += 1
                status = False
        else:
            if avg_leg_angle > 160:
                status = True

        return [counter, status]

    def walk(self, counter, status):
        right_knee = detection_body_part(self.landmarks, "RIGHT_KNEE")
        left_knee = detection_body_part(self.landmarks, "LEFT_KNEE")

        if status:
            if left_knee[0] > right_knee[0]:
                counter += 1
                status = False

        else:
            if left_knee[0] < right_knee[0]:
                counter += 1
                status = True

        return [counter, status]

    def sit_up(self, counter, status):
        angle = self.angle_of_the_abdomen()
        if status:
            if angle < 55:
                counter += 1
                status = False
        else:
            if angle > 105:
                status = True

        return [counter, status]

    def calculate_exercise(self, exercise_type, counter, status):
        if exercise_type == "push-up":
            counter, status = TypeOfExercise(self.landmarks).push_up(
                counter, status)
        elif exercise_type == "pull-up":
            counter, status = TypeOfExercise(self.landmarks).pull_up(
                counter, status)
        elif exercise_type == "squat":
            counter, status = TypeOfExercise(self.landmarks).squat(
                counter, status)
        elif exercise_type == "walk":
            counter, status = TypeOfExercise(self.landmarks).walk(
                counter, status)
        elif exercise_type == "sit-up":
            counter, status = TypeOfExercise(self.landmarks).sit_up(
                counter, status)

        return [counter, status]


# types_of_exercise.py
import time
from collections import deque
from body_part_angle import BodyPartAngle

def _safe(a):
    return None if a is None else float(a)

class TypeOfExercise(BodyPartAngle):
    """
    Gym-level rep counter + posture gating + progress value (0..1).
    Side-view tuned. Returns counter, stage, posture_bool, progress
    """

    SMOOTH_WINDOW = 5
    STABLE_FRAMES_REQUIRED = 3
    MIN_REP_INTERVAL = 0.6  # seconds

    def __init__(self, landmarks=None):
        super().__init__(landmarks)
        self.landmarks = landmarks
        self._buffers = {
            "left_elbow": deque(maxlen=self.SMOOTH_WINDOW),
            "right_elbow": deque(maxlen=self.SMOOTH_WINDOW),
            "left_knee": deque(maxlen=self.SMOOTH_WINDOW),
            "right_knee": deque(maxlen=self.SMOOTH_WINDOW),
            "abdomen": deque(maxlen=self.SMOOTH_WINDOW),
            "neck": deque(maxlen=self.SMOOTH_WINDOW),
        }
        self._smoothed = {}
        self._stable_counts = {"push": 0, "squat": 0, "sit": 0, "pull": 0}
        self._posture_stable = {"push": 0, "squat": 0, "sit": 0, "pull": 0}
        self._last_rep_time = {"push": 0.0, "squat": 0.0, "sit": 0.0, "pull": 0.0}

    def update_landmarks(self, landmarks):
        self.landmarks = landmarks
        try:
            a = self.angle_of_the_left_arm(); 
            if a is not None: self._buffers["left_elbow"].append(a)
        except: pass
        try:
            a = self.angle_of_the_right_arm(); 
            if a is not None: self._buffers["right_elbow"].append(a)
        except: pass
        try:
            a = self.angle_of_the_left_leg(); 
            if a is not None: self._buffers["left_knee"].append(a)
        except: pass
        try:
            a = self.angle_of_the_right_leg(); 
            if a is not None: self._buffers["right_knee"].append(a)
        except: pass
        try:
            a = self.angle_of_the_abdomen(); 
            if a is not None: self._buffers["abdomen"].append(a)
        except: pass
        try:
            a = self.angle_of_the_neck();
            if a is not None: self._buffers["neck"].append(a)
        except: pass

        for k, dq in self._buffers.items():
            self._smoothed[k] = (sum(dq) / len(dq)) if len(dq) > 0 else None

    def get_smoothed_angles(self):
        return dict(self._smoothed)

    def _can_count_rep(self, key):
        now = time.time()
        if now - self._last_rep_time.get(key, 0.0) >= self.MIN_REP_INTERVAL:
            self._last_rep_time[key] = now
            return True
        return False

    # -------------------------
    # Posture heuristics (side-view)
    # -------------------------
    def posture_correct_push(self):
        abdomen = _safe(self._smoothed.get("abdomen"))
        le = _safe(self._smoothed.get("left_elbow"))
        re = _safe(self._smoothed.get("right_elbow"))
        if abdomen is None: return False
        if abdomen < 150:  # torso should be fairly straight (plank)
            return False
        if le is not None and re is not None and abs(le - re) > 30:
            return False
        return True

    def posture_correct_squat(self):
        """
        Good posture = knee angle >= 90 degrees
        """
        lk = _safe(self._smoothed.get("left_knee"))
        rk = _safe(self._smoothed.get("right_knee"))

        if lk is None and rk is None:
            return False

        # take average knee angle (already used for reps)
        avg = None
        if lk is None:
            avg = rk
        elif rk is None:
            avg = lk
        else:
            avg = (lk + rk) / 2

        # GOOD posture if above 90 degrees
        if avg >= 90:
            return True
        else:
            return False


    def posture_correct_sit(self):
        abdomen = _safe(self._smoothed.get("abdomen"))
        neck = _safe(self._smoothed.get("neck"))
        if abdomen is None: return False
        if abdomen < 100: return False
        if neck is not None and neck > 40: return False
        return True

    def posture_correct_pull(self):
        abdomen = _safe(self._smoothed.get("abdomen"))
        le = _safe(self._smoothed.get("left_elbow"))
        re = _safe(self._smoothed.get("right_elbow"))
        if abdomen is None or (le is None and re is None): return False
        if abdomen < 100: return False
        return True

    # -------------------------
    # Normalized progress helper
    # For typical exercises where DOWN < UP (angle increases as you extend)
    # progress: 0.0 at DOWN position, 1.0 at UP position
    # For pull-up where UP angle is smaller, handle invert flag.
    # -------------------------
    def _progress_from_angle(self, angle, down_thresh, up_thresh, invert=False):
        if angle is None: 
            return 0.0
        if not invert:
            # clamp between down..up
            if angle <= down_thresh: return 0.0
            if angle >= up_thresh: return 1.0
            return (angle - down_thresh) / (up_thresh - down_thresh)
        else:
            # invert direction for cases where small angle = up (pull-up)
            if angle >= down_thresh: return 0.0
            if angle <= up_thresh: return 1.0
            # down_thresh > up_thresh here
            return (down_thresh - angle) / (down_thresh - up_thresh)

    # -------------------------
    # Exercise implementations
    # Each returns: (counter, stage, posture_bool, progress)
    # -------------------------
    def push_up(self, counter, stage):
        le = self._smoothed.get("left_elbow")
        re = self._smoothed.get("right_elbow")
        if le is None and re is None:
            return [counter, stage, False, 0.0]
        avg = le if re is None else (re if le is None else (le + re) / 2.0)

        DOWN_THRESH = 70.0
        UP_THRESH = 160.0
        key = "push"

        if stage is None:
            stage = "up" if avg is not None and avg > UP_THRESH else "down"

        # movement detection
        if stage == "up":
            if avg is not None and avg < DOWN_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    stage = "down"; self._stable_counts[key] = 0
            else:
                self._stable_counts[key] = 0
        else:
            if avg is not None and avg > UP_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    # only count if posture stable
                    if self.posture_correct_push() and self._posture_stable[key] >= self.STABLE_FRAMES_REQUIRED:
                        if self._can_count_rep(key):
                            counter += 1
                    stage = "up"; self._stable_counts[key] = 0; self._posture_stable[key] = 0
            else:
                self._stable_counts[key] = 0

        # posture stability update
        if self.posture_correct_push():
            self._posture_stable[key] = min(self._posture_stable[key] + 1, self.STABLE_FRAMES_REQUIRED); posture_bool = True
        else:
            self._posture_stable[key] = 0; posture_bool = False

        progress = self._progress_from_angle(avg, DOWN_THRESH, UP_THRESH, invert=False)
        return [counter, stage, posture_bool, progress]

    def pull_up(self, counter, stage):
        le = self._smoothed.get("left_elbow")
        re = self._smoothed.get("right_elbow")
        if le is None and re is None:
            return [counter, stage, False, 0.0]
        avg = le if re is None else (re if le is None else (le + re) / 2.0)

        DOWN_THRESH = 150.0  # extended
        UP_THRESH = 80.0     # flexed (top)
        key = "pull"

        if stage is None:
            stage = "down" if avg is not None and avg > DOWN_THRESH else "up"

        if stage == "down":
            if avg is not None and avg < UP_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    if self.posture_correct_pull() and self._posture_stable[key] >= self.STABLE_FRAMES_REQUIRED:
                        if self._can_count_rep(key):
                            counter += 1
                    stage = "up"; self._stable_counts[key] = 0; self._posture_stable[key] = 0
            else:
                self._stable_counts[key] = 0
        else:
            if avg is not None and avg > DOWN_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    stage = "down"; self._stable_counts[key] = 0
            else:
                self._stable_counts[key] = 0

        if self.posture_correct_pull():
            self._posture_stable[key] = min(self._posture_stable[key] + 1, self.STABLE_FRAMES_REQUIRED); posture_bool = True
        else:
            self._posture_stable[key] = 0; posture_bool = False

        progress = self._progress_from_angle(avg, DOWN_THRESH, UP_THRESH, invert=True)
        return [counter, stage, posture_bool, progress]

    def squat(self, counter, stage):
        # IMPORTANT: squat thresholds preserved EXACTLY as user requested
        lk = self._smoothed.get("left_knee")
        rk = self._smoothed.get("right_knee")
        if lk is None and rk is None:
            return [counter, stage, False, 0.0]
        avg = lk if rk is None else (rk if lk is None else (lk + rk) / 2.0)

        DOWN_THRESH = 70.0   # <-- preserved exactly
        UP_THRESH = 160.0    # <-- preserved exactly
        key = "squat"

        if stage is None:
            stage = "up" if avg is not None and avg > UP_THRESH else "down"

        if stage == "up":
            if avg is not None and avg < DOWN_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    stage = "down"; self._stable_counts[key] = 0
            else:
                self._stable_counts[key] = 0
        else:
            if avg is not None and avg > UP_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    if self.posture_correct_squat() and self._posture_stable[key] >= self.STABLE_FRAMES_REQUIRED:
                        if self._can_count_rep(key):
                            counter += 1
                    stage = "up"; self._stable_counts[key] = 0; self._posture_stable[key] = 0
            else:
                self._stable_counts[key] = 0

        if self.posture_correct_squat():
            self._posture_stable[key] = min(self._posture_stable[key] + 1, self.STABLE_FRAMES_REQUIRED); posture_bool = True
        else:
            self._posture_stable[key] = 0; posture_bool = False

        # progress computed with preserved thresholds (down->up)
        progress = self._progress_from_angle(avg, DOWN_THRESH, UP_THRESH, invert=False)
        return [counter, stage, posture_bool, progress]

    def sit_up(self, counter, stage):
        a = self._smoothed.get("abdomen")
        if a is None:
            return [counter, stage, False, 0.0]

        DOWN_THRESH = 70.0
        UP_THRESH = 120.0
        key = "sit"

        if stage is None:
            stage = "up" if a is not None and a > UP_THRESH else "down"

        if stage == "up":
            if a is not None and a < DOWN_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    stage = "down"; self._stable_counts[key] = 0
            else:
                self._stable_counts[key] = 0
        else:
            if a is not None and a > UP_THRESH:
                self._stable_counts[key] += 1
                if self._stable_counts[key] >= self.STABLE_FRAMES_REQUIRED:
                    if self.posture_correct_sit() and self._posture_stable[key] >= self.STABLE_FRAMES_REQUIRED:
                        if self._can_count_rep(key):
                            counter += 1
                    stage = "up"; self._stable_counts[key] = 0; self._posture_stable[key] = 0
            else:
                self._stable_counts[key] = 0

        if self.posture_correct_sit():
            self._posture_stable[key] = min(self._posture_stable[key] + 1, self.STABLE_FRAMES_REQUIRED); posture_bool = True
        else:
            self._posture_stable[key] = 0; posture_bool = False

        progress = self._progress_from_angle(a, DOWN_THRESH, UP_THRESH, invert=False)
        return [counter, stage, posture_bool, progress]

    def calculate_exercise(self, exercise_type, counter, stage):
        et = exercise_type.lower()
        if et == "push-up":
            return self.push_up(counter, stage)
        elif et == "pull-up":
            return self.pull_up(counter, stage)
        elif et == "squat":
            return self.squat(counter, stage)
        elif et == "sit-up":
            return self.sit_up(counter, stage)
        else:
            return [counter, stage, False, 0.0]

