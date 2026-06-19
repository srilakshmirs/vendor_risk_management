from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class CertificationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    cert_type: str
    status: str
    expiry_date: date | None


class DataAccessOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    access_level: str
    data_classes: str
    systems_accessed: str
    gdpr_compliant: bool


class RiskAssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    score: int
    traffic_light: str
    severity: str
    anomaly_type: str | None
    narrative: str | None
    components: dict
    triggered_rules: list[str]
    created_at: datetime


class VendorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vendor_id: str
    name: str
    vendor_type: str
    country: str
    criticality: str
    annual_spend_usd: int
    preliminary_risk_score: int
    under_investigation: bool
    status: str


class VendorDetailOut(VendorOut):
    primary_contact_email: str | None
    last_assessment_date: date | None
    financial_health_score: int
    certifications: list[CertificationOut] = []
    data_access: list[DataAccessOut] = []
    latest_risk: RiskAssessmentOut | None = None


class VendorListOut(BaseModel):
    total: int
    items: list[VendorOut]
