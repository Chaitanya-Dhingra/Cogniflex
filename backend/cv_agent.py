"""
Cogniflex CV Agent — runs on laptop
- Reads webcam with OpenCV
- Tracks index fingertip via MediaPipe
- Sends normalized (x, y) coords over WebSocket to cloud server
- No display window, no game logic

Usage:
    python cv_agent.py --server wss://your-app.railway.app --game apple

Arguments:
    --server   WebSocket base URL of the cloud server
                 (default: ws://localhost:8000)
    --game     Game name to activate: "apple" or "puzzle"
                 (default: apple)
    --camera   Camera device index (default: 0)
"""

import argparse
import asyncio
import json
import sys
import time

import cv2
import mediapipe as mp
import websockets

# ---------------------------------------------------------------------------
# CLI arguments
# ---------------------------------------------------------------------------

parser = argparse.ArgumentParser(description="Cogniflex CV Agent")
parser.add_argument("--server", default="ws://localhost:8000",
                    help="WebSocket server base URL")
parser.add_argument("--game", default="apple",
                    choices=["apple", "puzzle"],
                    help="Which game to start on the server")
parser.add_argument("--camera", type=int, default=0,
                    help="Camera device index")
args = parser.parse_args()

WS_URL = args.server.rstrip("/") + "/ws/agent"
GAME_NAME = args.game
CAMERA_IDX = args.camera

# ---------------------------------------------------------------------------
# MediaPipe hands
# ---------------------------------------------------------------------------

mp_hands = mp.solutions.hands
hands_detector = mp_hands.Hands(
    max_num_hands=2,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7,
)

# ---------------------------------------------------------------------------
# Async main loop
# ---------------------------------------------------------------------------

async def run() -> None:
    cap = cv2.VideoCapture(CAMERA_IDX)
    if not cap.isOpened():
        print(f"[cv_agent] ERROR: Cannot open camera {CAMERA_IDX}")
        sys.exit(1)

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print(f"[cv_agent] Connecting to {WS_URL} ...")

    reconnect_delay = 2  # seconds between reconnect attempts

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                print(f"[cv_agent] Connected. Starting game: {GAME_NAME}")

                # Tell the server which game to run
                await ws.send(json.dumps({"cmd": "start", "game": GAME_NAME}))

                while True:
                    ret, frame = cap.read()
                    if not ret:
                        print("[cv_agent] Camera read failed — retrying...")
                        await asyncio.sleep(0.1)
                        continue

                    # Mirror so left/right matches physical movement
                    frame = cv2.flip(frame, 1)
                    h, w = frame.shape[:2]

                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands_detector.process(rgb)

                    # Collect all detected fingertips (index finger tip = landmark 8)
                    fingertips: list[dict] = []
                    if results.multi_hand_landmarks:
                        for hand_lm in results.multi_hand_landmarks:
                            lm8 = hand_lm.landmark[8]
                            fingertips.append({
                                "x": round(lm8.x, 4),
                                "y": round(lm8.y, 4),
                                "game": GAME_NAME,
                            })

                    if fingertips:
                        # Send each detected hand (server uses the first one for
                        # collision; future multi-hand support is easy to add)
                        for tip in fingertips:
                            await ws.send(json.dumps(tip))
                    else:
                        # Send sentinel so server knows hand is off screen
                        await ws.send(json.dumps({
                            "x": -1.0,
                            "y": -1.0,
                            "game": GAME_NAME,
                        }))

                    # ~30 fps — yield control so asyncio can handle WS I/O
                    await asyncio.sleep(1 / 30)

        except (websockets.ConnectionClosed,
                websockets.InvalidURI,
                OSError) as e:
            print(f"[cv_agent] Connection error: {e}. "
                  f"Reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)

        except KeyboardInterrupt:
            print("\n[cv_agent] Stopped by user.")
            break

    cap.release()
    print("[cv_agent] Camera released. Bye.")


if __name__ == "__main__":
    asyncio.run(run())