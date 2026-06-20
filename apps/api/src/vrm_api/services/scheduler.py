"""APScheduler — registers continuous-monitoring jobs.

Three jobs, all idempotent:
  1. Expiry sweep        every hour  → creates Alert rows at 60/30/7 day windows
  2. Breach feed poll    every 6h    → ingests new BreachEvent rows + alerts
  3. Daily rescore       03:00 UTC   → recomputes risk for every vendor

Started/stopped by the FastAPI lifespan in main.py. Set RUN_SCHEDULER=false
in .env to disable (useful for tests, migrations, eval-only runs).
"""

from __future__ import annotations

import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..logging_config import get_logger
from .breach_feed import poll_breach_feed
from .cert_verifier import verify_certifications
from .expiry_sweep import sweep_expiries
from .financial_scraper import poll_financial_feed

log = get_logger(__name__)
_scheduler: AsyncIOScheduler | None = None


def _enabled() -> bool:
    return os.getenv("RUN_SCHEDULER", "true").lower() in {"1", "true", "yes"}


def _run_expiry_sweep() -> None:
    try:
        counts = sweep_expiries()
        log.info("scheduler_expiry_sweep_done", **counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduler_expiry_sweep_failed", error=str(exc))


def _run_breach_poll() -> None:
    try:
        counts = poll_breach_feed()
        log.info("scheduler_breach_poll_done", **counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduler_breach_poll_failed", error=str(exc))


def _run_daily_rescore() -> None:
    # Local import to avoid heavy module load at startup
    try:
        from ..scoring.score_all import run as run_score_all

        counts = run_score_all(replace=True)
        log.info("scheduler_daily_rescore_done", **counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduler_daily_rescore_failed", error=str(exc))


def _run_financial_scrape() -> None:
    try:
        counts = poll_financial_feed()
        log.info("scheduler_financial_scrape_done", **counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduler_financial_scrape_failed", error=str(exc))


def _run_cert_verify() -> None:
    try:
        counts = verify_certifications()
        log.info("scheduler_cert_verify_done", **counts)
    except Exception as exc:  # noqa: BLE001
        log.exception("scheduler_cert_verify_failed", error=str(exc))


def start() -> AsyncIOScheduler | None:
    global _scheduler
    if not _enabled():
        log.info("scheduler_disabled_via_env")
        return None
    if _scheduler is not None:
        return _scheduler

    s = AsyncIOScheduler(timezone="UTC")

    # Expiry sweep — every hour, with an immediate first run on startup
    s.add_job(
        _run_expiry_sweep,
        trigger=IntervalTrigger(hours=1),
        id="expiry_sweep",
        name="Cert + contract expiry sweep",
        next_run_time=None,  # APScheduler default: first run after `hours=1`
        replace_existing=True,
        max_instances=1,
    )

    # Breach feed poll — every 6 hours
    s.add_job(
        _run_breach_poll,
        trigger=IntervalTrigger(hours=6),
        id="breach_poll",
        name="Breach feed poll",
        replace_existing=True,
        max_instances=1,
    )

    # Daily rescore — 03:00 UTC
    s.add_job(
        _run_daily_rescore,
        trigger=CronTrigger(hour=3, minute=0),
        id="daily_rescore",
        name="Daily risk rescore",
        replace_existing=True,
        max_instances=1,
    )

    # Public records / financial health poll — daily at 04:00 UTC
    s.add_job(
        _run_financial_scrape,
        trigger=CronTrigger(hour=4, minute=0),
        id="financial_scrape",
        name="Public records financial health poll",
        replace_existing=True,
        max_instances=1,
    )

    # Third-party SOC 2 / ISO / PCI verification — weekly Monday 02:00 UTC
    s.add_job(
        _run_cert_verify,
        trigger=CronTrigger(day_of_week="mon", hour=2, minute=0),
        id="cert_verify",
        name="Third-party certification verification",
        replace_existing=True,
        max_instances=1,
    )

    s.start()
    _scheduler = s
    log.info("scheduler_started", jobs=[j.id for j in s.get_jobs()])
    return s


def shutdown() -> None:
    global _scheduler
    if _scheduler is None:
        return
    _scheduler.shutdown(wait=False)
    _scheduler = None
    log.info("scheduler_stopped")


def get_jobs_status() -> list[dict]:
    """For surfacing scheduler health in /healthz or /scheduler/status."""
    if _scheduler is None:
        return []
    return [
        {
            "id": j.id,
            "name": j.name,
            "next_run_time": j.next_run_time.isoformat() if j.next_run_time else None,
        }
        for j in _scheduler.get_jobs()
    ]
