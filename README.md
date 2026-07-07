# 📊 Grabber Telemetry Service

> **Repository `08`** · Real-time telemetry pipeline and media processing service for the Grabber robotic arm — built on Python 3.11, FastAPI, and SQLModel. Manages high-frequency sensor ingestion via MQTT, live WebSocket broadcasting, ESP32-CAM MJPEG stream proxying, single-frame JPEG extraction from MJPEG streams, and media uploads.

[![Language](https://img.shields.io/badge/Language-Python%203.11-3776AB?logo=python&style=flat-square)]()
[![Framework](https://img.shields.io/badge/Framework-FastAPI-009688?logo=fastapi&style=flat-square)]()
[![ORM](https://img.shields.io/badge/ORM-SQLModel-green.svg?style=flat-square)]()
[![Database](https://img.shields.io/badge/Database-MySQL-blue.svg?style=flat-square)]()
[![Streaming](https://img.shields.io/badge/Streaming-WebSockets%20%7C%20MJPEG-black.svg?style=flat-square)]()
[![Status](https://img.shields.io/badge/Status-Active-brightgreen.svg?style=flat-square)]()

---

## 🎥 Video Demonstration

<div align="center">
  <a href="https://youtu.be/nhmpPPoEyAE?si=xZPJJzwft5mCuo99">
    <img src="https://img.youtube.com/vi/nhmpPPoEyAE/maxresdefault.jpg" alt="Grabber Demo Video" width="70%">
  </a>
  <br/>
  <sub>Click the image above to watch the demonstration video on YouTube.</sub>
</div>

---

## 🧭 What Is This Repository?

The **Telemetry Service** is the high-performance data pipeline of the Grabber system. Designed using async frameworks, it handles high-throughput updates without impacting core robot movement commands.

### Key Core Functions
1. **MQTT Telemetry Ingestion**: Subscribes to the `robot/+/telemetry` topics, processes payloads, writes records to MySQL, and broadcasts updates via WebSockets.
2. **ESP32-CAM MJPEG Stream Proxy**: Proxies the camera stream from the ESP32-CAM local address to client dashboards using FastAPI's `StreamingResponse`, bypassing local network constraints.
3. **JPEG Frame Extractor**: Captures snapshots from MJPEG streams by parsing the stream for JPEG boundary markers (`\xff\xd8` to `\xff\xd9`).
4. **Media Gallery Manager**: Saves snapshots and video recordings to disk (`uploads/gallery`), registers metadata in MySQL, and handles deletion requests.

---

## 📦 Project Structure

The project implements a clean layer division, separating database structures, Pydantic parameters, API routers, and connection managers:

```
08-grabber-telemetry-service/
├── app/
│   ├── api/                 # Endpoint routers and dependency injection
│   │   └── routes/          # Core routers (telemetry, media, health)
│   ├── core/                # Database connections and settings configurations
│   │   ├── config.py        # Pydantic settings config base
│   │   └── db.py            # Async engine and SQLModel table initializations
│   ├── models/              # SQLModel database schemas (TelemetryRecord, MediaItem)
│   ├── schemas/             # Pydantic schemas validating payloads
│   ├── services/            # Background tasks (MQTT subscriber)
│   └── main.py              # Application lifespan management and WebSocket endpoints
├── uploads/
│   └── gallery/             # Local storage folder for screenshots and videos
├── Dockerfile               # Production multi-stage build configuration
├── docker-compose.yml       # Dev stack execution setups
├── requirements.txt         # Production library dependencies
└── README.md
```

### Module Code Index

* **App Core & Startup**:
  * [app/main.py](app/main.py): Sets up the FastAPI instance. Performs automatic database table synchronization (`init_db`), mounts the static media directory `/uploads/gallery`, registers the background MQTT subscriber task, and hosts the WebSocket endpoint (`/api/v1/telemetry/ws`).
  * [app/core/db.py](app/core/db.py): Creates the async engine using `aiomysql` and maps `SQLModel.metadata.create_all` to synchronize MySQL tables.
  * [app/core/config.py](app/core/config.py): Core settings module reading variables from `.env`.

* **API Endpoint Routers**:
  * [app/api/routes/telemetry.py](app/api/routes/telemetry.py): Handles telemetry retrieval, returning chronological records for a robot to feed front-end charts.
  * [app/api/routes/media.py](app/api/routes/media.py): Core media router. Provides the MJPEG camera stream proxy, handles single-frame camera snapshot captures, processes direct media uploads, and manages deletes.

* **Database Models (SQLModel)**:
  * [app/models/telemetry.py](app/models/telemetry.py): Defines the `telemetry_records` table, storing time-series logs for joint angles, current, voltage, power dynamics, and raw payloads.
  * [app/models/media.py](app/models/media.py): Defines the `media_gallery` table tracking files stored on disk.

* **Background Services**:
  * [app/services/mqtt_subscriber.py](app/services/mqtt_subscriber.py): Listens to `robot/+/telemetry`, processes JSON payloads, broadcasts updates to WebSockets, and writes records to MySQL.
  * [app/services/websocket_manager.py](app/services/websocket_manager.py): Manages active WebSocket connections and broadcasts telemetry updates to clients.

---

## 📊 Database Schema Specifications

The service connects to a MySQL database and uses **SQLModel** to define table structures:

### 1. Telemetry Records Table (`telemetry_records`)
Captures time-series logs for the robot's joints and power metrics.
```python
class TelemetryRecord(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    robot_id: str = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Motion angles
    base_angle: Optional[float] = None
    shoulder_angle: Optional[float] = None
    elbow_angle: Optional[float] = None
    grip_angle: Optional[float] = None
    
    # Power metrics
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    peak_current: Optional[float] = None
    idle_current: Optional[float] = None
    moving_current: Optional[float] = None
    energy_wh: Optional[float] = None
    remaining_capacity: Optional[float] = None
    runtime_mins: Optional[float] = None
    
    # Raw JSON payload
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(sa.JSON))
```

### 2. Media Gallery Table (`media_gallery`)
Tracks media files saved to local disk.
```python
class MediaItem(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str = Field(index=True)                              -- Unique UUID filename
    original_name: str                                             -- Original upload name
    media_type: str                                                -- "image" or "video"
    file_size: str                                                 -- Formatted size string (e.g. "1.2 MB")
    captured_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    duration: Optional[str] = None
    title: Optional[str] = None
```

---

## ⚡ Real-Time Ingestion & Streaming Flow

### 1. Ingestion Pipeline
The background task in [app/services/mqtt_subscriber.py](app/services/mqtt_subscriber.py) runs on startup:
* Subscribes to `robot/+/telemetry`.
* Receives payloads from the MQTT broker.
* Parses angles and power usage data.
* Broadcasts payload to all active WebSocket clients.
* Writes a `TelemetryRecord` database entry in MySQL.

### 2. WebSocket Telemetry Schema
Clients subscribing to `ws://{gateway}/api/v1/telemetry/ws` receive JSON telemetry frames:
```json
{
  "type": "telemetry",
  "robotId": "ROB_XYZ",
  "data": {
    "angles": {
      "base": 90.0,
      "shoulder": 100.0,
      "elbow": 60.0,
      "grip": 90.0
    },
    "power": {
      "voltage": 5.0,
      "current": 180.0,
      "power": 900.0,
      "remainingCapacity": 82.0
    }
  }
}
```

---

## 📷 ESP32-CAM Integration & Frame Capture

### 1. Live Stream Proxying
FastAPI proxies the camera feed using a custom stream:
* **Endpoint**: `GET /api/v1/telemetry/media/stream?camera_url={camera_url}`
* **Implementation**: Opens an async HTTP connection via `httpx` to stream bytes from the ESP32-CAM MJPEG server and returns them in a `StreamingResponse` using the `multipart/x-mixed-replace` media type.

### 2. Frame Capture (Snapshot) Engine
The capture endpoint extracts single frames from the camera's MJPEG stream:
* **Endpoint**: `POST /api/v1/telemetry/media/capture` (payload: `camera_url` and `title`)
* **Logic**: Intercepts the raw MJPEG stream and extracts a JPEG frame by identifying start (`\xff\xd8`) and end (`\xff\xd9`) byte markers.
* **Saving**: Writes the frame to `uploads/gallery/`, calculates file sizes, and saves a metadata entry in the `media_gallery` table.

---

## ⚙️ Core API Endpoints

### 1. Telemetry Data
* **Get Telemetry History**: `GET /api/v1/telemetry/{robotId}?limit=100`
  * Query parameters: `limit` (max 1000)
  * Note: Returns historical records in chronological order for charting.

### 2. Media Controls
* **Stream Camera**: `GET /api/v1/telemetry/media/stream?camera_url=http://...`
* **Capture Frame**: `POST /api/v1/telemetry/media/capture`
  * Body: `camera_url=http://...&title=Snapshot`
* **Upload Media**: `POST /api/v1/telemetry/media/upload` (Multipart Form)
  * File: `file` (Video/Image binary data)
* **List Media Gallery**: `GET /api/v1/telemetry/media`
* **Delete Media**: `DELETE /api/v1/telemetry/media/{media_id}`

---

## 🚀 Getting Started

### 1. Environment Configurations
Create a `.env` configuration file in the project root:
```env
PROJECT_NAME="Telemetry Service"

# Async MySQL Database URI
DATABASE_URL="mysql+aiomysql://thathsara:BandaPutha@db/grabber_telemetry"
PORT=8003

# MQTT Broker Configuration
MQTT_BROKER=grabber-mqtt-server
MQTT_PORT=1883
MQTT_USERNAME=thathsara
MQTT_PASSWORD=BandaPutha
```

### 2. Local Setup
Ensure you have Python 3.11+, a running MySQL database, and an active MQTT broker:
```bash
# Initialize and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --host 0.0.0.0 --port 8003 --reload
```

### 3. Run via Docker Compose
Build and run the container locally:
```bash
docker compose up -d --build
```

---

## 🔗 Related Grabber Repositories

| Repository | Purpose |
|---|---|
| [`01-grabber-architecture`](https://github.com/thathsarabandara/01-grabber-architecture) | System blueprints, MQTT schemas, and database designs |
| [`02-grabber-firmware`](https://github.com/thathsarabandara/02-grabber-firmware) | ESP32 controller and ESP32-CAM stream endpoints |
| [`03-grabber-mobile-app`](https://github.com/thathsarabandara/03-grabber-mobile-app) | Flutter app remote teleoperation HUD |
| [`05-grabber-api-gateway`](https://github.com/thathsarabandara/05-grabber-api-gateway) | Inbound router proxying app REST & WebSocket requests |
| [`06-grabber-auth-service`](https://github.com/thathsarabandara/06-grabber-auth-service) | Service managing user profiles, image updates, and JWT sessions |
| [`07-grabber-robot-service`](https://github.com/thathsarabandara/07-grabber-robot-service) | Service processing joint commands and homing schedules |
| [`09-grabber-ai-service`](https://github.com/thathsarabandara/09-grabber-ai-service) | Engine orchestrating autonomous sorting tasks and YOLO models |

---

<div align="center">
  <sub>Part of the <strong>Grabber</strong> AI-Powered Industrial Robotic Arm Platform</sub>
</div>
