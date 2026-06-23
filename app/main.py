import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.api.routes import health, telemetry, media
from app.core.config import settings
from app.core.db import init_db
from app.services.mqtt_subscriber import mqtt_subscriber_task
from app.services.websocket_manager import manager

# Ensure uploads/gallery directory exists
UPLOAD_DIR = os.path.join("uploads", "gallery")
os.makedirs(UPLOAD_DIR, exist_ok=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    app.state.mqtt_task = asyncio.create_task(mqtt_subscriber_task())
    yield
    app.state.mqtt_task.cancel()
    try:
        await app.state.mqtt_task
    except asyncio.CancelledError:
        pass

app = FastAPI(title=settings.PROJECT_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount gallery static files
app.mount("/uploads/gallery", StaticFiles(directory=UPLOAD_DIR), name="gallery")

@app.websocket("/api/v1/telemetry/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(media.router, prefix="/api/v1/telemetry/media", tags=["media"])
app.include_router(telemetry.router, prefix="/api/v1/telemetry", tags=["telemetry"])

@app.get("/")
def read_root():
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

