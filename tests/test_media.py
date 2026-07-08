import os
import pytest
import uuid
from unittest.mock import AsyncMock, patch, MagicMock
from app.models.media import MediaItem
from app.api.routes.media import format_size, fetch_frame_from_camera

# Test format_size utility
def test_format_size():
    assert format_size(500) == "500 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024 * 1024) == "1.0 MB"

@pytest.mark.anyio
async def test_fetch_frame_from_camera_raw_jpeg():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "image/jpeg"}
    mock_response.aread = AsyncMock(return_value=b"fake-jpeg-bytes")
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    
    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        frame = await fetch_frame_from_camera("http://camera/stream")
        assert frame == b"fake-jpeg-bytes"

@pytest.mark.anyio
async def test_fetch_frame_from_camera_mjpeg():
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "multipart/x-mixed-replace; boundary=frame"}
    
    # Yield JPEG frame bytes inside chunks

    async def aiter_bytes_gen():
        yield b"junk"
        yield b"\xff\xd8start_frame\xff\xd9end"
        
    mock_response.aiter_bytes = aiter_bytes_gen
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    
    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        frame = await fetch_frame_from_camera("http://camera/stream")
        assert frame == b"\xff\xd8start_frame\xff\xd9"

@pytest.mark.anyio
async def test_fetch_frame_from_camera_failures():
    # 1. Non-200 status
    mock_response = AsyncMock()
    mock_response.status_code = 404
    
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    
    mock_stream_ctx = AsyncMock()
    mock_stream_ctx.__aenter__.return_value = mock_response
    mock_client.stream = MagicMock(return_value=mock_stream_ctx)
    
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception, match="Camera returned status code 404"):
            await fetch_frame_from_camera("http://camera/stream")

    # 2. Network error exception
    mock_stream_ctx.__aenter__.side_effect = Exception("Conn Timeout")
    with patch("httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(Exception, match="Network error: Conn Timeout"):
            await fetch_frame_from_camera("http://camera/stream")

@pytest.mark.anyio
async def test_proxy_camera_stream_success(client):
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "multipart/x-mixed-replace; boundary=frame"}

    async def aiter_bytes_gen():
        yield b"chunk1"
        yield b"chunk2"
    mock_response.aiter_bytes = aiter_bytes_gen
    mock_response.aclose = AsyncMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.build_request = MagicMock()
    mock_client_instance.send = AsyncMock(return_value=mock_response)
    mock_client_instance.aclose = AsyncMock()
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        response = await client.get("/api/v1/telemetry/media/stream?camera_url=http://camera/stream")
        assert response.status_code == 200
        assert response.headers["content-type"] == "multipart/x-mixed-replace; boundary=frame"
        body = b""
        async for chunk in response.aiter_bytes():
            body += chunk
        assert body == b"chunk1chunk2"

@pytest.mark.anyio
async def test_proxy_camera_stream_non_200(client):
    mock_response = AsyncMock()
    mock_response.status_code = 403
    mock_response.aclose = AsyncMock()
    
    mock_client_instance = AsyncMock()
    mock_client_instance.build_request = MagicMock()
    mock_client_instance.send = AsyncMock(return_value=mock_response)
    mock_client_instance.aclose = AsyncMock()
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        response = await client.get("/api/v1/telemetry/media/stream?camera_url=http://camera/stream")
        assert response.status_code == 500
        assert "Camera returned status 403" in response.json()["detail"]

@pytest.mark.anyio
async def test_proxy_camera_stream_exception(client):
    mock_client_instance = AsyncMock()
    mock_client_instance.build_request = MagicMock()
    mock_client_instance.send = AsyncMock(side_effect=Exception("Connection Refused"))
    mock_client_instance.aclose = AsyncMock()
    
    with patch("httpx.AsyncClient", return_value=mock_client_instance):
        response = await client.get("/api/v1/telemetry/media/stream?camera_url=http://camera/stream")
        assert response.status_code == 500
        assert "Failed to connect to camera stream" in response.json()["detail"]

@pytest.mark.anyio
async def test_list_media(client, db):
    item = MediaItem(
        filename="test.jpg",
        original_name="test.jpg",
        media_type="image",
        file_size="1.2 MB",
        title="First Snapshot"
    )
    db.add(item)
    await db.commit()
    
    response = await client.get("/api/v1/telemetry/media")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["filename"] == "test.jpg"
    assert data[0]["url"] == "/uploads/gallery/test.jpg"

