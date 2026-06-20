"""Mock public-records scraper for vendor financial health.

In production this would poll Bloomberg / Moody's / DnB / S&P / national credit
bureaus and surface bankruptcy filings, credit downgrades, regulatory fines, etc.
For the demo we read a static JSON file with the same shape — swapping in a real
HTTP poller is a one-function change.

Behaviour:
  * Reads ``data/financial_signals.json`` (list of vendor_id → new score + reason).
  * If a vendor's ``financial_health_score`` differs by ≥ 15 points (in either direction),
    update the stored value and raise a ``FINANCIAL_HEALTH_DROP`` (or
    ``FINANCIAL_HEALTH_IMPROVED``) alert.
  * If the new score drops below 50, the alert is HIGH severity; below 35 is CRITICAL.
  * Auto-rescores affected vendors so the dashboard reflects new state.

Idempotent — re-runs only re-update if the score has since drifted back.
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
from ..models import Alert, AuditLog, RiskAssessment, Vendor

configure_logging()
log = get_logger(__name__)

DEFAULT_FEED_PATH = settings.data_dir / "financial_signals.json"

# Score-change threshold below which we don't bother creating an alert
SIGNIFICANT_DELTA = 15


def _severity_for_score(score: int, delta: int) -> str:
    """Map (new score, direction) → alert severity."""
    if delta > 0:  # health improved
        return "LOW"
    if score < 35:
        return "CRITICAL"
    if score < 50:
        return "HIGH"
    if score < 70:
        return "MEDIUM"
    return "LOW"


def _alert_exists_recently(db, vendor_pk: int, alert_type: str, days: int = 7) -> bool:
    """Dedupe — skip if we've already raised this alert type for this vendor recently."""
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


def poll_financial_feed(
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
        "rescored": 0,
    }

    if not feed_path.exists():
        log.warning("financial_feed_missing", path=str(feed_path))
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
                log.warning("financial_unknown_vendor", vendor_id=vid)
                continue

            old_score = vendor.financial_health_score
            new_score = int(entry.get("new_health_score", old_score))
            delta = new_score - old_score
            source = entry.get("source", "external")
            reason = entry.get("reason") or ""
            detected = entry.get("detected_at") or date.today().isoformat()

            if abs(delta) < SIGNIFICANT_DELTA:
                counts["skipped_unchanged"] += 1
                continue

            # Apply the update
            vendor.financial_health_score = new_score
            counts["updated"] += 1
            affected_vendor_pks.add(vendor.id)

            alert_type = "FINANCIAL_HEALTH_DROP" if delta < 0 else "FINANCIAL_HEALTH_IMPROVED"
            if _alert_exists_recently(db, vendor.id, alert_type):
                continue

            severity = _severity_for_score(new_score, delta)
            direction = "dropped" if delta < 0 else "improved"
            db.add(Alert(
                vendor_id=vendor.id,
                alert_type=alert_type,
                severity=severity,
                message=(
                    f"Financial health {direction} by {abs(delta)} points "
                    f"({old_score} → {new_score}/100) per {source} on {detected}. "
                    f"{reason}"
                ),
                status="open",
                due_date=None,
            ))
            counts["alerts_raised"] += 1

        if counts["updated"]:
            db.add(AuditLog(
                actor="scheduler",
                action="financial_scrape",
                entity_type="vendor",
                entity_id=None,
                payload={"counts": counts, "feed": str(feed_path)},
            ))
        db.commit()

    # Rescore affected vendors so risk reflects new financial signal
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
    counts = poll_financial_feed(feed_path=args.feed, rescore_affected=not args.no_rescore)
    log.info("financial_scrape_complete", **counts)
    print("Financial scrape:")
    for k, v in counts.items():
        print(f"  {k:25s} {v:5d}")


if __name__ == "__main__":
    main()
