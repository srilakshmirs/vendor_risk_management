"""Adapter — normalises a vendor (ORM or CSV row) into the scoring engine's input.

Keeping the engine ignorant of SQLAlchemy means we can score:
  • a single Vendor ORM object (for the API endpoint)
  • a Pandas row (for fast batch eval over the CSV)
  • a dict from a unit test
without three copies of the logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

# Sensitive data classes (drive several rules)
SENSITIVE_CLASSES = frozenset({"PII", "PCI", "PHI", "Financial"})

# Severity ordering used when ranking breach impact
BREACH_SEV_WEIGHT = {"None": 0, "Low": 20, "Medium": 50, "High": 80, "Critical": 100}

# Access level → numeric base risk
ACCESS_LEVEL_WEIGHT = {"None": 0, "Read": 20, "ReadWrite": 50, "FullAdmin": 80}


@dataclass(frozen=True)
class CertView:
    cert_type: str       # "SOC2" | "ISO27001" | "PCI-DSS"
    status: str          # "Certified" | "Expired" | "NotCertified" | "Pending"
    expiry_date: date | None


@dataclass(frozen=True)
class VendorContext:
    """Everything the scoring engine needs about one vendor."""

    vendor_id: str
    name: str
    vendor_type: str
    criticality: str
    annual_spend_usd: int
    under_investigation: bool
    financial_health_score: int   # 0-100, higher = healthier
    preliminary_risk_score: int   # 0-100, higher = riskier (analyst input)

    # Data access
    access_level: str
    data_classes: frozenset[str]
    systems_accessed: tuple[str, ...]
    gdpr_compliant: bool

    # Contract
    contract_start: date | None
    contract_end: date | None

    # Breach signal
    breach_count_12mo: int
    last_breach_date: date | None
    last_breach_severity: str   # "None" | "Low" | "Medium" | "High" | "Critical"

    # Certifications
    certifications: tuple[CertView, ...] = field(default_factory=tuple)

    # Audit
    last_assessment_date: date | None = None

    # ── Derived helpers ─────────────────────────────────────────────
    @property
    def has_sensitive_data(self) -> bool:
        return bool(self.data_classes & SENSITIVE_CLASSES)

    def cert(self, cert_type: str) -> CertView | None:
        for c in self.certifications:
            if c.cert_type == cert_type:
                return c
        return None

    def expired_certs(self) -> list[str]:
        return [c.cert_type for c in self.certifications if c.status == "Expired"]

    def days_since_assessment(self, today: date) -> int | None:
        if not self.last_assessment_date:
            return None
        return (today - self.last_assessment_date).days


# ── Builders ──────────────────────────────────────────────────────────
def _parse_classes(raw: str) -> frozenset[str]:
    return frozenset(c.strip() for c in (raw or "").split(";") if c.strip())


def _parse_tuple(raw: str) -> tuple[str, ...]:
    return tuple(s.strip() for s in (raw or "").split(";") if s.strip())


def _parse_date(raw: Any) -> date | None:
    if raw in (None, "", "nan"):
        return None
    if isinstance(raw, date):
        return raw
    try:
        return datetime.strptime(str(raw), "%Y-%m-%d").date()
    except ValueError:
        return None


def vendor_context_from_row(row: dict[str, Any]) -> VendorContext:
    """From a vendor_registry.csv row (dict). Fast path used by the evaluator."""
    certs = (
        CertView("SOC2", row.get("soc2_status", "NotCertified"), _parse_date(row.get("soc2_expiry_date"))),
        CertView("ISO27001", row.get("iso27001_status", "NotCertified"), _parse_date(row.get("iso27001_expiry_date"))),
        CertView("PCI-DSS", row.get("pci_dss_status", "NotCertified"), _parse_date(row.get("pci_dss_expiry_date"))),
    )
    return VendorContext(
        vendor_id=row["vendor_id"],
        name=row.get("vendor_name", ""),
        vendor_type=row.get("vendor_type", ""),
        criticality=row.get("criticality", "Tier3"),
        annual_spend_usd=int(row.get("annual_spend_usd") or 0),
        under_investigation=str(row.get("under_investigation", "No")).strip().lower() in {"yes", "true", "1"},
        financial_health_score=int(row.get("financial_health_score") or 70),
        preliminary_risk_score=int(row.get("preliminary_risk_score") or 0),
        access_level=row.get("data_access_level", "None"),
        data_classes=_parse_classes(row.get("data_classes", "")),
        systems_accessed=_parse_tuple(row.get("systems_accessed", "")),
        gdpr_compliant=str(row.get("gdpr_compliant", "Yes")).strip().lower() in {"yes", "true", "1"},
        contract_start=_parse_date(row.get("contract_start_date")),
        contract_end=_parse_date(row.get("contract_end_date")),
        breach_count_12mo=int(row.get("breach_history_12mo") or 0),
        last_breach_date=_parse_date(row.get("last_breach_date")),
        last_breach_severity=row.get("last_breach_severity") or "None",
        certifications=certs,
        last_assessment_date=_parse_date(row.get("last_assessment_date")),
    )


def vendor_context_from_orm(vendor: Any) -> VendorContext:
    """From an ORM Vendor (with relationships loaded)."""
    # data_access is a list; the seed creates exactly one row per vendor
    da = vendor.data_access[0] if vendor.data_access else None
    access_level = da.access_level if da else "None"
    data_classes = _parse_classes(da.data_classes) if da else frozenset()
    systems = _parse_tuple(da.systems_accessed) if da else ()
    gdpr = bool(da.gdpr_compliant) if da else True

    contract = vendor.contracts[0] if vendor.contracts else None
    contract_start = contract.start_date if contract else None
    contract_end = contract.end_date if contract else None

    # Latest breach
    breaches = sorted(vendor.breaches, key=lambda b: b.detected_at, reverse=True)
    last_breach = breaches[0] if breaches else None
    last_breach_date = last_breach.detected_at if last_breach else None
    last_breach_severity = last_breach.severity if last_breach else "None"

    certs = tuple(
        CertView(cert_type=c.cert_type, status=c.status, expiry_date=c.expiry_date)
        for c in vendor.certifications
    )

    return VendorContext(
        vendor_id=vendor.vendor_id,
        name=vendor.name,
        vendor_type=vendor.vendor_type,
        criticality=vendor.criticality,
        annual_spend_usd=vendor.annual_spend_usd,
        under_investigation=vendor.under_investigation,
        financial_health_score=vendor.financial_health_score,
        preliminary_risk_score=vendor.preliminary_risk_score,
        access_level=access_level,
        data_classes=data_classes,
        systems_accessed=systems,
        gdpr_compliant=gdpr,
        contract_start=contract_start,
        contract_end=contract_end,
        breach_count_12mo=len(breaches),
        last_breach_date=last_breach_date,
        last_breach_severity=last_breach_severity,
        certifications=certs,
        last_assessment_date=vendor.last_assessment_date,
    )
