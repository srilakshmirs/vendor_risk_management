"""Generate a vendor audit pack PDF.

This is the artefact judges score against the "<15 min audit report" rubric
metric. Built with reportlab so there are zero system dependencies — works
on macOS/Linux/Windows without Cairo/Pango/GTK installs.

Structure:
    1. Header banner          (vendor + classification)
    2. Executive summary      (KPI table)
    3. Risk score breakdown   (5 components + reasons)
    4. Risk narrative
    5. Triggered rules
    6. Data access posture    (GDPR + classes + systems)
    7. Certifications
    8. Contract
    9. Recent breach events
   10. Open alerts
   11. Compliance framework footer
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..models import Alert, BreachEvent, Vendor

# ── Palette ────────────────────────────────────────────────────────────
BRAND_RED = HexColor("#dc2626")
BRAND_AMBER = HexColor("#f59e0b")
GREEN = HexColor("#10b981")
ORANGE = HexColor("#f97316")
YELLOW = HexColor("#facc15")
SKY = HexColor("#7dd3fc")
ZINC_50 = HexColor("#fafafa")
ZINC_100 = HexColor("#f4f4f5")
ZINC_200 = HexColor("#e4e4e7")
ZINC_300 = HexColor("#d4d4d8")
ZINC_500 = HexColor("#71717a")
ZINC_700 = HexColor("#3f3f46")
ZINC_900 = HexColor("#18181b")

SEVERITY_COLOR = {
    "CRITICAL": BRAND_RED,
    "HIGH": ORANGE,
    "MEDIUM": YELLOW,
    "LOW": SKY,
    "NONE": GREEN,
}

CERT_COLOR = {
    "Certified": GREEN,
    "Expired": BRAND_RED,
    "Pending": BRAND_AMBER,
    "NotCertified": ZINC_500,
}

SENSITIVE = {"PII", "PCI", "PHI", "Financial"}


# ── Styles ─────────────────────────────────────────────────────────────
def _styles() -> dict[str, ParagraphStyle]:
    ss = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "title",
            parent=ss["Heading1"],
            fontSize=20,
            leading=24,
            textColor=ZINC_900,
            spaceAfter=2,
            fontName="Helvetica-Bold",
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=ss["BodyText"],
            fontSize=9,
            leading=12,
            textColor=ZINC_500,
            spaceAfter=12,
            fontName="Helvetica",
        ),
        "h2": ParagraphStyle(
            "h2",
            parent=ss["Heading2"],
            fontSize=12,
            leading=15,
            textColor=ZINC_900,
            spaceBefore=14,
            spaceAfter=6,
            fontName="Helvetica-Bold",
        ),
        "body": ParagraphStyle(
            "body",
            parent=ss["BodyText"],
            fontSize=9.5,
            leading=13,
            textColor=ZINC_700,
            fontName="Helvetica",
        ),
        "muted": ParagraphStyle(
            "muted",
            parent=ss["BodyText"],
            fontSize=8,
            leading=11,
            textColor=ZINC_500,
            fontName="Helvetica",
        ),
        "narrative": ParagraphStyle(
            "narrative",
            parent=ss["BodyText"],
            fontSize=10,
            leading=14,
            textColor=ZINC_900,
            leftIndent=10,
            rightIndent=10,
            spaceBefore=6,
            spaceAfter=6,
            backColor=ZINC_50,
            borderColor=ZINC_200,
            borderWidth=0.5,
            borderPadding=10,
            borderRadius=4,
            fontName="Helvetica",
        ),
        "score_big": ParagraphStyle(
            "score_big",
            parent=ss["BodyText"],
            fontSize=36,
            leading=40,
            alignment=TA_CENTER,
            fontName="Helvetica-Bold",
        ),
        "banner": ParagraphStyle(
            "banner",
            parent=ss["BodyText"],
            fontSize=8,
            leading=10,
            textColor=BRAND_RED,
            alignment=TA_RIGHT,
            fontName="Helvetica-Bold",
        ),
    }


# ── Helpers ────────────────────────────────────────────────────────────
def _fmt_usd(n: int | float | None) -> str:
    if n is None:
        return "—"
    return f"${int(n):,}"


def _fmt_date(d: date | None) -> str:
    return d.isoformat() if d else "—"


def _days_until(d: date | None, today: date) -> str:
    if d is None:
        return "—"
    delta = (d - today).days
    if delta < 0:
        return f"{-delta}d ago"
    return f"in {delta}d"


def _severity_pill(text: str, severity: str) -> Paragraph:
    colour = SEVERITY_COLOR.get(severity, ZINC_500)
    return Paragraph(
        f'<font color="{colour.hexval()}" backColor="{colour.hexval()}">  </font> '
        f'<font color="{colour.hexval()}"><b>{text}</b></font>',
        ParagraphStyle("pill", fontSize=10, leading=12, fontName="Helvetica-Bold"),
    )


def _section_header(text: str, style: ParagraphStyle) -> list:
    return [
        Paragraph(text, style),
        HRFlowable(width="100%", thickness=0.5, color=ZINC_200, spaceBefore=2, spaceAfter=6),
    ]


# ── Section builders ───────────────────────────────────────────────────
def _build_header(vendor: Vendor, generated_at: datetime, styles) -> list:
    title = Paragraph(f"<b>Vendor Risk Audit Report</b>", styles["title"])
    subtitle = Paragraph(
        f"{vendor.name} &nbsp;·&nbsp; <font color='#71717a'>{vendor.vendor_id}</font> &nbsp;·&nbsp; "
        f"{vendor.vendor_type} &nbsp;·&nbsp; {vendor.country} &nbsp;·&nbsp; {vendor.criticality}",
        styles["subtitle"],
    )
    classification = Paragraph(
        f"CONFIDENTIAL — Société Générale TPRM<br/>Generated {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        styles["banner"],
    )
    head_table = Table(
        [[Paragraph("VRM", ParagraphStyle("v", fontSize=22, fontName="Helvetica-Bold", textColor=BRAND_RED, alignment=TA_LEFT)), classification]],
        colWidths=["*", 6 * cm],
    )
    head_table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    return [
        head_table,
        Spacer(1, 6),
        title,
        subtitle,
        HRFlowable(width="100%", thickness=1.5, color=BRAND_RED, spaceBefore=0, spaceAfter=12),
    ]


def _build_executive_summary(vendor: Vendor, latest_risk: Any, styles) -> list:
    score = latest_risk.score if latest_risk else vendor.preliminary_risk_score
    severity = latest_risk.severity if latest_risk else "—"
    anomaly = latest_risk.anomaly_type if latest_risk and latest_risk.anomaly_type else "NONE"
    sev_colour = SEVERITY_COLOR.get(severity, ZINC_500)

    score_cell = [
        Paragraph(f'<font color="{sev_colour.hexval()}">{score}</font>', styles["score_big"]),
        Paragraph("Composite Risk", styles["muted"]),
        Spacer(1, 4),
        _severity_pill(severity, severity),
        Spacer(1, 2),
        Paragraph(
            f"<font color='#71717a' size='8'>Anomaly</font><br/>"
            f"<font size='7' name='Courier'>{anomaly}</font>",
            ParagraphStyle("anom", fontSize=8, leading=10, alignment=TA_CENTER, textColor=ZINC_700),
        ),
    ]

    profile_rows = [
        ["Vendor type", vendor.vendor_type, "Tier", vendor.criticality],
        ["Country", vendor.country, "Status", vendor.status],
        ["Annual spend", _fmt_usd(vendor.annual_spend_usd), "Investigation", "ACTIVE" if vendor.under_investigation else "None"],
        ["Financial health", f"{vendor.financial_health_score}/100", "Prelim risk", f"{vendor.preliminary_risk_score}/100"],
        ["Primary contact", vendor.primary_contact_email or "—", "Last assessment", _fmt_date(vendor.last_assessment_date)],
    ]
    # Use percentage widths so the table fits whatever column the outer grid
    # gives it (avoids overlapping the right-hand score panel).
    profile_table = Table(profile_rows, colWidths=["22%", "28%", "22%", "28%"])
    profile_table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), ZINC_500),
        ("TEXTCOLOR", (2, 0), (2, -1), ZINC_500),
        ("TEXTCOLOR", (1, 0), (1, -1), ZINC_900),
        ("TEXTCOLOR", (3, 0), (3, -1), ZINC_900),
        ("FONTNAME", (1, 0), (1, -1), "Helvetica-Bold"),
        ("FONTNAME", (3, 0), (3, -1), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, ZINC_200),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))

    score_panel = Table([[col] for col in score_cell], colWidths=[4.5 * cm])
    score_panel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), ZINC_50),
        ("BOX", (0, 0), (-1, -1), 0.5, ZINC_200),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))

    grid = Table([[profile_table, score_panel]], colWidths=["*", 5.0 * cm])
    grid.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (1, 0), (1, 0), 12),
        ("RIGHTPADDING", (0, 0), (0, 0), 12),
    ]))

    return _section_header("1. Executive Summary", styles["h2"]) + [grid]


def _build_score_breakdown(latest_risk: Any, styles) -> list:
    if latest_risk is None or not latest_risk.components:
        return _section_header("2. Risk Score Breakdown", styles["h2"]) + [
            Paragraph("No scoring on record yet — run risk recompute.", styles["muted"]),
        ]
    raw = (latest_risk.components or {}).get("raw", {})
    weighted = (latest_risk.components or {}).get("weighted", {})
    reasons = (latest_risk.components or {}).get("reasons", {})

    weights = {"breach": 0.30, "data_access": 0.25, "compliance": 0.20, "financial": 0.15, "operational": 0.10}
    labels = {
        "breach": "Breach history",
        "data_access": "Data access",
        "compliance": "Compliance",
        "financial": "Financial health",
        "operational": "Operational hygiene",
    }

    rows: list[list[Any]] = [["Component", "Weight", "Raw", "Weighted", "Top reason"]]
    for key, w in weights.items():
        v = int(raw.get(key, 0) or 0)
        wv = float(weighted.get(key, 0) or 0)
        first_reason = (reasons.get(key) or [""])[0]
        rows.append([
            labels[key],
            f"{int(w * 100)}%",
            f"{v}/100",
            f"{wv:.1f}",
            Paragraph(first_reason or "—", styles["muted"]),
        ])
    total = int(latest_risk.score or 0)
    rows.append(["", "", "", Paragraph("<b>Composite</b>", styles["body"]), Paragraph(f"<b>{total}/100</b>", styles["body"])])

    t = Table(rows, colWidths=[3.6 * cm, 1.6 * cm, 1.6 * cm, 1.8 * cm, "*"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ZINC_100),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), ZINC_700),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, ZINC_300),
        ("LINEBELOW", (0, -2), (-1, -2), 0.5, ZINC_300),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("ALIGN", (1, 0), (3, -1), "RIGHT"),
    ]))
    return _section_header("2. Risk Score Breakdown", styles["h2"]) + [t]


def _build_narrative(latest_risk: Any, styles) -> list:
    text = (latest_risk.narrative if latest_risk and latest_risk.narrative else
            "No risk narrative on record yet.")
    return _section_header("3. Risk Narrative", styles["h2"]) + [Paragraph(text, styles["narrative"])]


def _build_triggered_rules(latest_risk: Any, styles) -> list:
    rules = (latest_risk.triggered_rules or []) if latest_risk else []
    if not rules:
        body = Paragraph("No rule classifications triggered.", styles["muted"])
    else:
        body = Paragraph(
            " &nbsp; ".join(f'<font name="Courier" color="#3f3f46"><b>{r}</b></font>' for r in rules),
            styles["body"],
        )
    return _section_header("4. Triggered Risk Rules", styles["h2"]) + [body]


def _build_data_access(vendor: Vendor, styles) -> list:
    da = vendor.data_access[0] if vendor.data_access else None
    if da is None:
        return _section_header("5. Data Access Posture", styles["h2"]) + [
            Paragraph("No data-access mapping on record.", styles["muted"]),
        ]
    classes = [c for c in (da.data_classes or "").split(";") if c]
    systems = [s for s in (da.systems_accessed or "").split(";") if s]

    def _classes_html() -> str:
        if not classes:
            return "—"
        parts = []
        for c in classes:
            if c in SENSITIVE:
                parts.append(f'<font color="{BRAND_RED.hexval()}"><b>{c}</b></font>')
            else:
                parts.append(f'<font color="#3f3f46">{c}</font>')
        return " &nbsp;·&nbsp; ".join(parts)

    gdpr_html = (f'<font color="{GREEN.hexval()}"><b>Compliant</b></font>'
                 if da.gdpr_compliant else
                 f'<font color="{BRAND_RED.hexval()}"><b>NOT compliant</b></font>')

    rows = [
        ["Access level", Paragraph(f"<b>{da.access_level}</b>", styles["body"])],
        ["Data classes", Paragraph(_classes_html(), styles["body"])],
        ["Systems accessed", Paragraph(" &nbsp;·&nbsp; ".join(systems) or "—", styles["body"])],
        ["GDPR", Paragraph(gdpr_html, styles["body"])],
    ]
    t = Table(rows, colWidths=[3.5 * cm, "*"])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), ZINC_500),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, ZINC_200),
    ]))
    return _section_header("5. Data Access Posture", styles["h2"]) + [t]


def _build_certifications(vendor: Vendor, today: date, styles) -> list:
    if not vendor.certifications:
        return _section_header("6. Certifications", styles["h2"]) + [Paragraph("None on record.", styles["muted"])]
    rows: list[list[Any]] = [["Certification", "Status", "Expiry", "Window"]]
    for c in vendor.certifications:
        col = CERT_COLOR.get(c.status, ZINC_500)
        rows.append([
            c.cert_type,
            Paragraph(f'<font color="{col.hexval()}"><b>{c.status}</b></font>', styles["body"]),
            _fmt_date(c.expiry_date),
            _days_until(c.expiry_date, today),
        ])
    t = Table(rows, colWidths=[3.5 * cm, 3 * cm, 3 * cm, "*"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ZINC_100),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), ZINC_700),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, ZINC_300),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZINC_50]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return _section_header("6. Certifications", styles["h2"]) + [t]


def _build_contract(vendor: Vendor, today: date, styles) -> list:
    if not vendor.contracts:
        return _section_header("7. Contract", styles["h2"]) + [Paragraph("No contract on record.", styles["muted"])]
    c = vendor.contracts[0]
    days_left = (c.end_date - today).days
    days_text = (f"<font color='{BRAND_RED.hexval()}'><b>EXPIRED {-days_left} day(s) ago</b></font>"
                 if days_left < 0 else f"in {days_left} day(s)")
    rows = [
        ["Term", f"{_fmt_date(c.start_date)} → {_fmt_date(c.end_date)}"],
        ["Value", _fmt_usd(c.value_usd)],
        ["End date", Paragraph(days_text, styles["body"])],
        ["Auto-renew", "Yes" if c.auto_renew else "No"],
    ]
    t = Table(rows, colWidths=[3.5 * cm, "*"])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (0, -1), ZINC_500),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, ZINC_200),
    ]))
    return _section_header("7. Contract", styles["h2"]) + [t]


def _build_breaches(breaches: list[BreachEvent], styles) -> list:
    if not breaches:
        return _section_header("8. Breach History (12mo)", styles["h2"]) + [
            Paragraph("No breach events recorded in the last 12 months.", styles["muted"]),
        ]
    breaches = sorted(breaches, key=lambda b: b.detected_at, reverse=True)
    rows: list[list[Any]] = [["Date", "Source", "Severity", "Data exposed", "Summary"]]
    for b in breaches:
        sev_col = SEVERITY_COLOR.get(b.severity.upper() if b.severity else "NONE", ZINC_500)
        rows.append([
            _fmt_date(b.detected_at),
            b.source,
            Paragraph(f'<font color="{sev_col.hexval()}"><b>{b.severity}</b></font>', styles["body"]),
            b.data_exposed or "—",
            Paragraph(b.summary or "—", styles["muted"]),
        ])
    t = Table(rows, colWidths=[2.2 * cm, 2.2 * cm, 1.8 * cm, 3 * cm, "*"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ZINC_100),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), ZINC_700),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, ZINC_300),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZINC_50]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return _section_header("8. Breach History (12mo)", styles["h2"]) + [t]


def _build_alerts(alerts: list[Alert], styles) -> list:
    open_alerts = [a for a in alerts if a.status == "open"]
    if not open_alerts:
        return _section_header("9. Open Alerts", styles["h2"]) + [
            Paragraph("No open alerts. ", styles["muted"]),
        ]
    # Sort by severity (CRITICAL first) then due_date
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "NONE": 4}
    open_alerts.sort(key=lambda a: (order.get(a.severity, 9), a.due_date or date.max))

    rows: list[list[Any]] = [["Severity", "Type", "Due", "Message"]]
    for a in open_alerts:
        col = SEVERITY_COLOR.get(a.severity, ZINC_500)
        rows.append([
            Paragraph(f'<font color="{col.hexval()}"><b>{a.severity}</b></font>', styles["body"]),
            Paragraph(f'<font name="Courier" color="#3f3f46">{a.alert_type}</font>', styles["body"]),
            _fmt_date(a.due_date),
            Paragraph(a.message, styles["muted"]),
        ])
    t = Table(rows, colWidths=[1.8 * cm, 4.5 * cm, 2.2 * cm, "*"])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ZINC_100),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("TEXTCOLOR", (0, 0), (-1, 0), ZINC_700),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, ZINC_300),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, ZINC_50]),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return _section_header("9. Open Alerts", styles["h2"]) + [t]


def _build_footer(latest_risk: Any, styles) -> list:
    model = latest_risk.model_version if latest_risk else "—"
    assessed = (
        latest_risk.created_at.strftime("%Y-%m-%d %H:%M UTC")
        if latest_risk and latest_risk.created_at
        else "—"
    )
    text = (
        f"<b>Compliance frameworks referenced:</b> GDPR Article 28 (Processor Obligations), "
        f"GDPR Article 33 (72h Breach Notification), NIST SP 800-53 SA-9 (External Information "
        f"System Services), SOX 404 (Internal Controls).<br/>"
        f"<b>Model:</b> {model} &nbsp; <b>Last assessed:</b> {assessed} &nbsp; "
        f"<b>Generator:</b> VRM Intelligence API."
    )
    return [
        Spacer(1, 18),
        HRFlowable(width="100%", thickness=0.4, color=ZINC_200),
        Spacer(1, 4),
        Paragraph(text, styles["muted"]),
    ]


# ── Page decorations ───────────────────────────────────────────────────
def _on_page(canvas, doc) -> None:
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(ZINC_500)
    canvas.drawString(20 * mm, 12 * mm, "CONFIDENTIAL — Société Générale TPRM")
    canvas.drawRightString(A4[0] - 20 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


# ── Entry point ────────────────────────────────────────────────────────
def build_audit_pack(db: Session, vendor_code: str, *, today: date | None = None) -> BytesIO:
    """Build and return the PDF as a BytesIO. Raises ValueError if vendor not found."""
    today = today or date.today()
    stmt = (
        select(Vendor)
        .where(Vendor.vendor_id == vendor_code)
        .options(
            selectinload(Vendor.certifications),
            selectinload(Vendor.data_access),
            selectinload(Vendor.contracts),
            selectinload(Vendor.breaches),
            selectinload(Vendor.risk_assessments),
            selectinload(Vendor.alerts),
        )
    )
    vendor = db.execute(stmt).scalar_one_or_none()
    if vendor is None:
        raise ValueError(f"Vendor {vendor_code} not found")

    latest_risk = max(vendor.risk_assessments, key=lambda r: r.created_at, default=None)
    breaches = list(vendor.breaches)
    alerts = list(vendor.alerts)

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=20 * mm,
        title=f"Audit Pack — {vendor.name} ({vendor.vendor_id})",
        author="VRM Intelligence",
        subject="Third-party vendor risk audit report",
    )
    styles = _styles()
    now = datetime.now(timezone.utc)

    story: list[Any] = []
    story += _build_header(vendor, now, styles)
    story += _build_executive_summary(vendor, latest_risk, styles)
    story += _build_score_breakdown(latest_risk, styles)
    story += _build_narrative(latest_risk, styles)
    story += _build_triggered_rules(latest_risk, styles)
    story += _build_data_access(vendor, styles)
    story += _build_certifications(vendor, today, styles)
    story += _build_contract(vendor, today, styles)
    story += _build_breaches(breaches, styles)
    story += _build_alerts(alerts, styles)
    story += _build_footer(latest_risk, styles)

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    buf.seek(0)
    return buf
