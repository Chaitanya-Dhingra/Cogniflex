import cv2
import mediapipe as mp
import random
import time
import math
import numpy as np
import pygame

# ------------------ SOUND SETUP ------------------
pygame.mixer.init()

catch_sound = None
miss_sound = None

try:
    catch_sound = pygame.mixer.Sound("good.mp3")
except:
    print("Could not load good.mp3")

try:
    miss_sound = pygame.mixer.Sound("wrong.mp3")
except:
    print("Could not load wrong.mp3")

# ------------------ IMAGE LOADING ------------------
def load_and_resize_image(path, size=(80, 80)):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"Error loading {path}")
        return np.zeros((size[1], size[0], 4), dtype=np.uint8)

    img = cv2.resize(img, size)

    if img.shape[2] == 3:
        b, g, r = cv2.split(img)
        alpha = np.ones(b.shape, dtype=b.dtype) * 255
        img = cv2.merge([b, g, r, alpha])

    white_mask = (img[:, :, 0] > 200) & (img[:, :, 1] > 200) & (img[:, :, 2] > 200)
    img[white_mask, 3] = 0
    return img

fruit_images = {
    'apple': load_and_resize_image("fruit-apple.png"),
    'banana': load_and_resize_image("fruit-banana.png"),
    'strawberry': load_and_resize_image("fruit-strawberry.png"),
    'pineapple': load_and_resize_image("fruit-pineapple.png"),
    'green': load_and_resize_image("green_img.png")
}

# ------------------ HAND TRACKING ------------------
mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands = mp_hands.Hands(max_num_hands=2,
                       min_detection_confidence=0.7,
                       min_tracking_confidence=0.7)

# ------------------ OVERLAY FUNCTION ------------------
def overlay_image_alpha(img, img_overlay, x, y):
    h, w = img_overlay.shape[:2]
    x1, x2 = max(x - w // 2, 0), min(x + w // 2, img.shape[1])
    y1, y2 = max(y - h // 2, 0), min(y + h // 2, img.shape[0])

    if x1 >= x2 or y1 >= y2:
        return

    overlay_crop = img_overlay[0:y2 - y1, 0:x2 - x1]
    alpha_mask = overlay_crop[:, :, 3] / 255.0
    alpha_inv = 1.0 - alpha_mask

    for c in range(3):
        img[y1:y2, x1:x2, c] = (
            alpha_mask * overlay_crop[:, :, c] +
            alpha_inv * img[y1:y2, x1:x2, c]
        )

# ------------------ FRUIT CLASS ------------------
class Fruit:
    def __init__(self, kind, x, y, velocity):
        self.kind = kind
        self.image = fruit_images[kind]
        self.x = x
        self.y = y
        self.z_scale = random.uniform(0.7, 1.3)
        self.image = cv2.resize(self.image,
                                (int(80 * self.z_scale),
                                 int(80 * self.z_scale)))
        self.velocity = velocity
        self.radius = 35 * self.z_scale
        self.alive = True

    def move(self):
        self.y += self.velocity
        if self.y > 1080:
            self.alive = False

    def draw(self, frame):
        if self.alive:
            overlay_image_alpha(frame, self.image,
                                int(self.x), int(self.y))

# ------------------ VR STEREO VIEW ------------------
# def create_stereo_view(frame):
#     h, w = frame.shape[:2]
#     shift = 10
#     left_eye = frame[:, shift:]
#     right_eye = frame[:, :-shift]
#     left_eye = cv2.resize(left_eye, (w // 2, h))
#     right_eye = cv2.resize(right_eye, (w // 2, h))
#     return np.hstack((left_eye, right_eye))

# ------------------ REHAB METRICS ------------------
hand_movement = []
session_start = time.time()

def compute_rehab_stats(movement):
    if len(movement) < 2:
        return 0

    total_dist = 0
    for i in range(1, len(movement)):
        x1, y1 = movement[i-1]
        x2, y2 = movement[i]
        total_dist += math.hypot(x2 - x1, y2 - y1)

    return min(100, int((total_dist / 10000) * 100))

# ------------------ MAIN GAME ------------------
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

cv2.namedWindow("Fruit Game", cv2.WINDOW_NORMAL)
# cv2.namedWindow("Fruit Game", cv2.WINDOW_NORMAL)

lives = 3
score = 0
fruits = []
last_spawn = time.time()

while True:
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    h, w, _ = frame.shape

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    results = hands.process(rgb)

    fingertips = []

    if results.multi_hand_landmarks:
        for hand_landmarks in results.multi_hand_landmarks:
            lm8 = hand_landmarks.landmark[8]
            x = int(lm8.x * w)
            y = int(lm8.y * h)

            fingertips.append((x, y))
            hand_movement.append((x, y))

            mp_drawing.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS
            )

            cv2.circle(frame, (x, y), 20,
                       (255, 0, 255), 3)

    # Spawn fruits
    if time.time() - last_spawn > 1:
        kind = random.choice(list(fruit_images.keys()))
        fruits.append(Fruit(kind,
                            random.randint(50, w - 50),
                            0,
                            random.uniform(4, 7)))
        last_spawn = time.time()

    # Move fruits
    for fruit in fruits:
        fruit.move()
        for fx, fy in fingertips:
            if fruit.alive and math.hypot(
                fruit.x - fx,
                fruit.y - fy
            ) < fruit.radius + 20:

                fruit.alive = False

                if fruit.kind == 'apple':
                    score += 1
                    if catch_sound:
                        catch_sound.play()
                else:
                    lives -= 1
                    if miss_sound:
                        miss_sound.play()

        fruit.draw(frame)

    fruits = [f for f in fruits if f.alive]

    elapsed = int(time.time() - session_start)
    movement_score = compute_rehab_stats(hand_movement)

    cv2.putText(frame, f"Score: {score}",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 0, 255), 2)

    cv2.putText(frame, f"Lives: {lives}",
                (10, 80),
                cv2.FONT_HERSHEY_SIMPLEX,
                1, (0, 255, 255), 2)

    cv2.putText(frame, f"Movement: {movement_score}%",
                (10, 120),
                cv2.FONT_HERSHEY_SIMPLEX,
                1, (255, 0, 100), 2)

    if lives <= 0:
        cv2.putText(frame, "GAME OVER",
                    (w//3, h//2),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    2, (0, 0, 255), 4)
        cv2.imshow("Fruit Game", frame) 
        cv2.waitKey(4000)
        break
    
    cv2.imshow("Fruit Game", frame)

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()