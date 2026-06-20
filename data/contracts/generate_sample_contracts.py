# /// script
# requires-python = ">=3.11"
# dependencies = ["reportlab>=4.2"]
# ///
"""
Generate two sample vendor contracts for the /contracts/extract demo:

  sample-msa.pdf       — a clean, well-drafted MSA (judges see a "good" extraction)
  sample-msa-risky.pdf — a vague contract (judges see the LLM flag missing terms)

Both are realistic enough to exercise every field the extractor looks for:
  - data_access_permissions
  - compliance_obligations
  - sla_uptime_percentage
  - renewal_date
  - termination_conditions

Run:  uv run data/contracts/generate_sample_contracts.py
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

OUT_DIR = Path(__file__).parent
EFFECTIVE = date(2026, 1, 15)
TERM_END = date(2028, 1, 14)


# ── Styles ────────────────────────────────────────────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title", parent=ss["Title"], fontSize=18, leading=22, spaceAfter=6, alignment=1
        ),
        "subtitle": ParagraphStyle(
            "subtitle", parent=ss["Normal"], fontSize=10, leading=12,
            textColor=colors.HexColor("#71717a"), alignment=1, spaceAfter=18,
        ),
        "h2": ParagraphStyle(
            "h2", parent=ss["Heading2"], fontSize=12, leading=15,
            spaceBefore=14, spaceAfter=4, fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body", parent=ss["BodyText"], fontSize=10, leading=14, spaceAfter=6,
            alignment=4,  # justify
        ),
        "muted": ParagraphStyle(
            "muted", parent=ss["BodyText"], fontSize=9, leading=11,
            textColor=colors.HexColor("#71717a"),
        ),
    }


# ── Content ───────────────────────────────────────────────────────────
def _good_contract_content(styles) -> list:
    s = styles
    story = []
    story.append(Paragraph("MASTER SERVICES AGREEMENT", s["title"]))
    story.append(Paragraph(
        f"Effective Date: {EFFECTIVE.strftime('%d %B %Y')} &nbsp;·&nbsp; "
        f"Agreement Reference: MSA-2026-0114",
        s["subtitle"],
    ))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dc2626"), spaceAfter=10))

    story.append(Paragraph(
        "This <b>Master Services Agreement</b> (the &quot;Agreement&quot;) is entered into between "
        "<b>Société Générale S.A.</b>, having its registered office at 29 Boulevard Haussmann, "
        "75009 Paris, France (the &quot;Client&quot;), and <b>Acme Cloud Services Ltd</b>, "
        "having its registered office at 14 Finsbury Square, London EC2A 1AH, United Kingdom "
        "(the &quot;Vendor&quot;).",
        s["body"],
    ))

    story.append(Paragraph("1. Scope of Services", s["h2"]))
    story.append(Paragraph(
        "Vendor shall provide cloud-based document storage and processing services to Client, "
        "including secure ingestion, indexing, search, and retrieval of structured and "
        "unstructured business records, in accordance with the technical specification "
        "attached as Schedule A.",
        s["body"],
    ))

    story.append(Paragraph("2. Data Access and Processing", s["h2"]))
    story.append(Paragraph(
        "Vendor is granted <b>Read and Write access</b> to the following data classes: "
        "(i) <b>Personally Identifiable Information (PII)</b> of Client employees and "
        "customers; (ii) <b>Financial transaction records</b>; and (iii) Internal operational "
        "metadata. Vendor shall not access, replicate, or process any data outside the scope "
        "of Schedule A without prior written consent. All processing shall occur exclusively "
        "within EU/EEA data centres.",
        s["body"],
    ))
    story.append(Paragraph(
        "Vendor acts as a Data Processor under <b>GDPR Article 28</b> and shall execute the "
        "Data Processing Agreement attached as Schedule B prior to any production data "
        "ingestion.",
        s["body"],
    ))

    story.append(Paragraph("3. Compliance Obligations", s["h2"]))
    story.append(Paragraph(
        "Vendor warrants that throughout the Term it shall maintain valid and current "
        "certifications for: <b>SOC 2 Type II</b> (audited annually); <b>ISO/IEC 27001:2022</b>; "
        "and <b>PCI-DSS v4.0</b> where payment-card data is in scope. Vendor shall provide "
        "Client with the most recent audit report within ten (10) business days of request. "
        "Vendor shall also comply with applicable provisions of <b>GDPR (Regulation EU "
        "2016/679)</b>, <b>NIST SP 800-53 Rev. 5 (SA-9 External Information System Services)</b>, "
        "and <b>SOX Section 404</b> as it relates to Client&apos;s internal control attestation.",
        s["body"],
    ))

    story.append(Paragraph("4. Service Level Agreement", s["h2"]))
    story.append(Paragraph(
        "Vendor guarantees a monthly uptime of <b>99.95%</b>, measured calendar-monthly and "
        "excluding scheduled maintenance windows announced at least seventy-two (72) hours in "
        "advance. Critical incident response shall commence within fifteen (15) minutes of "
        "detection; resolution targets are four (4) hours for Severity-1 incidents and "
        "twenty-four (24) hours for Severity-2 incidents. Service credits equal to ten percent "
        "(10%) of monthly fees shall accrue for each one-percent (1%) shortfall below the "
        "uptime commitment.",
        s["body"],
    ))

    story.append(Paragraph("5. Security Incident and Breach Notification", s["h2"]))
    story.append(Paragraph(
        "Vendor shall notify Client of any actual or reasonably suspected Security Incident "
        "without undue delay and in any event within <b>twenty-four (24) hours</b> of "
        "discovery, including (i) the nature and scope of the incident, (ii) data classes "
        "affected, (iii) remediation actions taken, and (iv) Vendor&apos;s point-of-contact for "
        "ongoing coordination. This notification shall enable Client to discharge its own "
        "obligations under <b>GDPR Article 33</b> (notification to the supervisory authority "
        "within 72 hours).",
        s["body"],
    ))

    story.append(Paragraph("6. Term and Renewal", s["h2"]))
    story.append(Paragraph(
        f"The initial Term commences on {EFFECTIVE.strftime('%d %B %Y')} and shall continue "
        f"for a period of <b>twenty-four (24) months</b>, expiring on "
        f"{TERM_END.strftime('%d %B %Y')}. The Agreement shall <b>auto-renew</b> for "
        f"successive twelve (12) month periods unless either party provides written notice "
        f"of non-renewal at least ninety (90) days prior to the renewal date.",
        s["body"],
    ))

    story.append(Paragraph("7. Termination", s["h2"]))
    story.append(Paragraph(
        "Either party may terminate this Agreement for material breach upon thirty (30) days "
        "written notice if the breaching party fails to cure within such period. Client may "
        "terminate immediately, without cure period and without liability, in the event of: "
        "(a) Vendor&apos;s loss of any required compliance certification (SOC 2, ISO 27001, "
        "PCI-DSS); (b) a confirmed Security Incident materially affecting Client data; or "
        "(c) Vendor&apos;s insolvency or change of control to a competitor or sanctioned entity. "
        "Upon termination, Vendor shall return or, at Client&apos;s election, securely destroy "
        "all Client data within thirty (30) days and provide written certification of "
        "destruction.",
        s["body"],
    ))

    story.append(Paragraph("8. Indemnification", s["h2"]))
    story.append(Paragraph(
        "Vendor shall indemnify and hold Client harmless against any third-party claim "
        "arising from Vendor&apos;s breach of Sections 2, 3, or 5, up to an aggregate cap of "
        "five million euros (€5,000,000), provided such cap shall not apply to losses "
        "arising from gross negligence, wilful misconduct, or breach of confidentiality.",
        s["body"],
    ))

    story.append(Spacer(1, 18))
    story.append(HRFlowable(width="100%", thickness=0.4, color=colors.HexColor("#e4e4e7")))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<b>Signed for and on behalf of Société Générale S.A.</b><br/>"
        "______________________ &nbsp;&nbsp; Date: __________<br/><br/>"
        "<b>Signed for and on behalf of Acme Cloud Services Ltd</b><br/>"
        "______________________ &nbsp;&nbsp; Date: __________",
        s["body"],
    ))
    story.append(Spacer(1, 12))
    story.append(Paragraph(
        "Schedules: A — Technical Specification · B — Data Processing Agreement (Article 28) · "
        "C — Pricing &amp; Service Credits.",
        s["muted"],
    ))
    return story


def _risky_contract_content(styles) -> list:
    """Intentionally vague contract — exercises the LLM's null-when-missing instruction."""
    s = styles
    story = []
    story.append(Paragraph("SERVICES AGREEMENT", s["title"]))
    story.append(Paragraph("Reference: SA-2025-441", s["subtitle"]))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#dc2626"), spaceAfter=10))

    story.append(Paragraph(
        "Between <b>Société Générale S.A.</b> and <b>Northbridge Analytics LLC</b> "
        "(the &quot;Provider&quot;).",
        s["body"],
    ))

    story.append(Paragraph("1. Services", s["h2"]))
    story.append(Paragraph(
        "Provider will deliver data analytics services as broadly described in any active "
        "Statement of Work. Specific deliverables shall be agreed in writing from time to time.",
        s["body"],
    ))

    story.append(Paragraph("2. Data", s["h2"]))
    story.append(Paragraph(
        "Provider may access such data as is reasonably necessary to perform the Services. "
        "Data handling practices shall conform to Provider&apos;s standard policies.",
        s["body"],
    ))

    story.append(Paragraph("3. Service Levels", s["h2"]))
    story.append(Paragraph(
        "Provider shall use commercially reasonable efforts to maintain service availability.",
        s["body"],
    ))

    story.append(Paragraph("4. Incidents", s["h2"]))
    story.append(Paragraph(
        "Provider shall notify Client of any security incident in a timely manner.",
        s["body"],
    ))

    story.append(Paragraph("5. Duration", s["h2"]))
    story.append(Paragraph(
        "This Agreement shall remain in effect until terminated by either party.",
        s["body"],
    ))

    story.append(Paragraph("6. Termination", s["h2"]))
    story.append(Paragraph(
        "Either party may terminate this Agreement upon written notice. Provider&apos;s "
        "obligations regarding data return on termination are addressed under Provider&apos;s "
        "standard policy.",
        s["body"],
    ))

    story.append(Spacer(1, 24))
    story.append(Paragraph(
        "<b>Signed:</b> _________________________ &nbsp;&nbsp; Date: __________",
        s["body"],
    ))
    return story


# ── Build ─────────────────────────────────────────────────────────────
def build(filename: str, content_fn) -> Path:
    out = OUT_DIR / filename
    doc = SimpleDocTemplate(
        str(out),
        pagesize=A4,
        leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.0 * cm, bottomMargin=2.2 * cm,
        title="Master Services Agreement",
        author="Société Générale TPRM — sample data",
    )
    doc.build(content_fn(_styles()))
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    good = build("sample-msa.pdf", _good_contract_content)
    risky = build("sample-msa-risky.pdf", _risky_contract_content)
    for p in (good, risky):
        size_kb = p.stat().st_size / 1024
        print(f"  ✓ {p.name:25s} {size_kb:6.1f} KB  →  {p}")


if __name__ == "__main__":
    main()
