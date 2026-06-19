"""Scoring orchestrator — composes components + rules into a single ``ScoredVendor``."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from ..config import settings
from .components import COMPONENT_FNS
from .context import VendorContext
from .rules import RuleHit, classify, traffic_light_from_severity

MODEL_VERSION = "rules-v1.1"


@dataclass
class ScoredVendor:
    vendor_id: str
    score: int                           # 0-100, higher = riskier
    traffic_light: str                   # Red | Yellow | Green
    severity: str                        # CRITICAL | HIGH | MEDIUM | LOW | NONE
    anomaly_type: str | None             # the matched anomaly (or None)
    components: dict[str, int] = field(default_factory=dict)   # raw 0-100 per component
    weighted_components: dict[str, float] = field(default_factory=dict)
    triggered_rules: list[str] = field(default_factory=list)
    rule_hits: list[dict] = field(default_factory=list)        # full hit objects
    narrative: str = ""
    reasons: dict[str, list[str]] = field(default_factory=dict)
    model_version: str = MODEL_VERSION

    def as_dict(self) -> dict:
        return asdict(self)


def _weights() -> dict[str, float]:
    return {
        "breach": settings.weight_breach,
        "data_access": settings.weight_data_access,
        "compliance": settings.weight_compliance,
        "financial": settings.weight_financial,
        "operational": settings.weight_operational,
    }


def _build_narrative(ctx: VendorContext, primary: RuleHit | None, reasons: dict[str, list[str]]) -> str:
    """Deterministic 2-3 sentence narrative. (LLM enhancement is optional/separate.)"""
    if primary is None:
        return (
            f"{ctx.name} is within normal risk bands — no critical anomalies detected. "
            f"Continue routine quarterly monitoring."
        )

    headline = primary.rationale
    drivers = [r for bucket in reasons.values() for r in bucket][:3]
    drivers_str = "; ".join(drivers) if drivers else "no other significant drivers"

    action_by_severity = {
        "CRITICAL": "Immediate action required — revoke active credentials, trigger breach-response playbook, "
                    "and notify Procurement and Compliance within 24 hours.",
        "HIGH": "Schedule remediation within 7 days — re-attest the impacted certification, "
                "re-scope data access, and update the vendor record.",
        "MEDIUM": "Open a remediation ticket and re-assess within 30 days.",
        "LOW": "Increase monitoring cadence; re-assess at next quarterly review.",
        "NONE": "No action required.",
    }
    return (
        f"{ctx.name} — {primary.severity}: {headline}. "
        f"Other drivers: {drivers_str}. "
        f"{action_by_severity.get(primary.severity, '')}"
    ).strip()


def score_vendor(ctx: VendorContext, *, today: date | None = None) -> ScoredVendor:
    """Pure function — given a VendorContext, returns a ScoredVendor."""
    if today is None:
        today = date.today()

    weights = _weights()
    components: dict[str, int] = {}
    weighted: dict[str, float] = {}
    reasons: dict[str, list[str]] = {}

    composite = 0.0
    for name, fn in COMPONENT_FNS.items():
        value, why = fn(ctx, today)
        components[name] = value
        weighted[name] = round(value * weights[name], 2)
        reasons[name] = why
        composite += value * weights[name]

    score = int(round(composite))

    primary, hits = classify(ctx, today)
    if primary is None:
        anomaly_type, severity = "NONE", "NONE"
        triggered: list[str] = []
    else:
        anomaly_type, severity = primary.anomaly_type, primary.severity
        triggered = [h.rule_id for h in hits]

        # Critical/High rule-overrides also force the composite score upward, so the
        # numeric score never undersells the categorical classification.
        if severity == "CRITICAL":
            score = max(score, 85)
        elif severity == "HIGH":
            score = max(score, 70)

    return ScoredVendor(
        vendor_id=ctx.vendor_id,
        score=score,
        traffic_light=traffic_light_from_severity(severity),
        severity=severity,
        anomaly_type=anomaly_type,
        components=components,
        weighted_components=weighted,
        triggered_rules=triggered,
        rule_hits=[{"rule_id": h.rule_id, "anomaly_type": h.anomaly_type,
                    "severity": h.severity, "rationale": h.rationale} for h in hits],
        narrative=_build_narrative(ctx, primary, reasons),
        reasons=reasons,
    )
