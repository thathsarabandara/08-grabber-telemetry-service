import os

# Set DATABASE_URL env var before importing anything from app
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_temp.db"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
import asyncio  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402
from sqlmodel import SQLModel  # noqa: E402
import httpx  # noqa: E402

# Import app.core.db first to overwrite its engine
import app.core.db  # noqa: E402
engine = create_async_engine(
    "sqlite+aiosqlite:///./test_temp.db",
    poolclass=NullPool,
    future=True
)
app.core.db.engine = engine

# Now import the remaining app elements
from app.main import app  # noqa: E402
from app.core.db import get_db  # noqa: E402
from app.models.telemetry import TelemetryRecord  # noqa: F401, E402
from app.models.media import MediaItem  # noqa: F401, E402

@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    # Session-scoped initialization: create tables once at the start of the session
    async def create_tables():
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
            
    asyncio.run(create_tables())
    yield
    # File cleanup happens in pytest_sessionfinish

@pytest_asyncio.fixture(name="db")
async def db_fixture():
    # Transactional session for tests
    async with engine.connect() as connection:
        transaction = await connection.begin()
        # Bind Session to the connection
        async_session = sessionmaker(
            connection, class_=AsyncSession, expire_on_commit=False
        )
        async with async_session() as session:
            yield session
            await transaction.rollback()

@pytest_asyncio.fixture(name="client")
async def client_fixture(db):
    async def override_get_db():
        try:
            yield db
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()

class MockSessionMaker:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

@pytest.fixture(autouse=True)
def mock_session_maker(db):
    mock = MockSessionMaker(db)
    with patch("app.services.mqtt_subscriber.async_session_maker", new=mock), \
         patch("app.core.db.async_session_maker", new=mock):
        yield mock

# Mock MQTT Client
@pytest.fixture(autouse=True)
def mock_mqtt():
    with patch("aiomqtt.Client") as mock_client:
        mock_instance = AsyncMock()
        mock_client.return_value = mock_instance
        yield mock_client

# Dummy task for background tasks
async def dummy_task(*args, **kwargs):
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        pass

@pytest.fixture(autouse=True)
def mock_background_tasks():
    with patch("app.main.mqtt_subscriber_task", side_effect=dummy_task):
        yield

def pytest_sessionfinish(session, exitstatus):
    db_file = "test_temp.db"
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
