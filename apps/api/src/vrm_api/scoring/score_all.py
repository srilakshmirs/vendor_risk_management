"""CLI: score every vendor in the DB and persist a RiskAssessment row.

Usage:
    uv run python -m vrm_api.scoring.score_all
    uv run python -m vrm_api.scoring.score_all --replace   # wipe prior assessments first
"""

from __future__ import annotations

import argparse
from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ..db import SessionLocal
from ..logging_config import configure_logging, get_logger
from ..models import AuditLog, RiskAssessment, Vendor
from .context import vendor_context_from_orm
from .engine import score_vendor

configure_logging()
log = get_logger(__name__)


def run(replace: bool = False) -> dict[str, int]:
    today = date.today()
    counts = {"vendors": 0, "assessments_written": 0}

    with SessionLocal() as db:
        if replace:
            db.execute(delete(RiskAssessment))
            db.commit()
            log.info("replaced_prior_assessments")

        stmt = select(Vendor).options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.contracts),
            selectinload(Vendor.breaches),
        )
        for vendor in db.execute(stmt).scalars():
            ctx = vendor_context_from_orm(vendor)
            scored = score_vendor(ctx, today=today)

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
            counts["vendors"] += 1
            counts["assessments_written"] += 1

        db.add(AuditLog(
            actor="cli", action="score_all", entity_type="vendor", entity_id=None,
            payload={"counts": counts, "model_version": scored.model_version if counts["vendors"] else None},
        ))
        db.commit()

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true", help="Delete prior risk_assessments before scoring")
    args = parser.parse_args()
    counts = run(replace=args.replace)
    log.info("score_all_complete", **counts)
    print("Scored:")
    for k, v in counts.items():
        print(f"  {k:25s} {v:5d}")


if __name__ == "__main__":
    main()
