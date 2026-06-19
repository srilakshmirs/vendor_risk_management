# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "faker>=30",
# ]
# ///
"""
Generate vendor_registry.csv + vendor_labels.csv matching the Société Générale
Third-Party Vendor Risk Management hackathon spec.

Deterministic (seed=42). Run:  uv run data/generate_mock_data.py
"""
from __future__ import annotations

import csv
import random
from dataclasses import dataclass, asdict
from datetime import date, timedelta
from pathlib import Path

from faker import Faker

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SEED = 42
N_VENDORS = 400
TODAY = date(2026, 6, 19)
OUT_DIR = Path(__file__).parent

VENDOR_TYPES = [
    "CloudProvider", "SaaS", "Contractor", "MSP", "PaymentProcessor",
    "IntegrationPartner", "Hardware", "Consulting", "DataAnalytics", "Marketing",
]
COUNTRIES = ["US", "UK", "DE", "FR", "IN", "SG", "JP", "AU", "CA", "NL", "IE", "BR"]
CRITICALITY = ["Tier1", "Tier2", "Tier3", "Tier4"]
ACCESS_LEVELS = ["None", "Read", "ReadWrite", "FullAdmin"]
DATA_CLASS_POOL = ["PII", "PCI", "PHI", "Financial", "Internal", "Public"]
SENSITIVE_CLASSES = {"PII", "PCI", "PHI", "Financial"}
SYSTEMS_POOL = [
    "CoreBanking", "CRM", "DataWarehouse", "PaymentsAPI", "HRIS",
    "EmailGateway", "TradingPlatform", "CustomerPortal", "DocumentVault",
    "IdentityProvider", "AnalyticsLake", "MarketingCloud",
]
CERT_STATES = ["Certified", "Expired", "NotCertified", "Pending"]

ANOMALY_TYPES = [
    "BREACHED_VENDOR_HIGH_ACCESS",   # CRITICAL
    "VENDOR_UNDER_INVESTIGATION",    # CRITICAL
    "EXPIRED_CERTIFICATION",         # HIGH
    "HIGH_RISK_SCORE",               # HIGH
    "RECENTLY_BREACHED_VENDOR",      # MEDIUM
    "CONTRACT_EXPIRED_ACTIVE_ACCESS",# MEDIUM
    "ELEVATED_RISK_VENDOR",          # LOW
    "NONE",
]

SEVERITY_BY_TYPE = {
    "BREACHED_VENDOR_HIGH_ACCESS": "CRITICAL",
    "VENDOR_UNDER_INVESTIGATION": "CRITICAL",
    "EXPIRED_CERTIFICATION": "HIGH",
    "HIGH_RISK_SCORE": "HIGH",
    "RECENTLY_BREACHED_VENDOR": "MEDIUM",
    "CONTRACT_EXPIRED_ACTIVE_ACCESS": "MEDIUM",
    "ELEVATED_RISK_VENDOR": "LOW",
    "NONE": "NONE",
}

# Target distribution: ~80% anomalies (per spec — intentionally high flag rate
# reflects a ranked risk register, not a binary safe/unsafe model).
TARGET_DISTRIBUTION = {
    "BREACHED_VENDOR_HIGH_ACCESS": 0.08,
    "VENDOR_UNDER_INVESTIGATION": 0.05,
    "EXPIRED_CERTIFICATION": 0.18,
    "HIGH_RISK_SCORE": 0.12,
    "RECENTLY_BREACHED_VENDOR": 0.10,
    "CONTRACT_EXPIRED_ACTIVE_ACCESS": 0.10,
    "ELEVATED_RISK_VENDOR": 0.17,
    "NONE": 0.20,
}


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------
@dataclass
class Vendor:
    vendor_id: str
    vendor_name: str
    vendor_type: str
    country: str
    criticality: str
    annual_spend_usd: int
    contract_start_date: str
    contract_end_date: str
    contract_value_usd: int
    data_access_level: str
    data_classes: str
    systems_accessed: str
    soc2_status: str
    soc2_expiry_date: str
    iso27001_status: str
    iso27001_expiry_date: str
    pci_dss_status: str
    pci_dss_expiry_date: str
    gdpr_compliant: str
    breach_history_12mo: int
    last_breach_date: str
    last_breach_severity: str
    under_investigation: str
    financial_health_score: int
    preliminary_risk_score: int
    primary_contact_email: str
    last_assessment_date: str


@dataclass
class Label:
    vendor_id: str
    is_anomaly: int
    anomaly_type: str
    severity: str
    expired_cert_flag: int
    explanation: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def rand_date_between(rng: random.Random, start: date, end: date) -> date:
    delta = (end - start).days
    return start + timedelta(days=rng.randint(0, max(delta, 0)))


