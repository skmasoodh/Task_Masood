"""API-level tests exercising the full HTTP surface via the ASGI app."""
from __future__ import annotations

import app


async def test_health(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_punch_in_and_out_flow(client):
    r1 = await client.post(
        "/attendance/punch-in",
        json={"employee_id": "EMP-9", "timestamp": "2026-01-15T09:00:00Z"},
    )
    assert r1.status_code == 201
    assert r1.json()["status"] == "open"

    r2 = await client.post(
        "/attendance/punch-out",
        json={"employee_id": "EMP-9", "timestamp": "2026-01-15T17:00:00Z"},
    )
    assert r2.status_code == 200
    body = r2.json()
    assert body["status"] == "closed"
    assert body["worked_minutes"] == 480


async def test_double_punch_in_conflict(client):
    await client.post(
        "/attendance/punch-in",
        json={"employee_id": "EMP-10", "timestamp": "2026-01-15T09:00:00Z"},
    )
    resp = await client.post(
        "/attendance/punch-in",
        json={"employee_id": "EMP-10", "timestamp": "2026-01-15T10:00:00Z"},
    )
    assert resp.status_code == 409


async def test_correction_and_audit_endpoints(client):
    await client.post(
        "/attendance/punch-in",
        json={"employee_id": "EMP-11", "timestamp": "2026-01-15T09:00:00Z"},
    )
    out = await client.post(
        "/attendance/punch-out",
        json={"employee_id": "EMP-11", "timestamp": "2026-01-15T17:00:00Z"},
    )
    attendance_id = out.json()["id"]

    correction = await client.patch(
        f"/attendance/records/{attendance_id}/correct",
        json={
            "field": "punch_out",
            "new_value": "2026-01-15T18:00:00Z",
            "reason": "Late system punch-out",
            "corrected_by": "admin@corp.com",
        },
    )
    assert correction.status_code == 200
    assert correction.json()["record"]["worked_minutes"] == 540

    audit = await client.get(f"/attendance/records/{attendance_id}/audit")
    assert audit.status_code == 200
    assert len(audit.json()) == 1


async def test_analytics_endpoint(client):
    await client.post(
        "/attendance/punch-in",
        json={"employee_id": "EMP-12", "timestamp": "2026-01-15T10:00:00Z"},
    )
    await client.post(
        "/attendance/punch-out",
        json={"employee_id": "EMP-12", "timestamp": "2026-01-15T18:00:00Z"},
    )
    resp = await client.get("/analytics/late-arrivals")
    assert resp.status_code == 200
    rows = {r["employee_id"]: r["late_count"] for r in resp.json()}
    assert rows.get("EMP-12") == 1