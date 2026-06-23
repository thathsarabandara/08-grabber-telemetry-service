import uuid
from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field

class MediaItem(SQLModel, table=True):
    __tablename__ = "media_gallery"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    filename: str = Field(index=True)
    original_name: str
    media_type: str  # "image" or "video"
    file_size: str
    captured_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    duration: Optional[str] = None
    title: Optional[str] = None
