"""Poll the mock breach feed → ingest new BreachEvent rows + raise alerts + re-score.

In production this would hit HIBP, CISA-KEV, vendor disclosure feeds, etc.
For the demo we use a static JSON file (data/breach_feed.json) — the contract
is the same, swapping in a real HTTP poller is a one-function change.

Idempotency key: (source, vendor_id, detected_at) — if a BreachEvent already
exists for that triplet, the entry is skipped.
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select

from ..config import settings
from ..db import SessionLocal, init_db
from ..logging_config import configure_logging, get_logger
from ..models import Alert, AuditLog, BreachEvent, Vendor

configure_logging()
log = get_logger(__name__)


DEFAULT_FEED_PATH = settings.data_dir / "breach_feed.json"

# Map breach severity (Low/Medium/High/Critical) → alert severity (LOW/MEDIUM/HIGH/CRITICAL)
SEVERITY_MAP = {
    "Low": "LOW",
    "Medium": "MEDIUM",
    "High": "HIGH",
    "Critical": "CRITICAL",
}


def _parse_date(raw: str) -> date:
    return datetime.strptime(raw, "%Y-%m-%d").date()


def _normalise_data_exposed(raw: Any) -> str:
    if isinstance(raw, list):
        return ";".join(str(x) for x in raw)
    return str(raw or "")


def _already_ingested(db, source: str, vendor_pk: int, detected_at: date) -> bool:
    stmt = (
        select(BreachEvent.id)
        .where(
            BreachEvent.source == source,
            BreachEvent.vendor_id == vendor_pk,
            BreachEvent.detected_at == detected_at,
        )
        .limit(1)
    )
    return db.execute(stmt).first() is not None


def poll_breach_feed(
    feed_path: Path | None = None,
    *,
    rescore_affected: bool = True,
) -> dict[str, int]:
    """Read the feed, insert new breaches + alerts, optionally rescore affected vendors."""
    feed_path = feed_path or DEFAULT_FEED_PATH
    init_db()
    counts = {"entries": 0, "ingested": 0, "skipped_existing": 0, "skipped_unknown_vendor": 0, "rescored": 0}

    if not feed_path.exists():
        log.warning("breach_feed_missing", path=str(feed_path))
        return counts

    entries: list[dict] = json.loads(feed_path.read_text())
    counts["entries"] = len(entries)

    affected_vendor_pks: set[int] = set()

    with SessionLocal() as db:
        # Pre-fetch vendors mentioned in the feed
        wanted_ids = [e.get("vendor_id") for e in entries if e.get("vendor_id")]
        vendors_by_vid = {
            v.vendor_id: v
            for v in db.execute(select(Vendor).where(Vendor.vendor_id.in_(wanted_ids))).scalars()
        }

        for entry in entries:
            vid = entry.get("vendor_id")
            vendor = vendors_by_vid.get(vid) if vid else None
            if vendor is None:
                counts["skipped_unknown_vendor"] += 1
                log.warning("breach_feed_unknown_vendor", vendor_id=vid)
                continue

            source = str(entry.get("source", "unknown"))
            detected_at = _parse_date(entry["detected_at"])
            severity = str(entry.get("severity", "Medium"))
            data_exposed = _normalise_data_exposed(entry.get("data_exposed"))
            summary = entry.get("summary") or ""

            if _already_ingested(db, source, vendor.id, detected_at):
                counts["skipped_existing"] += 1
                continue

            # 1) BreachEvent row (drives the scoring engine's breach-history signal)
            db.add(BreachEvent(
                vendor_id=vendor.id,
                source=source,
                severity=severity,
                detected_at=detected_at,
                data_exposed=data_exposed,
                summary=summary,
            ))

            # 2) Visible Alert (so the dashboard surfaces it immediately)
            alert_sev = SEVERITY_MAP.get(severity, "MEDIUM")
            db.add(Alert(
                vendor_id=vendor.id,
                alert_type="NEW_BREACH_DETECTED",
                severity=alert_sev,
                message=(
                    f"New breach detected via {source} on {detected_at.isoformat()} "
                    f"(severity {severity}). Data exposed: {data_exposed or 'unknown'}. "
                    f"{summary}"
                ),
                status="open",
                due_date=detected_at,
            ))

            counts["ingested"] += 1
            affected_vendor_pks.add(vendor.id)

        if counts["ingested"]:
            db.add(AuditLog(
                actor="scheduler",
                action="breach_poll",
                entity_type="breach_event",
                entity_id=None,
                payload={"counts": counts, "feed": str(feed_path)},
            ))
        db.commit()

    # 3) Re-score affected vendors so their scores reflect the new breaches.
    #    Local import — avoids pulling pandas at module load.
    if rescore_affected and affected_vendor_pks:
        from ..scoring.engine import score_vendor
        from ..scoring.context import vendor_context_from_orm
        from sqlalchemy.orm import selectinload
        from ..models import RiskAssessment

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
    parser.add_argument("--feed", type=Path, default=None, help="Path to breach feed JSON")
    parser.add_argument("--no-rescore", action="store_true", help="Skip re-scoring affected vendors")
    args = parser.parse_args()
    counts = poll_breach_feed(feed_path=args.feed, rescore_affected=not args.no_rescore)
    log.info("breach_poll_complete", **counts)
    print("Breach poll:")
    for k, v in counts.items():
        print(f"  {k:25s} {v:5d}")


if __name__ == "__main__":
    main()
