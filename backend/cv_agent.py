import argparse
import asyncio
import json
import sys

import cv2
import mediapipe as mp
import websockets
from aiohttp import web
import socket

parser = argparse.ArgumentParser(description="Cogniflex CV Agent")
parser.add_argument("--server", default="ws://localhost:8000")
parser.add_argument("--game", default="apple", choices=["apple", "puzzle"])
parser.add_argument("--camera", type=int, default=0)
parser.add_argument("--video-port", type=int, default=8090,
                    help="Local port to serve the MJPEG video feed on")
args = parser.parse_args()

WS_URL = args.server.rstrip("/") + "/ws/agent"
GAME_NAME = args.game
CAMERA_IDX = args.camera
VIDEO_PORT = args.video_port

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils
hands_detector = mp_hands.Hands(
    max_num_hands=2, min_detection_confidence=0.7, min_tracking_confidence=0.7,
)

latest_jpeg: bytes | None = None
frame_ready = asyncio.Event()


async def mjpeg_handler(request: web.Request) -> web.StreamResponse:
    boundary = "frame"
    response = web.StreamResponse(
        headers={"Content-Type": f"multipart/x-mixed-replace; boundary={boundary}"}
    )
    await response.prepare(request)
    print("[cv_agent] TV connected to video stream")
    try:
        while True:
            await frame_ready.wait()
            frame_ready.clear()
            if latest_jpeg is None:
                continue
            await response.write(
                f"--{boundary}\r\nContent-Type: image/jpeg\r\n"
                f"Content-Length: {len(latest_jpeg)}\r\n\r\n".encode()
                + latest_jpeg + b"\r\n"
            )
    except (ConnectionResetError, asyncio.CancelledError, Exception):
        print("[cv_agent] TV disconnected from video stream")
    return response

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    finally:
        s.close()

async def start_video_server() -> None:
    app = web.Application()
    app.router.add_get("/video", mjpeg_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", VIDEO_PORT).start()
    print(f"[cv_agent] Video feed at http://{get_local_ip()}:{VIDEO_PORT}/video")

async def run() -> None:
    global latest_jpeg

    cap = cv2.VideoCapture(CAMERA_IDX)
    if not cap.isOpened():
        print(f"[cv_agent] ERROR: Cannot open camera {CAMERA_IDX}")
        sys.exit(1)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    print(f"[cv_agent] Connecting to {WS_URL} ...")
    reconnect_delay = 2

    while True:
        try:
            async with websockets.connect(WS_URL, ping_interval=20) as ws:
                print(f"[cv_agent] Connected. Starting game: {GAME_NAME}")
                await ws.send(json.dumps({"cmd": "start", "game": GAME_NAME}))

                frame_count = 0
                while True:
                    ret, frame = cap.read()
                    if not ret:
                        await asyncio.sleep(0.1)
                        continue

                    frame = cv2.flip(frame, 1)
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    results = hands_detector.process(rgb)

                    fingertips: list[dict] = []
                    if results.multi_hand_landmarks:
                        for hand_lm in results.multi_hand_landmarks:
                            mp_drawing.draw_landmarks(
                                frame, hand_lm, mp_hands.HAND_CONNECTIONS
                            )
                            lm8 = hand_lm.landmark[8]
                            fingertips.append({
                                "x": round(lm8.x, 4), "y": round(lm8.y, 4),
                                "game": GAME_NAME,
                            })

                    if fingertips:
                        for tip in fingertips:
                            await ws.send(json.dumps(tip))
                    else:
                        await ws.send(json.dumps(
                            {"x": -1.0, "y": -1.0, "game": GAME_NAME}))

                    # Encode every 2nd frame (~15fps) to keep it light
                    frame_count += 1
                    if frame_count % 2 == 0:
                        ok, buf = cv2.imencode(
                            ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                        if ok:
                            latest_jpeg = buf.tobytes()
                            frame_ready.set()

                    await asyncio.sleep(1 / 30)

        except (websockets.ConnectionClosed, websockets.InvalidURI, OSError) as e:
            print(f"[cv_agent] Connection error: {e}. Reconnecting in {reconnect_delay}s...")
            await asyncio.sleep(reconnect_delay)
        except KeyboardInterrupt:
            print("\n[cv_agent] Stopped by user.")
            break

    cap.release()


async def main() -> None:
    await start_video_server()
    await run()


if __name__ == "__main__":
    asyncio.run(main())