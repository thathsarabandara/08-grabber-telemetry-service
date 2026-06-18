from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List
from app.core.db import get_db
from app.models.telemetry import TelemetryRecord
from app.schemas.telemetry import TelemetryResponse

router = APIRouter()

@router.get("/{robotId}", response_model=List[TelemetryResponse])
async def get_robot_telemetry(
    robotId: str,
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(TelemetryRecord)
        .where(TelemetryRecord.robot_id == robotId)
        .order_by(TelemetryRecord.timestamp.desc())
        .limit(limit)
    )
    records = result.scalars().all()
    # Return in chronological order for charts
    return list(reversed(records))
