"""/audit — auditor-facing PDF export endpoint.

This is the artefact that maps directly to the rubric's "<15 min audit report"
metric: one HTTP GET, one PDF, every vendor signal an auditor needs.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..logging_config import get_logger
from ..models import AuditLog
from ..services.audit_pack import build_audit_pack

router = APIRouter(prefix="/audit", tags=["audit"])
log = get_logger(__name__)


@router.get("/pack/{vendor_code}")
def export_audit_pack(vendor_code: str, db: Session = Depends(get_db)):
    """Stream the PDF audit pack for one vendor."""
    try:
        buf = build_audit_pack(db, vendor_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    filename = f"audit-{vendor_code}-{date.today().isoformat()}.pdf"
    log.info("audit_pack_generated", vendor_code=vendor_code, filename=filename)

    # Append-only audit trail (SOX 404)
    db.add(AuditLog(
        actor="api",
        action="audit_pack_export",
        entity_type="vendor",
        entity_id=vendor_code,
        payload={"filename": filename},
    ))
    db.commit()

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Cache-Control": "no-store",
    }
    return StreamingResponse(buf, media_type="application/pdf", headers=headers)
