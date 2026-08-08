"""Liveness and readiness.

/healthz answers "is the process up" and must never touch a dependency --
Docker restarts containers based on it.
/readyz answers "can this instance serve traffic" and does check dependencies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Response, status
from sqlalchemy import text

from app.db import SessionDep, SettingsDep

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(session: SessionDep, settings: SettingsDep, response: Response) -> dict[str, Any]:
    checks: dict[str, str] = {}

    try:
        await session.execute(text("select 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001 - report, do not crash the probe
        checks["database"] = f"error: {type(exc).__name__}"

    healthy = all(value == "ok" for value in checks.values())
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if healthy else "degraded",
        "environment": settings.environment,
        "checks": checks,
    }