def cert_dates_for(rng: random.Random, status: str) -> str:
    """Return ISO date string for a certification expiry given its status."""
    if status == "Certified":
        return rand_date_between(rng, TODAY + timedelta(days=30), TODAY + timedelta(days=540)).isoformat()
    if status == "Expired":
        return rand_date_between(rng, TODAY - timedelta(days=400), TODAY - timedelta(days=1)).isoformat()
    if status == "Pending":
        return rand_date_between(rng, TODAY + timedelta(days=7), TODAY + timedelta(days=120)).isoformat()
    return ""  # NotCertified


def build_vendor(rng: random.Random, faker: Faker, idx: int, target_anomaly: str) -> tuple[Vendor, Label]:
    """Generate a vendor whose attributes deterministically yield `target_anomaly`."""
    vendor_id = f"V{idx:04d}"
    vendor_type = rng.choice(VENDOR_TYPES)
    vendor_name = f"{faker.company().replace(',', '')} {rng.choice(['Ltd', 'Inc', 'GmbH', 'SAS', 'BV', 'Pvt'])}"
    country = rng.choice(COUNTRIES)
    criticality = rng.choices(CRITICALITY, weights=[0.15, 0.35, 0.35, 0.15])[0]
    annual_spend = rng.choice([50_000, 120_000, 250_000, 500_000, 1_200_000, 3_500_000, 8_000_000])
    contract_start = rand_date_between(rng, TODAY - timedelta(days=1100), TODAY - timedelta(days=30))
    # default contract end is in the future
    contract_end = contract_start + timedelta(days=rng.choice([365, 730, 1095]))
    contract_value = int(annual_spend * rng.uniform(1.5, 3.5))

    # Data access defaults
    n_classes = rng.randint(1, 3)
    data_classes_list = rng.sample(DATA_CLASS_POOL, k=n_classes)
    systems_accessed = rng.sample(SYSTEMS_POOL, k=rng.randint(1, 4))
    access_level = rng.choices(ACCESS_LEVELS, weights=[0.10, 0.35, 0.40, 0.15])[0]

    # Certifications — start with healthy mix
    soc2 = rng.choices(CERT_STATES, weights=[0.55, 0.10, 0.25, 0.10])[0]
    iso = rng.choices(CERT_STATES, weights=[0.45, 0.10, 0.35, 0.10])[0]
    pci = rng.choices(CERT_STATES, weights=[0.30, 0.05, 0.60, 0.05])[0]

    gdpr = rng.choices(["Yes", "No"], weights=[0.80, 0.20])[0]
    breach_count = 0
    last_breach_date = ""
    last_breach_sev = "None"
    investigation = "No"
    financial = rng.randint(45, 95)
    prelim_risk = rng.randint(15, 65)

    explanation = ""

    # -------- Inject target anomaly conditions --------
    if target_anomaly == "BREACHED_VENDOR_HIGH_ACCESS":
        breach_count = rng.randint(1, 3)
        last_breach_date = rand_date_between(rng, TODAY - timedelta(days=350), TODAY - timedelta(days=5)).isoformat()
        last_breach_sev = rng.choice(["High", "Critical"])
        sensitive = rng.choice(["PII", "Financial", "PHI"])
        if sensitive not in data_classes_list:
            data_classes_list.append(sensitive)
        access_level = rng.choice(["ReadWrite", "FullAdmin"])
        prelim_risk = rng.randint(75, 95)
        explanation = f"Vendor breached on {last_breach_date} ({last_breach_sev}); holds {sensitive} with {access_level} access."

    elif target_anomaly == "VENDOR_UNDER_INVESTIGATION":
        investigation = "Yes"
        prelim_risk = rng.randint(70, 92)
        financial = rng.randint(30, 65)
        explanation = "Active regulatory or security investigation reported."

    elif target_anomaly == "EXPIRED_CERTIFICATION":
        # Force at least one sensitive class + an expired cert
        sensitive = rng.choice(["PII", "PCI", "Financial"])
        if sensitive not in data_classes_list:
            data_classes_list.append(sensitive)
        which = rng.choice(["soc2", "iso", "pci"])
        if which == "soc2":
            soc2 = "Expired"
        elif which == "iso":
            iso = "Expired"
        else:
            pci = "Expired"
        prelim_risk = rng.randint(55, 75)
        explanation = f"{which.upper()} certification expired while vendor still processes {sensitive}."

    elif target_anomaly == "HIGH_RISK_SCORE":
        prelim_risk = rng.randint(81, 99)
        financial = rng.randint(30, 60)
        explanation = f"Preliminary risk score {prelim_risk} exceeds 80/100 threshold."

    elif target_anomaly == "RECENTLY_BREACHED_VENDOR":
        breach_count = 1
        last_breach_date = rand_date_between(rng, TODAY - timedelta(days=350), TODAY - timedelta(days=30)).isoformat()
        last_breach_sev = rng.choice(["Low", "Medium"])
        # Lower data scope — strip sensitive classes if present
        data_classes_list = [c for c in data_classes_list if c not in SENSITIVE_CLASSES] or ["Internal"]
        access_level = rng.choice(["Read", "ReadWrite"])
        prelim_risk = rng.randint(50, 72)
        explanation = f"Breach within 12mo ({last_breach_date}) but limited data scope."

    elif target_anomaly == "CONTRACT_EXPIRED_ACTIVE_ACCESS":
        contract_end = rand_date_between(rng, TODAY - timedelta(days=180), TODAY - timedelta(days=2))
        if access_level == "None":
            access_level = rng.choice(["Read", "ReadWrite"])
        prelim_risk = rng.randint(55, 78)
        explanation = f"Contract ended {contract_end.isoformat()} but {access_level} access still provisioned."

    elif target_anomaly == "ELEVATED_RISK_VENDOR":
        prelim_risk = rng.randint(65, 80)
        explanation = f"Preliminary risk {prelim_risk} sits in elevated band (65–80); increased monitoring."

    else:  # NONE — clean vendor
        breach_count = 0
        investigation = "No"
        # Ensure certs not expired
        if soc2 == "Expired":
            soc2 = "Certified"
        if iso == "Expired":
            iso = "Certified"
        if pci == "Expired":
            pci = "Certified"
        contract_end = max(contract_end, TODAY + timedelta(days=60))
        prelim_risk = rng.randint(10, 55)
        financial = rng.randint(65, 95)
        explanation = "No anomaly detected; vendor within normal risk bands."

    last_assessment = rand_date_between(rng, TODAY - timedelta(days=400), TODAY - timedelta(days=1)).isoformat()
    contact_email = faker.company_email()

    expired_flag = int(any(s == "Expired" for s in (soc2, iso, pci)))

    vendor = Vendor(
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        vendor_type=vendor_type,
        country=country,
        criticality=criticality,
        annual_spend_usd=annual_spend,
        contract_start_date=contract_start.isoformat(),
        contract_end_date=contract_end.isoformat(),
        contract_value_usd=contract_value,
        data_access_level=access_level,
        data_classes=";".join(sorted(set(data_classes_list))),
        systems_accessed=";".join(systems_accessed),
        soc2_status=soc2,
        soc2_expiry_date=cert_dates_for(rng, soc2),
        iso27001_status=iso,
        iso27001_expiry_date=cert_dates_for(rng, iso),
        pci_dss_status=pci,
        pci_dss_expiry_date=cert_dates_for(rng, pci),
        gdpr_compliant=gdpr,
        breach_history_12mo=breach_count,
        last_breach_date=last_breach_date,
        last_breach_severity=last_breach_sev,
        under_investigation=investigation,
        financial_health_score=financial,
        preliminary_risk_score=prelim_risk,
        primary_contact_email=contact_email,
        last_assessment_date=last_assessment,
    )

    label = Label(
        vendor_id=vendor_id,
        is_anomaly=0 if target_anomaly == "NONE" else 1,
        anomaly_type=target_anomaly,
        severity=SEVERITY_BY_TYPE[target_anomaly],
        expired_cert_flag=expired_flag,
        explanation=explanation,
    )
    return vendor, label


