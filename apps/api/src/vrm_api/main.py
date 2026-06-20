"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import settings
from .db import init_db
from .logging_config import configure_logging, get_logger
from .routers import alerts, ask, audit, contracts, health, llm_info, risk, vendors
from .services import scheduler as scheduler_service
from .services.warmup import warmup_all

configure_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("api_startup", environment=settings.environment, llm_provider=settings.llm_provider)
    init_db()
    scheduler_service.start()

    # Fire warmup as background task — does NOT block startup.
    # API becomes reachable immediately; embedder + LLM warm in parallel.
    warmup_task: asyncio.Task | None = None
    if settings.warmup_on_startup:
        warmup_task = asyncio.create_task(warmup_all(), name="warmup")
        app.state.warmup_task = warmup_task

    try:
        yield
    finally:
        if warmup_task is not None and not warmup_task.done():
            warmup_task.cancel()
        scheduler_service.shutdown()
        log.info("api_shutdown")


app = FastAPI(
    title=settings.app_name,
    description=(
        "Société Générale TPRM — AI-powered Vendor Risk Intelligence (Hackathon Option A).\n\n"
        "Endpoints expose vendor inventory, risk scoring, alerts, contract extraction, "
        "and a streaming Q&A interface that runs on either local Ollama (llama3.2) "
        "or Anthropic Claude — selectable via `LLM_PROVIDER`."
    ),
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    bound = log.bind(rid=rid, method=request.method, path=request.url.path)
    try:
        response = await call_next(request)
    except Exception as exc:  # noqa: BLE001
        bound.exception("request_failed", error=str(exc))
        return JSONResponse({"detail": "Internal Server Error", "rid": rid}, status_code=500)
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    bound.info("request_complete", status=response.status_code, duration_ms=duration_ms)
    response.headers["x-request-id"] = rid
    response.headers["x-duration-ms"] = str(duration_ms)
    return response


app.include_router(health.router)
app.include_router(llm_info.router)
app.include_router(vendors.router)
app.include_router(risk.router)
app.include_router(contracts.router)
app.include_router(ask.router)
app.include_router(alerts.router)
app.include_router(audit.router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {
        "name": settings.app_name,
        "version": __version__,
        "docs": "/docs",
        "openapi": "/openapi.json",
    }
