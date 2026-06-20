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
from ..services.cert_verifier import verify_certifications
from ..services.email_service import get_email_status, notify_alert_resolved, send_email_fire_and_forget, build_risk_alert_html, build_alert_resolved_html, _resolve_recipients
from ..services.expiry_sweep import sweep_expiries
from ..services.financial_scraper import poll_financial_feed
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


class FinancialScrapeOut(BaseModel):
    entries: int
    updated: int
    alerts_raised: int
    skipped_unchanged: int
    skipped_unknown_vendor: int
    rescored: int


class CertVerifyOut(BaseModel):
    entries: int
    updated: int
    alerts_raised: int
    skipped_unchanged: int
    skipped_unknown_vendor: int
    skipped_unknown_cert: int
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

    # Send resolution email for CRITICAL/HIGH alerts being resolved
    if body.status == "resolved" and previous != "resolved":
        notify_alert_resolved(alert, vendor)

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


@router.post("/scrape-financial", response_model=FinancialScrapeOut)
def trigger_financial_scrape(
    background: BackgroundTasks,
    async_mode: bool = False,
    rescore: bool = True,
) -> FinancialScrapeOut:
    """Manual trigger for the public-records financial-health scraper."""
    if async_mode:
        background.add_task(poll_financial_feed, rescore_affected=rescore)
        return FinancialScrapeOut(entries=0, updated=0, alerts_raised=0,
                                   skipped_unchanged=0, skipped_unknown_vendor=0, rescored=0)
    return FinancialScrapeOut(**poll_financial_feed(rescore_affected=rescore))


@router.post("/verify-certs", response_model=CertVerifyOut)
def trigger_cert_verify(
    background: BackgroundTasks,
    async_mode: bool = False,
    rescore: bool = True,
) -> CertVerifyOut:
    """Manual trigger for the third-party SOC 2 / ISO / PCI verification poller."""
    if async_mode:
        background.add_task(verify_certifications, rescore_affected=rescore)
        return CertVerifyOut(entries=0, updated=0, alerts_raised=0,
                              skipped_unchanged=0, skipped_unknown_vendor=0,
                              skipped_unknown_cert=0, rescored=0)
    return CertVerifyOut(**verify_certifications(rescore_affected=rescore))


@router.get("/scheduler/status", response_model=SchedulerStatusOut)
def scheduler_status() -> SchedulerStatusOut:
    """Reports the active scheduled jobs and next-run times."""
    return SchedulerStatusOut(jobs=get_jobs_status())


# ── Email management endpoints ────────────────────────────────────────
class EmailStatusOut(BaseModel):
    enabled: bool
    mode: str
    smtp_host: str | None
    smtp_port: int | None
    from_address: str = ""
    admin_recipients: list[str]
    send_to_vendor_contact: bool


class NotifyOut(BaseModel):
    status: str
    alert_id: int
    recipients: list[str]


@router.get("/email-status", response_model=EmailStatusOut)
def email_status() -> EmailStatusOut:
    """Check if email service is configured and healthy."""
    info = get_email_status()
    return EmailStatusOut(
        enabled=info["enabled"],
        mode=info["mode"],
        smtp_host=info.get("smtp_host"),
        smtp_port=info.get("smtp_port"),
        from_address=info.get("from", ""),
        admin_recipients=info.get("admin_recipients", []),
        send_to_vendor_contact=info.get("send_to_vendor_contact", False),
    )


@router.post("/{alert_id}/notify", response_model=NotifyOut)
def notify_alert(alert_id: int, db: Session = Depends(get_db)) -> NotifyOut:
    """Manually re-send email notification for a specific alert."""
    row = db.execute(
        select(Alert, Vendor).join(Vendor, Alert.vendor_id == Vendor.id).where(Alert.id == alert_id)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    alert, vendor = row

    recipients = _resolve_recipients(vendor)
    if not recipients:
        raise HTTPException(status_code=400, detail="No email recipients configured")

    if alert.status == "resolved":
        html = build_alert_resolved_html(alert, vendor)
        subject = f"[VRM RESOLVED] Alert #{alert.id} — {alert.alert_type} for {vendor.name}"
    else:
        from ..services.email_service import _SEVERITY_COLORS, _base_html, _info_row, _section_divider
        sev_color, sev_icon = _SEVERITY_COLORS.get(alert.severity, ("#64748b", "⚪"))
        rows = '<table width="100%" cellpadding="0" cellspacing="0">'
        rows += _info_row("Vendor", f"{vendor.name} ({vendor.vendor_id})")
        rows += _info_row("Alert Type", alert.alert_type)
        rows += _info_row("Severity", f"{sev_icon} {alert.severity}", sev_color)
        rows += _info_row("Status", alert.status)
        rows += _section_divider()
        rows += f'<tr><td colspan="2" style="padding:8px 0;font-size:14px;color:#1e293b;">{alert.message}</td></tr>'
        rows += "</table>"
        html = _base_html("⚠️", f"VRM ALERT — {alert.severity}", sev_color, rows)
        subject = f"[VRM {alert.severity}] {alert.alert_type} — {vendor.name} ({vendor.vendor_id})"

    send_email_fire_and_forget(recipients, subject, html)
    return NotifyOut(status="sent", alert_id=alert_id, recipients=recipients)
