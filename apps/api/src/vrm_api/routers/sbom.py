"""SBOM endpoints — upload and retrieve Software Bill of Materials."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import AuditLog, Sbom, SbomComponent, Vendor
from ..scoring import score_vendor, vendor_context_from_orm
from ..services.email_service import notify_critical_high, notify_resolution
from ..services.vuln_db import check_component

router = APIRouter(prefix="/sbom", tags=["sbom"])


class VulnOut(BaseModel):
    cve_id: str
    severity: str
    description: str


class ComponentOut(BaseModel):
    name: str
    version: str
    type: str | None
    highest_severity: str | None
    vulnerabilities: list[VulnOut]


class SbomOut(BaseModel):
    id: int
    format: str
    version: str | None
    created_at: str
    components: list[ComponentOut]


# ── Helpers ───────────────────────────────────────────────────────────
def _parse_cyclonedx(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract components from a CycloneDX JSON."""
    components = []
    for comp in data.get("components", []):
        name = comp.get("name")
        version = comp.get("version")
        if name and version:
            components.append({
                "name": name,
                "version": version,
                "type": comp.get("type"),
            })
    return components


def _parse_spdx(data: dict[str, Any]) -> list[dict[str, str]]:
    """Extract components from an SPDX JSON."""
    components = []
    for pkg in data.get("packages", []):
        name = pkg.get("name")
        version = pkg.get("versionInfo")
        if name and version:
            components.append({
                "name": name,
                "version": version,
                "type": "package", # SPDX doesn't have a direct equivalent to CycloneDX type always
            })
    return components


# ── Endpoints ─────────────────────────────────────────────────────────

@router.post("/{vendor_id}/upload")
async def upload_sbom(vendor_id: str, file: UploadFile, db: Session = Depends(get_db)):
    """Upload an SBOM JSON file (CycloneDX or SPDX) for a vendor."""
    vendor = db.execute(select(Vendor).where(Vendor.vendor_id == vendor_id)).scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")

    content = await file.read()
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    # Determine format
    if "bomFormat" in data and data["bomFormat"] == "CycloneDX":
        format_name = "CycloneDX"
        version = data.get("specVersion")
        parsed_components = _parse_cyclonedx(data)
    elif "spdxVersion" in data:
        format_name = "SPDX"
        version = data.get("spdxVersion")
        parsed_components = _parse_spdx(data)
    else:
        # Fallback naive parse: look for any array of objects with name/version
        format_name = "Custom"
        version = "1.0"
        parsed_components = []
        if "components" in data and isinstance(data["components"], list):
             parsed_components = _parse_cyclonedx(data)
        elif "dependencies" in data and isinstance(data["dependencies"], list):
            for dep in data["dependencies"]:
                 if isinstance(dep, dict) and "name" in dep and "version" in dep:
                     parsed_components.append({
                         "name": dep["name"],
                         "version": dep["version"],
                         "type": dep.get("type", "dependency")
                     })
        
        if not parsed_components:
             raise HTTPException(status_code=400, detail="Could not determine SBOM format (CycloneDX or SPDX expected)")

    # Delete existing SBOMs for this vendor (keep latest only for simplicity)
    db.execute(select(Sbom).where(Sbom.vendor_id == vendor.id).execution_options(synchronize_session=False)).scalars()
    # Let cascade handle deletion, we just delete the root Sbom object
    existing_sboms = db.execute(select(Sbom).where(Sbom.vendor_id == vendor.id)).scalars().all()
    for es in existing_sboms:
        db.delete(es)
        
    db.flush()

    # Create new Sbom
    sbom = Sbom(
        vendor_id=vendor.id,
        format=format_name,
        version=version,
    )
    db.add(sbom)
    db.flush() # flush to get sbom.id

    critical_count = 0
    high_count = 0

    # Add components and check vulnerabilities
    for pc in parsed_components:
        vulns = check_component(pc["name"], pc["version"])
        
        highest_sev = None
        vuln_json = None
        
        if vulns:
            vuln_dicts = [{"cve_id": v.cve_id, "severity": v.severity, "description": v.description} for v in vulns]
            vuln_json = json.dumps(vuln_dicts)
            
            # Find highest severity
            sev_rank = {"NONE": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
            highest_sev = max((v.severity for v in vulns), key=lambda s: sev_rank.get(s, 0), default=None)
            
            if highest_sev == "CRITICAL":
                critical_count += 1
            elif highest_sev == "HIGH":
                high_count += 1

        db.add(SbomComponent(
            sbom_id=sbom.id,
            name=pc["name"],
            version=pc["version"],
            type=pc.get("type"),
            vulnerabilities=vuln_json,
            highest_severity=highest_sev
        ))

    db.add(AuditLog(
        actor="api",
        action="sbom_upload",
        entity_type="vendor",
        entity_id=str(vendor.id),
        payload={"format": format_name, "components_count": len(parsed_components), "critical_vulns": critical_count, "high_vulns": high_count},
    ))
    db.commit()

    # Trigger re-score now that SBOM is updated
    from sqlalchemy.orm import selectinload
    from ..routers.risk import _persist
    
    vendor_reloaded = db.execute(
        select(Vendor)
        .where(Vendor.id == vendor.id)
        .options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.contracts),
            selectinload(Vendor.breaches),
            selectinload(Vendor.risk_assessments),
            selectinload(Vendor.sboms).selectinload(Sbom.components),
        )
    ).scalar_one()

    # Capture previous severity for resolution detection
    prev_assessment = max(vendor_reloaded.risk_assessments, key=lambda r: r.created_at, default=None) if vendor_reloaded.risk_assessments else None
    prev_severity = prev_assessment.severity if prev_assessment else None
    prev_score = prev_assessment.score if prev_assessment else None

    ctx = vendor_context_from_orm(vendor_reloaded)
    scored = score_vendor(ctx)
    _persist(db, vendor_reloaded, scored)
    db.commit()
    
    # Email notifications
    notify_critical_high(scored, vendor_reloaded)
    if prev_severity in {"CRITICAL", "HIGH"} and scored.severity not in {"CRITICAL", "HIGH"}:
        notify_resolution(vendor_reloaded, prev_severity, scored.severity, scored.score, prev_score)

    return {
        "status": "success",
        "message": f"SBOM processed. Found {len(parsed_components)} components.",
        "vulnerabilities": {"CRITICAL": critical_count, "HIGH": high_count},
        "new_risk_score": scored.score,
        "new_severity": scored.severity
    }


@router.get("/{vendor_id}", response_model=list[SbomOut])
def get_sboms(vendor_id: str, db: Session = Depends(get_db)):
    """Get the latest SBOM and vulnerability data for a vendor."""
    vendor = db.execute(select(Vendor).where(Vendor.vendor_id == vendor_id)).scalar_one_or_none()
    if not vendor:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")

    from sqlalchemy.orm import selectinload
    sboms = db.execute(
        select(Sbom)
        .where(Sbom.vendor_id == vendor.id)
        .options(selectinload(Sbom.components))
        .order_by(Sbom.created_at.desc())
    ).scalars().all()

    results = []
    for s in sboms:
        comps_out = []
        for c in s.components:
            vulns = json.loads(c.vulnerabilities) if c.vulnerabilities else []
            comps_out.append(ComponentOut(
                name=c.name,
                version=c.version,
                type=c.type,
                highest_severity=c.highest_severity,
                vulnerabilities=[VulnOut(**v) for v in vulns]
            ))
        
        results.append(SbomOut(
            id=s.id,
            format=s.format,
            version=s.version,
            created_at=s.created_at.isoformat(),
            components=comps_out
        ))
        
    return results
