import pytest
from datetime import datetime, timedelta
from app.models.telemetry import TelemetryRecord

@pytest.mark.anyio
async def test_get_robot_telemetry_success(client, db):
    # Create test telemetry records
    now = datetime.utcnow()
    record1 = TelemetryRecord(
        robot_id="robot-1",
        timestamp=now - timedelta(seconds=10),
        base_angle=10.0,
        shoulder_angle=20.0,
        elbow_angle=30.0,
        grip_angle=40.0,
        voltage=12.0,
        current=1.5,
        power=18.0,
        raw_payload={"angles": {"base": 10.0}}
    )
    record2 = TelemetryRecord(
        robot_id="robot-1",
        timestamp=now,
        base_angle=15.0,
        shoulder_angle=25.0,
        elbow_angle=35.0,
        grip_angle=45.0,
        voltage=11.8,
        current=2.0,
        power=23.6,
        raw_payload={"angles": {"base": 15.0}}
    )
    record_other = TelemetryRecord(
        robot_id="robot-other",
        timestamp=now,
        base_angle=5.0,
        raw_payload={}
    )
    
    db.add_all([record1, record2, record_other])
    await db.commit()
    
    # Fetch records
    response = await client.get("/api/v1/telemetry/robot-1")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    
    # Should be in chronological order (record1 first, record2 second)
    assert data[0]["base_angle"] == 10.0
    assert data[1]["base_angle"] == 15.0
    assert data[0]["voltage"] == 12.0
    assert data[1]["voltage"] == 11.8

@pytest.mark.anyio
async def test_get_robot_telemetry_limit(client, db):
    # Insert multiple records
    records = [
        TelemetryRecord(robot_id="robot-1", base_angle=float(i), raw_payload={})
        for i in range(10)
    ]
    db.add_all(records)
    await db.commit()
    
    # Fetch with limit
    response = await client.get("/api/v1/telemetry/robot-1?limit=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 5
