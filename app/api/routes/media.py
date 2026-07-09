import os
import uuid
import shutil
import httpx
from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.db import get_db
from app.models.media import MediaItem
from app.schemas.media import MediaItemResponse

router = APIRouter()

@router.get("/stream")
async def proxy_camera_stream(camera_url: str):
    # No timeout required: live camera stream is indefinitely long
    client = httpx.AsyncClient(timeout=None)  # nosec B113
    try:
        req = client.build_request("GET", camera_url)
        response = await client.send(req, stream=True)
        
        if response.status_code != 200:
            await response.aclose()
            await client.aclose()
            raise HTTPException(status_code=response.status_code, detail=f"Camera returned status {response.status_code}")
            
        content_type = response.headers.get("content-type", "multipart/x-mixed-replace; boundary=frame")
        
        async def stream_generator():
            try:
                async for chunk in response.aiter_bytes():
                    yield chunk
            finally:
                await response.aclose()
                await client.aclose()
                
        return StreamingResponse(stream_generator(), media_type=content_type)
    except Exception as e:
        await client.aclose()
        raise HTTPException(status_code=500, detail=f"Failed to connect to camera stream: {str(e)}")

UPLOAD_DIR = os.path.join("uploads", "gallery")

def format_size(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}" if unit != 'B' else f"{bytes_size} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} TB"

async def fetch_frame_from_camera(url: str) -> bytes:
    import time
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            async with client.stream("GET", url) as response:
                if response.status_code != 200:
                    raise Exception(f"Camera returned status code {response.status_code}")
                    
                content_type = response.headers.get("content-type", "")
                if "multipart/x-mixed-replace" in content_type:
                    start_time = time.time()
                    buffer = b""
                    async for chunk in response.aiter_bytes():
                        if time.time() - start_time > 5.0:
                            raise Exception("Timed out waiting for a complete JPEG frame")
                        buffer += chunk
                        start = buffer.find(b"\xff\xd8")
                        end = buffer.find(b"\xff\xd9", start) if start != -1 else -1
                        if start != -1 and end != -1:
                            return buffer[start:end + 2]
                    raise Exception("Could not find JPEG frame in stream")
                else:
                    return await response.aread()
        except Exception as e:
            raise Exception(f"Network error: {str(e)}")

@router.get("", response_model=List[MediaItemResponse])
@router.get("/", response_model=List[MediaItemResponse])
async def list_media(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(MediaItem).order_by(MediaItem.captured_at.desc()))
    items = result.scalars().all()
    print(f"DEBUG: list_media found {len(items)} items", flush=True)
    for item in items:
        print(f"DEBUG: Item ID={item.id}, Title={item.title}", flush=True)
    
    response = []
    for item in items:
        response.append(
            MediaItemResponse(
                id=item.id,
                filename=item.filename,
                original_name=item.original_name,
                media_type=item.media_type,
                file_size=item.file_size,
                captured_at=item.captured_at,
                duration=item.duration,
                title=item.title,
                url=f"/uploads/gallery/{item.filename}"
            )
        )
    return response

@router.post("/upload", response_model=MediaItemResponse)
async def upload_media(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    duration: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Generate unique filename
    file_ext = os.path.splitext(file.filename)[1]
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save the file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    # Get file size
    file_size_bytes = os.path.getsize(file_path)
    file_size_str = format_size(file_size_bytes)
    
    # Determine media type
    content_type = file.content_type or ""
    media_type = "video" if "video" in content_type or file_ext.lower() in [".mp4", ".webm", ".avi", ".mov"] else "image"
    
    # Set default title if not provided
    if not title:
        title = "Snapshot" if media_type == "image" else "Video Recording"
        
    # Create DB entry
    db_item = MediaItem(
        filename=unique_filename,
        original_name=file.filename,
        media_type=media_type,
        file_size=file_size_str,
        duration=duration,
        title=title,
        captured_at=datetime.utcnow()
    )
    
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    return MediaItemResponse(
        id=db_item.id,
        filename=db_item.filename,
        original_name=db_item.original_name,
        media_type=db_item.media_type,
        file_size=db_item.file_size,
        captured_at=db_item.captured_at,
        duration=db_item.duration,
        title=db_item.title,
        url=f"/uploads/gallery/{db_item.filename}"
    )

@router.post("/capture", response_model=MediaItemResponse)
async def capture_media(
    camera_url: str = Form(...),
    title: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    
    # Fetch frame from camera_url
    try:
        frame_bytes = await fetch_frame_from_camera(camera_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to capture from camera: {str(e)}")
        
    # Generate unique filename
    unique_filename = f"{uuid.uuid4()}.jpg"
    file_path = os.path.join(UPLOAD_DIR, unique_filename)
    
    # Save frame bytes to file
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(frame_bytes)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save captured frame: {str(e)}")
        
    # Get file size
    file_size_bytes = len(frame_bytes)
    file_size_str = format_size(file_size_bytes)
    
    # Set default title if not provided
    if not title:
        title = f"Snapshot {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        
    # Create DB entry
    db_item = MediaItem(
        filename=unique_filename,
        original_name="capture.jpg",
        media_type="image",
        file_size=file_size_str,
        title=title,
        captured_at=datetime.utcnow()
    )
    
    db.add(db_item)
    await db.commit()
    await db.refresh(db_item)
    
    return MediaItemResponse(
        id=db_item.id,
        filename=db_item.filename,
        original_name=db_item.original_name,
        media_type=db_item.media_type,
        file_size=db_item.file_size,
        captured_at=db_item.captured_at,
        duration=db_item.duration,
        title=db_item.title,
        url=f"/uploads/gallery/{db_item.filename}"
    )

@router.delete("/{media_id}")
async def delete_media(media_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    item = await db.get(MediaItem, media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
        
    # Remove file from disk
    file_path = os.path.join(UPLOAD_DIR, item.filename)
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:  # nosec B110 - intentional: ignore errors if file is already gone or locked during cleanup
            pass
            
    await db.delete(item)
    await db.commit()
    
    return {"message": "Media item deleted successfully"}
