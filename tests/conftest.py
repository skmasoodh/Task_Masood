"""Shared test fixtures.

Tests run against a real MongoDB instance (the aggregation pipelines require it).
Set MONGO_URI to point at a test server; a throwaway database is created per
test session and dropped afterwards.
"""
from __future__ import annotations

import os
import uuid

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from motor.motor_asyncio import AsyncIOMotorClient

TEST_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
TEST_DB = f"attendance_test_{uuid.uuid4().hex[:8]}"


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(TEST_URI)
    database = client[TEST_DB]
    # Match the indexes created by the app so tests mirror production.
    await database["attendance"].create_index([("employee_id", 1), ("status", 1)])
    try:
        yield database
    finally:
        await client.drop_database(TEST_DB)
        client.close()


@pytest_asyncio.fixture
async def client():
    """HTTP client wired to the app with the database dependency overridden."""
    from app import database as db_module
    from app.database import get_database
    from app.main import app

    mongo = AsyncIOMotorClient(TEST_URI)
    database = mongo[TEST_DB]
    await db_module._ensure_indexes(database)

    app.dependency_overrides[get_database] = lambda: database

    transport = ASGITransport(app=app)
    async with LifespanManager(app, startup_timeout=30, shutdown_timeout=30):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    app.dependency_overrides.clear()
    await mongo.drop_database(TEST_DB)
    mongo.close()
