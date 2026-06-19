"""CSV → DB ingestion. Idempotent: re-running upserts on vendor_id.

Usage:
    uv run python -m vrm_api.seeds.ingest_csv          # uses data/vendor_registry.csv
    uv run python -m vrm_api.seeds.ingest_csv --reset  # drop + recreate tables first
"""

from __future__ import annotations

import argparse
import csv
from datetime import date, datetime
from pathlib import Path

from sqlalchemy import delete, select

from ..config import settings
from ..db import SessionLocal, engine, init_db
from ..logging_config import configure_logging, get_logger
from ..models import (
    Alert,
    AuditLog,
    Base,
    BreachEvent,
    Certification,
    Contract,
    DataAccess,
    RiskAssessment,
    Vendor,
)

configure_logging()
log = get_logger(__name__)


def _to_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _to_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"yes", "true", "1", "y"}


def _to_int(value: str | None, default: int = 0) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


def reset_schema() -> None:
    log.warning("dropping_all_tables")
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def ingest(csv_path: Path) -> dict[str, int]:
    if not csv_path.exists():
        raise FileNotFoundError(f"vendor registry CSV not found: {csv_path}")

    init_db()
    counts = {"vendors": 0, "certifications": 0, "data_access": 0, "breaches": 0, "contracts": 0}

    with SessionLocal() as db, csv_path.open() as f:
        reader = csv.DictReader(f)
        # wipe transactional data so re-runs are idempotent
        db.execute(delete(Certification))
        db.execute(delete(DataAccess))
        db.execute(delete(Contract))
        db.execute(delete(BreachEvent))
        db.execute(delete(RiskAssessment))
        db.execute(delete(Alert))
        db.commit()

        # upsert vendors by vendor_id
        existing = {v.vendor_id: v for v in db.execute(select(Vendor)).scalars().all()}

        for row in reader:
            vid = row["vendor_id"]
            vendor = existing.get(vid)
            if vendor is None:
                vendor = Vendor(vendor_id=vid)
                db.add(vendor)

            vendor.name = row["vendor_name"]
            vendor.vendor_type = row["vendor_type"]
            vendor.country = row["country"]
            vendor.criticality = row["criticality"]
            vendor.annual_spend_usd = _to_int(row["annual_spend_usd"])
            vendor.primary_contact_email = row.get("primary_contact_email")
            vendor.last_assessment_date = _to_date(row.get("last_assessment_date"))
            vendor.under_investigation = _to_bool(row["under_investigation"])
            vendor.financial_health_score = _to_int(row["financial_health_score"])
            vendor.preliminary_risk_score = _to_int(row["preliminary_risk_score"])
            vendor.status = "active"
            db.flush()
            counts["vendors"] += 1

            # Contract
            db.add(Contract(
                vendor_id=vendor.id,
                start_date=_to_date(row["contract_start_date"]) or date.today(),
                end_date=_to_date(row["contract_end_date"]) or date.today(),
                value_usd=_to_int(row["contract_value_usd"]),
            ))
            counts["contracts"] += 1

            # Certifications (3 rows per vendor)
            for cert_type, status_col, expiry_col in (
                ("SOC2", "soc2_status", "soc2_expiry_date"),
                ("ISO27001", "iso27001_status", "iso27001_expiry_date"),
                ("PCI-DSS", "pci_dss_status", "pci_dss_expiry_date"),
            ):
                db.add(Certification(
                    vendor_id=vendor.id,
                    cert_type=cert_type,
                    status=row[status_col],
                    expiry_date=_to_date(row[expiry_col]),
                ))
                counts["certifications"] += 1

            # Data access
            db.add(DataAccess(
                vendor_id=vendor.id,
                access_level=row["data_access_level"],
                data_classes=row["data_classes"],
                systems_accessed=row["systems_accessed"],
                gdpr_compliant=_to_bool(row["gdpr_compliant"]),
            ))
            counts["data_access"] += 1

            # Breach event (only if present)
            if _to_int(row.get("breach_history_12mo", "0")) > 0 and row.get("last_breach_date"):
                db.add(BreachEvent(
                    vendor_id=vendor.id,
                    source="seed",
                    severity=row.get("last_breach_severity") or "Medium",
                    detected_at=_to_date(row["last_breach_date"]) or date.today(),
                    data_exposed=row["data_classes"],
                    summary=f"Imported from registry seed; {row.get('breach_history_12mo')} breach(es) in last 12mo.",
                ))
                counts["breaches"] += 1

        db.add(AuditLog(actor="seed", action="csv_ingest", entity_type="vendor",
                        entity_id=None, payload={"counts": counts, "source": str(csv_path)}))
        db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="Drop and recreate all tables first")
    parser.add_argument("--csv", type=Path, default=settings.vendor_registry_csv)
    args = parser.parse_args()

    if args.reset:
        reset_schema()
    counts = ingest(args.csv)
    log.info("ingest_complete", **counts)
    print("Ingested:")
    for k, v in counts.items():
        print(f"  {k:15s} {v:5d}")


if __name__ == "__main__":
    main()
