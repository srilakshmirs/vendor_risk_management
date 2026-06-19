from __future__ import annotations

from fastapi import APIRouter

from ..config import settings
from ..schemas.common import HealthOut

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthOut)
async def healthz() -> HealthOut:
    return HealthOut(environment=settings.environment, version="0.1.0")


@router.get("/readyz", response_model=HealthOut)
async def readyz() -> HealthOut:
    # In a fuller build this would probe DB + Redis. For now: same as health.
    return HealthOut(environment=settings.environment, version="0.1.0")