def main() -> None:
    rng = random.Random(SEED)
    faker = Faker()
    Faker.seed(SEED)

    # Build the target anomaly assignment list per the spec distribution
    assignments: list[str] = []
    for atype, frac in TARGET_DISTRIBUTION.items():
        assignments.extend([atype] * round(frac * N_VENDORS))
    # pad/trim to N_VENDORS
    while len(assignments) < N_VENDORS:
        assignments.append("NONE")
    assignments = assignments[:N_VENDORS]
    rng.shuffle(assignments)

    vendors: list[Vendor] = []
    labels: list[Label] = []
    for i, target in enumerate(assignments, start=1):
        v, lab = build_vendor(rng, faker, i, target)
        vendors.append(v)
        labels.append(lab)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    reg_path = OUT_DIR / "vendor_registry.csv"
    with reg_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(vendors[0]).keys()))
        writer.writeheader()
        for v in vendors:
            writer.writerow(asdict(v))

    label_path = OUT_DIR / "vendor_labels.csv"
    with label_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(asdict(labels[0]).keys()))
        writer.writeheader()
        for lab in labels:
            writer.writerow(asdict(lab))

    # Summary
    from collections import Counter
    dist = Counter(lab.anomaly_type for lab in labels)
    sev_dist = Counter(lab.severity for lab in labels)
    print(f"Generated {len(vendors)} vendors -> {reg_path.name}")
    print(f"Generated {len(labels)} labels   -> {label_path.name}")
    print("\nAnomaly type distribution:")
    for k, v in sorted(dist.items(), key=lambda kv: -kv[1]):
        print(f"  {k:35s} {v:4d} ({v / N_VENDORS:.1%})")
    print("\nSeverity distribution:")
    for k, v in sorted(sev_dist.items(), key=lambda kv: -kv[1]):
        print(f"  {k:10s} {v:4d} ({v / N_VENDORS:.1%})")
    print(f"\nAnomaly rate: {sum(1 for l in labels if l.is_anomaly) / N_VENDORS:.1%} (target ~80%)")


if __name__ == "__main__":
    main()
