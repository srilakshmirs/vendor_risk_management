"""Anomaly classification — priority-ordered rules, first match wins.

These map 1:1 to the 7 anomaly types defined by the hackathon spec
(see data/vendor_labels.csv). Rules are designed to maximise RECALL on
CRITICAL/HIGH first, since the rubric explicitly penalises missed criticals
more than over-flagging.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable

from .context import VendorContext

# All possible anomaly labels + their severity (mirrors the data generator).
SEVERITY_BY_TYPE: dict[str, str] = {
    "BREACHED_VENDOR_HIGH_ACCESS": "CRITICAL",
    "VENDOR_UNDER_INVESTIGATION": "CRITICAL",
    "EXPIRED_CERTIFICATION": "HIGH",
    "HIGH_RISK_SCORE": "HIGH",
    "RECENTLY_BREACHED_VENDOR": "MEDIUM",
    "CONTRACT_EXPIRED_ACTIVE_ACCESS": "MEDIUM",
    "ELEVATED_RISK_VENDOR": "LOW",
    "NONE": "NONE",
}


@dataclass(frozen=True)
class RuleHit:
    anomaly_type: str
    severity: str
    rule_id: str
    rationale: str


Rule = Callable[[VendorContext, date], RuleHit | None]


# ── Individual rules ────────────────────────────────────────────────────
def rule_breached_high_access(ctx: VendorContext, today: date) -> RuleHit | None:
    if (
        ctx.breach_count_12mo > 0
        and ctx.last_breach_severity in {"High", "Critical"}
        and ctx.has_sensitive_data
        and ctx.access_level in {"ReadWrite", "FullAdmin"}
    ):
        return RuleHit(
            "BREACHED_VENDOR_HIGH_ACCESS",
            "CRITICAL",
            "R01",
            f"Recent {ctx.last_breach_severity} breach + {ctx.access_level} access to "
            f"{', '.join(sorted(ctx.data_classes))}",
        )
    return None


def rule_under_investigation(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.under_investigation:
        return RuleHit(
            "VENDOR_UNDER_INVESTIGATION",
            "CRITICAL",
            "R02",
            "Vendor flagged as under regulatory or security investigation",
        )
    return None


def rule_sbom_critical(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.sbom_critical_vulns > 0:
        return RuleHit(
            "CRITICAL_SBOM_VULNERABILITY",
            "CRITICAL",
            "R08",
            f"SBOM scan detected {ctx.sbom_critical_vulns} CRITICAL software vulnerabilities (e.g., Log4Shell, Heartbleed).",
        )
    return None


def rule_sbom_high(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.sbom_high_vulns > 0:
        return RuleHit(
            "HIGH_SBOM_VULNERABILITY",
            "HIGH",
            "R09",
            f"SBOM scan detected {ctx.sbom_high_vulns} HIGH software vulnerabilities.",
        )
    return None

def rule_expired_certification_sensitive(ctx: VendorContext, today: date) -> RuleHit | None:
    expired = ctx.expired_certs()
    if expired and ctx.has_sensitive_data:
        return RuleHit(
            "EXPIRED_CERTIFICATION",
            "HIGH",
            "R03",
            f"Expired {', '.join(expired)} while processing "
            f"{', '.join(sorted(ctx.data_classes & {'PII', 'PCI', 'PHI', 'Financial'}))}",
        )
    return None


def rule_high_risk_score(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.preliminary_risk_score > 80:
        return RuleHit(
            "HIGH_RISK_SCORE",
            "HIGH",
            "R04",
            f"Preliminary risk score {ctx.preliminary_risk_score}/100 exceeds 80 threshold",
        )
    return None


def rule_recently_breached_lower_scope(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.breach_count_12mo > 0:
        return RuleHit(
            "RECENTLY_BREACHED_VENDOR",
            "MEDIUM",
            "R05",
            f"Breach within 12 months (severity {ctx.last_breach_severity}); limited data scope",
        )
    return None


def rule_contract_expired_active_access(ctx: VendorContext, today: date) -> RuleHit | None:
    if ctx.contract_end and ctx.contract_end < today and ctx.access_level != "None":
        days = (today - ctx.contract_end).days
        return RuleHit(
            "CONTRACT_EXPIRED_ACTIVE_ACCESS",
            "MEDIUM",
            "R06",
            f"Contract ended {days}d ago; {ctx.access_level} access still provisioned",
        )
    return None


def rule_elevated_risk(ctx: VendorContext, today: date) -> RuleHit | None:
    if 65 <= ctx.preliminary_risk_score <= 80:
        return RuleHit(
            "ELEVATED_RISK_VENDOR",
            "LOW",
            "R07",
            f"Preliminary risk {ctx.preliminary_risk_score}/100 in elevated band (65–80)",
        )
    return None


# Order matters: most severe first. Within the same severity bucket, the more
# specific signal wins (HIGH_RISK_SCORE > EXPIRED_CERTIFICATION because a high
# composite score is a stronger statement than any single expired certificate).
RULE_PIPELINE: tuple[Rule, ...] = (
    rule_breached_high_access,           # CRITICAL
    rule_under_investigation,            # CRITICAL
    rule_sbom_critical,                  # CRITICAL
    rule_high_risk_score,                # HIGH — specific (prelim > 80)
    rule_sbom_high,                      # HIGH
    rule_expired_certification_sensitive, # HIGH — softer signal
    rule_recently_breached_lower_scope,  # MEDIUM
    rule_contract_expired_active_access, # MEDIUM
    rule_elevated_risk,                  # LOW
)


def classify(ctx: VendorContext, today: date) -> tuple[RuleHit | None, list[RuleHit]]:
    """Return (primary, all_hits). `primary` is the first hit (highest severity)."""
    hits: list[RuleHit] = []
    for rule in RULE_PIPELINE:
        hit = rule(ctx, today)
        if hit is not None:
            hits.append(hit)
    primary = hits[0] if hits else None
    return primary, hits


def traffic_light_from_severity(severity: str) -> str:
    return {
        "CRITICAL": "Red",
        "HIGH": "Red",
        "MEDIUM": "Yellow",
        "LOW": "Yellow",
        "NONE": "Green",
    }.get(severity, "Green")
