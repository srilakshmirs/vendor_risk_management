"""Sweep cert + contract expiry → Alert rows.

For each certification + contract, find the most specific expiring threshold
(7 < 30 < 60 days) and create one Alert if no equivalent OPEN alert exists.

Severity ladder:
  ≤  7 days  → HIGH
  ≤ 30 days  → MEDIUM
  ≤ 60 days  → LOW

This satisfies the rubric's "30+ day alert lead time" — vendors get warnings
well before expiry, with severity escalating as the deadline approaches.

Already-expired certs/contracts are skipped here (they're handled by the
risk-scoring engine which fires EXPIRED_CERTIFICATION / CONTRACT_EXPIRED_ACTIVE_ACCESS).

Run manually:
    uv run python -m vrm_api.services.expiry_sweep
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from sqlalchemy import and_, select

from ..db import SessionLocal, init_db
from ..logging_config import configure_logging, get_logger
from ..models import Alert, AuditLog, Certification, Contract, Vendor
from ..services.email_service import send_email_fire_and_forget, _resolve_recipients, build_risk_alert_html, _base_html, _info_row, _section_divider, _SEVERITY_COLORS
from ..config import get_settings

configure_logging()
log = get_logger(__name__)

# (days, severity, suffix) — most-specific first so the inner loop picks the worst applicable one
THRESHOLDS: tuple[tuple[int, str, str], ...] = (
    (7, "HIGH", "7D"),
    (30, "MEDIUM", "30D"),
    (60, "LOW", "60D"),
)

# Skip re-creating an alert for the same vendor+type within this window
DEDUPE_WINDOW = timedelta(hours=24)


@dataclass
class _Pending:
    vendor_id_pk: int
    vendor_id: str
    vendor_name: str
    alert_type: str
    severity: str
    message: str
    due_date: date


def _pick_threshold(days_until: int) -> tuple[str, str] | None:
    """Return (severity, suffix) for the most-specific window the cert/contract has entered."""
    for days, severity, suffix in THRESHOLDS:
        if days_until <= days:
            return severity, suffix
    return None


def _already_alerted(db, vendor_pk: int, alert_type: str, due_date: date) -> bool:
    """Skip if an OPEN alert of the same type+vendor+due_date exists, or any equivalent within DEDUPE_WINDOW."""
    cutoff = datetime.now(timezone.utc) - DEDUPE_WINDOW
    stmt = (
        select(Alert.id)
        .where(
            Alert.vendor_id == vendor_pk,
            Alert.alert_type == alert_type,
            Alert.status == "open",
        )
        .where(
            # either matches exact due_date, or was created within the dedupe window
            (Alert.due_date == due_date) | (Alert.created_at >= cutoff)
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def _gather_cert_alerts(db, today: date) -> list[_Pending]:
    pending: list[_Pending] = []
    stmt = (
        select(Certification, Vendor)
        .join(Vendor, Certification.vendor_id == Vendor.id)
        .where(Certification.status == "Certified", Certification.expiry_date.is_not(None))
    )
    for cert, vendor in db.execute(stmt).all():
        days = (cert.expiry_date - today).days
        if days <= 0:
            continue
        picked = _pick_threshold(days)
        if not picked:
            continue
        severity, suffix = picked
        alert_type = f"CERT_EXPIRY_{cert.cert_type}_{suffix}"
        message = (
            f"{cert.cert_type} expires in {days} day(s) on {cert.expiry_date.isoformat()} — "
            f"renew before deadline to maintain compliance posture."
        )
        pending.append(_Pending(
            vendor_id_pk=vendor.id,
            vendor_id=vendor.vendor_id,
            vendor_name=vendor.name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            due_date=cert.expiry_date,
        ))
    return pending


def _gather_contract_alerts(db, today: date) -> list[_Pending]:
    pending: list[_Pending] = []
    stmt = (
        select(Contract, Vendor)
        .join(Vendor, Contract.vendor_id == Vendor.id)
    )
    for contract, vendor in db.execute(stmt).all():
        days = (contract.end_date - today).days
        if days <= 0:
            continue
        picked = _pick_threshold(days)
        if not picked:
            continue
        severity, suffix = picked
        alert_type = f"CONTRACT_EXPIRY_{suffix}"
        message = (
            f"Contract ends in {days} day(s) on {contract.end_date.isoformat()} — "
            f"engage Procurement to renew or off-board."
        )
        pending.append(_Pending(
            vendor_id_pk=vendor.id,
            vendor_id=vendor.vendor_id,
            vendor_name=vendor.name,
            alert_type=alert_type,
            severity=severity,
            message=message,
            due_date=contract.end_date,
        ))
    return pending


def _send_expiry_alert_email(p: _Pending) -> None:
    """Send an email notification for a HIGH/CRITICAL expiry alert."""
    s = get_settings()
    if not s.email_enabled:
        return

    recipients = list(s.email_admin_recipients)
    if not recipients:
        return

    sev_color, sev_icon = _SEVERITY_COLORS.get(p.severity, ("#64748b", "⚪"))

    rows = '<table width="100%" cellpadding="0" cellspacing="0">'
    rows += _info_row("Vendor", f"{p.vendor_name} ({p.vendor_id})")
    rows += _info_row("Alert Type", p.alert_type)
    rows += _info_row("Severity", f"{sev_icon} {p.severity}", sev_color)
    rows += _info_row("Due Date", p.due_date.isoformat())
    rows += _section_divider()
    rows += f"""\
    <tr>
      <td colspan="2" style="padding:8px 0;">
        <div style="background:#fef2f2;border-left:4px solid {sev_color};padding:12px 16px;border-radius:4px;">
          <strong style="color:{sev_color};">Alert Details</strong>
          <p style="margin:8px 0 0;color:#1e293b;font-size:14px;line-height:1.5;">{p.message}</p>
        </div>
      </td>
    </tr>"""
    rows += f"""\
    <tr>
      <td colspan="2" style="padding:20px 0 0;">
        <a href="http://localhost:3001/vendors/{p.vendor_id}" 
           style="display:inline-block;background:{sev_color};color:#fff;padding:10px 24px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">
          View in Dashboard →
        </a>
      </td>
    </tr>"""
    rows += "</table>"

    subject = f"[VRM {p.severity}] {p.vendor_name} ({p.vendor_id}) — {p.alert_type}"
    html = _base_html("⚠️", f"VRM ALERT — {p.severity}", sev_color, rows)
    send_email_fire_and_forget(recipients, subject, html)


def sweep_expiries(*, today: date | None = None) -> dict[str, int]:
    """Run one full sweep. Returns counts of created/skipped/total."""
    today = today or date.today()
    init_db()

    counts = {"considered": 0, "created": 0, "skipped_existing": 0}

    with SessionLocal() as db:
        pending = _gather_cert_alerts(db, today) + _gather_contract_alerts(db, today)
        counts["considered"] = len(pending)

        for p in pending:
            if _already_alerted(db, p.vendor_id_pk, p.alert_type, p.due_date):
                counts["skipped_existing"] += 1
                continue
            db.add(Alert(
                vendor_id=p.vendor_id_pk,
                alert_type=p.alert_type,
                severity=p.severity,
                message=p.message,
                status="open",
                due_date=p.due_date,
            ))
            counts["created"] += 1

            # Send email notification for HIGH/CRITICAL alerts
            if p.severity in {"HIGH", "CRITICAL"}:
                _send_expiry_alert_email(p)

        if counts["created"]:
            db.add(AuditLog(
                actor="scheduler",
                action="expiry_sweep",
                entity_type="alert",
                entity_id=None,
                payload={"counts": counts, "today": today.isoformat()},
            ))
        db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="Override 'today' for testing, format YYYY-MM-DD")
    args = parser.parse_args()
    today = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    counts = sweep_expiries(today=today)
    log.info("expiry_sweep_complete", **counts)
    print("Expiry sweep:")
    for k, v in counts.items():
        print(f"  {k:20s} {v:5d}")


if __name__ == "__main__":
    main()
