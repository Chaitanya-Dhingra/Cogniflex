"""
Cogniflex cloud game server
Endpoints:
  ws://.../ws/agent  — laptop CV agent sends fingertip coords
  ws://.../ws/tv     — Flutter TV client receives game state
  GET /health        — Railway health check
"""

import asyncio
import json
import math
import random
import time
import uuid
from typing import Optional

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Connection registry
# ---------------------------------------------------------------------------

agent_ws: Optional[WebSocket] = None   # one laptop at a time
tv_clients: list[WebSocket] = []       # multiple TV screens allowed


async def broadcast_to_tvs(payload: dict) -> None:
    dead: list[WebSocket] = []
    msg = json.dumps(payload)
    for ws in tv_clients:
        try:
            await ws.send_text(msg)
        except Exception:
            dead.append(ws)
    for ws in dead:
        tv_clients.remove(ws)


# ---------------------------------------------------------------------------
# Game state — all coordinates are normalized 0.0–1.0
# ---------------------------------------------------------------------------

FRUIT_KINDS = ["apple", "banana", "strawberry", "pineapple", "green"]
SPAWN_INTERVAL = 1.0          # seconds between fruit spawns
FALL_SPEED_MIN = 0.004        # fraction of screen height per tick (~30 fps)
FALL_SPEED_MAX = 0.008
CATCH_RADIUS = 0.06           # normalized collision radius
TICK_RATE = 1 / 30            # 30 fps game loop


class FruitObj:
    def __init__(self):
        self.id = str(uuid.uuid4())[:8]
        self.kind = random.choice(FRUIT_KINDS)
        self.x = random.uniform(0.05, 0.95)
        self.y = 0.0
        self.scale = random.uniform(0.7, 1.3)
        self.velocity = random.uniform(FALL_SPEED_MIN, FALL_SPEED_MAX)
        self.alive = True

    def tick(self) -> None:
        self.y += self.velocity
        if self.y > 1.1:
            self.alive = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "x": round(self.x, 4),
            "y": round(self.y, 4),
            "scale": round(self.scale, 2),
        }


class GameState:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.game_name = "apple"
        self.fruits: list[FruitObj] = []
        self.score = 0
        self.lives = 3
        self.game_over = False
        self.fingertip = {"x": -1.0, "y": -1.0}
        self.last_spawn = time.time()

    def start(self, game_name: str) -> None:
        self.reset()
        self.game_name = game_name.lower()
        self.active = True

    def update_fingertip(self, x: float, y: float) -> None:
        self.fingertip = {"x": round(x, 4), "y": round(y, 4)}

    def tick(self) -> None:
        if not self.active or self.game_over:
            return

        # Spawn
        now = time.time()
        if now - self.last_spawn >= SPAWN_INTERVAL:
            self.fruits.append(FruitObj())
            self.last_spawn = now

        # Move & collision
        fx = self.fingertip["x"]
        fy = self.fingertip["y"]
        for fruit in self.fruits:
            if not fruit.alive:
                continue
            fruit.tick()
            if fx >= 0 and fy >= 0:
                dist = math.hypot(fruit.x - fx, fruit.y - fy)
                if dist < CATCH_RADIUS * fruit.scale:
                    fruit.alive = False
                    if fruit.kind == "apple":
                        self.score += 1
                    else:
                        self.lives -= 1

        self.fruits = [f for f in self.fruits if f.alive]

        if self.lives <= 0:
            self.lives = 0
            self.game_over = True
            self.active = False

    def to_dict(self) -> dict:
        return {
            "fruits": [f.to_dict() for f in self.fruits],
            "fingertip": self.fingertip,
            "score": self.score,
            "lives": self.lives,
            "game_over": self.game_over,
            "game_name": self.game_name,
        }


game = GameState()


# ---------------------------------------------------------------------------
# Background game loop
# ---------------------------------------------------------------------------

async def game_loop() -> None:
    while True:
        game.tick()
        if tv_clients:
            await broadcast_to_tvs(game.to_dict())
        await asyncio.sleep(TICK_RATE)


@app.on_event("startup")
async def startup_event() -> None:
    asyncio.create_task(game_loop())


# ---------------------------------------------------------------------------
# HTTP endpoints
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {"message": "Cogniflex WebSocket server is running"}


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket: laptop CV agent → server
# Accepts JSON: {"x": 0.45, "y": 0.32, "game": "apple"}
# Also accepts control messages: {"cmd": "start", "game": "apple"}
#                                {"cmd": "reset"}
# ---------------------------------------------------------------------------

@app.websocket("/ws/agent")
async def ws_agent(websocket: WebSocket):
    global agent_ws
    await websocket.accept()
    agent_ws = websocket
    print("[agent] connected")
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            # Control commands
            if "cmd" in msg:
                cmd = msg["cmd"]
                if cmd == "start":
                    game.start(msg.get("game", "apple"))
                    print(f"[agent] game started: {game.game_name}")
                elif cmd == "reset":
                    game.reset()
                    print("[agent] game reset")
                continue

            # Fingertip coordinates
            x = float(msg.get("x", -1))
            y = float(msg.get("y", -1))
            game.update_fingertip(x, y)

            # Auto-start on first coord if not already running
            if not game.active and not game.game_over:
                game.start(msg.get("game", "apple"))

    except WebSocketDisconnect:
        print("[agent] disconnected")
        agent_ws = None
        game.update_fingertip(-1, -1)


# ---------------------------------------------------------------------------
# WebSocket: Flutter TV client ← server
# Receives broadcast game state JSON every ~33 ms
# Accepts control messages from TV: {"cmd": "start", "game": "apple"}
#                                    {"cmd": "reset"}
# ---------------------------------------------------------------------------

@app.websocket("/ws/tv")
async def ws_tv(websocket: WebSocket):
    await websocket.accept()
    tv_clients.append(websocket)
    print(f"[tv] connected ({len(tv_clients)} total)")

    # Send current state immediately so the TV doesn't wait for the next tick
    await websocket.send_text(json.dumps(game.to_dict()))

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            if "cmd" in msg:
                cmd = msg["cmd"]
                if cmd == "start":
                    game.start(msg.get("game", "apple"))
                elif cmd == "reset":
                    game.reset()

    except WebSocketDisconnect:
        print("[tv] disconnected")
        if websocket in tv_clients:
            tv_clients.remove(websocket)


# ---------------------------------------------------------------------------
# Entry point (local dev)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)