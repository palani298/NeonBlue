"""Pytest configuration and fixtures."""

import asyncio
import os
from typing import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.database import Base, get_db
from app.core.cache import redis_client
from app.core.config import settings

# Override settings for testing
os.environ["TESTING"] = "true"
settings.database_url = os.getenv("TEST_DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test_experiments")
settings.redis_url = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/1")


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    # Create test engine
    engine = create_async_engine(
        str(settings.database_url),
        poolclass=NullPool,
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    
    # Create session
    async_session = async_sessionmaker(
        engine, 
        class_=AsyncSession, 
        expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
    
    # Clean up
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_client(test_db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database."""
    
    async def override_get_db():
        yield test_db
    
    app.dependency_overrides[get_db] = override_get_db
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Add default auth header
        client.headers["Authorization"] = "Bearer test-token-1"
        yield client
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def clean_redis():
    """Clean Redis before each test."""
    await redis_client.flushdb()
    yield
    await redis_client.flushdb()


@pytest.fixture
def sample_experiment_data():
    """Sample experiment data for testing."""
    return {
        "key": "test_experiment",
        "name": "Test Experiment",
        "description": "A test experiment for unit tests",
        "status": "draft",
        "variants": [
            {
                "key": "control",
                "name": "Control Group",
                "allocation_pct": 50,
                "is_control": True
            },
            {
                "key": "treatment",
                "name": "Treatment Group", 
                "allocation_pct": 50,
                "is_control": False
            }
        ]
    }


@pytest.fixture
def sample_event_data():
    """Sample event data for testing."""
    return {
        "experiment_id": 1,
        "user_id": "test_user_123",
        "event_type": "click",
        "properties": {
            "button": "cta",
            "page": "homepage"
        }
    }


@pytest.fixture
def auth_headers():
    """Authentication headers for testing."""
    return {"Authorization": "Bearer test-token-1"}