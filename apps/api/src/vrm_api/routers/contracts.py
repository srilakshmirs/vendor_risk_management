"""Contract intelligence — upload a PDF, get structured risk metadata.

Improvements over the v1 of this router:
  * Hardened input validation (file.filename can be None)
  * Granular exception handling (ValueError → 400; everything else → 500 with
    a generic message — internal error details no longer leak to the client)
  * Optional `vendor_id` form field — when present, the extraction is persisted
    to the most recent `Contract.extracted_terms` for that vendor so the data
    survives a page refresh
  * Uses the project logger (structured + JSON-rendered in prod)
"""

from __future__ import annotations

import io
from datetime import datetime
from typing import Any

import pypdf
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..llm import get_llm
from ..logging_config import get_logger
from ..models import AuditLog, Contract, Vendor

router = APIRouter(prefix="/contracts", tags=["Contracts"])
log = get_logger(__name__)

# Hard cap on text sent to the LLM — protects against runaway PDFs blowing the context window.
MAX_TEXT_CHARS = 30_000

SCHEMA_HINT = """
{
    "data_access_permissions": ["list of inferred or explicit data access rights"],
    "compliance_obligations": ["list of certifications, audits, or compliance duties mentioned"],
    "sla_uptime_percentage": "extracted SLA uptime % or null if not found",
    "renewal_date": "YYYY-MM-DD or null if not found",
    "termination_conditions": "brief summary of termination rights"
}
"""

SYSTEM_PROMPT = """\
You are an expert Third-Party Risk Management (TPRM) legal analyst.
Your job is to read raw text extracted from a vendor contract, Master Services
Agreement (MSA), or Data Processing Agreement (DPA), and extract key risk
indicators and obligations.

Be precise. If a value is not found in the text, return null or an empty list
rather than hallucinating.
"""


def _extract_pdf_text(content: bytes) -> str:
    """Read all pages, join with double-newline, truncate to MAX_TEXT_CHARS."""
    try:
        pdf = pypdf.PdfReader(io.BytesIO(content))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Not a valid PDF: {exc}") from exc

    chunks: list[str] = []
    for page in pdf.pages:
        text = page.extract_text()
        if text:
            chunks.append(text)
    full_text = "\n\n".join(chunks).strip()

    if not full_text:
        raise ValueError("No extractable text in the PDF (scanned image without OCR?)")

    if len(full_text) > MAX_TEXT_CHARS:
        log.warning("contract_text_truncated", chars=len(full_text), max=MAX_TEXT_CHARS)
        full_text = full_text[:MAX_TEXT_CHARS] + "\n...[TRUNCATED]..."

    return full_text


def _persist_extraction(
    db: Session,
    vendor_code: str,
    filename: str,
    extracted: dict[str, Any],
) -> dict[str, Any]:
    """Save the LLM output onto the most recent Contract row for this vendor."""
    vendor = db.execute(
        select(Vendor).where(Vendor.vendor_id == vendor_code)
    ).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_code} not found")

    contract = db.execute(
        select(Contract)
        .where(Contract.vendor_id == vendor.id)
        .order_by(Contract.start_date.desc())
        .limit(1)
    ).scalar_one_or_none()
    if contract is None:
        raise HTTPException(
            status_code=404,
            detail=f"Vendor {vendor_code} has no contract on record to attach extraction to",
        )

    # Preserve any prior extraction history so re-uploads don't silently overwrite
    payload = {
        "fields": extracted,
        "source_filename": filename,
        "extracted_at": datetime.utcnow().isoformat() + "Z",
    }
    existing = dict(contract.extracted_terms or {})
    history = list(existing.get("history", []))
    if existing.get("fields"):
        history.append({
            "fields": existing["fields"],
            "source_filename": existing.get("source_filename"),
            "extracted_at": existing.get("extracted_at"),
        })
    payload["history"] = history
    contract.extracted_terms = payload

    db.add(AuditLog(
        actor="api",
        action="contract_extract",
        entity_type="contract",
        entity_id=str(contract.id),
        payload={"vendor": vendor_code, "filename": filename, "field_count": len(extracted)},
    ))
    db.commit()
    return payload


@router.post("/extract")
async def extract_contract_obligations(
    file: UploadFile = File(..., description="Vendor contract PDF (MSA, DPA, or similar)"),
    vendor_id: str | None = Form(
        default=None,
        description="Optional vendor code (e.g. V0276). When supplied, the extraction is persisted "
                    "to the vendor's most recent Contract row.",
    ),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Upload a PDF → structured risk metadata via the configured LLM."""

    # 1) Input validation — filename can be None on some clients
    filename = (file.filename or "").strip()
    if not filename or not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported (filename must end with .pdf).",
        )

    # 2) Read + extract text
    try:
        content = await file.read()
        full_text = _extract_pdf_text(content)
    except ValueError as exc:
        # User-facing validation error — surface the reason
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        log.exception("contract_pdf_read_failed", filename=filename, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to read PDF — see server logs.",
        ) from exc

    # 3) LLM extraction
    log.info("contract_extract_start", filename=filename, chars=len(full_text), vendor_id=vendor_id)
    user_prompt = f"Extract structured risk metadata from the following contract text:\n\n{full_text}"

    try:
        provider = get_llm()
        extracted = await provider.extract_json(
            system=SYSTEM_PROMPT,
            user=user_prompt,
            schema_hint=SCHEMA_HINT,
            max_tokens=1024,
            prefer_smart=True,
        )
    except Exception as exc:  # noqa: BLE001
        log.exception("contract_llm_call_failed", filename=filename, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM extraction failed — see server logs.",
        ) from exc

    # 4) Optional persistence
    response: dict[str, Any] = {"fields": extracted, "source_filename": filename}
    if vendor_id:
        try:
            persisted = _persist_extraction(db, vendor_id, filename, extracted)
            response = {**persisted, "persisted": True}
            log.info(
                "contract_extract_persisted",
                vendor_id=vendor_id,
                field_count=len(extracted),
            )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("contract_persist_failed", vendor_id=vendor_id, error=str(exc))
            # Don't fail the whole request — the extraction still happened
            response["persistence_error"] = "Persist failed; extraction returned for display only."
    else:
        response["persisted"] = False

    return response
