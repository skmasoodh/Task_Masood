"""MongoDB connection management using Motor (async driver)."""
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


class _Database:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


_state = _Database()

# Collection names
ATTENDANCE_COLLECTION = "attendance"
AUDIT_COLLECTION = "corrections_audit"


async def connect_to_mongo(uri: str | None = None, db_name: str | None = None) -> None:
    """Open the client and create indexes. Called on application startup."""
    _state.client = AsyncIOMotorClient(uri or settings.mongo_uri)
    _state.db = _state.client[db_name or settings.mongo_db]
    await _ensure_indexes(_state.db)


async def close_mongo_connection() -> None:
    """Close the client. Called on application shutdown."""
    if _state.client is not None:
        _state.client.close()
        _state.client = None
        _state.db = None


def get_database() -> AsyncIOMotorDatabase:
    """Return the active database handle.

    Exposed as a FastAPI dependency so it can be overridden in tests.
    """
    if _state.db is None:
        raise RuntimeError("Database connection has not been initialised.")
    return _state.db


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> None:
    # Fast lookup of a given employee's currently open session.
    await db[ATTENDANCE_COLLECTION].create_index(
        [("employee_id", 1), ("status", 1)]
    )
    # Analytics commonly filter by employee + date range.
    await db[ATTENDANCE_COLLECTION].create_index(
        [("employee_id", 1), ("work_date", 1)]
    )
    await db[ATTENDANCE_COLLECTION].create_index([("work_date", 1)])
    # Audit records are looked up per attendance record.
    await db[AUDIT_COLLECTION].create_index([("attendance_id", 1)])
