from typing import Optional
from datetime import datetime
import uuid
from sqlmodel import SQLModel, Field
from sqlalchemy import Column, JSON

class TelemetryRecord(SQLModel, table=True):
    __tablename__ = "telemetry_records"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    robot_id: str = Field(index=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Motion
    base_angle: Optional[float] = None
    shoulder_angle: Optional[float] = None
    elbow_angle: Optional[float] = None
    grip_angle: Optional[float] = None
    
    # Power
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    peak_current: Optional[float] = None
    idle_current: Optional[float] = None
    moving_current: Optional[float] = None
    energy_wh: Optional[float] = None
    remaining_capacity: Optional[float] = None
    runtime_mins: Optional[float] = None
    
    raw_payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
