from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class TelemetryResponse(BaseModel):
    id: uuid.UUID
    robot_id: str
    timestamp: datetime
    
    base_angle: Optional[float] = None
    shoulder_angle: Optional[float] = None
    elbow_angle: Optional[float] = None
    grip_angle: Optional[float] = None
    
    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    peak_current: Optional[float] = None
    idle_current: Optional[float] = None
    moving_current: Optional[float] = None
    energy_wh: Optional[float] = None
    remaining_capacity: Optional[float] = None
    runtime_mins: Optional[float] = None

    class Config:
        from_attributes = True
