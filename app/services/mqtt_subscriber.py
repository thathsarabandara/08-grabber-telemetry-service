import asyncio
import json
import logging
from datetime import datetime
import aiomqtt

from app.core.config import settings
from app.core.db import async_session_maker
from app.models.telemetry import TelemetryRecord
from app.services.websocket_manager import manager

logger = logging.getLogger("mqtt_subscriber")
logging.basicConfig(level=logging.INFO)

async def process_telemetry(robot_id: str, payload: dict):
    # Broadcast to WebSocket first for real-time low latency
    ws_message = {
        "type": "telemetry",
        "robotId": robot_id,
        "data": payload
    }
    await manager.broadcast(ws_message)

    # Save to database
    try:
        angles = payload.get("angles", {})
        power = payload.get("power", {})
        
        record = TelemetryRecord(
            robot_id=robot_id,
            timestamp=datetime.utcnow(),
            base_angle=angles.get("base"),
            shoulder_angle=angles.get("shoulder"),
            elbow_angle=angles.get("elbow"),
            grip_angle=angles.get("grip"),
            voltage=power.get("voltage"),
            current=power.get("current"),
            power=power.get("power"),
            peak_current=power.get("peakCurrent"),
            idle_current=power.get("idleCurrent"),
            moving_current=power.get("movingCurrent"),
            energy_wh=power.get("energyWh"),
            remaining_capacity=power.get("remainingCapacity"),
            runtime_mins=power.get("runtimeMins"),
            raw_payload=payload
        )
        
        async with async_session_maker() as session:
            session.add(record)
            await session.commit()
            
    except Exception as e:
        logger.error(f"Error saving telemetry to DB: {e}")

async def mqtt_subscriber_task():
    logger.info("Starting Telemetry MQTT Subscriber...")
    
    while True:
        try:
            async with aiomqtt.Client(
                hostname=settings.MQTT_BROKER,
                port=settings.MQTT_PORT,
                username=settings.MQTT_USERNAME,
                password=settings.MQTT_PASSWORD,
            ) as client:
                logger.info("Telemetry MQTT Client connected.")
                
                await client.subscribe("robot/+/telemetry")
                logger.info("Subscribed to telemetry channels.")
                
                async for message in client.messages:
                    topic = str(message.topic)
                    payload_bytes = message.payload
                    
                    try:
                        payload_str = payload_bytes.decode("utf-8")
                        payload = json.loads(payload_str) if payload_str else {}
                    except Exception:  # nosec B112 - intentional: skip malformed/non-UTF8 MQTT payloads to keep subscriber loop alive
                        continue
                    
                    parts = topic.split("/")
                    if len(parts) >= 3 and parts[2] == "telemetry":
                        robot_id = parts[1]
                        asyncio.create_task(process_telemetry(robot_id, payload))
                        
        except aiomqtt.MqttError as e:
            logger.error(f"MQTT connection error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Retrying in 5s...")
            await asyncio.sleep(5)
