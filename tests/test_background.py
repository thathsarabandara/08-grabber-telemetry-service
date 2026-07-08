import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from app.core.db import get_db
from app.services.websocket_manager import ConnectionManager
from app.services.mqtt_subscriber import (
    process_telemetry,
    mqtt_subscriber_task
)
from app.models.telemetry import TelemetryRecord

@pytest.mark.anyio
async def test_get_db_generator():
    async for db in get_db():
        assert db is not None

@pytest.mark.anyio
async def test_websocket_manager():
    manager = ConnectionManager()
    
    # Mock WebSocket
    mock_ws1 = MagicMock()
    mock_ws1.accept = AsyncMock()
    mock_ws1.send_text = AsyncMock()
    
    mock_ws2 = MagicMock()
    mock_ws2.accept = AsyncMock()
    mock_ws2.send_text = AsyncMock(side_effect=Exception("WS Disconnected"))
    
    # Connect
    await manager.connect(mock_ws1)
    await manager.connect(mock_ws2)
    assert len(manager.active_connections) == 2
    
    # Broadcast
    await manager.broadcast({"data": "hello"})
    mock_ws1.send_text.assert_called_once()
    mock_ws2.send_text.assert_called_once()
    
    # ws2 should be cleaned up due to exception
    assert len(manager.active_connections) == 1
    assert mock_ws2 not in manager.active_connections
    
    # Disconnect remaining
    manager.disconnect(mock_ws1)
    assert len(manager.active_connections) == 0
    
    # Disconnect non-existent does nothing
    manager.disconnect(mock_ws1)

def test_websocket_route_endpoint():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as test_client:
        with test_client.websocket_connect("/api/v1/telemetry/ws") as websocket:
            websocket.send_text("ping")
            websocket.close()

@pytest.mark.anyio
async def test_process_telemetry_success(db):
    payload = {
        "angles": {
            "base": 10.0,
            "shoulder": 20.0,
            "elbow": 30.0,
            "grip": 40.0
        },
        "power": {
            "voltage": 12.0,
            "current": 1.5,
            "power": 18.0,
            "peakCurrent": 2.0,
            "idleCurrent": 0.5,
            "movingCurrent": 1.5,
            "energyWh": 5.0,
            "remainingCapacity": 80.0,
            "runtimeMins": 120.0
        }
    }
    
    # WebSocket broadcast mock
    mock_manager = AsyncMock()
    with patch("app.services.mqtt_subscriber.manager", mock_manager):
        await process_telemetry("robot-abc", payload)
        
        # Verify WS broadcast
        mock_manager.broadcast.assert_called_once()
        broadcasted = mock_manager.broadcast.call_args[0][0]
        assert broadcasted["type"] == "telemetry"
        assert broadcasted["robotId"] == "robot-abc"
        
    # Verify DB entry
    from sqlmodel import select
    res = await db.execute(select(TelemetryRecord).where(TelemetryRecord.robot_id == "robot-abc"))
    record = res.scalars().first()
    assert record is not None
    assert record.base_angle == 10.0
    assert record.voltage == 12.0
    assert record.power == 18.0
    assert record.raw_payload == payload

@pytest.mark.anyio
async def test_process_telemetry_db_error():
    # Force DB error inside async_session_maker
    with patch("app.services.mqtt_subscriber.async_session_maker", side_effect=Exception("DB Connection Error")), \
         patch("app.services.mqtt_subscriber.logger") as mock_logger:
        await process_telemetry("robot-abc", {})
        # Exception should be caught and logged
        mock_logger.error.assert_called_with("Error saving telemetry to DB: DB Connection Error")

class MockMqttMessage:
    def __init__(self, topic: str, payload: bytes):
        self.topic = topic
        self.payload = payload

@pytest.mark.anyio
@patch("app.services.mqtt_subscriber.asyncio.sleep", new_callable=AsyncMock)
async def test_mqtt_subscriber_task_loops(mock_sleep):
    # Injects mock MQTT packets:
    # 1. Telemetry message with correct JSON
    # 2. Telemetry message with invalid JSON (should continue)
    # 3. Topic that is not matching telemetry format (should ignore)
    async def mock_messages():
        yield MockMqttMessage("robot/robot-abc/telemetry", b'{"angles":{"base":45.0}}')
        yield MockMqttMessage("robot/robot-abc/telemetry", b'invalid-json')
        yield MockMqttMessage("robot/robot-abc/status", b'{}')
        # Raise CancelledError to break the while loop
        raise asyncio.CancelledError()

    mock_client_instance = AsyncMock()
    mock_client_instance.messages = mock_messages()
    
    with patch("aiomqtt.Client") as mock_client, \
         patch("app.services.mqtt_subscriber.process_telemetry", new_callable=AsyncMock) as mock_process:
        mock_client.return_value.__aenter__.return_value = mock_client_instance
        try:
            await mqtt_subscriber_task()
        except asyncio.CancelledError:
            pass
            
        # Verify process_telemetry was called with correct arguments
        mock_process.assert_called_once_with("robot-abc", {"angles": {"base": 45.0}})

@pytest.mark.anyio
@patch("app.services.mqtt_subscriber.asyncio.sleep")
async def test_mqtt_subscriber_reconnect_mqtt_error(mock_sleep):
    # Tests aiomqtt.MqttError exception catching and sleep reconnect block
    from aiomqtt import MqttError
    mock_sleep.side_effect = [None, asyncio.CancelledError()]
    with patch("aiomqtt.Client", side_effect=[MqttError("Mqtt Broken"), asyncio.CancelledError()]):
        try:
            await mqtt_subscriber_task()
        except asyncio.CancelledError:
            pass
        mock_sleep.assert_called_with(5)

@pytest.mark.anyio
@patch("app.services.mqtt_subscriber.asyncio.sleep")
async def test_mqtt_subscriber_reconnect_unexpected_error(mock_sleep):
    # Tests unexpected Exception catching and sleep reconnect block
    mock_sleep.side_effect = [None, asyncio.CancelledError()]
    with patch("aiomqtt.Client", side_effect=[Exception("Unexpected Broker Failure"), asyncio.CancelledError()]):
        try:
            await mqtt_subscriber_task()
        except asyncio.CancelledError:
            pass
        mock_sleep.assert_called_with(5)
