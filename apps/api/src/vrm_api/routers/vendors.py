"""Vendor CRUD + list/filter endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from ..db import get_db
from ..models import Vendor, Certification
from ..models.risk import RiskAssessment
from ..schemas.vendor import VendorDetailOut, VendorListOut, VendorOut, CertStatsOut
from collections import defaultdict

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("", response_model=VendorListOut)
def list_vendors(
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Search in vendor_id, name"),
    vendor_type: str | None = None,
    country: str | None = None,
    criticality: str | None = None,
    min_risk: int | None = None,
    max_risk: int | None = None,
    under_investigation: bool | None = None,
    severity: str | None = Query(None, description="Filter by latest RiskAssessment severity"),
    missing_certs: bool = Query(False, description="Filter for vendors with missing/expired certifications"),
    missing_cert_type: str | None = Query(None, description="Specific certification type to filter for (e.g. SOC2)"),
    sort: str = Query("vendor_id:asc", description="Field:direction"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> VendorListOut:
    stmt = select(Vendor)
    count_stmt = select(func.count(Vendor.id))

    filters = []
    if q:
        like = f"%{q}%"
        filters.append(or_(Vendor.name.ilike(like), Vendor.vendor_id.ilike(like)))
    if vendor_type:
        filters.append(Vendor.vendor_type == vendor_type)
    if country:
        filters.append(Vendor.country == country)
    if criticality:
        filters.append(Vendor.criticality == criticality)
    if min_risk is not None:
        filters.append(Vendor.preliminary_risk_score >= min_risk)
    if max_risk is not None:
        filters.append(Vendor.preliminary_risk_score <= max_risk)
    if under_investigation is not None:
        filters.append(Vendor.under_investigation == under_investigation)
    if severity:
        # Subquery: find the latest RiskAssessment for each vendor and filter by severity
        latest_ra = (
            select(RiskAssessment.vendor_id)
            .where(RiskAssessment.severity == severity)
            .correlate(Vendor)
            .subquery()
        )
        filters.append(Vendor.id.in_(select(latest_ra.c.vendor_id)))
    if missing_certs or missing_cert_type:
        bad_certs = select(Certification.vendor_id).where(Certification.status.in_(["NotCertified", "Expired"]))
        if missing_cert_type:
            bad_certs = bad_certs.where(Certification.cert_type == missing_cert_type)
            
        bad_certs = bad_certs.correlate(Vendor).subquery()
        filters.append(Vendor.id.in_(select(bad_certs.c.vendor_id)))

    if filters:
        stmt = stmt.where(*filters)
        count_stmt = count_stmt.where(*filters)

    # sort=field:dir
    field, _, direction = sort.partition(":")
    column = getattr(Vendor, field, Vendor.preliminary_risk_score)
    stmt = stmt.order_by(column.desc() if direction == "desc" else column.asc())
    stmt = stmt.limit(limit).offset(offset)

    total = db.execute(count_stmt).scalar_one()
    items = db.execute(stmt).scalars().all()
    return VendorListOut(total=total, items=[VendorOut.model_validate(v) for v in items])


@router.get("/certifications/stats", response_model=list[CertStatsOut])
def get_cert_stats(db: Session = Depends(get_db)):
    stats = db.execute(
        select(Certification.cert_type, Certification.status, func.count(Certification.id))
        .group_by(Certification.cert_type, Certification.status)
    ).all()
    
    res = defaultdict(lambda: {"certified": 0, "expired": 0, "not_certified": 0, "pending": 0})
    for ct, status, count in stats:
        if status == "Certified": res[ct]["certified"] = count
        elif status == "Expired": res[ct]["expired"] = count
        elif status == "NotCertified": res[ct]["not_certified"] = count
        elif status == "Pending": res[ct]["pending"] = count
        
    out = []
    for ct in ["SOC2", "ISO27001", "PCI-DSS"]:
        data = res[ct]
        out.append(CertStatsOut(cert_type=ct, certified=data["certified"], expired=data["expired"], not_certified=data["not_certified"], pending=data["pending"]))
    return out


@router.get("/{vendor_id}", response_model=VendorDetailOut)
def get_vendor(vendor_id: str, db: Session = Depends(get_db)) -> VendorDetailOut:
    stmt = (
        select(Vendor)
        .where(Vendor.vendor_id == vendor_id)
        .options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.risk_assessments),
        )
    )
    vendor = db.execute(stmt).scalar_one_or_none()
    if vendor is None:
        raise HTTPException(status_code=404, detail=f"Vendor {vendor_id} not found")

    latest_risk = vendor.risk_assessments[0] if vendor.risk_assessments else None
    return VendorDetailOut(
        **VendorOut.model_validate(vendor).model_dump(),
        primary_contact_email=vendor.primary_contact_email,
        last_assessment_date=vendor.last_assessment_date,
        financial_health_score=vendor.financial_health_score,
        certifications=[c.__dict__ for c in vendor.certifications],
        data_access=[d.__dict__ for d in vendor.data_access],
        latest_risk=latest_risk.__dict__ if latest_risk else None,
    )
