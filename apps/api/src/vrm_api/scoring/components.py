"""Five pure score components, each returning a 0-100 number + a reason trail.

Composed in ``engine.py`` via the weighted sum configured in ``settings``:
    weight_breach (.30) + weight_data_access (.25) + weight_compliance (.20)
  + weight_financial (.15) + weight_operational (.10) = 1.00

Each function takes a frozen ``VendorContext`` and the current date, returns
``(score: int, reasons: list[str])`` where ``reasons`` are human-readable
strings used to populate the narrative.
"""

from __future__ import annotations

from datetime import date, timedelta

from .context import ACCESS_LEVEL_WEIGHT, BREACH_SEV_WEIGHT, SENSITIVE_CLASSES, VendorContext


def _clip(v: float) -> int:
    return max(0, min(100, int(round(v))))


def breach_score(ctx: VendorContext, today: date) -> tuple[int, list[str]]:
    """How bad were the recent breaches?

    • Severity of the last breach dominates (Critical = 100, Low = 20).
    • Multiple breaches add a penalty.
    • Very recent breach (≤30 days) is a flat +20.
    """
    reasons: list[str] = []
    if ctx.breach_count_12mo == 0:
        return 0, []

    base = BREACH_SEV_WEIGHT.get(ctx.last_breach_severity, 30)
    count_penalty = min(40, (ctx.breach_count_12mo - 1) * 20)
    recency_penalty = 0
    if ctx.last_breach_date and (today - ctx.last_breach_date).days <= 30:
        recency_penalty = 20
        reasons.append(f"Breach detected within last 30 days ({ctx.last_breach_date.isoformat()})")
    elif ctx.last_breach_date:
        reasons.append(f"Breach within last 12 months ({ctx.last_breach_date.isoformat()})")

    if ctx.breach_count_12mo > 1:
        reasons.append(f"{ctx.breach_count_12mo} breach events in 12mo")

    reasons.append(f"Last breach severity: {ctx.last_breach_severity}")
    return _clip(base + count_penalty + recency_penalty), reasons


def data_access_score(ctx: VendorContext, today: date) -> tuple[int, list[str]]:
    """Blast radius if this vendor is compromised."""
    reasons: list[str] = []
    base = ACCESS_LEVEL_WEIGHT.get(ctx.access_level, 0)
    sensitive_hits = ctx.data_classes & SENSITIVE_CLASSES
    sensitive_bonus = 18 * len(sensitive_hits)

    reasons.append(f"{ctx.access_level} access to {len(ctx.systems_accessed) or 0} system(s)")
    if sensitive_hits:
        reasons.append(f"Handles sensitive data: {', '.join(sorted(sensitive_hits))}")
    if not ctx.gdpr_compliant and ("PII" in ctx.data_classes):
        reasons.append("Holds PII without GDPR compliance attestation")
        return _clip(base + sensitive_bonus + 20), reasons

    return _clip(base + sensitive_bonus), reasons


def compliance_score(ctx: VendorContext, today: date) -> tuple[int, list[str]]:
    """Certification + regulatory posture. Higher score = more gaps."""
    reasons: list[str] = []
    score = 0

    soc2 = ctx.cert("SOC2")
    iso = ctx.cert("ISO27001")
    pci = ctx.cert("PCI-DSS")

    # Expired certs are the biggest hit, especially with sensitive data.
    expired = ctx.expired_certs()
    if expired:
        weight_per_cert = 30 if ctx.has_sensitive_data else 18
        score += weight_per_cert * len(expired)
        reasons.append(f"Expired certification(s): {', '.join(expired)}")

    # Certs expiring within 30 days = pre-emptive warning.
    soon_expiring = [
        c.cert_type for c in ctx.certifications
        if c.status == "Certified" and c.expiry_date and 0 < (c.expiry_date - today).days <= 30
    ]
    if soon_expiring:
        score += 8 * len(soon_expiring)
        reasons.append(f"Certification(s) expiring within 30 days: {', '.join(soon_expiring)}")

    # Missing certs on a sensitive-data vendor.
    if ctx.has_sensitive_data:
        if soc2 and soc2.status == "NotCertified":
            score += 12
            reasons.append("No SOC 2 attestation despite sensitive data")
        if "PCI" in ctx.data_classes and pci and pci.status != "Certified":
            score += 15
            reasons.append("Processes PCI data without active PCI-DSS")

    if not ctx.gdpr_compliant:
        score += 20
        reasons.append("Not GDPR compliant")

    return _clip(score), reasons


def financial_score(ctx: VendorContext, today: date) -> tuple[int, list[str]]:
    """Vendor failure risk → service continuity risk to us."""
    reasons: list[str] = []
    # Invert: financial_health_score 100 = healthy, so risk = 100 - health.
    base_score = 100 - ctx.financial_health_score
    if ctx.financial_health_score < 50:
        reasons.append(f"Low financial health score ({ctx.financial_health_score}/100)")
    elif ctx.financial_health_score < 70:
        reasons.append(f"Moderate financial health ({ctx.financial_health_score}/100)")
    if ctx.under_investigation:
        base_score += 25
        reasons.append("Vendor is under active investigation")

    if not reasons:
        reasons.append("No financial flags")

    return min(100, base_score), reasons


def operational_score(ctx: VendorContext, today: date) -> tuple[int, list[str]]:
    """Process hygiene: contract validity, assessment freshness, tier."""
    reasons: list[str] = []
    score = 0

    if ctx.contract_end and ctx.contract_end < today and ctx.access_level != "None":
        score += 45
        reasons.append(
            f"Contract ended {ctx.contract_end.isoformat()} but {ctx.access_level} access still provisioned"
        )

    days_since = ctx.days_since_assessment(today)
    if days_since is not None and days_since > 365:
        score += 20
        reasons.append(f"Last assessed {days_since} days ago (>365d stale)")
    elif days_since is None:
        score += 10
        reasons.append("No assessment on record")

    if ctx.criticality == "Tier1":
        # Higher operational sensitivity for top-tier vendors
        score += 5

    # We heavily penalize known vulnerabilities in the supply chain.
    if ctx.sbom_critical_vulns > 0:
        score += 40
        reasons.append(f"SBOM contains {ctx.sbom_critical_vulns} CRITICAL vulnerabilities")
    elif ctx.sbom_high_vulns > 0:
        score += 25
        reasons.append(f"SBOM contains {ctx.sbom_high_vulns} HIGH vulnerabilities")

    return _clip(score), reasons


COMPONENT_FNS = {
    "breach": breach_score,
    "data_access": data_access_score,
    "compliance": compliance_score,
    "financial": financial_score,
    "operational": operational_score,
}