@pytest.mark.anyio
async def test_upload_media_success(client, db, tmp_path):
    # Setup temp uploads dir
    temp_upload_dir = str(tmp_path / "gallery")
    with patch("app.api.routes.media.UPLOAD_DIR", temp_upload_dir):
        # Create a mock file to upload
        file_content = b"fake-image-bytes"
        response = await client.post(
            "/api/v1/telemetry/media/upload",
            data={"title": "Custom Title", "duration": "00:05"},
            files={"file": ("upload.jpg", file_content, "image/jpeg")}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["original_name"] == "upload.jpg"
        assert data["title"] == "Custom Title"
        assert data["media_type"] == "image"
        
        # Verify saved file exists on disk
        saved_filename = data["filename"]
        assert os.path.exists(os.path.join(temp_upload_dir, saved_filename))

@pytest.mark.anyio
async def test_upload_media_disk_error(client, db, tmp_path):
    temp_upload_dir = str(tmp_path / "gallery")
    with patch("app.api.routes.media.UPLOAD_DIR", temp_upload_dir), \
         patch("app.api.routes.media.open", side_effect=IOError("Mock Write Error")):
        response = await client.post(
            "/api/v1/telemetry/media/upload",
            files={"file": ("upload.jpg", b"bytes", "image/jpeg")}
        )
        assert response.status_code == 500
        assert "Failed to save file" in response.json()["detail"]

@pytest.mark.anyio
async def test_capture_media_success(client, db, tmp_path):
    temp_upload_dir = str(tmp_path / "gallery")
    with patch("app.api.routes.media.UPLOAD_DIR", temp_upload_dir), \
         patch("app.api.routes.media.fetch_frame_from_camera", return_value=b"captured-jpeg-frame"):
        
        response = await client.post(
            "/api/v1/telemetry/media/capture",
            data={"camera_url": "http://camera/snapshot", "title": "Captured Frame"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["original_name"] == "capture.jpg"
        assert data["title"] == "Captured Frame"
        assert data["media_type"] == "image"
        
        # Verify saved file exists on disk
        saved_filename = data["filename"]
        assert os.path.exists(os.path.join(temp_upload_dir, saved_filename))

@pytest.mark.anyio
async def test_capture_media_fetch_error(client, db):
    with patch("app.api.routes.media.fetch_frame_from_camera", side_effect=Exception("Stream dead")):
        response = await client.post(
            "/api/v1/telemetry/media/capture",
            data={"camera_url": "http://camera/snapshot"}
        )
        assert response.status_code == 400
        assert "Failed to capture from camera: Stream dead" in response.json()["detail"]

@pytest.mark.anyio
async def test_capture_media_disk_error(client, db, tmp_path):
    temp_upload_dir = str(tmp_path / "gallery")
    with patch("app.api.routes.media.UPLOAD_DIR", temp_upload_dir), \
         patch("app.api.routes.media.open", side_effect=IOError("Mock Write Error")), \
         patch("app.api.routes.media.fetch_frame_from_camera", return_value=b"frame-bytes"):
        response = await client.post(
            "/api/v1/telemetry/media/capture",
            data={"camera_url": "http://camera/snapshot"}
        )
        assert response.status_code == 500
        assert "Failed to save captured frame" in response.json()["detail"]

@pytest.mark.anyio
async def test_delete_media_success(client, db, tmp_path):
    temp_upload_dir = str(tmp_path / "gallery")
    os.makedirs(temp_upload_dir, exist_ok=True)
    
    # Create fake file on disk
    filename = "delete_target.jpg"
    file_path = os.path.join(temp_upload_dir, filename)
    with open(file_path, "wb") as f:
        f.write(b"bytes")
        
    # Save record to DB
    item = MediaItem(
        filename=filename,
        original_name="delete_target.jpg",
        media_type="image",
        file_size="10 B",
        title="To Delete"
    )
    db.add(item)
    await db.commit()
    
    with patch("app.api.routes.media.UPLOAD_DIR", temp_upload_dir):
        response = await client.delete(f"/api/v1/telemetry/media/{item.id}")
        assert response.status_code == 200
        assert response.json()["message"] == "Media item deleted successfully"
        
        # Verify file removed from disk
        assert not os.path.exists(file_path)
        
        # Verify record deleted from DB
        from sqlmodel import select
        res = await db.execute(select(MediaItem).where(MediaItem.id == item.id))
        assert res.scalars().first() is None

@pytest.mark.anyio
async def test_delete_media_not_found(client, db):
    non_existent_id = uuid.uuid4()
    response = await client.delete(f"/api/v1/telemetry/media/{non_existent_id}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Media item not found"
