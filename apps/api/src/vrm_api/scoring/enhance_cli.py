"""CLI: LLM-enhance the risk narrative for one or more vendors.

Bypasses the API — talks directly to SessionLocal so it works inside
``make demo-reset`` without the FastAPI process being up.

Usage:
    uv run python -m vrm_api.scoring.enhance_cli V0276 V0007
    uv run python -m vrm_api.scoring.enhance_cli --all-critical
    uv run python -m vrm_api.scoring.enhance_cli --severity CRITICAL --severity HIGH
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..db import SessionLocal
from ..logging_config import configure_logging, get_logger
from ..models import AuditLog, RiskAssessment, Vendor
from .context import vendor_context_from_orm
from .engine import score_vendor
from .narratives import enhance_narrative

configure_logging()
log = get_logger(__name__)


async def enhance_one(vendor_code: str) -> dict:
    """Enhance one vendor's latest narrative. Returns a result summary."""
    with SessionLocal() as db:
        stmt = (
            select(Vendor)
            .where(Vendor.vendor_id == vendor_code)
            .options(
                selectinload(Vendor.certifications),
                selectinload(Vendor.data_access),
                selectinload(Vendor.contracts),
                selectinload(Vendor.breaches),
                selectinload(Vendor.risk_assessments),
            )
        )
        vendor = db.execute(stmt).scalar_one_or_none()
        if vendor is None:
            return {"vendor_id": vendor_code, "status": "missing"}

        ctx = vendor_context_from_orm(vendor)
        scored = score_vendor(ctx)
        deterministic = scored.narrative

        text, meta = await enhance_narrative(ctx, scored, prefer_smart=True)

        latest = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None)
        if latest is None:
            # No prior scoring → insert one with the enhanced narrative
            latest = RiskAssessment(
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
                narrative=text,
                triggered_rules=scored.triggered_rules,
                model_version=scored.model_version,
            )
            db.add(latest)
            db.flush()
        else:
            latest.narrative = text

        # Provenance metadata
        components = dict(latest.components or {})
        meta_block = dict(components.get("meta", {}))
        meta_block.update({
            "narrative_source": meta.get("source"),
            "narrative_provider": meta.get("provider"),
            "narrative_model": meta.get("model"),
            "narrative_usage": meta.get("usage"),
            "deterministic_narrative": deterministic,
        })
        components["meta"] = meta_block
        latest.components = components

        db.add(AuditLog(
            actor="cli",
            action="narrative_enhance",
            entity_type="risk_assessment",
            entity_id=str(latest.id),
            payload={
                "vendor": vendor_code,
                "source": meta.get("source"),
                "model": meta.get("model"),
            },
        ))
        db.commit()

    return {
        "vendor_id": vendor_code,
        "status": "ok",
        "source": meta.get("source"),
        "provider": meta.get("provider"),
        "model": meta.get("model"),
        "chars": len(text),
    }


def _resolve_targets(args: argparse.Namespace) -> list[str]:
    if args.vendors:
        return args.vendors
    severities = list(args.severity or [])
    if args.all_critical:
        severities.append("CRITICAL")
    if not severities:
        return []
    severities = list({s.upper() for s in severities})
    with SessionLocal() as db:
        # Take the latest RiskAssessment per vendor — match on severity
        stmt = (
            select(Vendor.vendor_id, RiskAssessment.severity)
            .join(RiskAssessment, RiskAssessment.vendor_id == Vendor.id)
            .where(RiskAssessment.severity.in_(severities))
            .order_by(RiskAssessment.created_at.desc())
        )
        seen: set[str] = set()
        targets: list[str] = []
        for vid, _sev in db.execute(stmt).all():
            if vid not in seen:
                seen.add(vid)
                targets.append(vid)
        return targets


async def run(args: argparse.Namespace) -> int:
    targets = _resolve_targets(args)
    if not targets:
        print("No targets — pass vendor IDs or --all-critical / --severity CRITICAL")
        return 1

    print(f"Enhancing {len(targets)} vendor(s) — this calls the LLM, can be slow on Ollama")
    failures = 0
    for vid in targets:
        result = await enhance_one(vid)
        status = result["status"]
        if status == "ok":
            print(f"  ✓ {vid:6s}  source={result['source']:24s}  provider={result.get('provider')}  model={result.get('model')}  ({result.get('chars')} chars)")
        else:
            failures += 1
            print(f"  ✗ {vid:6s}  {status}")
    return 0 if failures == 0 else 2


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vendors", nargs="*", help="Vendor IDs to enhance (e.g. V0276 V0007)")
    parser.add_argument("--all-critical", action="store_true",
                        help="Shortcut for --severity CRITICAL")
    parser.add_argument("--severity", action="append",
                        help="Enhance every vendor whose latest assessment matches this severity (repeatable)")
    args = parser.parse_args()
    rc = asyncio.run(run(args))
    raise SystemExit(rc)


if __name__ == "__main__":
    main()
