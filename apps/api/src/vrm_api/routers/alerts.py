"""/alerts — list, count, ack/resolve, and manual triggers for sweep + breach poll."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Alert, AuditLog, Vendor
from ..services.breach_feed import poll_breach_feed
from ..services.expiry_sweep import sweep_expiries
from ..services.scheduler import get_jobs_status

router = APIRouter(prefix="/alerts", tags=["alerts"])

AlertStatus = Literal["open", "ack", "resolved"]


# ── Schemas ───────────────────────────────────────────────────────────
class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vendor_id: int          # PK; the human-facing vendor_id is in vendor_code
    vendor_code: str        # e.g. "V0042"
    vendor_name: str
    alert_type: str
    severity: str           # CRITICAL | HIGH | MEDIUM | LOW
    message: str
    status: str             # open | ack | resolved
    due_date: date | None
    created_at: datetime


class AlertListOut(BaseModel):
    total: int
    items: list[AlertOut]


class AlertCountsOut(BaseModel):
    total: int
    open: int
    ack: int
    resolved: int
    by_severity: dict[str, int]   # CRITICAL/HIGH/MEDIUM/LOW counts (open only)
    by_type: dict[str, int]       # alert_type counts (open only)
    open_critical: int            # convenience field for the topbar badge
    open_high: int


class AlertUpdate(BaseModel):
    status: AlertStatus


class SweepOut(BaseModel):
    considered: int
    created: int
    skipped_existing: int


class BreachPollOut(BaseModel):
    entries: int
    ingested: int
    skipped_existing: int
    skipped_unknown_vendor: int
    rescored: int


class SchedulerStatusOut(BaseModel):
    jobs: list[dict]


# ── Helpers ───────────────────────────────────────────────────────────
def _row_to_out(alert: Alert, vendor: Vendor) -> AlertOut:
    return AlertOut(
        id=alert.id,
        vendor_id=alert.vendor_id,
        vendor_code=vendor.vendor_id,
        vendor_name=vendor.name,
        alert_type=alert.alert_type,
        severity=alert.severity,
        message=alert.message,
        status=alert.status,
        due_date=alert.due_date,
        created_at=alert.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────
@router.get("", response_model=AlertListOut)
def list_alerts(
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Search in vendor_code, vendor_name, alert_type, message"),
    severity: str | None = Query(None, description="CRITICAL | HIGH | MEDIUM | LOW"),
    status: AlertStatus | None = None,
    vendor_code: str | None = None,
    alert_type: str | None = None,
    sort: str = Query("created_at:desc"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> AlertListOut:
    base = select(Alert, Vendor).join(Vendor, Alert.vendor_id == Vendor.id)
    count_base = select(func.count(Alert.id)).join(Vendor, Alert.vendor_id == Vendor.id)

    conds = []
    if q:
        like = f"%{q}%"
        conds.append(or_(
            Vendor.vendor_id.ilike(like),
            Vendor.name.ilike(like),
            Alert.alert_type.ilike(like),
            Alert.message.ilike(like),
        ))
    if severity:
        conds.append(Alert.severity == severity)
    if status:
        conds.append(Alert.status == status)
    if vendor_code:
        conds.append(Vendor.vendor_id == vendor_code)
    if alert_type:
        conds.append(Alert.alert_type == alert_type)

    if conds:
        base = base.where(*conds)
        count_base = count_base.where(*conds)

    field, _, direction = sort.partition(":")
    sort_col = {
        "created_at": Alert.created_at,
        "severity": Alert.severity,
        "due_date": Alert.due_date,
        "alert_type": Alert.alert_type,
    }.get(field, Alert.created_at)
    base = base.order_by(sort_col.desc() if direction == "desc" else sort_col.asc())
    base = base.limit(limit).offset(offset)

    total = db.execute(count_base).scalar_one()
    rows = db.execute(base).all()
    return AlertListOut(total=total, items=[_row_to_out(a, v) for a, v in rows])


@router.get("/count", response_model=AlertCountsOut)
def alert_counts(db: Session = Depends(get_db)) -> AlertCountsOut:
    total = db.execute(select(func.count(Alert.id))).scalar_one()
    by_status = dict(
        db.execute(
            select(Alert.status, func.count(Alert.id)).group_by(Alert.status)
        ).all()
    )
    by_sev_rows = db.execute(
        select(Alert.severity, func.count(Alert.id))
        .where(Alert.status == "open")
        .group_by(Alert.severity)
    ).all()
    by_type_rows = db.execute(
        select(Alert.alert_type, func.count(Alert.id))
        .where(Alert.status == "open")
        .group_by(Alert.alert_type)
    ).all()

    by_severity = dict(by_sev_rows)
    return AlertCountsOut(
        total=total,
        open=int(by_status.get("open", 0)),
        ack=int(by_status.get("ack", 0)),
        resolved=int(by_status.get("resolved", 0)),
        by_severity={k: int(v) for k, v in by_severity.items()},
        by_type={k: int(v) for k, v in by_type_rows},
        open_critical=int(by_severity.get("CRITICAL", 0)),
        open_high=int(by_severity.get("HIGH", 0)),
    )


@router.patch("/{alert_id}", response_model=AlertOut)
def update_alert(alert_id: int, body: AlertUpdate, db: Session = Depends(get_db)) -> AlertOut:
    row = db.execute(
        select(Alert, Vendor).join(Vendor, Alert.vendor_id == Vendor.id).where(Alert.id == alert_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    alert, vendor = row
    previous = alert.status
    alert.status = body.status
    db.add(AuditLog(
        actor="api",
        action="alert_update",
        entity_type="alert",
        entity_id=str(alert.id),
        payload={"from": previous, "to": body.status, "vendor": vendor.vendor_id},
    ))
    db.commit()
    db.refresh(alert)
    return _row_to_out(alert, vendor)


@router.post("/sweep", response_model=SweepOut)
def trigger_sweep(background: BackgroundTasks, async_mode: bool = False) -> SweepOut:
    """Manual trigger for the cert/contract expiry sweep — useful for live demos."""
    if async_mode:
        background.add_task(sweep_expiries)
        return SweepOut(considered=0, created=0, skipped_existing=0)
    return SweepOut(**sweep_expiries())


@router.post("/breach-poll", response_model=BreachPollOut)
def trigger_breach_poll(
    background: BackgroundTasks,
    async_mode: bool = False,
    rescore: bool = True,
) -> BreachPollOut:
    """Manual trigger for the breach feed poller — drives the 'new breach detected' demo beat."""
    if async_mode:
        background.add_task(poll_breach_feed, rescore_affected=rescore)
        return BreachPollOut(entries=0, ingested=0, skipped_existing=0, skipped_unknown_vendor=0, rescored=0)
    return BreachPollOut(**poll_breach_feed(rescore_affected=rescore))


@router.get("/scheduler/status", response_model=SchedulerStatusOut)
def scheduler_status() -> SchedulerStatusOut:
    """Reports the active scheduled jobs and next-run times."""
    return SchedulerStatusOut(jobs=get_jobs_status())
