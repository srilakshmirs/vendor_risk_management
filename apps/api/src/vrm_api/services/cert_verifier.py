"""Mock third-party certification verification.

In production this would poll the AICPA SOC registry, BSI / Schellman / Coalfire
auditor APIs, etc., to detect real-time changes in vendor certification status
(e.g. surprise revocations, mid-cycle suspensions).

For the demo we read a static JSON feed with the same shape — swap for HTTP
calls without touching the consumer code.

Behaviour:
  * Reads ``data/cert_verifications.json`` (list of vendor_id + cert_type → new
    status + expiry + reason).
  * If the stored ``Certification`` row's status or expiry has changed, update it.
  * Raise a ``CERT_STATUS_CHANGED`` alert with appropriate severity:
      Certified → Expired/Revoked  : HIGH
      Pending   → Certified         : LOW
      anything → Expired            : HIGH
      anything → Pending            : MEDIUM
  * Auto-rescores affected vendors so any new EXPIRED_CERTIFICATION rule fires
    and the dashboard reflects new state.

Idempotent — re-runs only re-update if the cert has since drifted back.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..config import settings
from ..db import SessionLocal, init_db
from ..logging_config import configure_logging, get_logger
from ..models import Alert, AuditLog, Certification, RiskAssessment, Vendor

configure_logging()
log = get_logger(__name__)

DEFAULT_FEED_PATH = settings.data_dir / "cert_verifications.json"


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        return None


def _severity_for_status_change(old_status: str, new_status: str) -> str:
    if new_status in {"Expired", "Revoked"} and old_status == "Certified":
        return "HIGH"
    if new_status == "Expired":
        return "HIGH"
    if new_status == "Pending":
        return "MEDIUM"
    if new_status == "Certified" and old_status != "Certified":
        return "LOW"
    return "MEDIUM"


def _alert_exists_recently(db, vendor_pk: int, alert_type: str, days: int = 7) -> bool:
    from datetime import timedelta, timezone
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    stmt = (
        select(Alert.id)
        .where(
            Alert.vendor_id == vendor_pk,
            Alert.alert_type == alert_type,
            Alert.status == "open",
            Alert.created_at >= cutoff,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def verify_certifications(
    feed_path: Path | None = None,
    *,
    rescore_affected: bool = True,
) -> dict[str, int]:
    feed_path = feed_path or DEFAULT_FEED_PATH
    init_db()
    counts = {
        "entries": 0,
        "updated": 0,
        "alerts_raised": 0,
        "skipped_unchanged": 0,
        "skipped_unknown_vendor": 0,
        "skipped_unknown_cert": 0,
        "rescored": 0,
    }

    if not feed_path.exists():
        log.warning("cert_feed_missing", path=str(feed_path))
        return counts

    entries: list[dict] = json.loads(feed_path.read_text())
    counts["entries"] = len(entries)
    affected_vendor_pks: set[int] = set()

    with SessionLocal() as db:
        ids = [e.get("vendor_id") for e in entries if e.get("vendor_id")]
        vendors_by_vid = {
            v.vendor_id: v
            for v in db.execute(select(Vendor).where(Vendor.vendor_id.in_(ids))).scalars()
        }

        for entry in entries:
            vid = entry.get("vendor_id")
            vendor = vendors_by_vid.get(vid) if vid else None
            if vendor is None:
                counts["skipped_unknown_vendor"] += 1
                log.warning("cert_unknown_vendor", vendor_id=vid)
                continue

            cert_type = entry.get("cert_type")
            cert = db.execute(
                select(Certification)
                .where(
                    Certification.vendor_id == vendor.id,
                    Certification.cert_type == cert_type,
                )
            ).scalar_one_or_none()
            if cert is None:
                counts["skipped_unknown_cert"] += 1
                log.warning("cert_unknown_cert_type", vendor_id=vid, cert_type=cert_type)
                continue

            new_status = entry.get("new_status", cert.status)
            new_expiry = _parse_date(entry.get("new_expiry_date"))
            source = entry.get("source", "external")
            reason = entry.get("reason") or ""
            detected = entry.get("detected_at") or date.today().isoformat()

            changed = (
                new_status != cert.status
                or (new_expiry is not None and new_expiry != cert.expiry_date)
            )
            if not changed:
                counts["skipped_unchanged"] += 1
                continue

            old_status = cert.status
            cert.status = new_status
            if new_expiry is not None:
                cert.expiry_date = new_expiry
            counts["updated"] += 1
            affected_vendor_pks.add(vendor.id)

            alert_type = "CERT_STATUS_CHANGED"
            if _alert_exists_recently(db, vendor.id, f"{alert_type}_{cert_type}"):
                continue

            severity = _severity_for_status_change(old_status, new_status)
            db.add(Alert(
                vendor_id=vendor.id,
                alert_type=f"{alert_type}_{cert_type}",
                severity=severity,
                message=(
                    f"{cert_type} status changed: {old_status} → {new_status} "
                    f"(expiry {new_expiry.isoformat() if new_expiry else 'unchanged'}). "
                    f"Source: {source} on {detected}. {reason}"
                ),
                status="open",
                due_date=new_expiry,
            ))
            counts["alerts_raised"] += 1

        if counts["updated"]:
            db.add(AuditLog(
                actor="scheduler",
                action="cert_verify",
                entity_type="certification",
                entity_id=None,
                payload={"counts": counts, "feed": str(feed_path)},
            ))
        db.commit()

    if rescore_affected and affected_vendor_pks:
        from ..scoring.context import vendor_context_from_orm
        from ..scoring.engine import score_vendor

        with SessionLocal() as db:
            stmt = (
                select(Vendor)
                .where(Vendor.id.in_(affected_vendor_pks))
                .options(
                    selectinload(Vendor.certifications),
                    selectinload(Vendor.data_access),
                    selectinload(Vendor.contracts),
                    selectinload(Vendor.breaches),
                )
            )
            for vendor in db.execute(stmt).scalars():
                ctx = vendor_context_from_orm(vendor)
                scored = score_vendor(ctx)
                db.add(RiskAssessment(
                    vendor_id=vendor.id,
                    score=scored.score,
                    traffic_light=scored.traffic_light,
                    severity=scored.severity,
                    anomaly_type=scored.anomaly_type if scored.anomaly_type != "NONE" else None,
                    components={
                        "raw": scored.components,
                        "weighted": scored.weighted_components,
                        "reasons": scored.reasons,
                    },
                    narrative=scored.narrative,
                    triggered_rules=scored.triggered_rules,
                    model_version=scored.model_version,
                ))
                counts["rescored"] += 1
            db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feed", type=Path, default=None)
    parser.add_argument("--no-rescore", action="store_true")
    args = parser.parse_args()
    counts = verify_certifications(feed_path=args.feed, rescore_affected=not args.no_rescore)
    log.info("cert_verify_complete", **counts)
    print("Cert verify:")
    for k, v in counts.items():
        print(f"  {k:25s} {v:5d}")


if __name__ == "__main__":
    main()
