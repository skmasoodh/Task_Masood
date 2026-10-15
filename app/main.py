"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import close_mongo_connection, connect_to_mongo
from app.routers import analytics, attendance


@asynccontextmanager
async def lifespan(_: FastAPI):
    await connect_to_mongo()
    yield
    await close_mongo_connection()


app = FastAPI(
    title="Employee Attendance & Analytics API",
    description=(
        "Punch-in/punch-out with business rules, manual corrections with an "
        "audit trail, and MongoDB aggregation-based analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(attendance.router)
app.include_router(analytics.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
@app.get("/")
async def root():
    return {"message":"Employee Attendance API is running"}

