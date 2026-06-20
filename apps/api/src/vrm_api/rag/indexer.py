"""Index vendor profiles into the embeddings table.

One chunk per vendor — a compact summary covering every signal the retriever
might need to match against a user question. Re-running drops + reinserts so
the table always reflects the current ORM state.

CLI:
    uv run python -m vrm_api.rag.indexer            # reindex all vendors
"""

from __future__ import annotations

import argparse

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from ..db import SessionLocal, init_db
from ..logging_config import configure_logging, get_logger
from ..models import Embedding, Vendor
from .embedder import embed_many

configure_logging()
log = get_logger(__name__)


def build_vendor_chunk(vendor: Vendor) -> str:
    """Compact text representation packed with every retrieval-useful signal."""
    da = vendor.data_access[0] if vendor.data_access else None
    contract = vendor.contracts[0] if vendor.contracts else None
    latest_risk = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None) if vendor.risk_assessments else None

    parts: list[str] = []
    parts.append(
        f"{vendor.vendor_id} {vendor.name} ({vendor.vendor_type}, {vendor.country}, {vendor.criticality})"
    )
    parts.append(f"Annual spend: ${vendor.annual_spend_usd:,}.")

    if da:
        parts.append(
            f"Data access: {da.access_level} to {da.systems_accessed or 'no systems on record'}."
        )
        parts.append(
            f"Data classes handled: {da.data_classes or 'none on record'}. "
            f"GDPR: {'compliant' if da.gdpr_compliant else 'NOT compliant'}."
        )

    cert_strs = [f"{c.cert_type}={c.status}" for c in vendor.certifications]
    if cert_strs:
        parts.append(f"Certifications: {'; '.join(cert_strs)}.")

    expired = [c.cert_type for c in vendor.certifications if c.status == "Expired"]
    if expired:
        parts.append(f"EXPIRED CERTIFICATIONS: {', '.join(expired)}.")

    if vendor.under_investigation:
        parts.append("Vendor is UNDER ACTIVE INVESTIGATION.")

    breaches = sorted(vendor.breaches, key=lambda b: b.detected_at, reverse=True)
    if breaches:
        last = breaches[0]
        parts.append(
            f"Breach history: {len(breaches)} event(s) in 12mo; latest on {last.detected_at.isoformat()} "
            f"severity={last.severity}; data exposed: {last.data_exposed or 'unknown'}."
        )
    else:
        parts.append("No breach events recorded.")

    parts.append(
        f"Financial health: {vendor.financial_health_score}/100. "
        f"Preliminary risk: {vendor.preliminary_risk_score}/100."
    )

    if contract:
        parts.append(
            f"Contract: {contract.start_date.isoformat()} → {contract.end_date.isoformat()}, value ${contract.value_usd:,}."
        )

    if latest_risk:
        parts.append(
            f"Latest risk assessment: score {latest_risk.score}/100, severity {latest_risk.severity}, "
            f"anomaly={latest_risk.anomaly_type or 'NONE'}."
        )
        if latest_risk.narrative:
            parts.append(f"Narrative: {latest_risk.narrative}")

    return " ".join(parts)


def reindex_all(*, batch_size: int = 32) -> dict[str, int]:
    """Wipe + reindex every vendor's embedding row. Returns counts."""
    init_db()
    counts = {"vendors": 0, "chunks": 0}

    with SessionLocal() as db:
        # wipe vendor embeddings (keep other entity_types if any)
        db.execute(delete(Embedding).where(Embedding.entity_type == "vendor"))
        db.commit()

        stmt = select(Vendor).options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.contracts),
            selectinload(Vendor.breaches),
            selectinload(Vendor.risk_assessments),
        )
        vendors = list(db.execute(stmt).scalars())

        # batched embed for speed
        for start in range(0, len(vendors), batch_size):
            batch = vendors[start : start + batch_size]
            chunks = [build_vendor_chunk(v) for v in batch]
            vectors = embed_many(chunks)
            for vendor, chunk, vec in zip(batch, chunks, vectors, strict=True):
                db.add(Embedding(
                    entity_type="vendor",
                    entity_id=vendor.vendor_id,
                    chunk=chunk,
                    vector=vec,
                    source="indexer",
                ))
                counts["vendors"] += 1
                counts["chunks"] += 1
            db.commit()
            log.info("reindex_progress", done=start + len(batch), total=len(vendors))

    return counts


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=32)
    args = parser.parse_args()
    counts = reindex_all(batch_size=args.batch)
    log.info("reindex_complete", **counts)
    print("Reindexed:")
    for k, v in counts.items():
        print(f"  {k:10s} {v:5d}")


if __name__ == "__main__":
    main()
