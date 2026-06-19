"""Scoring engine + eval rubric tests."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from vrm_api.scoring import evaluate_all, score_vendor
from vrm_api.scoring.context import CertView, VendorContext

TODAY = date(2026, 6, 19)


def _make_ctx(**overrides) -> VendorContext:
    defaults = dict(
        vendor_id="V9999",
        name="Acme Corp",
        vendor_type="SaaS",
        criticality="Tier2",
        annual_spend_usd=500_000,
        under_investigation=False,
        financial_health_score=80,
        preliminary_risk_score=40,
        access_level="Read",
        data_classes=frozenset({"Internal"}),
        systems_accessed=("CRM",),
        gdpr_compliant=True,
        contract_start=TODAY - timedelta(days=300),
        contract_end=TODAY + timedelta(days=300),
        breach_count_12mo=0,
        last_breach_date=None,
        last_breach_severity="None",
        certifications=(
            CertView("SOC2", "Certified", TODAY + timedelta(days=200)),
            CertView("ISO27001", "Certified", TODAY + timedelta(days=200)),
            CertView("PCI-DSS", "NotCertified", None),
        ),
        last_assessment_date=TODAY - timedelta(days=60),
    )
    defaults.update(overrides)
    return VendorContext(**defaults)


# ── Per-rule tests ────────────────────────────────────────────────────
def test_breached_high_access_yields_critical():
    ctx = _make_ctx(
        breach_count_12mo=1,
        last_breach_date=TODAY - timedelta(days=10),
        last_breach_severity="Critical",
        data_classes=frozenset({"PII", "Financial"}),
        access_level="FullAdmin",
    )
    s = score_vendor(ctx, today=TODAY)
    assert s.anomaly_type == "BREACHED_VENDOR_HIGH_ACCESS"
    assert s.severity == "CRITICAL"
    assert s.score >= 85  # critical floor


def test_under_investigation_yields_critical():
    s = score_vendor(_make_ctx(under_investigation=True), today=TODAY)
    assert s.anomaly_type == "VENDOR_UNDER_INVESTIGATION"
    assert s.severity == "CRITICAL"


def test_high_risk_score_beats_expired_cert():
    """When both fire, HIGH_RISK_SCORE wins (more specific signal)."""
    ctx = _make_ctx(
        preliminary_risk_score=92,
        data_classes=frozenset({"PII"}),
        certifications=(
            CertView("SOC2", "Expired", TODAY - timedelta(days=10)),
            CertView("ISO27001", "Certified", TODAY + timedelta(days=200)),
            CertView("PCI-DSS", "NotCertified", None),
        ),
    )
    s = score_vendor(ctx, today=TODAY)
    assert s.anomaly_type == "HIGH_RISK_SCORE"
    assert s.severity == "HIGH"


def test_expired_cert_with_sensitive_data_is_high():
    ctx = _make_ctx(
        preliminary_risk_score=60,
        data_classes=frozenset({"PCI"}),
        certifications=(
            CertView("SOC2", "Certified", TODAY + timedelta(days=200)),
            CertView("ISO27001", "Certified", TODAY + timedelta(days=200)),
            CertView("PCI-DSS", "Expired", TODAY - timedelta(days=5)),
        ),
    )
    s = score_vendor(ctx, today=TODAY)
    assert s.anomaly_type == "EXPIRED_CERTIFICATION"
    assert s.severity == "HIGH"


def test_contract_expired_active_access_is_medium():
    ctx = _make_ctx(
        contract_end=TODAY - timedelta(days=20),
        access_level="ReadWrite",
        preliminary_risk_score=50,
        data_classes=frozenset({"Internal"}),
    )
    s = score_vendor(ctx, today=TODAY)
    assert s.anomaly_type == "CONTRACT_EXPIRED_ACTIVE_ACCESS"
    assert s.severity == "MEDIUM"


def test_elevated_risk_low_severity():
    s = score_vendor(_make_ctx(preliminary_risk_score=72), today=TODAY)
    assert s.anomaly_type == "ELEVATED_RISK_VENDOR"
    assert s.severity == "LOW"


def test_clean_vendor_yields_none():
    s = score_vendor(_make_ctx(), today=TODAY)
    assert s.anomaly_type == "NONE"
    assert s.severity == "NONE"
    assert s.traffic_light == "Green"


# ── Rubric gate — the headline test ──────────────────────────────────
def test_evaluator_passes_all_rubric_gates():
    """This single test is the contract with the hackathon judges."""
    rep = evaluate_all()
    assert rep.anomaly_accuracy >= 0.80, f"anomaly_accuracy={rep.anomaly_accuracy:.3f}"
    assert rep.recall_by_severity["CRITICAL"] >= 0.95, f"CRITICAL recall={rep.recall_by_severity['CRITICAL']:.3f}"
    assert rep.recall_by_severity["HIGH"] >= 0.80, f"HIGH recall={rep.recall_by_severity['HIGH']:.3f}"
    assert rep.binary_f1 >= 0.85, f"binary_f1={rep.binary_f1:.3f}"
    assert all(rep.rubric_pass.values()), f"Failing gates: {rep.rubric_pass}"


def test_engine_is_deterministic():
    ctx = _make_ctx(preliminary_risk_score=72)
    a = score_vendor(ctx, today=TODAY)
    b = score_vendor(ctx, today=TODAY)
    assert a.as_dict() == b.as_dict()
