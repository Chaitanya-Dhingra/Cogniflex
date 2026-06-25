import cv2
import mediapipe as mp
import numpy as np
import math
import random
import os
import time

# -------- CONFIGURATION --------
IMAGE_PATH = "dog.jpg"
GRID_ROWS = 3
GRID_COLS = 3
TILE_SIZE = 100
TRANSPARENCY = 1.0
SMOOTHING = 0.2

VR_DISPARITY = 12
EYE_WIDTH = 640
EYE_HEIGHT = 720

DWELL_TIME_SECONDS = 3.0

COLOR_HOLO_BORDER = (255, 255, 200)
COLOR_SELECTION = (0, 255, 0)
COLOR_PROGRESS = (0, 255, 255)
COLOR_TEXT = (255, 255, 255)


class PointSmoother:
    def __init__(self, alpha=0.5):
        self.x = None
        self.y = None
        self.alpha = alpha

    def update(self, new_x, new_y):
        if self.x is None:
            self.x, self.y = new_x, new_y
        else:
            self.x = self.x * (1 - self.alpha) + new_x * self.alpha
            self.y = self.y * (1 - self.alpha) + new_y * self.alpha
        return int(self.x), int(self.y)


class ARPuzzleVR:
    def __init__(self, img_path, screen_w, screen_h):
        self.screen_w = screen_w
        self.screen_h = screen_h

        self.grid_w = GRID_COLS * TILE_SIZE
        self.grid_h = GRID_ROWS * TILE_SIZE
        self.start_x = (screen_w - self.grid_w) // 2
        self.start_y = (screen_h - self.grid_h) // 2

        self.original_image = self.load_and_prep_image(img_path)
        self.tiles = []
        self.order = []
        self.correct_order = []

        self.state = "IDLE"
        self.current_hover_idx = None
        self.hover_start_time = 0
        self.progress = 0.0
        self.locked_tile_idx = None
        self.message = "GAZE AT TILE"

        self.start_time = time.time()
        self.final_time_taken = None

        self.slice_image()
        self.shuffle()

    def load_and_prep_image(self, path):
        if os.path.exists(path):
            img = cv2.imread(path)
        else:
            img = np.zeros((600, 600, 3), dtype=np.uint8)
            cv2.putText(img, "404", (50, 300),
                        cv2.FONT_HERSHEY_SIMPLEX, 2,
                        (255, 255, 255), 5)

        img = cv2.resize(img, (self.grid_w, self.grid_h))
        return img

    def slice_image(self):
        self.tiles = []
        count = 1
        for r in range(GRID_ROWS):
            for c in range(GRID_COLS):
                y1, y2 = r * TILE_SIZE, (r + 1) * TILE_SIZE
                x1, x2 = c * TILE_SIZE, (c + 1) * TILE_SIZE

                tile = self.original_image[y1:y2, x1:x2].copy()
                cv2.rectangle(tile, (0, 0),
                              (TILE_SIZE, TILE_SIZE),
                              COLOR_HOLO_BORDER, 2)
                cv2.putText(tile, str(count),
                            (15, 40),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            1.0, COLOR_TEXT, 2)

                self.tiles.append(tile)
                self.order.append(len(self.tiles) - 1)
                self.correct_order.append(len(self.tiles) - 1)
                count += 1

    def shuffle(self):
        random.shuffle(self.order)

    def get_slot_at(self, x, y):
        if (self.start_x <= x < self.start_x + self.grid_w and
                self.start_y <= y < self.start_y + self.grid_h):
            col = (x - self.start_x) // TILE_SIZE
            row = (y - self.start_y) // TILE_SIZE
            return int(row * GRID_COLS + col)
        return None

    def update(self, finger_x, finger_y):
        curr_tile = self.get_slot_at(finger_x, finger_y)
        current_time = time.time()

        if self.order == self.correct_order:
            if self.final_time_taken is None:
                self.final_time_taken = current_time - self.start_time
            return

        if self.state in ["IDLE", "DWELLING_SOURCE"]:
            if curr_tile is not None:
                if curr_tile != self.current_hover_idx:
                    self.current_hover_idx = curr_tile
                    self.hover_start_time = current_time
                    self.state = "DWELLING_SOURCE"
                    self.progress = 0.0
                else:
                    elapsed = current_time - self.hover_start_time
                    self.progress = min(1.0, elapsed / DWELL_TIME_SECONDS)
                    if self.progress >= 1.0:
                        self.state = "LOCKED"
                        self.locked_tile_idx = curr_tile
                        self.current_hover_idx = None
                        self.progress = 0.0
            else:
                self.current_hover_idx = None
                self.state = "IDLE"
                self.progress = 0.0

        elif self.state in ["LOCKED", "DWELLING_TARGET"]:
            if curr_tile is not None and curr_tile != self.locked_tile_idx:
                if curr_tile != self.current_hover_idx:
                    self.current_hover_idx = curr_tile
                    self.hover_start_time = current_time
                    self.state = "DWELLING_TARGET"
                    self.progress = 0.0
                else:
                    elapsed = current_time - self.hover_start_time
                    self.progress = min(1.0, elapsed / DWELL_TIME_SECONDS)
                    if self.progress >= 1.0:
                        a = self.locked_tile_idx
                        b = curr_tile
                        self.order[a], self.order[b] = self.order[b], self.order[a]
                        self.state = "IDLE"
                        self.locked_tile_idx = None
                        self.current_hover_idx = None
                        self.progress = 0.0

    def draw_eye_view(self, frame, finger_x, finger_y, x_offset=0):
        for i, tile_idx in enumerate(self.order):
            r = i // GRID_COLS
            c = i % GRID_COLS
            x = self.start_x + c * TILE_SIZE + x_offset
            y = self.start_y + r * TILE_SIZE
            frame[y:y+TILE_SIZE, x:x+TILE_SIZE] = self.tiles[tile_idx]

        cv2.circle(frame, (finger_x, finger_y), 5, (255, 255, 255), -1)

        if self.final_time_taken:
            cv2.putText(frame,
                        f"SOLVED! {self.final_time_taken:.1f}s",
                        (100, 50),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        1, (0, 255, 0), 2)


def main():
    cap = cv2.VideoCapture(0)
    cap.set(3, 1280)
    cap.set(4, 720)

    mp_hands = mp.solutions.hands
    mp_draw = mp.solutions.drawing_utils

    hands = mp_hands.Hands(
        max_num_hands=1,
        min_detection_confidence=0.7,
        min_tracking_confidence=0.5
    )

    game = ARPuzzleVR(IMAGE_PATH, EYE_WIDTH, EYE_HEIGHT)
    smoother = PointSmoother(alpha=SMOOTHING)

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        eye_view = cv2.resize(frame, (EYE_WIDTH, EYE_HEIGHT))

        rgb = cv2.cvtColor(eye_view, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        finger_x, finger_y = 0, 0

        if results.multi_hand_landmarks:
            for lm in results.multi_hand_landmarks:
                idx_tip = lm.landmark[8]
                raw_x = int(idx_tip.x * EYE_WIDTH)
                raw_y = int(idx_tip.y * EYE_HEIGHT)
                finger_x, finger_y = smoother.update(raw_x, raw_y)
                break

        game.update(finger_x, finger_y)

        left_eye = eye_view.copy()
        right_eye = eye_view.copy()

        game.draw_eye_view(left_eye, finger_x, finger_y, 0)
        game.draw_eye_view(right_eye, finger_x, finger_y, -VR_DISPARITY)

        vr_frame = np.hstack((left_eye, right_eye))

        cv2.imshow("VR Puzzle", vr_frame)

        if cv2.waitKey(1) == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()