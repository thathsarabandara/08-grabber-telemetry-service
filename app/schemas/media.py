from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import uuid

class MediaItemResponse(BaseModel):
    id: uuid.UUID
    filename: str
    original_name: str
    media_type: str
    file_size: str
    captured_at: datetime
    duration: Optional[str] = None
    title: Optional[str] = None
    url: str

    class Config:
        from_attributes = True
