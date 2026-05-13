# 📊 Grabber Telemetry Service

> **Repository `08`** · Real-time data pipeline for the Grabber platform. Handles high-frequency telemetry updates, WebSocket streaming, and camera MJPEG relay.

[![Language](https://img.shields.io/badge/Language-Python-3776AB?logo=python)]()
[![Framework](https://img.shields.io/badge/Framework-FastAPI-009688?logo=fastapi)]()
[![Streaming](https://img.shields.io/badge/Streaming-WebSockets-010101?logo=socketdotio)]()
[![Storage](https://img.shields.io/badge/Storage-Redis%20%2B%20MinIO-blue)]()
[![Status](https://img.shields.io/badge/Status-Planned-yellow)]()

---

## 🧭 What Is This Repository?

The **Telemetry Service** manages the flow of real-time information from the robot to the user interfaces, implemented in **Python / FastAPI**. It utilizes FastAPI's native support for asynchronous WebSockets and background tasks to handle high-throughput, low-latency data.

---

## 📦 Module Structure

```
08-grabber-telemetry-service/
├── app/
│   ├── realtime/          ← Async WebSocket handlers for live streaming
│   ├── cache/             ← Redis client for ephemeral state management
│   ├── camera_relay/      ← Async MJPEG proxy for ESP32-CAM stream
│   ├── snapshots/         ← Integration with aiobotocore / MinIO
│   ├── recordings/        ← Media processing and playback logic
│   └── events/            ← Logging and alert distribution
├── requirements.txt
└── README.md
```

---

## ⚡ Data Pipeline

| Data Type | Frequency | Path | Tech |
|---|---|---|---|
| **Joint Angles** | 10 Hz | MQTT → FastAPI → WebSockets | `aiomqtt` + `websockets` |
| **Health** | 1 Hz | MQTT → FastAPI → WebSockets | `aiomqtt` + `websockets` |
| **Camera Stream** | 15 FPS | ESP32-CAM → FastAPI → MJPEG | `httpx` (async proxy) |
| **Snapshots** | On Demand | ESP32-CAM → FastAPI → MinIO | `aiobotocore` |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Redis ≥ 7
- MinIO or AWS S3

### Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in REDIS_URL, MINIO_ENDPOINT, MQTT_URL
uvicorn app.main:app --reload
```

---

## 🔗 Related Repositories
| Repo | Role |
|---|---|
| [`01-grabber-architecture`](../01-grabber-architecture) | Telemetry data model and topic schema |
| [`02-grabber-firmware`](../02-grabber-firmware) | Source of all telemetry and MJPEG stream |
| [`04-grabber-web-dashboard`](../04-grabber-web-dashboard) | Primary consumer of the WebSocket and MJPEG relay |
| [`09-grabber-ai-service`](../09-grabber-ai-service) | Consumes frames for inference via this service |

---
<div align="center">
  <sub>Part of the <strong>Grabber</strong> AI-Powered Industrial Robotic Arm Platform</sub>
</div>
